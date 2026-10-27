"""Exercise the deferred build transaction with a stub; never import a real host."""
import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import build_nuke as builder


class Knob:
    def __init__(self, value=None, values=()):
        self.current = value
        self.choices = values

    def values(self):
        return self.choices

    def value(self):
        return self.current

    def setValue(self, value):
        self.current = value

    def fromScript(self, value):
        self.current = value

    def setExpression(self, value, axis):
        self.current = (value, axis)


class Node:
    def __init__(self, app, kind, name):
        self.app, self.kind, self.label = app, kind, name
        self.knobs = {}

    def __getitem__(self, name):
        if name not in self.knobs:
            values = ("Nuke", "linear", "rec709", "sRGB", "hold", "fit", "B", "exr", "png")
            if self.app.missing_enum == (self.label, name):
                values = ()
            self.knobs[name] = Knob(values=values)
        return self.knobs[name]

    knob = __getitem__

    def name(self):
        return self.label

    def Class(self):
        return self.kind

    def setInput(self, index, node):
        pass

    def setXYpos(self, x, y):
        pass


class Undo:
    def __init__(self, app):
        self.app, self.calls = app, []

    def disabled(self):
        return self.app.undo_disabled

    def begin(self, name):
        self.calls.append("begin")
        self.before = list(self.app.graph)
        self.root_values = {key: copy.deepcopy(knob.value())
                            for key, knob in self.app.root_node.knobs.items()}

    def cancel(self):
        self.calls.append("cancel")
        self.app.graph[:] = self.before
        self.app.root_node.knobs = {key: Knob(value) for key, value in self.root_values.items()}

    def end(self):
        self.calls.append("end")


class NukeStub(types.ModuleType):
    NUKE_VERSION_STRING = "17.0v3"

    def __init__(self):
        super().__init__("nuke")
        self.graph, self.saved = [], []
        self.missing_enum = self.constructor_failure = None
        self.undo_disabled = False
        self.created = 0
        self.root_node = Node(self, "Root", "Root")
        self.root_node.knobs["fps"] = Knob(24)
        self.undo = Undo(self)
        self.nodes = types.SimpleNamespace(**{
            kind: self.constructor(kind) for kind in
            ("Read", "Reformat", "Roto", "Transform", "Merge2", "Write", "Constant", "Grade", "ContactSheet")
        })

    def constructor(self, kind):
        def create(**kwargs):
            node = Node(self, kind, kwargs["name"])
            self.graph.append(node)
            self.created += 1
            if self.constructor_failure:
                raise self.constructor_failure
            return node
        return create

    def Undo(self):
        return self.undo

    def root(self):
        return self.root_node

    def allNodes(self, **kwargs):
        return list(self.graph)

    def addFormat(self, value):
        return value

    def scriptSaveAs(self, path, overwrite):
        self.saved.append(path)
        Path(path).write_text("stub graph, not a Nuke native artifact", encoding="utf-8")


class BuildTransactionTests(unittest.TestCase):
    @contextmanager
    def fixture(self, grant_check=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = json.loads(Path(__file__).with_name("build-config.json").read_text(encoding="utf-8"))
            for mask in cfg["masks"].values():
                curves = root / mask["curves_script"]["path"]
                curves.parent.mkdir(parents=True, exist_ok=True)
                curves.write_text("stub curves", encoding="utf-8")
            config = root / "config.json"
            config.write_text(json.dumps(cfg), encoding="utf-8")
            app = NukeStub()
            # These external prerequisites are replaced only inside this fixture.
            # The public build() and its actual runtime-binding guard still run.
            with patch.dict(sys.modules, {"nuke": app}), \
                    patch.object(builder, "preflight", return_value=(cfg, {"blockers": []})), \
                    patch.object(builder, "validate_host_grant", side_effect=grant_check), \
                    patch.object(builder, "validate_live_window"):
                binding = {"runtime_session_id": "offline-fixture", "expected_owner_id": "offline-fixture",
                           "expected_grant_id": "offline-fixture", "expected_process_id": os.getpid(),
                           "expected_window_handle": 1}
                yield app, config, binding

    def assert_cancelled(self, app, config):
        self.assertGreater(app.created, 0)
        self.assertEqual(app.undo.calls, ["begin", "cancel"])
        self.assertEqual(app.graph, [])
        self.assertEqual(app.root()["fps"].value(), 24)
        self.assertEqual(app.saved, [])
        self.assertFalse((config.parent / "build-readback.json").exists())

    def retry(self, app, config, binding):
        app.missing_enum = app.constructor_failure = None
        result = builder.build(config, **binding)
        self.assertEqual(app.undo.calls, ["begin", "cancel", "begin", "end"])
        self.assertEqual(result["status"], "graph-saved-not-rendered")

    def test_missing_enum_discards_partial_graph_and_allows_retry(self):
        with self.fixture() as (app, config, binding):
            app.missing_enum = ("SKY_sRGB", "colorspace")
            with self.assertRaisesRegex(RuntimeError, "lacks exact enum"):
                builder.build(config, **binding)
            self.assert_cancelled(app, config)
            self.retry(app, config, binding)

    def test_constructor_failure_preserves_error_and_allows_retry(self):
        with self.fixture() as (app, config, binding):
            error = RuntimeError("injected constructor failure")
            app.constructor_failure = error
            with self.assertRaises(RuntimeError) as caught:
                builder.build(config, **binding)
            self.assertIs(caught.exception, error)
            self.assert_cancelled(app, config)
            self.retry(app, config, binding)

    def test_interruption_discards_partial_graph_and_allows_retry(self):
        with self.fixture() as (app, config, binding):
            error = KeyboardInterrupt("injected interruption")
            app.constructor_failure = error
            with self.assertRaises(KeyboardInterrupt) as caught:
                builder.build(config, **binding)
            self.assertIs(caught.exception, error)
            self.assert_cancelled(app, config)
            self.retry(app, config, binding)

    def test_revoked_binding_before_save_discards_graph_and_allows_retry(self):
        calls = []
        error = RuntimeError("injected binding revocation")

        def grant_check(*args):
            calls.append(args)
            if len(calls) == 4:
                raise error

        with self.fixture(grant_check) as (app, config, binding):
            with self.assertRaises(RuntimeError) as caught:
                builder.build(config, **binding)
            self.assertIs(caught.exception, error)
            self.assert_cancelled(app, config)
            self.retry(app, config, binding)

    def test_disabled_undo_refuses_before_begin_or_mutation(self):
        with self.fixture() as (app, config, binding):
            app.undo_disabled = True
            with self.assertRaisesRegex(RuntimeError, "undo recording"):
                builder.build(config, **binding)
            self.assertEqual(app.undo.calls, [])
            self.assertEqual(app.created, 0)
            self.assertEqual(app.root()["fps"].value(), 24)
            self.assertEqual(app.saved, [])
            self.assertFalse((config.parent / "build-readback.json").exists())

    def test_success_ends_without_cancel_and_returns_the_saved_receipt(self):
        with self.fixture() as (app, config, binding):
            result = builder.build(config, **binding)
            self.assertEqual(app.undo.calls, ["begin", "end"])
            self.assertTrue(app.graph)
            self.assertEqual(len(app.saved), 1)
            self.assertEqual(json.loads((config.parent / "build-readback.json").read_text()), result)
            self.assertFalse(result["render_executed"])

    def test_unbound_public_build_still_refuses_before_preflight(self):
        with patch.object(builder, "preflight") as preflight:
            with self.assertRaisesRegex(RuntimeError, "Missing trusted runtime binding"):
                builder.build("unused.json")
            preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
