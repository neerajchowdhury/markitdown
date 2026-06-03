"""Focused tests for app startup and settings UI behavior."""

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import markitdesk.config as config_module
from markitdesk.audit import get_audit_events, init_audit_table
from markitdesk.config import Settings
from markitdesk.database import create_project, get_connection, init_db
from markitdesk.ui.convert import get_or_create_default_project_id


class _FakeElement:
    """Minimal chainable UI element for settings-page callback capture."""

    def __init__(self, recorder):
        self.recorder = recorder
        self.options = {}
        self.value = None

    def __call__(self, *args, **kwargs):
        if "on_change" in kwargs:
            self.recorder.append(kwargs["on_change"])
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def classes(self, *args, **kwargs):
        return self

    def props(self, *args, **kwargs):
        return self

    def on_click(self, *args, **kwargs):
        return self

    def clear(self):
        return None


class _FakeUI:
    """Simple UI double that captures number-change handlers."""

    def __init__(self):
        self.number_handlers = []

    def number(self, *args, **kwargs):
        return _FakeElement(self.number_handlers)(*args, **kwargs)

    def __getattr__(self, name):
        return _FakeElement([])


@pytest.fixture
def temp_settings_env(monkeypatch):
    """Create isolated settings and database state for app/settings tests."""
    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)
    workspace = root / "workspace"
    output = root / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output)
    db_path = root / "markitdesk.db"
    init_db(db_path)
    init_audit_table(db_path)
    monkeypatch.setattr(config_module, "settings", settings)

    try:
        yield SimpleNamespace(root=root, workspace=workspace, output=output, settings=settings, db_path=db_path)
    finally:
        temp_dir.cleanup()


def test_app_main_initializes_dependencies_and_runs(monkeypatch, temp_settings_env):
    """App startup should initialize DB/queue, render pages, and start the server."""
    from markitdesk import app

    monkeypatch.setattr(app, "settings", temp_settings_env.settings)

    init_db_mock = Mock()
    init_queue_mock = Mock()
    dashboard_mock = Mock()
    convert_mock = Mock()
    queue_mock = Mock()
    preview_mock = Mock()
    settings_mock = Mock()
    run_mock = Mock()

    monkeypatch.setattr(app, "init_db", init_db_mock)
    monkeypatch.setattr(app, "initialize_job_queue", init_queue_mock)
    monkeypatch.setattr(app, "dashboard_page", dashboard_mock)
    monkeypatch.setattr(app, "convert_page", convert_mock)
    monkeypatch.setattr(app, "queue_page", queue_mock)
    monkeypatch.setattr(app, "preview_page", preview_mock)
    monkeypatch.setattr(app, "settings_page", settings_mock)
    monkeypatch.setattr(app.ui, "run", run_mock)

    app.main()

    init_db_mock.assert_called_once_with(temp_settings_env.root / "markitdesk.db")
    init_queue_mock.assert_called_once_with(temp_settings_env.settings)
    dashboard_mock.assert_called_once()
    convert_mock.assert_called_once()
    queue_mock.assert_called_once()
    preview_mock.assert_called_once()
    settings_mock.assert_called_once()
    run_mock.assert_called_once_with(title="MarkItDesk", port=8080, show=False, reload=False)


def test_get_or_create_default_project_id_is_idempotent(temp_settings_env, monkeypatch):
    """Default project lookup should reuse the existing project instead of creating duplicates."""
    monkeypatch.setattr("markitdesk.ui.convert.settings", temp_settings_env.settings)

    first_id = get_or_create_default_project_id(temp_settings_env.db_path)
    second_id = get_or_create_default_project_id(temp_settings_env.db_path)

    assert first_id == second_id
    with get_connection(temp_settings_env.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


def test_get_or_create_default_project_id_prefers_existing_project(temp_settings_env, monkeypatch):
    """Default project lookup should return the first project when one already exists."""
    monkeypatch.setattr("markitdesk.ui.convert.settings", temp_settings_env.settings)
    existing_id = create_project(
        temp_settings_env.db_path,
        "Existing",
        str(temp_settings_env.workspace),
        str(temp_settings_env.output),
    )

    project_id = get_or_create_default_project_id(temp_settings_env.db_path)

    assert project_id == existing_id
    with get_connection(temp_settings_env.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


def test_settings_page_uses_numeric_value_from_change_event(monkeypatch, temp_settings_env):
    """The settings page should pass the numeric event value, not the event object."""
    import markitdesk.ui.settings as settings_module

    fake_ui = _FakeUI()
    monkeypatch.setattr(settings_module, "ui", fake_ui)
    monkeypatch.setattr(settings_module, "settings", temp_settings_env.settings)

    settings_module.settings_page()

    assert fake_ui.number_handlers, "Expected settings_page to register a ui.number on_change handler"
    fake_ui.number_handlers[0](SimpleNamespace(value=321))
    assert temp_settings_env.settings.max_file_mb == 321


@pytest.mark.parametrize(
    ("handler_name", "attribute", "new_value"),
    [
        ("handle_max_file_size_change", "max_file_mb", 256),
        ("handle_plugins_change", "allow_plugins", True),
        ("handle_remote_urls_change", "allow_remote_urls", True),
        ("handle_ai_enrichment_change", "allow_ai_enrichment", True),
    ],
)
def test_settings_handlers_update_settings_and_audit(monkeypatch, temp_settings_env, handler_name, attribute, new_value):
    """Settings handlers should mutate config and emit a settings_changed audit event."""
    import markitdesk.ui.settings as settings_module

    monkeypatch.setattr(settings_module, "settings", temp_settings_env.settings)
    handler = getattr(settings_module, handler_name)
    old_value = getattr(temp_settings_env.settings, attribute)

    handler(new_value)

    assert getattr(temp_settings_env.settings, attribute) == new_value
    events = get_audit_events(limit=10)
    assert events[-1]["event_type"] == "settings_changed"
    assert events[-1]["metadata"]["setting"] == attribute
    assert events[-1]["metadata"]["old_value"] == old_value
    assert events[-1]["metadata"]["new_value"] == new_value
