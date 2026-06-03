"""Convert page for MarkItDesk."""

import asyncio
import io
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..config import settings
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


def _queue_state_label() -> str:
    """Summarize queue availability for the page header."""
    return "Queue ready" if get_job_queue() else "Queue unavailable"


def convert_page() -> None:
    """Render the convert page."""
    db_path = settings.workspace_root.parent / "markitdesk.db"
    init_db(db_path)
    from ..recipes import initialize_recipes

    initialize_recipes()

    project_id = get_or_create_default_project_id(db_path)
    initialize_job_queue(settings)

    status_label = ui.label("Ready to import").classes("text-sm text-slate-300")
    output_status = ui.label("No jobs queued yet").classes("text-sm text-slate-300")
    recipe_hint = ui.label("No recipe selected").classes("text-sm text-slate-300")
    dialog_message = ui.label("").classes("text-sm text-slate-300")
    url_input = None
    dialog = None
    import_upload = None
    recipe_select = None

    def handle_recipe_change(recipe_name):
        set_selected_recipe(recipe_name)
        recipe_hint.text = f"Selected recipe: {recipe_name}" if recipe_name else "No recipe selected"

    async def handle_upload(file_event):
        try:
            status_label.text = "Indexing selected files..."
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

    with ui.element("div").classes("w-full min-h-screen").style(
        "background:"
        "radial-gradient(circle at top left, rgba(99,102,241,0.18), transparent 34%),"
        "radial-gradient(circle at top right, rgba(16,185,129,0.14), transparent 26%),"
        "linear-gradient(180deg, #0b1120 0%, #0f172a 38%, #111827 100%);"
    ):
        with ui.column().classes("w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 gap-6"):
            with ui.card().classes("w-full p-6 sm:p-8 border border-white/10 shadow-2xl shadow-black/20").style(
                "background: linear-gradient(135deg, rgba(15,23,42,.92), rgba(15,23,42,.72));"
                "backdrop-filter: blur(18px);"
            ):
                with ui.row().classes("w-full items-start justify-between gap-6"):
                    with ui.column().classes("gap-3 max-w-3xl"):
                        with ui.row().classes("items-center gap-2 flex-wrap"):
                            ui.badge("Local-first").props("color=green")
                            ui.badge(_queue_state_label()).props("outline")
                            ui.badge("URL gated").props("outline")
                        ui.label("Import and Convert").classes("text-4xl sm:text-5xl font-black tracking-tight text-white")
                        ui.label(
                            "Drop in files, folders, ZIPs, or approved links. The import studio keeps discovery, queueing, and output visibility in one place."
                        ).classes("text-base sm:text-lg text-slate-300 max-w-3xl")
                        with ui.row().classes("items-center gap-3 flex-wrap mt-2"):
                            ui.button("Open import studio", on_click=open_import_dialog).props("color=primary size=lg")
                            ui.button("Refresh recipes", on_click=lambda: refresh_recipes(recipe_select)).props("outline color=white")
                    with ui.card().classes("w-full sm:w-[20rem] p-4 border border-white/10").style(
                        "background: rgba(15, 23, 42, .72); backdrop-filter: blur(18px);"
                    ):
                        ui.label("Live context").classes("text-sm font-semibold uppercase tracking-[0.2em] text-slate-400")
                        with ui.column().classes("gap-3 mt-4"):
                            _metric("Workspace", str(settings.workspace_root))
                            _metric("Output", _format_output_root())
                            _metric("Remote URLs", "Enabled" if settings.allow_remote_urls else "Disabled")

            with ui.row().classes("w-full gap-4 items-stretch"):
                with ui.card().classes("flex-[1.25] p-5 border border-white/10").style(
                    "background: linear-gradient(180deg, rgba(17,24,39,.94), rgba(15,23,42,.88));"
                ):
                    ui.label("Conversion recipe").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
                    ui.label("Define how content is discovered before it enters the queue.").classes("text-lg text-white mt-1")
                    with ui.row().classes("w-full items-center gap-3 mt-4"):
                        recipe_select = ui.select(
                            options={},
                            label="Select a recipe",
                            with_input=True,
                            on_change=lambda e: handle_recipe_change(e.value),
                        ).classes("flex-1")
                        ui.button("Refresh", on_click=lambda: refresh_recipes(recipe_select)).props("outline")
                    recipe_hint

                with ui.card().classes("flex-[0.95] p-5 border border-white/10").style(
                    "background: linear-gradient(180deg, rgba(15,23,42,.94), rgba(17,24,39,.88));"
                ):
                    ui.label("Output destination").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
                    ui.label("Markdown output stays local and separate from raw input.").classes("text-lg text-white mt-1")
                    with ui.row().classes("items-center gap-3 mt-4"):
                        ui.icon("folder").classes("text-2xl text-emerald-400")
                        ui.label(_format_output_root()).classes("font-mono text-sm text-slate-200 break-all")
                    output_status
                    ui.separator().classes("my-4 bg-white/10")
                    ui.label("Status").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
                    status_label
                    ui.linear_progress(value=0.72).classes("w-full mt-3")

        dialog = ui.dialog()
        with dialog:
            with ui.card().classes("w-[min(92vw,58rem)] p-6 sm:p-7 border border-white/10").style(
                "background: linear-gradient(180deg, rgba(15,23,42,.98), rgba(17,24,39,.96));"
                "backdrop-filter: blur(18px);"
            ):
                with ui.row().classes("items-start justify-between w-full gap-4"):
                    with ui.column().classes("gap-2"):
                        ui.label("Import studio").classes("text-2xl sm:text-3xl font-black text-white")
                        ui.label("One place to bring content in, choose a recipe, and queue it with the right guardrails.").classes("text-sm text-slate-300 max-w-2xl")
                    ui.button(icon="close", on_click=dialog.close).props("flat round")

                with ui.row().classes("gap-3 mt-5 flex-wrap"):
                    ui.badge("Files / folders / ZIPs").props("color=primary")
                    ui.badge("URL gate enforced").props("outline")
                    ui.badge("Local workspace only").props("outline")

                with ui.tabs().classes("w-full mt-5") as tabs:
                    files_tab = ui.tab("Files")
                    links_tab = ui.tab("Links")

                with ui.tab_panels(tabs, value=files_tab).classes("w-full"):
                    with ui.tab_panel(files_tab):
                        ui.label("Pick local content from the workspace boundary.").classes("text-sm text-slate-300 mb-3")
                        import_upload = ui.upload(
                            auto_upload=False,
                            multiple=True,
                            on_upload=lambda e: asyncio.create_task(handle_upload(e)),
                        ).classes("w-full")
                        ui.label("The uploaded file is discovered, validated, and queued automatically.").classes("text-xs text-slate-400 mt-2")

                    with ui.tab_panel(links_tab):
                        ui.label("Remote links are opt-in and remain disabled unless the app setting allows them.").classes("text-sm text-slate-300 mb-3")
                        if settings.allow_remote_urls:
                            url_input = ui.input("https://example.com/file").classes("w-full")
                            ui.button("Queue URL", on_click=lambda: asyncio.create_task(handle_url_ingest())).props("color=primary")
                            ui.label("Only http and https URLs are accepted. The file downloads into the workspace before queueing.").classes("text-xs text-slate-400 mt-2")
                        else:
                            with ui.card().classes("w-full p-4 border border-amber-500/20").style("background: rgba(245,158,11,.08);"):
                                ui.label("Remote URL ingestion is disabled in settings.").classes("text-sm font-semibold text-amber-300")
                                ui.label("Enable `allow_remote_urls` to activate the URL form.").classes("text-xs text-amber-100/90 mt-1")
                            url_input = ui.input("https://example.com/file").props("readonly").classes("w-full mt-3")
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


def _metric(label_text: str, value_text: str):
    """Render a small headline metric block."""
    with ui.column().classes("gap-1"):
        ui.label(label_text).classes("text-[11px] uppercase tracking-[0.2em] text-slate-400")
        ui.label(value_text).classes("text-sm text-slate-100 break-all")
