# EcoFlow Solar Surplus Controller v0.1.6

## Native realtime Envoy MQTT telemetry

- Subscribe directly to the local Envoy bridge topic `/envoy/json` when Home Assistant MQTT is available.
- Parse Envoy meter EID `704643328` as solar production and EID `704643584` as signed net-grid power.
- Prefer fresh realtime MQTT readings for both grid and solar while keeping the configured Home Assistant entities as automatic fallbacks.
- Fail back automatically when realtime data is missing, invalid, unavailable, or older than five seconds.
- Replace the previous resettable two-second grid debounce with a one-second coalescing cadence so a continuously updating realtime feed cannot starve controller decisions.
- Keep raw sub-second MQTT packets inside the integration runtime instead of requiring YAML MQTT sensors.
- Expose coalesced diagnostic entities for Envoy realtime grid power, Envoy realtime solar power, site-grid source, and solar source.
- Preserve all existing controller gains, thresholds, DPU selection behavior, recovery behavior, and safety checks.
- Include realtime timestamps, source selection, and MQTT payload errors in integration diagnostics.
- Add pure regression tests for primary/fallback power-source selection.

The separate `envoy_realtime.yaml` package is no longer required by this release. The configured site-grid and solar entities remain valid fallbacks, so existing installations do not need to remap those entities.

This release does not change planner behavior or intentionally alter battery headroom policy. It changes the telemetry path used by the EcoFlow surplus controller.
