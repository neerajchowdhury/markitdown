"""Dashboard page for MarkItDesk."""

from ..ui_runtime import ui


def dashboard_page() -> None:
    """Render the dashboard page."""
    with ui.column().classes('w-full max-w-4xl mx-auto p-4'):
        # App header
        ui.label('MarkItDesk').classes('text-3xl font-bold mb-2')
        ui.label('Local-first Markdown converter').classes('text-muted mb-4')
        
        # Local-first safety badge
        with ui.row().classes('items-center mb-4'):
            ui.icon('lock', color='green').classes('text-xl')
            ui.label('Local-first processing - No data leaves your machine').classes('text-sm text-green-600 ml-2')
        
        # Recent jobs placeholder
        with ui.card().classes('w-full'):
            ui.label('Recent Jobs').classes('text-xl font-bold mb-4')
            with ui.column().classes('w-full min-h-32 bg-gray-50 rounded p-4'):
                ui.label('No recent jobs').classes('text-muted text-center py-8')
