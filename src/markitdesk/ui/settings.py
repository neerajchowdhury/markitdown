"""Settings page for MarkItDesk."""

from pathlib import Path
from ..ui_runtime import ui
from ..config import settings
from ..audit import log_audit_event


def settings_page() -> None:
    """Render the settings page."""
    with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
        with ui.card().classes("w-full p-6 border border-white/10").style(
            "background: linear-gradient(135deg, rgba(15,23,42,.92), rgba(15,23,42,.72));"
        ):
            with ui.row().classes("w-full items-start justify-between gap-4"):
                with ui.column().classes("gap-2 max-w-3xl"):
                    ui.label("Settings").classes("text-sm font-semibold uppercase tracking-[0.22em] text-slate-400")
                    ui.label("Choose where files are stored and which features are allowed.").classes("text-4xl font-black tracking-tight text-white")
                    ui.label("These settings control where MarkItDesk reads and writes files, plus whether optional features like URL ingestion are available.").classes("text-base text-slate-300")
                ui.badge("Security-sensitive").props("outline")

        with ui.card().classes("w-full p-5 border border-white/10").style("background: rgba(15,23,42,.82);"):
            ui.label("Workspace").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
            ui.label("These folders decide where your input files are read from and where converted Markdown is written.").classes("text-sm text-slate-300 mt-1")
            _setting_row("Workspace Root", str(settings.workspace_root), "folder_open")
            _setting_row("Output Root", str(settings.output_root), "folder")

        with ui.card().classes("w-full p-5 border border-white/10").style("background: rgba(15,23,42,.82);"):
            ui.label("Limits").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
            ui.label("This is the largest file size the app will accept. Bigger files are blocked before conversion starts.").classes("text-sm text-slate-300 mt-1")
            with ui.row().classes("items-center gap-3 mt-3"):
                ui.icon('storage').classes('text-xl text-slate-300')
                ui.label('Max file size (MB)').classes('text-white')
                ui.number(value=settings.max_file_mb, min=1, max=10000, on_change=lambda e: handle_max_file_size_change(e.value)).classes('ml-2 w-32')

        with ui.card().classes("w-full p-5 border border-white/10").style("background: rgba(15,23,42,.82);"):
            ui.label("Features").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
            ui.label("Turn these on only if you understand the tradeoff. Each switch changes what the app is allowed to do.").classes("text-sm text-slate-300 mt-1")
            with ui.column().classes('space-y-3 mt-3'):
                ui.switch('Allow plugins', value=settings.allow_plugins, on_change=lambda e: handle_plugins_change(e.value)).classes('text-sm')
                ui.label('Lets the app load plugin code. Leave this off unless you trust the source.').classes('text-xs text-slate-400')

                ui.switch('Allow remote URLs', value=settings.allow_remote_urls, on_change=lambda e: handle_remote_urls_change(e.value)).classes('text-sm')
                ui.label('Lets you import files from links on the internet. Turn this on only when needed.').classes('text-xs text-slate-400')

                ui.switch('Allow AI enrichment', value=settings.allow_ai_enrichment, on_change=lambda e: handle_ai_enrichment_change(e.value)).classes('text-sm')
                ui.label('Adds optional AI-assisted output. The original Markdown stays separate.').classes('text-xs text-slate-400')


def _setting_row(label_text, value_text, icon_name):
    with ui.row().classes("items-center gap-3 mt-4"):
        ui.icon(icon_name).classes("text-xl text-slate-300")
        with ui.column().classes("flex-1 gap-1"):
            ui.label(label_text).classes("text-sm text-white")
            ui.input(value=value_text, on_change=lambda e: None).props('readonly').classes('w-full')
        ui.button('Change', on_click=lambda: ui.notify('Changing these folders is not implemented yet.')).props('outline size=sm')


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
