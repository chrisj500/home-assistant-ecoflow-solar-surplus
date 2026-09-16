from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GridSourceSelection:
    """Selected whole-site grid input for one controller snapshot."""

    value_w: float
    ok: bool
    source: str


def select_grid_source(
    *,
    preferred_w: float | None,
    preferred_fresh: bool,
    fallback_w: float | None,
    fallback_fresh: bool,
) -> GridSourceSelection:
    """Prefer the realtime grid source and fall back safely when unavailable."""
    if preferred_w is not None and preferred_fresh:
        return GridSourceSelection(
            value_w=float(preferred_w),
            ok=True,
            source="realtime_mqtt",
        )

    if fallback_w is not None and fallback_fresh:
        return GridSourceSelection(
            value_w=float(fallback_w),
            ok=True,
            source="configured_fallback",
        )

    return GridSourceSelection(value_w=0.0, ok=False, source="unavailable")
