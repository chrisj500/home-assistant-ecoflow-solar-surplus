# v0.1.11 — fresh post-command cadence

v0.1.11 keeps the v0.1.10 serialized latest-state executor, but changes how the controller re-enters control after a slow EcoFlow service call.

## What changed

- Busy-time control decisions are still discarded rather than queued or replayed.
- Envoy MQTT telemetry received while EcoFlow is busy is still retained.
- When the EcoFlow command completes, any grid-evaluation timer that began during the busy period is discarded.
- The controller starts one fresh adaptive evaluation window after the actuator is free: 0.5 seconds for urgent conditions and 1.5 seconds normally.
- New MQTT readings arriving during that fresh window are coalesced into the pending evaluation.
- The final decision uses the latest telemetry and the current post-command controller state.
- No gains, thresholds, DPU-selection rules, safety limits, or service-call serialization behavior changed.

## Why

Diagnostics from v0.1.10 showed that EcoFlow service calls still average roughly eight seconds. Immediate post-command reconciliation could react to a transient reading before the physical system had a short chance to settle, contributing to small import/export hunting. Reusing a timer that started while the command was still in flight would have the same problem because part or all of its smoothing window would occur before the actuator was free.

v0.1.11 therefore preserves the observations from the busy period but deliberately restarts the adaptive timing window after command completion. This avoids averaging stale in-flight decisions while giving the latest physical state a short post-actuation observation window before another command is issued.

## Expected result

The controller should retain fast response to material export/import while reducing command-to-command oscillation caused by immediately reversing an EcoFlow adjustment after a slow service call.
