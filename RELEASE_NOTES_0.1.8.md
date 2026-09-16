# EcoFlow Solar Surplus Controller v0.1.8

## Adaptive realtime cadence

v0.1.8 keeps the v0.1.7 charging policy and instrumentation, but changes how high-frequency Envoy MQTT updates are scheduled for control evaluation.

- Normal grid conditions use a 1.5-second smoothing window to avoid chasing sub-second noise.
- Material export (500 W or more) or large import (1,000 W or more) uses a 0.5-second urgent reaction window.
- If an urgent reading arrives while a normal evaluation is pending, the pending evaluation is accelerated only when the urgent deadline is actually earlier.
- The controller continues to use the latest available telemetry at evaluation time rather than processing every MQTT packet.
- Existing charging thresholds, gains, DPU selection, fallback behavior, reserve behavior, and physical-recovery behavior are unchanged.
- Diagnostics add an `accelerated` grid-evaluation counter so the adaptive path can be validated during the next charging cycle.
