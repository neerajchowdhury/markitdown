"""NiceGUI import shim for environments where the dependency is absent."""

from html import escape as html_escape

try:
    from nicegui import ui as ui  # type: ignore
except ImportError:
    class _NullUI:
        """Minimal chainable stub that keeps UI modules importable in tests."""

        def __call__(self, *args, **kwargs):
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __getattr__(self, name):
            if name == "escape_html":
                return html_escape
            return self

        def clear(self):
            return None

        def set_options(self, *args, **kwargs):
            return None

        def set_value(self, *args, **kwargs):
            return None

        def on_value_change(self, *args, **kwargs):
            return None

    ui = _NullUI()
