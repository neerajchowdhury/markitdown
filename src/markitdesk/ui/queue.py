"""Queue page for MarkItDesk."""

import asyncio
from datetime import datetime
from ..ui_runtime import ui
from ..jobs import get_job_queue
from ..config import settings
from ..exports import export_markdown_zip, export_jsonl_chunks, export_csv_index


def format_job_duration(started_at, finished_at) -> str:
    """Format a job duration for queue display."""
    if not started_at or not finished_at:
        return ""

    try:
        start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        finish = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
        duration = finish - start
        return f"{int(duration.total_seconds())}s"
    except Exception:
        return "N/A"


def build_queue_view_model(jobs):
    """Shape queue snapshot data for the UI table, selector, and summary."""
    rows = []
    job_options = {}

    total = len(jobs)
    completed = 0
    failed = 0
    pending = 0
    processing = 0
    cancelled = 0

    for job in jobs:
        status = job.get("status") or "pending"
        if status == "completed":
            completed += 1
        elif status == "failed":
            failed += 1
        elif status == "pending":
            pending += 1
        elif status == "processing":
            processing += 1
        elif status == "cancelled":
            cancelled += 1

        quality_score = job.get("quality_score") or 0
        rows.append({
            "file": job.get("source_path") or "Unknown",
            "status": status,
            "output": job.get("output_path", "") or "",
            "quality": f"{quality_score}" if quality_score > 0 else "N/A",
            "error": job.get("error_message") or "",
            "duration": format_job_duration(job.get("started_at"), job.get("finished_at")),
        })

        if status in {"pending", "failed"}:
            label = f"#{job['job_id']} {status} {job.get('source_path') or 'Unknown'}"
            job_options[label] = job["job_id"]

    finished = completed + failed + cancelled
    return {
        "rows": rows,
        "job_options": job_options,
        "status_summary": (
            f"Total: {total} | Pending: {pending} | Processing: {processing} | "
            f"Completed: {completed} | Failed: {failed} | Cancelled: {cancelled}"
        ),
        "progress_text": f"Progress: {finished}/{total}",
        "progress_value": (finished / total) if total else 0,
    }


def collect_completed_output_ids(jobs):
    """Return output IDs from completed jobs that have exportable outputs."""
    output_ids = []
    for job in jobs:
        if job.get("status") == "completed" and job.get("output_id") is not None:
            output_ids.append(job["output_id"])
    return output_ids


def queue_page() -> None:
    """Render the queue page."""
    with ui.column().classes('w-full max-w-6xl mx-auto p-4'):
        ui.label('Job Queue').classes('text-2xl font-bold mb-4')
        
        # Status summary and export buttons
        with ui.row().classes('w-full justify-between mb-4'):
            with ui.column():
                ui.label('Queue Status').classes('text-lg font-bold')
                status_summary = ui.label('Loading...').classes('text-muted')
                progress_label = ui.label('Progress: 0/0').classes('text-muted')
                progress_bar = ui.linear_progress(value=0).classes('w-full')
            with ui.row().classes('items-center gap-2'):
                ui.button('Export ZIP', on_click=lambda: asyncio.create_task(export_as_zip())).props('outline size=sm')
                ui.button('Export JSONL', on_click=lambda: asyncio.create_task(export_as_jsonl())).props('outline size=sm')
                ui.button('Export CSV', on_click=lambda: asyncio.create_task(export_as_csv())).props('outline size=sm')
        
        # Table
        table = ui.table(
            columns=[
                {'name': 'file', 'label': 'File', 'field': 'file', 'align': 'left'},
                {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'left'},
                {'name': 'output', 'label': 'Output', 'field': 'output', 'align': 'left'},
                {'name': 'quality', 'label': 'Quality', 'field': 'quality', 'align': 'left'},
                {'name': 'error', 'label': 'Error', 'field': 'error', 'align': 'left'},
                {'name': 'duration', 'label': 'Duration', 'field': 'duration', 'align': 'left'},
            ],
            rows=[],
        ).classes('w-full')

        with ui.row().classes('items-center gap-2 my-4'):
            job_selector = ui.select(options={}, label='Select job').classes('min-w-96')
            ui.button('Retry Failed', on_click=lambda: asyncio.create_task(retry_selected_job())).props('outline size=sm')
            ui.button('Cancel Pending', on_click=lambda: asyncio.create_task(cancel_selected_job())).props('outline size=sm')
        
        # Refresh button
        with ui.row().classes('justify-end mt-4'):
            refresh_button = ui.button('Refresh', on_click=lambda: asyncio.create_task(refresh_queue())).props('outline')
        
        async def refresh_queue():
            """Refresh the queue data from the database."""
            try:
                job_queue = get_job_queue()
                if job_queue:
                    jobs = job_queue.get_queue_snapshot()
                    view_model = build_queue_view_model(jobs)

                    table.rows = view_model["rows"]
                    job_selector.options = view_model["job_options"]
                    if job_selector.value not in view_model["job_options"].values():
                        job_selector.value = next(iter(view_model["job_options"].values()), None)

                    status_summary.text = view_model["status_summary"]
                    progress_label.text = view_model["progress_text"]
                    progress_bar.value = view_model["progress_value"]
                else:
                    status_summary.text = "Job queue not available"
            except Exception as e:
                status_summary.text = f"Error loading queue: {str(e)}"
                progress_label.text = "Progress: unavailable"
                progress_bar.value = 0

        async def retry_selected_job():
            """Retry the selected failed job."""
            try:
                job_queue = get_job_queue()
                job_id = job_selector.value
                if not job_queue or job_id is None:
                    ui.notify("Select a failed job first", type='warning')
                    return

                new_job_id = job_queue.retry_job(int(job_id))
                ui.notify(f"Retry started as job #{new_job_id}", type='positive')
                await refresh_queue()
            except Exception as e:
                ui.notify(f"Retry failed: {str(e)}", type='negative')

        async def cancel_selected_job():
            """Cancel the selected pending job."""
            try:
                job_queue = get_job_queue()
                job_id = job_selector.value
                if not job_queue or job_id is None:
                    ui.notify("Select a pending job first", type='warning')
                    return

                cancelled = job_queue.cancel_job(int(job_id))
                if cancelled:
                    ui.notify(f"Job #{job_id} cancelled", type='positive')
                else:
                    ui.notify("Only pending jobs can be cancelled", type='warning')
                await refresh_queue()
            except Exception as e:
                ui.notify(f"Cancel failed: {str(e)}", type='negative')
        
        async def export_as_zip():
            """Export completed jobs as markdown ZIP."""
            try:
                job_queue = get_job_queue()
                if job_queue:
                    jobs = job_queue.get_queue_snapshot()
                    output_ids = collect_completed_output_ids(jobs)

                    if not output_ids:
                        ui.notify("No completed jobs to export", type='warning')
                        return

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    export_path = settings.output_root / f"export_{timestamp}.zip"
                    result = export_markdown_zip(output_ids, export_path, settings)

                    if result["success"]:
                        ui.notify(result["message"], type='positive')
                    else:
                        ui.notify(result["message"], type='negative')
                else:
                    ui.notify("Job queue not available", type='negative')
            except Exception as e:
                ui.notify(f"Export failed: {str(e)}", type='negative')
        
        async def export_as_jsonl():
            """Export completed jobs as JSONL chunks."""
            try:
                job_queue = get_job_queue()
                if job_queue:
                    jobs = job_queue.get_queue_snapshot()
                    output_ids = collect_completed_output_ids(jobs)

                    if not output_ids:
                        ui.notify("No completed jobs to export", type='warning')
                        return

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    export_path = settings.output_root / f"export_{timestamp}.jsonl"
                    result = export_jsonl_chunks(output_ids, export_path, settings)

                    if result["success"]:
                        ui.notify(result["message"], type='positive')
                    else:
                        ui.notify(result["message"], type='negative')
                else:
                    ui.notify("Job queue not available", type='negative')
            except Exception as e:
                ui.notify(f"Export failed: {str(e)}", type='negative')
        
        async def export_as_csv():
            """Export completed jobs as CSV index."""
            try:
                job_queue = get_job_queue()
                if job_queue:
                    jobs = job_queue.get_queue_snapshot()
                    output_ids = collect_completed_output_ids(jobs)

                    if not output_ids:
                        ui.notify("No completed jobs to export", type='warning')
                        return

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    export_path = settings.output_root / f"export_{timestamp}.csv"
                    result = export_csv_index(output_ids, export_path, settings)

                    if result["success"]:
                        ui.notify(result["message"], type='positive')
                    else:
                        ui.notify(result["message"], type='negative')
                else:
                    ui.notify("Job queue not available", type='negative')
            except Exception as e:
                ui.notify(f"Export failed: {str(e)}", type='negative')
        
        # Initial load once the UI event loop is active.
        ui.timer(0.0, lambda: asyncio.create_task(refresh_queue()), once=True)

        # Set up periodic refresh (every 5 seconds).
        ui.timer(5.0, lambda: asyncio.create_task(refresh_queue()))
