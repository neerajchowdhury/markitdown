"""Recovery and robustness tests for the job queue."""

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.config import Settings
from markitdesk.converter import ConversionResult
from markitdesk.database import create_project, init_db, update_job_status, get_job_by_id, register_file_and_create_job
from markitdesk.jobs import JobQueue


def make_environment():
    """Create a temporary workspace, output folder, and initialized database."""
    temp_dir = Path(tempfile.mkdtemp())
    workspace = temp_dir / "workspace"
    output = temp_dir / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output)

    import markitdesk.config as config_module
    import markitdesk.audit as audit_module
    original_settings = config_module.settings
    original_audit_settings = getattr(audit_module, "settings", None)
    config_module.settings = settings
    if original_audit_settings is not None:
        audit_module.settings = settings

    db_path = temp_dir / "markitdesk.db"
    init_db(db_path)
    project_id = create_project(db_path, "Default", str(workspace), str(output))

    return temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings


def restore_environment(original_settings, original_audit_settings):
    """Restore the global settings object."""
    import markitdesk.config as config_module
    import markitdesk.audit as audit_module

    config_module.settings = original_settings
    if original_audit_settings is not None:
        audit_module.settings = original_audit_settings


def successful_conversion(source_path: Path, output_root: Path) -> ConversionResult:
    """Build a successful conversion result with an on-disk output file."""
    output_path = output_root / f"{source_path.stem}.md"
    output_path.write_text(f"# {source_path.stem}\n", encoding="utf-8")
    return ConversionResult(
        source_path=source_path,
        output_path=output_path,
        success=True,
        text_length=12,
        duration_ms=1,
        quality_report=SimpleNamespace(score=90),
    )


def failed_conversion(source_path: Path) -> ConversionResult:
    """Build a failed conversion result with a readable error."""
    return ConversionResult(
        source_path=source_path,
        output_path=Path(),
        success=False,
        error_message="Readable conversion failure",
        duration_ms=1,
    )


def test_failed_job_isolation(monkeypatch):
    """A failed job should not stop later jobs from completing."""
    from markitdesk import jobs as jobs_module

    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        call_count = {"count": 0}

        def fake_convert_file(input_path, output_root, config):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return failed_conversion(input_path)
            return successful_conversion(input_path, output_root)

        monkeypatch.setattr(jobs_module, "convert_file", fake_convert_file)

        queue = JobQueue(settings, max_workers=1)

        first = workspace / "first.txt"
        second = workspace / "second.txt"
        first.write_text("one", encoding="utf-8")
        second.write_text("two", encoding="utf-8")

        first_job = queue.enqueue_file(first, project_id)
        second_job = queue.enqueue_file(second, project_id)

        snapshot = {row["job_id"]: row for row in queue.get_queue_snapshot()}

        assert snapshot[first_job]["status"] == "failed"
        assert snapshot[second_job]["status"] == "completed"
        assert snapshot[first_job]["error_message"] == "Readable conversion failure"
    finally:
        restore_environment(original_settings, original_audit_settings)


def test_retry_behavior(monkeypatch):
    """Retrying a failed job should create a new successful attempt."""
    from markitdesk import jobs as jobs_module

    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        call_count = {"count": 0}

        def fake_convert_file(input_path, output_root, config):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return failed_conversion(input_path)
            return successful_conversion(input_path, output_root)

        monkeypatch.setattr(jobs_module, "convert_file", fake_convert_file)

        queue = JobQueue(settings, max_workers=1)
        source = workspace / "retry.txt"
        source.write_text("retry", encoding="utf-8")

        failed_job = queue.enqueue_file(source, project_id)
        retry_job = queue.retry_job(failed_job)

        original = get_job_by_id(db_path, failed_job)
        retried = get_job_by_id(db_path, retry_job)

        assert retry_job != failed_job
        assert original["status"] == "failed"
        assert retried["status"] == "completed"
    finally:
        restore_environment(original_settings, original_audit_settings)


def test_retry_preserves_recipe_name(monkeypatch):
    """Retrying a failed recipe-backed job should preserve its recipe association."""
    from markitdesk import jobs as jobs_module

    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        monkeypatch.setattr(jobs_module, "convert_file", lambda input_path, output_root, config: failed_conversion(input_path))

        source = workspace / "recipe.txt"
        source.write_text("recipe", encoding="utf-8")

        from markitdesk.database import create_job, register_file

        file_id = register_file(db_path, project_id, str(source), ".txt", source.stat().st_size)
        failed_job = create_job(db_path, file_id, "RAG Pack")
        update_job_status(db_path, failed_job, "processing")
        update_job_status(db_path, failed_job, "failed", "failed")

        queue = JobQueue(settings, max_workers=1)
        retry_job = queue.retry_job(failed_job)

        retried = get_job_by_id(db_path, retry_job)
        assert retried["recipe_name"] == "RAG Pack"
    finally:
        restore_environment(original_settings, original_audit_settings)


def test_invalid_status_transition_guarded():
    """Invalid state transitions should be rejected by the database layer."""
    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        source = workspace / "status.txt"
        source.write_text("status", encoding="utf-8")

        from markitdesk.database import create_job, register_file

        file_id = register_file(db_path, project_id, str(source), ".txt", source.stat().st_size)
        job_id = create_job(db_path, file_id, None)

        with pytest.raises(ValueError, match="Invalid job status transition"):
            update_job_status(db_path, job_id, "completed")
    finally:
        restore_environment(original_settings, original_audit_settings)


def test_cancel_pending_job():
    """Pending jobs should be cancellable before processing starts."""
    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        source = workspace / "cancel.txt"
        source.write_text("cancel", encoding="utf-8")

        _, job_id = register_file_and_create_job(
            db_path,
            project_id,
            str(source),
            recipe_name=None,
            file_type=".txt",
            size_bytes=source.stat().st_size,
        )

        queue = JobQueue(settings, max_workers=1)
        assert queue.cancel_job(job_id) is True
        assert get_job_by_id(db_path, job_id)["status"] == "cancelled"
    finally:
        restore_environment(original_settings, original_audit_settings)


def test_cancel_non_pending_job_returns_false(monkeypatch):
    """Cancelling a started job should fail cleanly without changing its status."""
    from markitdesk import jobs as jobs_module

    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        monkeypatch.setattr(jobs_module, "convert_file", lambda input_path, output_root, config: successful_conversion(input_path, output_root))

        source = workspace / "started.txt"
        source.write_text("started", encoding="utf-8")

        queue = JobQueue(settings, max_workers=1)
        job_id = queue.enqueue_file(source, project_id)

        assert queue.cancel_job(job_id) is False
        assert get_job_by_id(db_path, job_id)["status"] == "completed"
    finally:
        restore_environment(original_settings, original_audit_settings)


def test_retry_rejects_non_failed_job(monkeypatch):
    """Only failed jobs should be retryable."""
    from markitdesk import jobs as jobs_module

    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        monkeypatch.setattr(jobs_module, "convert_file", lambda input_path, output_root, config: successful_conversion(input_path, output_root))

        source = workspace / "ok.txt"
        source.write_text("ok", encoding="utf-8")

        queue = JobQueue(settings, max_workers=1)
        job_id = queue.enqueue_file(source, project_id)

        with pytest.raises(ValueError, match="Only failed jobs can be retried"):
            queue.retry_job(job_id)
    finally:
        restore_environment(original_settings, original_audit_settings)


def test_queue_snapshot_stable(monkeypatch):
    """Queue snapshots should remain stable across repeated reads and restarts."""
    from markitdesk import jobs as jobs_module

    temp_dir, workspace, output, db_path, settings, project_id, original_settings, original_audit_settings = make_environment()
    try:
        call_count = {"count": 0}

        def fake_convert_file(input_path, output_root, config):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return failed_conversion(input_path)
            return successful_conversion(input_path, output_root)

        monkeypatch.setattr(jobs_module, "convert_file", fake_convert_file)

        queue = JobQueue(settings, max_workers=1)
        first = workspace / "alpha.txt"
        second = workspace / "beta.txt"
        first.write_text("alpha", encoding="utf-8")
        second.write_text("beta", encoding="utf-8")

        first_job = queue.enqueue_file(first, project_id)
        second_job = queue.enqueue_file(second, project_id)

        snapshot_one = queue.get_queue_snapshot()
        snapshot_two = queue.get_queue_snapshot()
        restarted_queue = JobQueue(settings, max_workers=1)
        snapshot_three = restarted_queue.get_queue_snapshot()

        assert snapshot_one == snapshot_two == snapshot_three
        assert snapshot_one[0]["job_id"] == second_job
        assert snapshot_one[1]["job_id"] == first_job
        assert {"output_id", "output_path", "quality_score"}.issubset(snapshot_one[0].keys())
    finally:
        restore_environment(original_settings, original_audit_settings)
