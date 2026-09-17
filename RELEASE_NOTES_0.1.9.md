# EcoFlow Solar Surplus Controller v0.1.9

## Urgent-import cadence refinement

v0.1.9 keeps the adaptive realtime cadence from v0.1.8 while avoiding unnecessary urgent evaluations when charging is already off.

- Material export (>=500 W export) remains urgent at the 0.5-second reaction window.
- Large import (>=1,000 W import) uses the urgent 0.5-second window only while the controller has an active charging mask that can still be reduced.
- When charging is already off, large household import uses the normal 1.5-second smoothing cadence.
- No new diagnostics counters or control variables were added.
- Charge-rate gains, DPU selection, fallback behavior, physical recovery, and safety logic are unchanged.
