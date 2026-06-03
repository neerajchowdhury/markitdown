"""Settings page for MarkItDesk."""

from pathlib import Path
from ..ui_runtime import ui
from ..config import settings
from ..audit import log_audit_event


def settings_page() -> None:
    """Render the settings page."""
    with ui.column().classes('w-full max-w-4xl mx-auto p-4'):
        ui.label('Settings').classes('text-2xl font-bold mb-4')
        
        with ui.card().classes('w-full mb-4'):
            ui.label('Workspace Root').classes('mb-2')
            with ui.row().classes('items-center'):
                ui.icon('folder_open').classes('text-xl')
                ui.input(value=str(settings.workspace_root), on_change=lambda e: None).props('readonly').classes('flex-1 ml-2')
                ui.button('Change', on_click=lambda: ui.notify('Not implemented yet')).props('outline size=sm')
        
        with ui.card().classes('w-full mb-4'):
            ui.label('Output Root').classes('mb-2')
            with ui.row().classes('items-center'):
                ui.icon('folder').classes('text-xl')
                ui.input(value=str(settings.output_root), on_change=lambda e: None).props('readonly').classes('flex-1 ml-2')
                ui.button('Change', on_click=lambda: ui.notify('Not implemented yet')).props('outline size=sm')
        
        with ui.card().classes('w-full mb-4'):
            ui.label('Max File Size (MB)').classes('mb-2')
            with ui.row().classes('items-center'):
                ui.icon('storage').classes('text-xl')
                ui.number(value=settings.max_file_mb, min=1, max=10000, on_change=lambda e: handle_max_file_size_change(e.value)).classes('ml-2 w-32')
        
        with ui.card().classes('w-full mb-4'):
            ui.label('Features').classes('mb-2')
            with ui.column().classes('space-y-2'):
                ui.switch('Enable plugins', value=settings.allow_plugins, on_change=lambda e: handle_plugins_change(e.value)).classes('text-sm')
                ui.label('Plugins can execute code. Only enable if you trust the plugin source.').classes('text-xs text-muted mt-1')
                
                ui.switch('Enable remote URLs', value=settings.allow_remote_urls, on_change=lambda e: handle_remote_urls_change(e.value)).classes('text-sm')
                ui.label('Allows processing files from the internet. May pose security risks.').classes('text-xs text-muted mt-1')
                
                ui.switch('Enable AI enrichment', value=settings.allow_ai_enrichment, on_change=lambda e: handle_ai_enrichment_change(e.value)).classes('text-sm')
                ui.label('Requires external AI services. Keeps raw output separate from enriched output.').classes('text-xs text-muted mt-1')


def handle_max_file_size_change(value):
    """Handle max file size change."""
    from ..config import settings
    old_value = settings.max_file_mb
    settings.max_file_mb = value
    log_audit_event(
        level="info",
        event_type="settings_changed",
        message=f"Max file size changed from {old_value} MB to {value} MB",
        metadata={
            "setting": "max_file_mb",
            "old_value": old_value,
            "new_value": value
        }
    )


def handle_plugins_change(value):
    """Handle plugins setting change."""
    from ..config import settings
    old_value = settings.allow_plugins
    settings.allow_plugins = value
    log_audit_event(
        level="info",
        event_type="settings_changed",
        message=f"Enable plugins changed from {old_value} to {value}",
        metadata={
            "setting": "allow_plugins",
            "old_value": old_value,
            "new_value": value
        }
    )


def handle_remote_urls_change(value):
    """Handle remote URLs setting change."""
    from ..config import settings
    old_value = settings.allow_remote_urls
    settings.allow_remote_urls = value
    log_audit_event(
        level="info",
        event_type="settings_changed",
        message=f"Enable remote URLs changed from {old_value} to {value}",
        metadata={
            "setting": "allow_remote_urls",
            "old_value": old_value,
            "new_value": value
        }
    )


def handle_ai_enrichment_change(value):
    """Handle AI enrichment setting change."""
    from ..config import settings
    old_value = settings.allow_ai_enrichment
    settings.allow_ai_enrichment = value
    log_audit_event(
        level="info",
        event_type="settings_changed",
        message=f"Enable AI enrichment changed from {old_value} to {value}",
        metadata={
            "setting": "allow_ai_enrichment",
            "old_value": old_value,
            "new_value": value
        }
    )
