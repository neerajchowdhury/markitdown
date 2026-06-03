"""Runtime startup smoke tests using the real NiceGUI import path."""

import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _is_port_available(port: int) -> bool:
    """Return whether the local TCP port is currently free to bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def test_app_main_smoke_with_real_ui_runtime():
    """app.main should construct all pages successfully before ui.run is invoked."""
    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)

    env = os.environ.copy()
    src_path = str((Path(__file__).parent.parent / "src").resolve())
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    script = """
from markitdesk import app

def fake_run(**kwargs):
    print(f"UI_RUN:{kwargs['port']}")

app.ui.run = fake_run
app.main()
print("APP_MAIN_OK")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    temp_dir.cleanup()

    assert result.returncode == 0, result.stderr
    assert "UI_RUN:8080" in result.stdout
    assert "APP_MAIN_OK" in result.stdout


def test_app_main_builds_expected_shell_before_run():
    """The app should assemble the expected tabs and pages before handing off to ui.run."""
    from markitdesk import app

    calls = []

    class FakeContext:
        def __init__(self, name):
            self.name = name

        def classes(self, *_args, **_kwargs):
            return self

        def __enter__(self):
            calls.append(("enter", self.name))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("exit", self.name))
            return False

    class FakeElement:
        def __init__(self, label):
            self.label = label
            self.value = None
            self.options = {}

        def classes(self, *_args, **_kwargs):
            return self

        def props(self, *_args, **_kwargs):
            return self

        def set_options(self, options):
            self.options = options
            return self

        def set_value(self, value):
            self.value = value
            return self

        def on_click(self, *_args, **_kwargs):
            return self

        def on_value_change(self, *_args, **_kwargs):
            return self

    class FakeUI:
        def tabs(self):
            return FakeContext("tabs")

        def tab(self, label):
            calls.append(("tab", label))
            return label

        def tab_panels(self, *_args, **_kwargs):
            return FakeContext("tab_panels")

        def tab_panel(self, label):
            calls.append(("tab_panel", label))
            return FakeContext(f"panel:{label}")

        def column(self):
            return FakeContext("column")

        def row(self):
            return FakeContext("row")

        def card(self):
            return FakeContext("card")

        def label(self, text=""):
            calls.append(("label", text))
            return FakeElement(text)

        def upload(self, **_kwargs):
            return FakeElement("upload")

        def select(self, **_kwargs):
            return FakeElement("select")

        def button(self, label, **_kwargs):
            calls.append(("button", label))
            return FakeElement(label)

        def table(self, **_kwargs):
            return FakeElement("table")

        def linear_progress(self, **_kwargs):
            return FakeElement("progress")

        def markdown(self, *_args, **_kwargs):
            return FakeElement("markdown")

        def html(self, *_args, **_kwargs):
            return FakeElement("html")

        def expansion(self, *_args, **_kwargs):
            return FakeContext("expansion")

        def grid(self, **_kwargs):
            return FakeContext("grid")

        def icon(self, *_args, **_kwargs):
            return FakeElement("icon")

        def space(self):
            return FakeElement("space")

        def notify(self, *_args, **_kwargs):
            return None

        def timer(self, *_args, **_kwargs):
            return None

        def run(self, **kwargs):
            calls.append(("run", kwargs))

    fake_ui = FakeUI()
    fake_init_db_calls = []
    fake_queue_calls = []
    page_calls = []

    app.ui = fake_ui
    app.init_db = lambda db_path: fake_init_db_calls.append(db_path)
    app.initialize_job_queue = lambda settings: fake_queue_calls.append(settings)
    app.dashboard_page = lambda: page_calls.append("dashboard")
    app.convert_page = lambda: page_calls.append("convert")
    app.queue_page = lambda: page_calls.append("queue")
    app.preview_page = lambda: page_calls.append("preview")
    app.settings_page = lambda: page_calls.append("settings")

    app.main()

    assert page_calls == ["dashboard", "convert", "queue", "preview", "settings"]
    assert fake_init_db_calls
    assert fake_queue_calls
    assert ("tab", "Dashboard") in calls
    assert ("tab", "Convert") in calls
    assert ("tab", "Queue") in calls
    assert ("tab", "Preview") in calls
    assert ("tab", "Settings") in calls
    assert any(call[0] == "run" and call[1]["title"] == "MarkItDesk" for call in calls)


def test_full_app_process_survives_initial_startup_window():
    """The real app process should survive initial startup without crashing."""
    if not _is_port_available(8080):
        pytest.skip("Port 8080 is already in use")

    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)

    env = os.environ.copy()
    src_path = str((Path(__file__).parent.parent / "src").resolve())
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUNBUFFERED"] = "1"

    stdout_path = root / "app.out.log"
    stderr_path = root / "app.err.log"
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "markitdesk.app"],
        cwd=root,
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )

    ready_seen = False

    try:
        deadline = __import__("time").time() + 10
        while __import__("time").time() < deadline:
            stdout_handle.flush()
            stderr_handle.flush()
            if stdout_path.exists():
                stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
                if "NiceGUI ready to go on" in stdout_text:
                    ready_seen = True
                    break
            if process.poll() is not None:
                break
            __import__("time").sleep(0.5)

        still_running = process.poll() is None
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    finally:
        stdout_handle.close()
        stderr_handle.close()

    stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
    temp_dir.cleanup()

    assert "Traceback" not in stderr_text, stderr_text + stdout_text
    assert "Starting MarkItDesk..." in stderr_text
    assert still_running or ready_seen or process.returncode == 0, stderr_text + stdout_text
