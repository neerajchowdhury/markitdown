"""Tests for export functionality."""

import sys
import tempfile
import types
import zipfile
from pathlib import Path

import pytest

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if "markitdown" not in sys.modules:
    markitdown_stub = types.ModuleType("markitdown")

    class _FakeMarkItDown:
        def __init__(self, enable_plugins=False):
            self.enable_plugins = enable_plugins

        def convert(self, source_path: str):
            return Path(source_path).read_text(encoding="utf-8")

    markitdown_stub.MarkItDown = _FakeMarkItDown
    sys.modules["markitdown"] = markitdown_stub

import markitdesk.config as config_module
from markitdesk.audit import get_audit_events
from markitdesk.audit import init_audit_table
from markitdesk.config import Settings
from markitdesk.database import add_output, create_job, create_project, init_db, register_file, update_job_status
from markitdesk.exports import _resolve_export_path


def test_exports_import():
    """Test that exports module can be imported."""
    from markitdesk.exports import (
        export_markdown_zip, 
        export_jsonl_chunks, 
        export_csv_index,
        get_recent_outputs
    )
    assert export_markdown_zip is not None
    assert export_jsonl_chunks is not None
    assert export_csv_index is not None
    assert get_recent_outputs is not None


def test_resolve_export_path_allows_missing_nested_output_path():
    """Test that export paths can point to new files inside the output root."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir) / "output"
        output_root.mkdir()

        resolved = _resolve_export_path(Path("nested/export.zip"), output_root)

        assert resolved == (output_root / "nested" / "export.zip").resolve(strict=False)
        assert resolved.is_relative_to(output_root.resolve())


def test_resolve_export_path_rejects_escape():
    """Test that export path traversal outside the output root is blocked."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir) / "output"
        output_root.mkdir()

        with pytest.raises(ValueError, match="Export path must be inside output root"):
            _resolve_export_path(Path("../escape.zip"), output_root)


def test_export_markdown_zip_skips_missing_files_but_keeps_manifest(monkeypatch):
    """ZIP export should include existing files, skip missing ones, and still log the export."""
    from markitdesk.exports import export_markdown_zip

    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)
    workspace = root / "workspace"
    output_root = root / "output"
    workspace.mkdir()
    output_root.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output_root)
    monkeypatch.setattr(config_module, "settings", settings)

    db_path = root / "markitdesk.db"
    init_db(db_path)
    init_audit_table(db_path)

    project_id = create_project(db_path, "Export", str(workspace), str(output_root))
    first_source = workspace / "first.txt"
    second_source = workspace / "second.txt"
    first_source.write_text("first", encoding="utf-8")
    second_source.write_text("second", encoding="utf-8")

    first_file_id = register_file(db_path, project_id, str(first_source), ".txt", first_source.stat().st_size)
    second_file_id = register_file(db_path, project_id, str(second_source), ".txt", second_source.stat().st_size)

    first_job_id = create_job(db_path, first_file_id)
    second_job_id = create_job(db_path, second_file_id)
    update_job_status(db_path, first_job_id, "processing")
    update_job_status(db_path, first_job_id, "completed")
    update_job_status(db_path, second_job_id, "processing")
    update_job_status(db_path, second_job_id, "completed")

    existing_output = output_root / "first.md"
    missing_output = output_root / "second.md"
    existing_output.write_text("# First", encoding="utf-8")

    first_output_id = add_output(db_path, first_file_id, str(existing_output), "markdown", 7, 80)
    second_output_id = add_output(db_path, second_file_id, str(missing_output), "markdown", 8, 70)

    export_path = output_root / "bundle.zip"
    result = export_markdown_zip([first_output_id, second_output_id], export_path, settings)

    assert result["success"] is True
    assert export_path.exists()

    with zipfile.ZipFile(export_path, "r") as archive:
        names = archive.namelist()
        assert "first.md" in names
        assert "second.md" not in names
        assert "manifest.json" in names

    events = get_audit_events(limit=10)
    assert events[-1]["event_type"] == "export_created"
    assert events[-1]["metadata"]["export_type"] == "markdown_zip"
    assert events[-1]["job_id"] in {first_job_id, second_job_id}
    assert events[-1]["metadata"]["output_ids"] == [first_output_id, second_output_id]

    temp_dir.cleanup()


@pytest.mark.parametrize("export_name,suffix", [
    ("export_markdown_zip", ".zip"),
    ("export_jsonl_chunks", ".jsonl"),
    ("export_csv_index", ".csv"),
])
def test_exports_fail_cleanly_when_no_outputs_exist(monkeypatch, export_name, suffix):
    """Export functions should return a friendly failure when nothing is exportable."""
    from markitdesk import exports as exports_module

    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)
    workspace = root / "workspace"
    output_root = root / "output"
    workspace.mkdir()
    output_root.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output_root)
    monkeypatch.setattr(config_module, "settings", settings)

    db_path = root / "markitdesk.db"
    init_db(db_path)
    init_audit_table(db_path)

    export_fn = getattr(exports_module, export_name)
    export_path = output_root / f"empty{suffix}"

    result = export_fn([999], export_path, settings)

    assert result["success"] is False
    assert "No valid outputs found for export" in result["message"]
    assert not export_path.exists()

    temp_dir.cleanup()


if __name__ == "__main__":
    test_exports_import()
    print("Export import test passed!")
