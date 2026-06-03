"""Dashboard page for MarkItDesk."""

from ..ui_runtime import ui
from .navigation import navigate_to


def dashboard_page() -> None:
    """Render the dashboard page."""
    with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
        with ui.card().classes("w-full p-6 border border-white/10").style(
            "background: linear-gradient(135deg, rgba(15,23,42,.9), rgba(15,23,42,.72));"
        ):
            with ui.row().classes("w-full items-start justify-between gap-4"):
                with ui.column().classes("gap-3 max-w-3xl"):
                    ui.label("Command Center").classes("text-sm font-semibold uppercase tracking-[0.22em] text-slate-400")
                    ui.label("The workspace that keeps ingestion, review, and export in one place.").classes("text-4xl font-black tracking-tight text-white")
                    ui.label("MarkItDesk is tuned for local-first document pipelines with clear boundaries, visible outputs, and fast recovery when something fails.").classes("text-base text-slate-300")
                with ui.column().classes("gap-3"):
                    ui.label("Safety posture").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
                    ui.label("Local-first processing").classes("text-lg font-semibold text-emerald-300")
                    ui.label("No data leaves your machine by default.").classes("text-sm text-slate-300")

        with ui.card().classes("w-full p-5 border border-white/10").style("background: rgba(15,23,42,.82);"):
            ui.label("Start here").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
            ui.label("The shortest path from empty workspace to Markdown output is: import, queue, preview, export.").classes("text-base text-slate-300 mt-1")
            with ui.row().classes("w-full gap-4 mt-4 flex-wrap"):
                _path_card("1", "Convert", "Import files, folders, ZIPs, or approved URLs.", "Open Convert")
                _path_card("2", "Queue", "Watch jobs move through processing and recovery.", "Open Queue")
                _path_card("3", "Preview", "Inspect the rendered Markdown and quality score.", "Open Preview")
                _path_card("4", "Settings", "Adjust workspace and security boundaries.", "Open Settings")

        with ui.row().classes("w-full gap-4 flex-wrap"):
            _stat_card("Workspace", "Locked to configured folders")
            _stat_card("Pipeline", "Files, folders, ZIPs, URLs")
            _stat_card("Output", "Separate Markdown artifacts")

        with ui.card().classes("w-full p-5 border border-white/10").style("background: rgba(15,23,42,.82);"):
            ui.label("Recent Jobs").classes("text-lg font-semibold text-white")
            ui.label("Nothing has run yet. Use Convert to enqueue content and this area will surface the latest activity.").classes("text-sm text-slate-300 mt-1")
            with ui.column().classes("w-full min-h-36 rounded-2xl border border-dashed border-white/10 mt-4 p-6 items-center justify-center"):
                ui.icon("hourglass_empty").classes("text-4xl text-slate-500")
                ui.label("Waiting for your first import").classes("text-slate-300 mt-2")


def _stat_card(title: str, value: str):
    with ui.card().classes("flex-1 min-w-64 p-5 border border-white/10").style("background: rgba(15,23,42,.72);"):
        ui.label(title).classes("text-xs uppercase tracking-[0.2em] text-slate-400")
        ui.label(value).classes("text-lg font-semibold text-white mt-2")


def _path_card(step: str, title: str, body: str, cta: str):
    with ui.card().classes("flex-1 min-w-56 p-4 border border-white/10").style("background: rgba(2,6,23,.55);"):
        ui.label(step).classes("text-xs uppercase tracking-[0.25em] text-emerald-300")
        ui.label(title).classes("text-lg font-semibold text-white mt-2")
        ui.label(body).classes("text-sm text-slate-300 mt-2")
        ui.button(cta, on_click=lambda name=title: navigate_to(name)).props("outline size=sm").classes("mt-4")
