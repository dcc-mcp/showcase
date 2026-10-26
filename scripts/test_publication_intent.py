#!/usr/bin/env python3
"""Regression tests for explicit gallery admission and intentional exclusions."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import publication_intent


class PublicationIntentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entries = self.root / "docs" / "showcase"
        self.entries.mkdir(parents=True)
        self.entry("selected")
        self.cases = [{"slug": "selected"}]

    def entry(self, slug):
        entry = self.entries / slug
        entry.mkdir()
        for name in ("README.md", "manifest.json", "validation.json"):
            (entry / name).write_text("private unselected bytes", encoding="utf-8")
        return entry

    def registry(self, rows):
        self.write_registry({"schema_version": 1, "cases": rows})

    def write_registry(self, value):
        (self.root / "unlisted-cases.json").write_text(json.dumps(value), encoding="utf-8")

    def decision(self, **changes):
        return dict({"slug": "pending", "status": "review", "reason": "Visual review is pending."}, **changes)

    def problems(self):
        return publication_intent.validate(self.root, self.cases)[0]

    def test_selected_only_needs_no_duplicate_registry(self):
        self.assertEqual(self.problems(), [])

    def test_intentionally_unlisted_case_is_reported_without_reading_its_contents(self):
        self.entry("pending")
        self.registry([self.decision()])
        problems, notes = publication_intent.validate(self.root, self.cases)
        self.assertEqual(problems, [])
        self.assertIn("1 selected; 1 deliberately unlisted", notes[0])
        self.assertIn("Visual review is pending.", notes[1])
        self.assertNotIn("private unselected bytes", " ".join(notes))

    def test_new_complete_entry_requires_a_decision(self):
        self.entry("forgotten")
        self.assertTrue(any("forgotten needs" in problem for problem in self.problems()))

    def test_partial_private_directory_is_not_an_entry_or_crawled(self):
        entry = self.entries / "private-work"
        entry.mkdir()
        (entry / "notes.txt").write_text("private unselected bytes", encoding="utf-8")
        self.assertEqual(self.problems(), [])

    def test_selected_and_unlisted_decisions_must_be_disjoint(self):
        self.registry([self.decision(slug="selected")])
        self.assertTrue(any("both selected and unlisted" in problem for problem in self.problems()))

    def test_stale_decision_is_rejected(self):
        self.registry([self.decision()])
        self.assertTrue(any("stale unlisted decision pending" in problem for problem in self.problems()))

    def test_duplicate_decisions_are_rejected(self):
        self.entry("pending")
        self.registry([self.decision(), self.decision()])
        self.assertTrue(any("duplicate slug pending" in problem for problem in self.problems()))
        self.cases.append({"slug": "selected"})
        self.assertTrue(any("duplicate selected slug selected" in problem for problem in self.problems()))

    def test_invalid_status_reason_and_fields_fail_closed(self):
        self.entry("pending")
        for changes in ({"status": "published"}, {"status": []}, {"reason": " "},
                        {"reason": None}, {"extra": "accidental field"}):
            with self.subTest(changes=changes):
                self.registry([self.decision(**changes)])
                self.assertTrue(self.problems())

    def test_invalid_registry_schema_and_json_are_rejected(self):
        for registry in ([], {"schema_version": True, "cases": []},
                         {"schema_version": 1.0, "cases": []},
                         {"schema_version": 2, "cases": []}, {"schema_version": 1, "cases": {}},
                         {"schema_version": 1, "cases": [None]}):
            with self.subTest(registry=registry):
                self.write_registry(registry)
                self.assertTrue(self.problems())
        (self.root / "unlisted-cases.json").write_text("{", encoding="utf-8")
        self.assertTrue(any("unreadable JSON" in problem for problem in self.problems()))

    def test_unsafe_selected_registry_and_directory_slugs_are_rejected(self):
        self.registry([self.decision(slug="../outside")])
        self.assertTrue(any("unsafe slug" in problem for problem in self.problems()))
        self.cases = [{"slug": "../outside"}]
        self.assertTrue(any("selected case has an unsafe slug" in problem for problem in self.problems()))
        self.entry("Not-A-Slug")
        self.assertTrue(any("complete entry has an unsafe slug" in problem for problem in self.problems()))

    def test_selected_entry_must_be_complete(self):
        (self.entries / "selected" / "validation.json").unlink()
        self.assertTrue(any("selected entry selected is missing or incomplete" in problem
                            for problem in self.problems()))

    def test_malformed_selected_cases_are_rejected(self):
        for cases in (None, {}, [None], [{"slug": 42}]):
            with self.subTest(cases=cases):
                self.assertTrue(publication_intent.validate(self.root, cases)[0])

    def test_sensitive_reason_is_not_echoed(self):
        self.entry("pending")
        private = "/home/owner/private-notes"
        self.registry([self.decision(reason=private)])
        problems, notes = publication_intent.validate(self.root, self.cases)
        self.assertTrue(problems)
        self.assertNotIn(private, " ".join(problems + notes))
        self.assertEqual(notes, [])

    def test_symlink_entry_and_metadata_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            alias = self.entries / "alias"
            try:
                alias.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Creating symlinks is unavailable in this environment")
            self.assertTrue(any("must not be symlinks" in problem for problem in self.problems()))
            alias.unlink()
            metadata = self.entries / "selected" / "README.md"
            metadata.unlink()
            metadata.symlink_to(self.entries / "selected" / "validation.json")
            self.assertTrue(any("metadata must not be symlinks" in problem for problem in self.problems()))

    def test_symlink_registry_and_escaping_parent_directory_are_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        record = outside / "registry.json"
        record.write_text('{"schema_version":1,"cases":[]}', encoding="utf-8")
        try:
            (self.root / "unlisted-cases.json").symlink_to(record)
        except OSError:
            self.skipTest("Creating symlinks is unavailable in this environment")
        self.assertTrue(any("must not be a symlink" in problem for problem in self.problems()))
        (outside / "showcase").mkdir()
        alternate = self.root / "alternate"
        alternate.mkdir()
        (alternate / "docs").symlink_to(outside, target_is_directory=True)
        problems, _ = publication_intent.validate(alternate, [])
        self.assertEqual(problems, ["publication intent: showcase directory is missing or unsafe"])


if __name__ == "__main__":
    unittest.main()
