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
                    ui.label("Turn files into Markdown, then review and export the results.").classes("text-4xl font-black tracking-tight text-white")
                    ui.label("Use Convert to add files, Queue to watch progress, Preview to check the output, and Settings to choose where files are saved.").classes("text-base text-slate-300")
                with ui.column().classes("gap-3"):
                    ui.label("Safety posture").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
                    ui.label("Files stay on this computer").classes("text-lg font-semibold text-emerald-300")
                    ui.label("Nothing is uploaded unless you enable that feature yourself.").classes("text-sm text-slate-300")

        with ui.card().classes("w-full p-5 border border-white/10").style("background: rgba(15,23,42,.82);"):
            ui.label("Start here").classes("text-sm font-semibold uppercase tracking-[0.18em] text-slate-400")
            ui.label("Follow this simple flow: add files, wait for conversion, inspect the Markdown, then export when ready.").classes("text-base text-slate-300 mt-1")
            with ui.row().classes("gap-3 mt-4 flex-wrap"):
                ui.button("Add files", on_click=lambda: navigate_to("Convert")).props("color=primary")
                ui.button("See progress", on_click=lambda: navigate_to("Queue")).props("outline")
                ui.button("Check output", on_click=lambda: navigate_to("Preview")).props("outline")
                ui.button("Change settings", on_click=lambda: navigate_to("Settings")).props("outline")
            with ui.row().classes("w-full gap-4 mt-4 flex-wrap"):
                _path_card("1", "Add files", "Choose the files or folders you want to convert to Markdown.", "Open Convert")
                _path_card("2", "Watch progress", "See which files are processing, finished, or need attention.", "Open Queue")
                _path_card("3", "Review output", "Read the converted Markdown and check its quality.", "Open Preview")
                _path_card("4", "Set options", "Pick where files go and which features are allowed.", "Open Settings")

        with ui.row().classes("w-full gap-4 flex-wrap"):
            _stat_card("Workspace", "Locked to configured folders")
            _stat_card("Pipeline", "Files, folders, ZIPs, URLs")
            _stat_card("Output", "Separate Markdown artifacts")

        with ui.card().classes("w-full p-5 border border-white/10").style("background: rgba(15,23,42,.82);"):
            ui.label("Recent Jobs").classes("text-lg font-semibold text-white")
            ui.label("Your latest conversions will appear here. Start by adding files in Convert.").classes("text-sm text-slate-300 mt-1")
            with ui.column().classes("w-full min-h-36 rounded-2xl border border-dashed border-white/10 mt-4 p-6 items-center justify-center"):
                ui.icon("hourglass_empty").classes("text-4xl text-slate-500")
                ui.label("No conversions yet").classes("text-slate-300 mt-2")


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
