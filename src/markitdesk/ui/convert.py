"""Convert page for MarkItDesk."""

import asyncio
import io
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..config import settings
from ..converter import convert_file
from ..database import create_project, get_connection, init_db
from ..discovery import discover_files, discover_files_from_zip
from ..jobs import get_job_queue, initialize_job_queue
from ..ui_runtime import ui

_selected_recipe_name = None


def get_selected_recipe():
    """Get the currently selected recipe name."""
    return _selected_recipe_name


def set_selected_recipe(recipe_name):
    """Update the selected recipe name."""
    global _selected_recipe_name
    _selected_recipe_name = recipe_name if recipe_name else None


def get_or_create_default_project_id(db_path: Path) -> int:
    """Return the first project if present, otherwise create a default one."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM projects ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        if row:
            return row["id"]

    return create_project(
        db_path,
        "Default",
        str(settings.workspace_root),
        str(settings.output_root),
    )


def _is_valid_remote_url(url_text: str) -> bool:
    """Return True when the URL uses an allowed network scheme."""
    parsed = urllib.parse.urlparse(url_text.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _download_remote_url(url_text: str, destination_dir: Path) -> Path:
    """Download a remote URL into the workspace for processing."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(url_text.strip())
    safe_name = Path(parsed.path).name or "downloaded_url"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name).strip("._-") or "downloaded_url"
    destination_path = destination_dir / safe_name

    counter = 1
    while destination_path.exists():
        destination_path = destination_dir / f"{Path(safe_name).stem}_{counter}{Path(safe_name).suffix}"
        counter += 1

    request = urllib.request.Request(url_text.strip(), headers={"User-Agent": "MarkItDesk/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec: local-first app gate
        max_bytes = settings.max_file_mb * 1024 * 1024
        chunk_size = 1024 * 64
        written = 0
        with open(destination_path, "wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    destination_path.unlink(missing_ok=True)
                    raise ValueError(f"Remote file exceeds size limit: {settings.max_file_mb} MB")
                handle.write(chunk)

    return destination_path


def _ingest_remote_url(url_text: str, project_id: int) -> str:
    """Download a remote URL and enqueue it like a local file."""
    if not settings.allow_remote_urls:
        return "Remote URLs are disabled. Enable allow_remote_urls to ingest links."
    if not _is_valid_remote_url(url_text):
        return "Enter a valid http or https URL."

    try:
        downloaded_path = _download_remote_url(url_text, settings.workspace_root / "_remote")
        return process_uploaded_files([DownloadedUploadFile(downloaded_path)], project_id)
    except Exception as exc:
        return f"Error processing URL: {exc}"


class DownloadedUploadFile:
    """Small adapter for reusing file ingestion for downloaded URLs."""

    def __init__(self, path: Path):
        self.name = path.name
        self.content = io.BytesIO(path.read_bytes())


def process_uploaded_files(files, project_id: int) -> str:
    """Persist uploaded files, discover supported inputs, and enqueue them."""
    if not files:
        return "No files selected"

    all_file_paths = []
    errors = []
    for file_info in files:
        content = file_info.content.read()
        item_path = settings.workspace_root / file_info.name
        item_path.parent.mkdir(parents=True, exist_ok=True)
        with open(item_path, "wb") as handle:
            handle.write(content)

        try:
            recipe_name = get_selected_recipe()
            if item_path.suffix.lower() == ".zip":
                discovered_paths = discover_files_from_zip(item_path, settings, recipe_name)
            else:
                discovered_paths = discover_files([item_path], settings, recipe_name)
            all_file_paths.extend(discovered_paths)
        except Exception as exc:
            errors.append(f"{file_info.name}: {exc}")
            continue
        finally:
            try:
                file_info.content.close()
            except Exception:
                pass

    job_queue = get_job_queue()
    if job_queue and all_file_paths:
        job_ids = job_queue.enqueue_many(all_file_paths, project_id=project_id)
        message = f"Added {len(all_file_paths)} file(s) to queue. Job IDs: {job_ids}"
        if errors:
            return f"{message}. Skipped {len(errors)} item(s): {'; '.join(errors)}"
        return message
    if errors:
        return f"Error processing upload(s): {'; '.join(errors)}"
    if not all_file_paths:
        return "No supported files found in upload"
    return "Error: Job queue not initialized"


def _format_output_root() -> str:
    """Render the output path with a short explanatory label."""
    return str(settings.output_root)


def convert_page() -> None:
    """Render the convert page."""
    db_path = settings.workspace_root.parent / "markitdesk.db"
    init_db(db_path)
    from ..recipes import initialize_recipes

    initialize_recipes()

    project_id = get_or_create_default_project_id(db_path)
    initialize_job_queue(settings)

    status_label = ui.label().classes("mt-2")
    output_status = ui.label("No imports yet").classes("text-sm text-muted")
    recipe_hint = ui.label("No recipe selected").classes("text-sm text-muted")
    dialog_message = ui.label("").classes("text-sm text-muted")
    url_input = None
    dialog = None
    import_upload = None
    recipe_select = None

    def handle_recipe_change(recipe_name):
        set_selected_recipe(recipe_name)
        recipe_hint.text = f"Selected recipe: {recipe_name}" if recipe_name else "No recipe selected"

    async def handle_upload(file_event):
        try:
            status_label.text = "Processing uploads..."
            files = [file_event] if hasattr(file_event, "content") else []
            status_label.text = process_uploaded_files(files, project_id)
            output_status.text = f"Outputs land in {_format_output_root()}"
        except Exception as exc:
            status_label.text = f"Error: {exc}"

    async def handle_url_ingest():
        try:
            status_label.text = "Processing URL..."
            result = _ingest_remote_url(url_input.value or "", project_id)
            status_label.text = result
            output_status.text = f"Outputs land in {_format_output_root()}"
            dialog_message.text = result
        except Exception as exc:
            status_label.text = f"Error: {exc}"

    def open_import_dialog():
        dialog.open()

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        with ui.row().classes("w-full items-start justify-between gap-4"):
            with ui.column().classes("gap-1"):
                ui.label("Import and Convert").classes("text-3xl font-bold")
                ui.label("Bring in local files, folders, ZIPs, or remote links and queue them for conversion.").classes("text-muted")
            ui.button("Import files or links", on_click=open_import_dialog).props("color=primary")

        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("flex-1 p-5"):
                ui.label("Conversion recipe").classes("text-lg font-semibold")
                ui.label("Choose how the file should be discovered and processed before it enters the queue.").classes("text-sm text-muted mb-3")
                with ui.row().classes("w-full items-center gap-3"):
                    recipe_select = ui.select(options={}, label="Select a recipe", with_input=True, on_change=lambda e: handle_recipe_change(e.value)).classes("flex-1")
                    ui.button("Refresh", on_click=lambda: refresh_recipes(recipe_select)).props("outline size=sm")
                recipe_hint

            with ui.card().classes("flex-1 p-5"):
                ui.label("Output location").classes("text-lg font-semibold")
                ui.label("Converted Markdown is written locally to the configured output directory.").classes("text-sm text-muted mb-3")
                with ui.row().classes("items-center gap-2"):
                    ui.icon("folder").classes("text-xl")
                    ui.label(_format_output_root()).classes("font-mono text-sm")
                output_status

        with ui.card().classes("w-full p-5"):
            ui.label("Status").classes("text-lg font-semibold mb-2")
            status_label

        dialog = ui.dialog()
        with dialog:
            with ui.card().classes("w-[min(92vw,52rem)] p-5"):
                with ui.row().classes("items-start justify-between w-full"):
                    with ui.column().classes("gap-1"):
                        ui.label("Import content").classes("text-2xl font-bold")
                        ui.label("Choose a local file or queue a remote URL.").classes("text-sm text-muted")
                    ui.button(icon="close", on_click=dialog.close).props("flat round")

                with ui.tabs().classes("w-full mt-4") as tabs:
                    files_tab = ui.tab("Files")
                    links_tab = ui.tab("Links")

                with ui.tab_panels(tabs, value=files_tab).classes("w-full"):
                    with ui.tab_panel(files_tab):
                        ui.label("Select files, folders, or ZIPs.").classes("text-sm text-muted mb-2")
                        import_upload = ui.upload(
                            auto_upload=False,
                            multiple=True,
                            on_upload=lambda e: asyncio.create_task(handle_upload(e)),
                        ).classes("w-full")
                        ui.label("Choose files in the picker, then queue them through the upload control.").classes("text-xs text-muted mt-2")

                    with ui.tab_panel(links_tab):
                        ui.label("Remote URLs are disabled unless allowed in settings.").classes("text-sm text-muted mb-2")
                        if settings.allow_remote_urls:
                            url_input = ui.input("https://example.com/file").classes("w-full")
                            ui.button("Queue URL", on_click=lambda: asyncio.create_task(handle_url_ingest())).props("color=primary")
                        else:
                            url_input = ui.input("https://example.com/file").props("readonly").classes("w-full")
                            ui.label("Remote URL ingestion is disabled in settings.").classes("text-sm text-warning")
                        dialog_message

        refresh_recipes(recipe_select)


def refresh_recipes(recipe_select):
    """Refresh the recipe dropdown with available recipes."""
    from ..recipes import load_all_recipes

    recipes = load_all_recipes()
    options = {recipe.name: recipe.name for recipe in recipes}
    recipe_select.set_options(options)
    if options and recipe_select.value not in options:
        recipe_select.set_value(list(options.keys())[0] if options else None)
