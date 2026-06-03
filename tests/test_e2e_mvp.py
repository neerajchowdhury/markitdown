"""Focused end-to-end coverage for the MarkItDesk MVP flow."""

import csv
import json
import sys
import types
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if "markitdown" not in sys.modules:
    markitdown_stub = types.ModuleType("markitdown")

    class _FakeMarkItDown:
        def __init__(self, enable_plugins=False):
            self.enable_plugins = enable_plugins

        def convert(self, source_path: str):
            return SimpleNamespace(text_content=Path(source_path).read_text(encoding="utf-8"))

    markitdown_stub.MarkItDown = _FakeMarkItDown
    sys.modules["markitdown"] = markitdown_stub

import markitdesk.config as config_module
import markitdesk.ui.convert as convert_module
import markitdesk.ui.preview as preview_module
from markitdesk.audit import get_audit_events, init_audit_table
from markitdesk.config import Settings
from markitdesk.converter import ConversionResult
from markitdesk.database import (
    create_job,
    create_project,
    get_connection,
    get_job_by_id,
    init_db,
    register_file,
)
from markitdesk.discovery import discover_files
from markitdesk.exports import export_csv_index, export_jsonl_chunks, export_markdown_zip, get_recent_outputs
from markitdesk.jobs import JobQueue
from markitdesk.quality import assess_markdown_quality
from markitdesk.recipes import initialize_recipes, load_all_recipes


@pytest.fixture
def e2e_env(monkeypatch):
    """Create an isolated app environment with a real database."""
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
    monkeypatch.setattr(convert_module, "settings", settings)
    monkeypatch.setattr(preview_module, "settings", settings)

    env = SimpleNamespace(
        root=root,
        workspace=workspace,
        output=output,
        settings=settings,
        db_path=db_path,
    )
    try:
        yield env
    finally:
        temp_dir.cleanup()


def _patch_markitdown_success(monkeypatch, markdown_text: str = "# MVP\n\nConverted body\n") -> None:
    """Patch MarkItDown to return deterministic markdown."""

    if markdown_text == "# MVP\n\nConverted body\n":
        markdown_text = "# MVP\n\n" + ("Converted body " * 10).strip() + "\n"

    class FakeMarkItDown:
        def __init__(self, enable_plugins=False):
            self.enable_plugins = enable_plugins

        def convert(self, source_path: str):
            return SimpleNamespace(text_content=markdown_text)

    monkeypatch.setattr("markitdesk.converter.MarkItDown", FakeMarkItDown)


def _successful_result(source_path: Path, output_root: Path, body: str = "# Title\n\nBody text\n") -> ConversionResult:
    """Create a successful conversion result with a real output file."""
    output_path = output_root / f"{source_path.stem}.md"
    output_path.write_text(body, encoding="utf-8")
    return ConversionResult(
        source_path=source_path,
        output_path=output_path,
        success=True,
        text_length=len(body),
        duration_ms=1,
        quality_report=SimpleNamespace(score=88),
    )


def _failed_result(source_path: Path, message: str = "Readable conversion failure") -> ConversionResult:
    """Create a failed conversion result."""
    return ConversionResult(
        source_path=source_path,
        output_path=Path(),
        success=False,
        error_message=message,
        duration_ms=1,
    )


def test_e2e_bootstraps_default_project_and_persists_conversion(monkeypatch, e2e_env):
    """First-run flow should create a project, convert, persist output, and audit it."""
    markdown_text = "# MVP\n\n" + ("Converted body " * 10).strip() + "\n"
    _patch_markitdown_success(monkeypatch, markdown_text)
    source = e2e_env.workspace / "alpha.txt"
    source.write_text("alpha input", encoding="utf-8")

    with get_connection(e2e_env.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0

    project_id = convert_module.get_or_create_default_project_id(e2e_env.db_path)
    queue = JobQueue(e2e_env.settings, max_workers=1)
    job_id = queue.enqueue_file(source, project_id)

    with get_connection(e2e_env.db_path) as conn:
        project_row = conn.execute("SELECT id, name FROM projects").fetchone()
        assert project_row["id"] == project_id
        assert project_row["name"] == "Default"

    job = get_job_by_id(e2e_env.db_path, job_id)
    assert job["status"] == "completed"
    assert Path(job["output_path"]).exists()
    assert Path(job["output_path"]).read_text(encoding="utf-8") == markdown_text
    assert job["quality_score"] == 20

    event_types = [event["event_type"] for event in get_audit_events(limit=20)]
    assert "conversion_started" in event_types
    assert "conversion_done" in event_types


def test_e2e_retry_flow_exposes_latest_output_to_preview(monkeypatch, e2e_env):
    """Preview data should point at the successful retry output, not the failed original attempt."""
    project_id = create_project(
        e2e_env.db_path,
        "Default",
        str(e2e_env.workspace),
        str(e2e_env.output),
    )
    source = e2e_env.workspace / "retry.txt"
    source.write_text("retry input", encoding="utf-8")

    call_count = {"value": 0}

    def fake_convert_file(input_path, output_root, config):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return _failed_result(input_path)
        return _successful_result(input_path, output_root, "# Retry Title\n\nRecovered body\n")

    monkeypatch.setattr("markitdesk.jobs.convert_file", fake_convert_file)

    queue = JobQueue(e2e_env.settings, max_workers=1)
    failed_job_id = queue.enqueue_file(source, project_id)
    retry_job_id = queue.retry_job(failed_job_id)

    preview = preview_module.get_preview_job_details(retry_job_id)
    assert preview is not None
    assert retry_job_id != get_job_by_id(e2e_env.db_path, retry_job_id)["file_id"]
    assert preview["status"] == "completed"
    assert Path(preview["output_path"]).exists()
    assert Path(preview["output_path"]).read_text(encoding="utf-8") == "# Retry Title\n\nRecovered body\n"
    assert preview["quality_score"] == 88


def test_e2e_retry_export_deduplicates_output_rows(monkeypatch, e2e_env):
    """Export should package one logical output after a failed attempt and retry."""
    project_id = create_project(
        e2e_env.db_path,
        "Default",
        str(e2e_env.workspace),
        str(e2e_env.output),
    )
    source = e2e_env.workspace / "export.txt"
    source.write_text("export input", encoding="utf-8")

    call_count = {"value": 0}

    def fake_convert_file(input_path, output_root, config):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return _failed_result(input_path)
        return _successful_result(input_path, output_root, "# Export Title\n\nRecovered body\n")

    monkeypatch.setattr("markitdesk.jobs.convert_file", fake_convert_file)

    queue = JobQueue(e2e_env.settings, max_workers=1)
    failed_job_id = queue.enqueue_file(source, project_id)
    retry_job_id = queue.retry_job(failed_job_id)

    outputs = get_recent_outputs(limit=20)
    matching_outputs = [row for row in outputs if Path(row["source_path"]).name == "export.txt"]
    assert len(matching_outputs) == 1

    output_row = matching_outputs[0]
    assert output_row["job_id"] == retry_job_id
    assert output_row["job_status"] == "completed"

    export_path = e2e_env.output / "exports" / "retry-export.zip"
    result = export_markdown_zip([output_row["output_id"]], export_path, e2e_env.settings)

    assert result["success"] is True
    assert export_path.exists()

    with zipfile.ZipFile(export_path, "r") as archive:
        names = archive.namelist()
        assert names.count("export.md") == 1
        assert "manifest.json" in names

        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["export_info"]["total_files"] == 1
        assert len(manifest["files"]) == 1
        assert manifest["files"][0]["job_id"] == retry_job_id
        assert manifest["files"][0]["job_status"] == "completed"


def test_e2e_mvp_pipeline_covers_bootstrap_discovery_queue_preview_and_exports(monkeypatch, e2e_env):
    """Exercise the practical MVP path from bootstrap through exports."""
    initialize_recipes()
    recipes = load_all_recipes()
    assert "Basic Markdown" in {recipe.name for recipe in recipes}

    project_id = create_project(
        e2e_env.db_path,
        "MVP",
        str(e2e_env.workspace),
        str(e2e_env.output),
    )

    docs = e2e_env.workspace / "docs"
    docs.mkdir()
    alpha = docs / "alpha.txt"
    beta = docs / "beta.md"
    cancel_source = docs / "cancel.txt"
    alpha.write_text("alpha input", encoding="utf-8")
    beta.write_text("beta input", encoding="utf-8")
    cancel_source.write_text("cancel input", encoding="utf-8")

    discovered = discover_files([e2e_env.workspace], e2e_env.settings, recipe_name="Basic Markdown")
    assert discovered == [alpha, beta, cancel_source]

    queue = JobQueue(e2e_env.settings, max_workers=1)
    attempts = {"beta.md": 0}

    def fake_convert_file(input_path, output_root, config):
        output_path = output_root / f"{input_path.stem}.md"
        markdown = (
            f"# {input_path.stem.title()}\n\n"
            "This document has enough structure for queue quality scoring.\n\n"
            "## Details\n\n"
            "| Field | Value |\n"
            "| --- | --- |\n"
            f"| File | {input_path.name} |\n\n"
            "Reference: [example](https://example.com)\n"
        )
        report = assess_markdown_quality(markdown, input_path)
        if input_path.name == "beta.md":
            attempts["beta.md"] += 1
            if attempts["beta.md"] == 1:
                return ConversionResult(
                    source_path=input_path,
                    output_path=output_path,
                    success=False,
                    error_message="simulated failure",
                    duration_ms=1,
                )
        output_path.write_text(markdown, encoding="utf-8")
        return ConversionResult(
            source_path=input_path,
            output_path=output_path,
            success=True,
            text_length=len(markdown),
            duration_ms=1,
            quality_report=report,
        )

    monkeypatch.setattr("markitdesk.jobs.convert_file", fake_convert_file)

    alpha_file_id = register_file(e2e_env.db_path, project_id, str(alpha), alpha.suffix.lower(), alpha.stat().st_size)
    beta_file_id = register_file(e2e_env.db_path, project_id, str(beta), beta.suffix.lower(), beta.stat().st_size)
    cancel_file_id = register_file(
        e2e_env.db_path,
        project_id,
        str(cancel_source),
        cancel_source.suffix.lower(),
        cancel_source.stat().st_size,
    )

    beta_job_id = create_job(e2e_env.db_path, beta_file_id, recipe_name="Basic Markdown")
    alpha_job_id = create_job(e2e_env.db_path, alpha_file_id, recipe_name="Basic Markdown")
    cancel_job_id = create_job(e2e_env.db_path, cancel_file_id, recipe_name="Basic Markdown")

    queue._process_job(alpha_job_id, alpha, project_id, alpha_file_id)
    queue._process_job(beta_job_id, beta, project_id, beta_file_id)
    assert queue.cancel_job(cancel_job_id) is True

    retry_job_id = queue.retry_job(beta_job_id)

    snapshot = queue.get_queue_snapshot()
    by_source = {row["source_path"]: row for row in snapshot}

    assert by_source[str(alpha)]["status"] == "completed"
    assert by_source[str(alpha)]["quality_score"] > 0
    assert by_source[str(beta)]["status"] == "failed"
    assert by_source[str(cancel_source)]["status"] == "cancelled"
    assert by_source[str(alpha)]["output_path"].endswith("alpha.md")

    preview = preview_module.get_preview_job_details(retry_job_id)
    assert preview is not None
    assert preview["status"] == "completed"
    assert Path(preview["output_path"]).exists()
    assert Path(preview["output_path"]).read_text(encoding="utf-8").startswith("# Beta")
    assert preview["quality_score"] > 0

    outputs = get_recent_outputs(limit=20)
    completed_outputs = [row for row in outputs if row["job_status"] == "completed" and Path(row["source_path"]).name in {"alpha.txt", "beta.md"}]
    assert len(completed_outputs) == 2

    output_ids = [row["output_id"] for row in completed_outputs]

    zip_path = e2e_env.output / "exports" / "mvp.zip"
    jsonl_path = e2e_env.output / "exports" / "mvp.jsonl"
    csv_path = e2e_env.output / "exports" / "mvp.csv"

    zip_result = export_markdown_zip(output_ids, zip_path, e2e_env.settings)
    jsonl_result = export_jsonl_chunks(output_ids, jsonl_path, e2e_env.settings)
    csv_result = export_csv_index(output_ids, csv_path, e2e_env.settings)

    assert zip_result["success"] is True
    assert jsonl_result["success"] is True
    assert csv_result["success"] is True
    assert zip_path.exists()
    assert jsonl_path.exists()
    assert csv_path.exists()

    with zipfile.ZipFile(zip_path, "r") as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["export_info"]["format"] == "markdown_zip"
        assert {entry["job_status"] for entry in manifest["files"]} == {"completed"}

    jsonl_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert {row["job_status"] for row in jsonl_rows} == {"completed"}

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert {row["job_status"] for row in csv_rows} == {"completed"}
