"""Task-owned headed Chrome with Playwright's supported no-default-overrides attach.

Never attach to an existing user profile or create an overridden new context.
The caller verifies the official executable and supplies an outer process deadline.
Chrome inherits the worker process group so its supervisor can reap descendants.
"""
from contextlib import contextmanager
from pathlib import Path
import math
import os
import subprocess
import tempfile
import time


def _budget(timeout):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("Chrome startup timeout must be finite and within (0, 30] seconds")
    return time.monotonic() + timeout


def _remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("Task-owned Chrome startup exceeded its bounded deadline")
    return value


def _read_endpoint(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    if len(lines) != 2 or not lines[0].isdigit():
        return None  # Chrome may still be writing its own port file.
    port = int(lines[0])
    route = lines[1]
    if not 1 <= port <= 65535 or not route.startswith("/devtools/browser/") or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/" for c in route):
        raise RuntimeError("Invalid task-owned Chrome DevTools endpoint")
    return f"ws://127.0.0.1:{port}{route}"


def _stop_owned_process(process):
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        process.wait(timeout=2)


@contextmanager
def external_chrome(pw, executable_path, *, report, timeout=5):
    """Yield (browser, default_context); report startup and owned-process cleanup.

    Headed only. No sandbox-disabling switches, focus override, visibility override,
    private Playwright API, existing profile, or new browser context is used.
    Caller must not close the default context before taking all required evidence.
    """
    deadline = _budget(timeout)
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Task-owned headed Chrome requires the provisioned Xvfb DISPLAY")
    executable = Path(executable_path).resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("Preverified Chrome executable must be an executable file")
    process = None
    with tempfile.TemporaryDirectory(prefix="tidal-owned-chrome-") as profile:
        arguments = [str(executable), f"--user-data-dir={profile}",
                     "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
                     "--no-first-run", "--no-default-browser-check", "--enable-automation",
                     "--disable-dev-shm-usage", "--disable-background-timer-throttling",
                     "--window-size=1288,805", "about:blank"]
        report.update({"method": "task-owned headed Chrome; public connect_over_cdp(no_defaults=True)",
                       "arguments": arguments, "default_context_only": True, "connected": False})
        try:
            # File-backed output avoids a full pipe blocking Chrome; retained in
            # report on failure and removed with this task-owned temporary profile.
            with open(Path(profile) / "chrome.log", "w+b") as log:
                process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT,
                                           start_new_session=False)
                report["owned_pid"] = process.pid
                try:
                    endpoint = None
                    while endpoint is None:
                        remaining = _remaining(deadline)
                        if process.poll() is not None:
                            raise RuntimeError(f"Task-owned Chrome exited during startup: {process.returncode}")
                        endpoint = _read_endpoint(Path(profile) / "DevToolsActivePort")
                        if endpoint is None:
                            time.sleep(min(.025, remaining))
                    browser = pw.chromium.connect_over_cdp(
                        endpoint, no_defaults=True, timeout=_remaining(deadline) * 1000)
                    _remaining(deadline)  # Reject late success.
                    if len(browser.contexts) != 1:
                        raise RuntimeError("Expected exactly the fresh default Chrome context")
                    report["connected"] = True
                    yield browser, browser.contexts[0]
                finally:
                    _stop_owned_process(process)
                    report["owned_process_exit_code"] = process.poll()
                    log.flush()
                    log.seek(0, os.SEEK_END)
                    length = log.tell()
                    log.seek(max(0, length - 16384))
                    report["chrome_log_tail"] = log.read().decode("utf-8", errors="replace")
        finally:
            report["owned_process_stopped"] = process is None or process.poll() is not None
