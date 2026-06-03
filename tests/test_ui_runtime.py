"""Tests for the NiceGUI runtime shim."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_ui_runtime_imports_ui_object():
    """The runtime shim should always expose a ui object."""
    from markitdesk.ui_runtime import ui

    assert ui is not None


def test_ui_runtime_fallback_escape_html_and_chainability():
    """The fallback UI object should support escaping and common chainable calls."""
    from markitdesk.ui_runtime import ui

    escaped = ui.escape_html("<tag>")
    assert escaped == "&lt;tag&gt;"

    element = ui.label("text").classes("foo").props("bar")
    assert element is not None
    assert ui.button("go").on_click(lambda: None) is not None
    assert ui.select(options={}).set_options({"a": "a"}) is None
    assert ui.select(options={}).set_value("a") is None
    assert ui.select(options={}).on_value_change(lambda e: None) is None


def test_ui_runtime_context_manager_noops_cleanly():
    """The fallback UI object should work as a context manager for nested layout code."""
    from markitdesk.ui_runtime import ui

    with ui.column().classes("w-full") as column:
        nested = ui.row().classes("items-center")

    assert column is not None
    assert nested is not None
