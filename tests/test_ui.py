"""Smoke tests for the UI modules."""

import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class _FakeElement:
    """Chainable fake UI element for render smoke tests."""

    def __init__(self):
        self.options = {}
        self.value = None
        self.rows = []
        self.text = ""
        self.content = ""

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        return self

    def classes(self, *args, **kwargs):
        return self

    def props(self, *args, **kwargs):
        return self

    def on_click(self, *args, **kwargs):
        return self

    def on_value_change(self, *args, **kwargs):
        return self

    def set_options(self, options):
        self.options = options

    def set_value(self, value):
        self.value = value

    def clear(self):
        return None


class _FakeUI:
    """Minimal fake UI surface for render-time page smoke tests."""

    def __getattr__(self, name):
        return _FakeElement()

    def timer(self, *args, **kwargs):
        return _FakeElement()


def test_dashboard_import():
    """Test that dashboard page can be imported."""
    from markitdesk.ui.dashboard import dashboard_page
    assert dashboard_page is not None


def test_convert_import():
    """Test that convert page can be imported."""
    from markitdesk.ui.convert import convert_page
    assert convert_page is not None


def test_queue_import():
    """Test that queue page can be imported."""
    from markitdesk.ui.queue import queue_page
    assert queue_page is not None


def test_settings_import():
    """Test that settings page can be imported."""
    from markitdesk.ui.settings import settings_page
    assert settings_page is not None


def test_app_import():
    """Test that the app can be imported."""
    from markitdesk import app
    assert app is not None


def test_queue_page_renders_without_running_event_loop(monkeypatch):
    """Queue page construction should not require an active asyncio loop."""
    import markitdesk.ui.queue as queue_module

    monkeypatch.setattr(queue_module, "ui", _FakeUI())
    monkeypatch.setattr(queue_module, "get_job_queue", lambda: None)

    queue_module.queue_page()


def test_preview_page_renders_without_running_event_loop(monkeypatch):
    """Preview page construction should not require an active asyncio loop."""
    import markitdesk.ui.preview as preview_module

    monkeypatch.setattr(preview_module, "ui", _FakeUI())
    monkeypatch.setattr(preview_module, "get_job_queue", lambda: None)

    preview_module.preview_page()
