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

    # Create tabbed interface
    with ui.tabs().classes('w-full') as tabs:
        dashboard_tab = ui.tab('Dashboard')
        convert_tab = ui.tab('Convert')
        queue_tab = ui.tab('Queue')
        preview_tab = ui.tab('Preview')
        settings_tab = ui.tab('Settings')

    with ui.tab_panels(tabs, value=dashboard_tab).classes('w-full'):
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
