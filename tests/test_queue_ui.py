"""Focused tests for queue-page helper logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.ui.queue import build_queue_view_model, collect_completed_output_ids, format_job_duration


def test_format_job_duration_returns_blank_without_both_timestamps():
    """Duration formatting should be blank until both timestamps exist."""
    assert format_job_duration(None, None) == ""
    assert format_job_duration("2026-01-01T00:00:00", None) == ""


def test_format_job_duration_parses_iso_and_handles_invalid_values():
    """Duration formatting should produce seconds or N/A for bad timestamps."""
    assert format_job_duration("2026-01-01T00:00:00", "2026-01-01T00:00:05") == "5s"
    assert format_job_duration("bad", "2026-01-01T00:00:05") == "N/A"


def test_build_queue_view_model_shapes_rows_options_and_summary():
    """Queue view model should shape rows, selector options, and progress correctly."""
    jobs = [
        {
            "job_id": 1,
            "status": "pending",
            "source_path": "/workspace/a.txt",
            "output_path": "",
            "error_message": None,
            "quality_score": 0,
            "started_at": None,
            "finished_at": None,
            "output_id": None,
        },
        {
            "job_id": 2,
            "status": "failed",
            "source_path": "/workspace/b.txt",
            "output_path": "",
            "error_message": "boom",
            "quality_score": 0,
            "started_at": "2026-01-01T00:00:00",
            "finished_at": "2026-01-01T00:00:03",
            "output_id": None,
        },
        {
            "job_id": 3,
            "status": "completed",
            "source_path": "/workspace/c.txt",
            "output_path": "/output/c.md",
            "error_message": None,
            "quality_score": 88,
            "started_at": "2026-01-01T00:00:00",
            "finished_at": "2026-01-01T00:00:08",
            "output_id": 30,
        },
        {
            "job_id": 4,
            "status": "cancelled",
            "source_path": "/workspace/d.txt",
            "output_path": "",
            "error_message": None,
            "quality_score": 0,
            "started_at": None,
            "finished_at": None,
            "output_id": None,
        },
        {
            "job_id": 5,
            "status": "processing",
            "source_path": None,
            "output_path": "",
            "error_message": None,
            "quality_score": 0,
            "started_at": "bad",
            "finished_at": "2026-01-01T00:00:09",
            "output_id": None,
        },
    ]

    view_model = build_queue_view_model(jobs)

    assert view_model["rows"] == [
        {"file": "/workspace/a.txt", "status": "pending", "output": "", "quality": "N/A", "error": "", "duration": ""},
        {"file": "/workspace/b.txt", "status": "failed", "output": "", "quality": "N/A", "error": "boom", "duration": "3s"},
        {"file": "/workspace/c.txt", "status": "completed", "output": "/output/c.md", "quality": "88", "error": "", "duration": "8s"},
        {"file": "/workspace/d.txt", "status": "cancelled", "output": "", "quality": "N/A", "error": "", "duration": ""},
        {"file": "Unknown", "status": "processing", "output": "", "quality": "N/A", "error": "", "duration": "N/A"},
    ]
    assert view_model["job_options"] == {
        "#1 pending /workspace/a.txt": 1,
        "#2 failed /workspace/b.txt": 2,
    }
    assert view_model["status_summary"] == (
        "Total: 5 | Pending: 1 | Processing: 1 | Completed: 1 | Failed: 1 | Cancelled: 1"
    )
    assert view_model["progress_text"] == "Progress: 3/5"
    assert view_model["progress_value"] == 3 / 5


def test_build_queue_view_model_handles_empty_queue():
    """Empty queue snapshots should produce stable empty-state values."""
    view_model = build_queue_view_model([])

    assert view_model["rows"] == []
    assert view_model["job_options"] == {}
    assert view_model["status_summary"] == (
        "Total: 0 | Pending: 0 | Processing: 0 | Completed: 0 | Failed: 0 | Cancelled: 0"
    )
    assert view_model["progress_text"] == "Progress: 0/0"
    assert view_model["progress_value"] == 0


def test_collect_completed_output_ids_returns_only_exportable_completed_jobs():
    """Only completed jobs with output IDs should be considered exportable."""
    jobs = [
        {"status": "completed", "output_id": 10},
        {"status": "completed", "output_id": None},
        {"status": "failed", "output_id": 20},
        {"status": "pending", "output_id": 30},
        {"status": "completed", "output_id": 40},
    ]

    assert collect_completed_output_ids(jobs) == [10, 40]
