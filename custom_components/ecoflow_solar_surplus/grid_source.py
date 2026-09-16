from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GridSourceSelection:
    """Selected site-grid reading and source label."""

    value_w: float | None
    source: str


def select_grid_source(
    *,
    primary_w: float | None,
    primary_ok: bool,
    fallback_w: float | None,
    fallback_ok: bool,
) -> GridSourceSelection:
    """Prefer a valid primary reading, otherwise use a valid fallback."""
    if primary_ok and primary_w is not None:
        return GridSourceSelection(value_w=float(primary_w), source="primary")
    if fallback_ok and fallback_w is not None:
        return GridSourceSelection(value_w=float(fallback_w), source="fallback")
    return GridSourceSelection(value_w=None, source="unavailable")
