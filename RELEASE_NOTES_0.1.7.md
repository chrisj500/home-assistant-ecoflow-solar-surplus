# EcoFlow Solar Surplus Controller v0.1.7

## Controller performance instrumentation

v0.1.7 adds session-scoped diagnostics for the realtime control path introduced in v0.1.6. It does not change charging thresholds, gains, DPU selection policy, fallback behavior, or the 1-second grid coalescing interval.

Diagnostics now include:

- Envoy MQTT messages received, valid messages, and payload errors.
- Grid evaluations scheduled, coalesced, completed, and skipped because the controller was busy.
- Grid evaluation execution timing: last, average, and maximum duration.
- Site-grid and solar source-switch counts, including configured-entity fallback activations.
- EcoFlow/Home Assistant service-call timing grouped by call type, including charging-rate writes and Force Charge switch operations.

These counters are intentionally session-scoped and reset when the integration reloads or Home Assistant restarts. They are exposed through the integration's Home Assistant diagnostics download so intermittent control delays can be separated into MQTT cadence, controller concurrency, source fallback, or downstream EcoFlow service-call latency.
