"""Tests for bulk queue registration behavior."""

import sys
import tempfile
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.config import Settings
from markitdesk.jobs import JobQueue


def test_enqueue_many_batches_registration(monkeypatch):
    """Bulk enqueue should register files in one batch and preserve order."""
    temp_dir = Path(tempfile.mkdtemp())
    workspace = temp_dir / "workspace"
    output = temp_dir / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output)
    queue = JobQueue(settings, max_workers=1)

    file_records_seen = {}
    processed = []

    def fake_register_files_and_create_jobs(db_path, project_id, file_records, recipe_name=None):
        file_records_seen["db_path"] = db_path
        file_records_seen["project_id"] = project_id
        file_records_seen["file_records"] = list(file_records)
        file_records_seen["recipe_name"] = recipe_name
        return [(200 + i, 100 + i) for i, _ in enumerate(file_records)]

    def fake_process_job(self, job_id, file_path, project_id, file_id=None):
        processed.append((job_id, file_path.name, project_id, file_id))

    monkeypatch.setattr("markitdesk.jobs.register_files_and_create_jobs", fake_register_files_and_create_jobs)
    monkeypatch.setattr(JobQueue, "_process_job", fake_process_job)
    monkeypatch.setattr(JobQueue, "_get_selected_recipe_name", lambda self: "recipe-a")

    files = []
    for name in ("a.txt", "b.txt", "c.txt"):
        path = workspace / name
        path.write_text("x", encoding="utf-8")
        files.append(path)

    job_ids = queue.enqueue_many(files, project_id=7)

    assert job_ids == [100, 101, 102]
    assert file_records_seen["project_id"] == 7
    assert file_records_seen["recipe_name"] == "recipe-a"
    assert file_records_seen["file_records"] == [
        (str(files[0]), ".txt", files[0].stat().st_size),
        (str(files[1]), ".txt", files[1].stat().st_size),
        (str(files[2]), ".txt", files[2].stat().st_size),
    ]
    assert processed == [
        (100, "a.txt", 7, 200),
        (101, "b.txt", 7, 201),
        (102, "c.txt", 7, 202),
    ]
