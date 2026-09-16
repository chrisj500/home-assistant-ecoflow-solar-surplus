from __future__ import annotations

NORMAL_GRID_EVALUATION_SECONDS = 1.5
URGENT_GRID_EVALUATION_SECONDS = 0.5
URGENT_EXPORT_W = 500.0
URGENT_IMPORT_W = 1000.0


def grid_evaluation_delay_seconds(grid_w: float | None) -> float:
    """Return the control delay for the latest signed site-grid reading.

    Positive grid power is import and negative grid power is export. Normal
    telemetry is intentionally smoothed to avoid chasing sub-second noise.
    Material export or import excursions use a shorter reaction window.
    """
    if grid_w is None:
        return NORMAL_GRID_EVALUATION_SECONDS
    if grid_w <= -URGENT_EXPORT_W or grid_w >= URGENT_IMPORT_W:
        return URGENT_GRID_EVALUATION_SECONDS
    return NORMAL_GRID_EVALUATION_SECONDS
