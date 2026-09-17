# v0.1.10 — latest-state reconciliation after slow EcoFlow commands

The EcoFlow service layer can take roughly eight seconds to complete a command. v0.1.10 keeps accepting realtime Envoy telemetry while a command is in flight, but deliberately does not queue intermediate control decisions.

## What changed

- Busy-time controller triggers are collapsed into a single reconciliation request.
- The in-flight EcoFlow command transaction is allowed to finish without overlapping service calls.
- As soon as the controller is free, it immediately performs one fresh grid evaluation using the latest telemetry and current command state.
- Intermediate decisions observed while the executor is busy are discarded instead of being replayed later.
- No control gains, thresholds, DPU-selection logic, safety limits, or adaptive cadence settings changed.

## Why

Diagnostics from v0.1.9 showed that Home Assistant `number.set_value` and switch service calls to the EcoFlow integration commonly take about eight seconds. During those calls the controller lock is intentionally held to prevent overlapping hardware commands. The previous behavior dropped triggers received during that period. The new behavior preserves serialization while guaranteeing a fresh latest-state reconciliation immediately afterward.

## Expected result

The controller should no longer act on a backlog of stale decisions. If grid or solar conditions change several times during one slow EcoFlow service call, only the newest state matters when the executor becomes available again.
