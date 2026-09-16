# EcoFlow Solar Surplus Controller v0.1.6

## Realtime Envoy grid input with failover

- Prefer `sensor.envoy_realtime_grid_power` automatically when it is present, valid, and fresh.
- Keep the configured site/grid power entity as the automatic fallback.
- Fail back to the configured sensor when the realtime MQTT entity is missing, unavailable, invalid, or stale.
- Replace the previous resettable two-second grid debounce with a one-second coalescing cadence so a continuously updating realtime feed cannot starve controller decisions.
- Preserve all existing controller gains, thresholds, DPU selection behavior, recovery behavior, and safety checks.
- Add the selected grid source to controller snapshots and diagnostics.
- Add pure regression tests for primary/fallback grid-source selection.

This release does not change planner behavior or intentionally alter battery headroom policy. It changes only the site-grid telemetry path used by the EcoFlow surplus controller.
