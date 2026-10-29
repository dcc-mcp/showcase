"""Task-local lifecycle and evidence helpers carried forward from the native-passing pilot 03.
No native work occurs on import. Paths are supplied by the caller.
"""
import hashlib
import json
import shutil
import socket
import threading
import time
from pathlib import Path
BUDGET = 256 * 1024**2
FREE_FLOOR = 1024**3
DEADLINE = 600

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def unwrap(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json')
    if isinstance(value, dict):
        if value.get('structuredContent') is not None:
            return unwrap(value['structuredContent'])
        for item in value.get('content', []):
            if isinstance(item, dict) and item.get('type') == 'text':
                try:
                    return unwrap(json.loads(item['text']))
                except (ValueError, TypeError):
                    pass
    return value


def field(value, name):
    value = unwrap(value)
    if isinstance(value, dict):
        if name in value:
            return value[name]
        for key in ('result', 'data', 'context', 'job', 'output'):
            if key in value:
                answer = field(value[key], name)
                if answer is not None:
                    return answer
    return None


def has_failure(value):
    value = unwrap(value)
    if isinstance(value, dict):
        if value.get('success') is False or value.get('isError') is True:
            return True
        return any(has_failure(v) for k, v in value.items() if k in ('result', 'data', 'context', 'job', 'output'))
    if isinstance(value, list):
        return any(has_failure(v) for v in value)
    return False


def exception_tree(exc, redact=lambda text: text):
    """Bounded private exception evidence: no locals, credentials or unbounded repr."""
    seen = set()
    count = 0

    def safe_text(value, maximum):
        try:
            value = str(value)
        except Exception:
            value = '<unprintable exception value>'
        # Redact the complete value before truncation, so no secret prefix leaks.
        value = redact(value)
        return value if len(value) <= maximum else value[:maximum] + ' [truncated]'

    def visit(error, depth):
        nonlocal count
        if id(error) in seen:
            return {'reference': 'already reported exception'}
        if depth >= 6 or count >= 24:
            return {'truncated': True, 'reason': 'exception depth/node budget'}
        seen.add(id(error))
        count += 1
        node = {'type': safe_text(type(error).__name__, 128), 'message': safe_text(error, 512)}
        frames = []
        cursor = error.__traceback__
        while cursor is not None:
            frames.append({'file': safe_text(cursor.tb_frame.f_code.co_filename, 160),
                           'function': safe_text(cursor.tb_frame.f_code.co_name, 64),
                           'line': cursor.tb_lineno})
            frames = frames[-3:]
            cursor = cursor.tb_next
        if frames:
            node['last_frames_without_locals'] = frames
        if isinstance(error, BaseExceptionGroup):
            children = []
            for child in error.exceptions:
                if count >= 24:
                    children.append({'truncated': True, 'reason': 'remaining exception children omitted'})
                    break
                children.append(visit(child, depth + 1))
            node['exceptions'] = children
        cause = error.__cause__
        if cause is not None:
            node['cause'] = visit(cause, depth + 1)
        elif error.__context__ is not None and not error.__suppress_context__:
            node['context'] = visit(error.__context__, depth + 1)
        return node

    result = visit(exc, 0)
    return {'root': result, 'reported_exception_nodes': count,
            'limits': {'max_nodes': 24, 'max_depth': 6, 'message_chars': 512, 'frames_per_exception': 3},
            'traceback_locals_recorded': False}


def image_from_result(result):
    require(field(result, 'layers') is not None, 'No native layer tree in inspection')
    return {k: field(result, k) for k in ('image_id', 'width', 'height', 'base_type', 'precision',
            'color_profile', 'typed_color_encoding', 'dirty', 'bridge_owned_display', 'layers', 'metadata')}


def canonical_image(info):
    layers = info['layers']
    names = {x['layer_id']: x['name'] for x in layers}
    require(len(set(names.values())) == len(names), 'Layer names must be unique for identity normalization')
    normalized = []
    for row in layers:
        copy_row = {k: v for k, v in row.items() if k not in ('layer_id', 'parent_id')}
        copy_row['parent_name'] = names.get(row['parent_id'])
        normalized.append(copy_row)
    # Keep all native layer fields, order and parent mapping; drop only volatile IDs.
    # Top-level document filename, dirty flag and selection are not visual structure.
    return {**{k: info[k] for k in ('width', 'height', 'base_type', 'precision', 'color_profile', 'typed_color_encoding')},
            'layers': normalized}


def close_checkpoint_arguments(info, baseline, identifiers, saved_ids, root):
    """Permit only an explicit new save of unchanged, owned, previously saved data."""
    image_id = info['image_id']
    require(image_id in saved_ids and info['bridge_owned_display'] is True,
            'Refuse checkpoint of foreign or never-saved image')
    require(baseline is not None and canonical_image(info) == baseline,
            'Refuse checkpoint: native structure changed after accepted save/export')
    require(type(info['dirty']) is bool, 'Native dirty-state readback missing')
    if info['dirty'] is False:
        return None
    if image_id == identifiers.get('$IMAGE'):
        name = 'original-after-export.xcf'
    elif image_id == identifiers.get('$REOPENED'):
        name = 'reopened-after-export.xcf'
    else:
        raise RuntimeError('Refuse checkpoint: image is not one of the two owned pilot images')
    target = root / name
    require(not target.exists() and not target.is_symlink(), 'Checkpoint target must be new, with no overwrite')
    return {'image_id': image_id, 'path': str(target), 'overwrite': False}


def verify_clean_checkpoint(before, after, baseline):
    require(after['image_id'] == before['image_id'] and after['bridge_owned_display'] is True,
            'Checkpoint inspection changed image ownership/identity')
    require(canonical_image(before) == canonical_image(after) == baseline,
            'Checkpoint save changed native hierarchy/text/font/offset/opacity/visibility')
    require(after['dirty'] is False, 'Checkpoint save did not leave the owned image clean')


class Run:
    def __init__(self, root, token):
        self.root, self.token = root, token
        self.host = self.server = None
        self.plugin_identity = None
        self.ports = set()
        self.stop = threading.Event()
        self.guard_done = threading.Event()
        self.halt_reason = None
        self.started = time.monotonic()
        self.lock = threading.RLock()
        self.events = 0
        self.max_bytes = 0
        self.bridge_attempts = 0

    def clean(self, value):
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, str):
            return value.replace(self.token, '[EPHEMERAL_TOKEN_REDACTED]')
        if isinstance(value, dict):
            return {k: self.clean(v) for k, v in value.items() if k not in ('token', 'DCC_MCP_GIMP_BRIDGE_TOKEN')}
        if isinstance(value, (list, tuple)):
            return [self.clean(v) for v in value]
        return value

    def usage(self):
        total = 0
        for path in self.root.rglob('*'):
            if path.is_symlink():
                raise RuntimeError('Unexpected symlink in owned run root')
            try:
                if path.is_file():
                    total += path.stat().st_size
            except FileNotFoundError:
                pass  # A native temporary artifact completed during the observation.
        self.max_bytes = max(self.max_bytes, total)
        return total

    def budget(self, extra=0):
        if self.halt_reason:
            raise RuntimeError(self.halt_reason)
        require(self.usage() + extra < BUDGET, '256 MiB aggregate stopping budget reached')
        require(shutil.disk_usage(self.root).free - extra > FREE_FLOOR, '1 GiB free floor reached')
        require(time.monotonic() - self.started < DEADLINE, '600-second run deadline reached')

    def write(self, name, value):
        content = (json.dumps(self.clean(value), indent=2, ensure_ascii=False) + '\n').encode()
        require(len(content) < 16 * 1024**2, 'Evidence object exceeds per-write bound')
        with self.lock:
            self.budget(len(content))
            path = self.root / name
            require(path.parent == self.root, 'Evidence file must be directly under run root')
            path.write_bytes(content)

    def trace(self, value):
        content = (json.dumps(self.clean(value), ensure_ascii=False) + '\n').encode()
        require(len(content) < 16 * 1024**2, 'MCP event exceeds evidence bound')
        with self.lock:
            self.budget(len(content))
            with (self.root / 'mcp-trace.jsonl').open('ab') as handle:
                handle.write(content)
            self.events += 1

    def emergency_receipt(self, name, value):
        # Bounded cleanup evidence remains writable after a stopping condition.
        content = (json.dumps(self.clean(value), indent=2) + '\n').encode()
        if len(content) <= 64 * 1024 and shutil.disk_usage(self.root).free > 1024**2:
            (self.root / name).write_bytes(content)

    def halt(self, reason):
        self.halt_reason = self.halt_reason or reason
        self.stop.set()
        if self.host is not None and self.host.poll() is None:
            self.host.terminate()  # Only the Popen-owned GIMP process.

    def watch(self):
        while not self.guard_done.wait(0.5):
            try:
                self.budget()
            except BaseException as exc:
                self.halt(str(exc))
                return

    def collect_log(self):
        # Redact a complete bounded line; never persist environment/argv/token.
        pending = bytearray()
        suppress = False
        with (self.root / 'native.log').open('ab') as out:
            while True:
                chunk = self.host.stdout.read1(4096)
                if not chunk:
                    break
                for byte in chunk:
                    if byte == 10:
                        line = b'[native log line over 64KiB suppressed]\n' if suppress else bytes(pending) + b'\n'
                        line = line.replace(self.token.encode(), b'[EPHEMERAL_TOKEN_REDACTED]')
                        if out.tell() + len(line) <= 8 * 1024**2:
                            out.write(line)
                            out.flush()
                        else:
                            self.halt('8 MiB native log stopping limit reached')
                        pending.clear()
                        suppress = False
                    elif not suppress:
                        pending.append(byte)
                        if len(pending) > 65536:
                            pending.clear()
                            suppress = True
            if pending and not suppress:
                out.write(bytes(pending).replace(self.token.encode(), b'[EPHEMERAL_TOKEN_REDACTED]'))


def unused_loopback_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def port_closed(port):
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(('127.0.0.1', port)) != 0
