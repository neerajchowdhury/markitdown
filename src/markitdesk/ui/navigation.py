"""Shared tab navigation helpers for the MarkItDesk shell."""

from typing import Any, Optional

_tabs: Optional[Any] = None
_tab_map: dict[str, Any] = {}


def register_tabs(tabs: Any, tab_map: dict[str, Any]) -> None:
    """Register the active tab container and its named tabs."""
    global _tabs, _tab_map
    _tabs = tabs
    _tab_map = tab_map


def navigate_to(tab_name: str) -> bool:
    """Switch the active shell tab if it has been registered."""
    tab = _tab_map.get(tab_name)
    if tab is None or _tabs is None:
        return False

    _tabs.value = tab
    return True
