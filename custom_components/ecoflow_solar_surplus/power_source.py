from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PowerSourceSelection:
    """Selected power reading and source label."""

    value_w: float | None
    source: str


def select_power_source(
    *,
    primary_w: float | None,
    primary_ok: bool,
    fallback_w: float | None,
    fallback_ok: bool,
    primary_source: str = "primary",
    fallback_source: str = "fallback",
) -> PowerSourceSelection:
    """Prefer a valid primary reading, otherwise use a valid fallback."""
    if primary_ok and primary_w is not None:
        return PowerSourceSelection(value_w=float(primary_w), source=primary_source)
    if fallback_ok and fallback_w is not None:
        return PowerSourceSelection(value_w=float(fallback_w), source=fallback_source)
    return PowerSourceSelection(value_w=None, source="unavailable")
