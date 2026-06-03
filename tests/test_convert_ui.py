"""Focused tests for convert-page helper logic and upload processing."""

import io
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import markitdesk.config as config_module
import markitdesk.ui.convert as convert_module
from markitdesk.config import Settings


class _FakeRecipeSelect:
    """Minimal select object for refresh_recipes tests."""

    def __init__(self, value=None):
        self.value = value
        self.options = None
        self.set_value_calls = []

    def set_options(self, options):
        self.options = options

    def set_value(self, value):
        self.value = value
        self.set_value_calls.append(value)


@pytest.fixture
def convert_env(monkeypatch):
    """Create isolated workspace/output settings for convert helper tests."""
    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)
    workspace = root / "workspace"
    output = root / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output)
    monkeypatch.setattr(config_module, "settings", settings)
    monkeypatch.setattr(convert_module, "settings", settings)
    convert_module.set_selected_recipe(None)

    try:
        yield SimpleNamespace(root=root, workspace=workspace, output=output, settings=settings)
    finally:
        temp_dir.cleanup()


def _fake_upload(name: str, content: bytes):
    """Create a file-info object compatible with process_uploaded_files."""
    return SimpleNamespace(name=name, content=io.BytesIO(content))


def test_selected_recipe_round_trip():
    """Recipe selection helpers should persist and clear the selected recipe."""
    convert_module.set_selected_recipe("RAG Pack")
    assert convert_module.get_selected_recipe() == "RAG Pack"

    convert_module.set_selected_recipe("")
    assert convert_module.get_selected_recipe() is None


def test_refresh_recipes_selects_first_option_when_current_value_is_invalid(monkeypatch):
    """Refreshing recipes should load options and select the first valid recipe."""
    fake_select = _FakeRecipeSelect(value="Missing")
    recipes = [SimpleNamespace(name="Basic Markdown"), SimpleNamespace(name="RAG Pack")]
    monkeypatch.setattr("markitdesk.recipes.load_all_recipes", lambda: recipes)

    convert_module.refresh_recipes(fake_select)

    assert fake_select.options == {
        "Basic Markdown": "Basic Markdown",
        "RAG Pack": "RAG Pack",
    }
    assert fake_select.value == "Basic Markdown"
    assert fake_select.set_value_calls == ["Basic Markdown"]


def test_refresh_recipes_preserves_valid_existing_selection(monkeypatch):
    """Refreshing recipes should not overwrite a valid current selection."""
    fake_select = _FakeRecipeSelect(value="RAG Pack")
    recipes = [SimpleNamespace(name="Basic Markdown"), SimpleNamespace(name="RAG Pack")]
    monkeypatch.setattr("markitdesk.recipes.load_all_recipes", lambda: recipes)

    convert_module.refresh_recipes(fake_select)

    assert fake_select.options == {
        "Basic Markdown": "Basic Markdown",
        "RAG Pack": "RAG Pack",
    }
    assert fake_select.value == "RAG Pack"
    assert fake_select.set_value_calls == []


def test_process_uploaded_files_handles_empty_selection(convert_env):
    """Uploading nothing should return the expected empty-selection message."""
    assert convert_module.process_uploaded_files([], project_id=7) == "No files selected"


def test_process_uploaded_files_enqueues_with_resolved_project_id(monkeypatch, convert_env):
    """Uploaded files should be enqueued against the provided project id, not a hardcoded value."""
    upload = _fake_upload("notes.txt", b"hello world")
    queue_calls = {}

    class FakeQueue:
        def enqueue_many(self, file_paths, project_id):
            queue_calls["file_paths"] = list(file_paths)
            queue_calls["project_id"] = project_id
            return [41]

    monkeypatch.setattr(convert_module, "get_job_queue", lambda: FakeQueue())
    monkeypatch.setattr(convert_module, "discover_files", lambda paths, settings, recipe_name=None: list(paths))

    status = convert_module.process_uploaded_files([upload], project_id=77)

    saved_path = convert_env.workspace / "notes.txt"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"hello world"
    assert queue_calls["file_paths"] == [saved_path]
    assert queue_calls["project_id"] == 77
    assert status == "Added 1 files to queue. Job IDs: [41]"


def test_process_uploaded_files_uses_selected_recipe_for_zip_discovery(monkeypatch, convert_env):
    """ZIP uploads should pass the selected recipe into ZIP discovery."""
    upload = _fake_upload("bundle.zip", b"zip-bytes")
    captured = {}

    class FakeQueue:
        def enqueue_many(self, file_paths, project_id):
            return [12]

    discovered_path = convert_env.workspace / "extracted" / "doc.txt"
    discovered_path.parent.mkdir(parents=True, exist_ok=True)
    discovered_path.write_text("doc", encoding="utf-8")

    def fake_discover_from_zip(item_path, settings, recipe_name=None):
        captured["item_path"] = item_path
        captured["recipe_name"] = recipe_name
        return [discovered_path]

    convert_module.set_selected_recipe("Tender/RFP Pack")
    monkeypatch.setattr(convert_module, "get_job_queue", lambda: FakeQueue())
    monkeypatch.setattr(convert_module, "discover_files_from_zip", fake_discover_from_zip)

    status = convert_module.process_uploaded_files([upload], project_id=5)

    assert captured["item_path"] == convert_env.workspace / "bundle.zip"
    assert captured["recipe_name"] == "Tender/RFP Pack"
    assert status == "Added 1 files to queue. Job IDs: [12]"


def test_process_uploaded_files_reports_missing_queue(monkeypatch, convert_env):
    """A discovered file with no active job queue should return a clear error."""
    upload = _fake_upload("notes.txt", b"hello world")
    monkeypatch.setattr(convert_module, "discover_files", lambda paths, settings, recipe_name=None: list(paths))
    monkeypatch.setattr(convert_module, "get_job_queue", lambda: None)

    status = convert_module.process_uploaded_files([upload], project_id=9)

    assert status == "Error: Job queue not initialized"


def test_process_uploaded_files_surfaces_discovery_errors(monkeypatch, convert_env):
    """Discovery failures should be surfaced as a per-file upload error."""
    upload = _fake_upload("notes.txt", b"hello world")
    monkeypatch.setattr(convert_module, "discover_files", lambda paths, settings, recipe_name=None: (_ for _ in ()).throw(ValueError("boom")))

    status = convert_module.process_uploaded_files([upload], project_id=9)

    assert status == "Error processing upload(s): notes.txt: boom"


def test_process_uploaded_files_continues_after_one_discovery_failure(monkeypatch, convert_env):
    """A bad upload item should not prevent later valid items from being enqueued."""
    bad_upload = _fake_upload("bad.txt", b"bad")
    good_upload = _fake_upload("good.txt", b"good")
    queue_calls = {}

    class FakeQueue:
        def enqueue_many(self, file_paths, project_id):
            queue_calls["file_paths"] = list(file_paths)
            queue_calls["project_id"] = project_id
            return [101]

    def fake_discover(paths, settings, recipe_name=None):
        path = paths[0]
        if path.name == "bad.txt":
            raise ValueError("boom")
        return [path]

    monkeypatch.setattr(convert_module, "get_job_queue", lambda: FakeQueue())
    monkeypatch.setattr(convert_module, "discover_files", fake_discover)

    status = convert_module.process_uploaded_files([bad_upload, good_upload], project_id=55)

    assert queue_calls["project_id"] == 55
    assert queue_calls["file_paths"] == [convert_env.workspace / "good.txt"]
    assert status == "Added 1 files to queue. Job IDs: [101]. Skipped 1 item(s): bad.txt: boom"
