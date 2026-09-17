from __future__ import annotations

NORMAL_GRID_EVALUATION_SECONDS = 1.5
URGENT_GRID_EVALUATION_SECONDS = 0.5
URGENT_EXPORT_W = 500.0
URGENT_IMPORT_W = 1000.0


def grid_evaluation_delay_seconds(
    grid_w: float | None, *, charging_active: bool = False
) -> float:
    """Return the control delay for the latest signed site-grid reading.

    Positive grid power is import and negative grid power is export. Normal
    telemetry is intentionally smoothed to avoid chasing sub-second noise.
    Material export is always urgent because avoidable export is the primary
    control target. Large import is urgent only while the controller still has
    an active charging mask that can be reduced.
    """
    if grid_w is None:
        return NORMAL_GRID_EVALUATION_SECONDS
    if grid_w <= -URGENT_EXPORT_W:
        return URGENT_GRID_EVALUATION_SECONDS
    if charging_active and grid_w >= URGENT_IMPORT_W:
        return URGENT_GRID_EVALUATION_SECONDS
    return NORMAL_GRID_EVALUATION_SECONDS
