"""MarkItDesk application entry point."""

import logging
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from markitdesk.ui_runtime import ui
from markitdesk.config import settings
from markitdesk.database import init_db
from markitdesk.jobs import initialize_job_queue
from markitdesk.ui.dashboard import dashboard_page
from markitdesk.ui.convert import convert_page
from markitdesk.ui.queue import queue_page
from markitdesk.ui.settings import settings_page
from markitdesk.ui.preview import preview_page

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the MarkItDesk application."""
    logger.info("Starting MarkItDesk...")
    logger.info(f"Workspace root: {settings.workspace_root}")
    logger.info(f"Output root: {settings.output_root}")
    logger.info(f"Max file size: {settings.max_file_mb} MB")
    logger.info(f"Allow plugins: {settings.allow_plugins}")
    logger.info(f"Allow remote URLs: {settings.allow_remote_urls}")
    logger.info(f"Allow AI enrichment: {settings.allow_ai_enrichment}")

    # Initialize database and job queue
    db_path = settings.workspace_root.parent / "markitdesk.db"
    init_db(db_path)
    initialize_job_queue(settings)

    with ui.element("div").classes("w-full min-h-screen").style(
        "background:"
        "radial-gradient(circle at top left, rgba(34,197,94,0.12), transparent 26%),"
        "radial-gradient(circle at top right, rgba(59,130,246,0.14), transparent 22%),"
        "linear-gradient(180deg, #020617 0%, #0f172a 55%, #111827 100%);"
    ):
        with ui.column().classes("w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-4 gap-4"):
            with ui.card().classes("w-full p-4 sm:p-5 border border-white/10").style(
                "background: rgba(15, 23, 42, .78); backdrop-filter: blur(18px);"
            ):
                with ui.row().classes("w-full items-center justify-between gap-4"):
                    with ui.column().classes("gap-1"):
                        ui.label("MarkItDesk").classes("text-2xl sm:text-3xl font-black tracking-tight text-white")
                        ui.label("Local-first Markdown conversion, preview, queueing, and export in one workspace.").classes("text-sm text-slate-300")
                    with ui.row().classes("items-center gap-2 flex-wrap justify-end"):
                        ui.badge("Local-first").props("color=green")
                        ui.badge("Workspace locked").props("outline")
                        ui.badge("AI optional").props("outline")

            with ui.card().classes("w-full p-2 border border-white/10").style(
                "background: rgba(15, 23, 42, .65); backdrop-filter: blur(12px);"
            ):
                with ui.tabs().classes("w-full") as tabs:
                    dashboard_tab = ui.tab('Dashboard')
                    convert_tab = ui.tab('Convert')
                    queue_tab = ui.tab('Queue')
                    preview_tab = ui.tab('Preview')
                    settings_tab = ui.tab('Settings')

            with ui.tab_panels(tabs, value=dashboard_tab).classes("w-full"):
                with ui.tab_panel(dashboard_tab):
                    dashboard_page()
                with ui.tab_panel(convert_tab):
                    convert_page()
                with ui.tab_panel(queue_tab):
                    queue_page()
                with ui.tab_panel(preview_tab):
                    preview_page()
                with ui.tab_panel(settings_tab):
                    settings_page()

    # Start the NiceGUI server
    ui.run(title='MarkItDesk', port=8080, show=False, reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
