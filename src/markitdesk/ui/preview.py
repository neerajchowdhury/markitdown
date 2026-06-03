"""Markdown preview page for MarkItDesk."""

import asyncio
from pathlib import Path
from typing import Optional

from ..config import settings
from ..database import get_job_by_id
from ..jobs import get_job_queue
from ..ui_runtime import ui


def get_preview_job_details(job_id: int) -> Optional[dict]:
    """Load the latest preview metadata for a job from the database."""
    db_path = settings.workspace_root.parent / "markitdesk.db"
    job_data = get_job_by_id(db_path, job_id)
    if job_data is None:
        return None

    return {
        "job_id": job_data["job_id"],
        "status": job_data["status"],
        "error_message": job_data["error_message"],
        "source_path": job_data["source_path"],
        "output_path": job_data["output_path"],
        "text_length": job_data["text_length"],
        "quality_score": job_data["quality_score"],
    }


def preview_page() -> None:
    """Render the preview page."""
    with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
        ui.label("Markdown Preview").classes("text-2xl font-bold mb-4")

        with ui.card().classes("w-full mb-4"):
            ui.label("Select Job to Preview").classes("mb-2")
            with ui.row().classes("w-full items-center"):
                job_select = ui.select(
                    label="Recent Jobs",
                    options={},
                    with_input=True,
                ).classes("flex-1")
                refresh_button = ui.button(
                    "Refresh",
                    on_click=lambda: asyncio.create_task(refresh_job_list()),
                ).props("outline size=sm")

        with ui.card().classes("w-full"):
            with ui.tabs().classes("w-full") as preview_tabs:
                raw_tab = ui.tab("Raw Markdown")
                rendered_tab = ui.tab("Rendered")
                outline_tab = ui.tab("Outline")

            with ui.tab_panels(preview_tabs, value=raw_tab).classes("w-full"):
                with ui.tab_panel(raw_tab):
                    raw_content = ui.markdown("").classes("w-full h-96 p-4 bg-gray-50 rounded")

                with ui.tab_panel(rendered_tab):
                    rendered_content = ui.html("").classes("w-full h-96 p-4 bg-white")

                with ui.tab_panel(outline_tab):
                    outline_content = ui.markdown("").classes("w-full h-96 p-4 bg-gray-50 rounded")

            with ui.expansion("Job Details", icon="info").classes("w-full mt-4"):
                with ui.column().classes("w-full p-4"):
                    metadata_grid = ui.grid(columns=2).classes("w-full gap-4")

        with ui.row().classes("w-full justify-between mt-4"):
            quality_label = ui.label("Quality: N/A").classes("text-lg font-bold")
            warnings_label = ui.label("").classes("text-sm text-muted")

        current_output_path: Optional[Path] = None

        async def refresh_job_list():
            """Refresh the list of recent jobs."""
            try:
                job_queue = get_job_queue()
                if not job_queue:
                    job_select.options = {"Error": -1}
                    return

                jobs = job_queue.get_queue_snapshot()
                options = {}
                for job in jobs:
                    if job["status"] == "completed":
                        label = f"Job {job['job_id']}: {job['source_path'] or 'Unknown'} ({job['status']})"
                        options[label] = job["job_id"]

                job_select.options = options
                if options:
                    first_job_id = list(options.values())[0]
                    job_select.value = first_job_id
                    await load_job_preview(first_job_id)
            except Exception as exc:
                job_select.options = {"Error": -1}
                ui.notify(f"Error loading jobs: {str(exc)}", type="negative")

        async def load_job_preview(job_id: int):
            """Load and display preview for a specific job."""
            nonlocal current_output_path

            try:
                job_data = get_preview_job_details(job_id)
                if not job_data:
                    ui.notify(f"Job {job_id} not found", type="negative")
                    return

                output_path = job_data["output_path"]
                output_path_obj = Path(output_path) if output_path else None
                if output_path_obj:
                    try:
                        resolved_output = output_path_obj.resolve()
                        output_root_resolved = settings.output_root.resolve()
                        resolved_output.relative_to(output_root_resolved)
                    except Exception:
                        ui.notify(f"Invalid output path: {output_path}", type="negative")
                        return

                current_output_path = output_path_obj

                await update_metadata(
                    job_data["job_id"],
                    job_data["source_path"],
                    output_path,
                    job_data["status"],
                    job_data["error_message"],
                    job_data["text_length"],
                    job_data["quality_score"],
                )

                if output_path and current_output_path and current_output_path.exists():
                    try:
                        content = current_output_path.read_text(encoding="utf-8")
                        raw_content.content = content
                        rendered_content.content = f"<pre>{ui.utils.escape_html(content)}</pre>"
                        outline_content.content = generate_outline(content)

                        quality_score = job_data["quality_score"]
                        if quality_score is not None:
                            quality_label.text = f"Quality: {quality_score}/100"
                        else:
                            quality_label.text = "Quality: N/A"

                        if quality_score is None:
                            warnings_label.text = "No quality data available"
                            warnings_label.classes(
                                "remove(text-muted text-green-600 text-yellow-600 text-red-600) add(text-muted)"
                            )
                        elif quality_score >= 80:
                            warnings_label.text = "Excellent quality"
                            warnings_label.classes(
                                "remove(text-muted text-green-600 text-yellow-600 text-red-600) add(text-green-600)"
                            )
                        elif quality_score >= 50:
                            warnings_label.text = "Fair quality"
                            warnings_label.classes(
                                "remove(text-muted text-green-600 text-yellow-600 text-red-600) add(text-yellow-600)"
                            )
                        else:
                            warnings_label.text = "Poor quality"
                            warnings_label.classes(
                                "remove(text-muted text-green-600 text-yellow-600 text-red-600) add(text-red-600)"
                            )
                    except Exception as exc:
                        raw_content.content = f"Error loading file: {str(exc)}"
                        rendered_content.content = f"<p>Error loading file: {ui.utils.escape_html(str(exc))}</p>"
                        outline_content.content = ""
                        quality_label.text = "Quality: Error"
                        warnings_label.text = f"Error loading preview: {str(exc)}"
                        warnings_label.classes(
                            "remove(text-muted text-green-600 text-yellow-600 text-red-600) add(text-negative)"
                        )
                else:
                    raw_content.content = "*No output file available*"
                    rendered_content.content = "<p><em>No output file available</em></p>"
                    outline_content.content = ""
                    quality_label.text = "Quality: N/A"
                    warnings_label.text = "No output file to preview"
                    warnings_label.classes(
                        "remove(text-muted text-green-600 text-yellow-600 text-red-600) add(text-muted)"
                    )
            except Exception as exc:
                ui.notify(f"Error loading preview: {str(exc)}", type="negative")

        def generate_outline(markdown_text: str) -> str:
            """Generate a markdown outline from headings."""
            lines = markdown_text.split("\n")
            outline_lines = ["# Document Outline\n"]

            for line in lines:
                if not line.startswith("#"):
                    continue

                level = 0
                for char in line:
                    if char == "#":
                        level += 1
                    else:
                        break

                if level <= 6 and len(line) > level and line[level] == " ":
                    heading_text = line[level + 1 :].strip()
                    indent = "  " * (level - 1)
                    outline_lines.append(
                        f"{indent}- [{heading_text}](#{heading_text.lower().replace(' ', '-')})"
                    )

            if len(outline_lines) == 1:
                outline_lines.append("*No headings found in document*")

            return "\n".join(outline_lines)

        async def update_metadata(
            job_id: int,
            source_path: Optional[str],
            output_path: Optional[str],
            status: Optional[str],
            error_message: Optional[str],
            text_length: Optional[int],
            quality_score: Optional[int],
        ):
            """Update the metadata display."""
            metadata_grid.clear()

            with metadata_grid:
                ui.label("Job ID:").classes("font-medium")
                ui.label(str(job_id))

                ui.label("Status:").classes("font-medium")
                status_label = ui.label(status or "unknown")
                if status == "completed":
                    status_label.classes("text-green-600")
                elif status == "failed":
                    status_label.classes("text-red-600")
                elif status == "processing":
                    status_label.classes("text-blue-600")
                else:
                    status_label.classes("text-gray-600")

                ui.label("Source File:").classes("font-medium")
                ui.label(source_path or "Unknown")

                ui.label("Output File:").classes("font-medium")
                ui.label(str(Path(output_path).name) if output_path else "None")

                ui.label("Text Length:").classes("font-medium")
                ui.label(f"{text_length or 0:,} characters")

                ui.label("Quality Score:").classes("font-medium")
                if quality_score is None:
                    ui.label("N/A")
                else:
                    score_label = ui.label(f"{quality_score}/100")
                    if quality_score >= 80:
                        score_label.classes("text-green-600")
                    elif quality_score >= 50:
                        score_label.classes("text-yellow-600")
                    else:
                        score_label.classes("text-red-600")

                if error_message:
                    ui.label("Error:").classes("font-medium")
                    ui.label(error_message).classes("text-red-600")

        job_select.on_value_change(
            lambda e: asyncio.create_task(load_job_preview(e.value)) if e.value else None
        )
        refresh_button.on_click(lambda: asyncio.create_task(refresh_job_list()))

        ui.timer(0.0, lambda: asyncio.create_task(refresh_job_list()), once=True)
