# 0.1.12 — Verified force-charge shutdown

When the controller recorded no active chargers but EcoFlow continued charging, grid evaluations, sunset and the watchdog could skip shutdown. Control mode now checks actual force-charge switch states and fresh panel charging power independently of the saved command.

- Verify all force-charge switches are off and fresh panel charging is at most 200 W before reporting shutdown confirmed.
- Retry off requests at most three times, at least 30 seconds apart; report an error if shutdown remains unconfirmed.
- Apply the safety check before nighttime reassertions as well as grid and watchdog handling. Observe mode remains read-only.
- Include actual force-charge states and verification details in diagnostics, with a separately retained, persistent shutdown-event history that routine grid decisions cannot evict.
- Preserve AC channel enablement and configured reserve/charging limits. This changes only the surplus controller’s force-charge shutdown behavior.

Validation: 40 regression tests passed, including the 1,102 W nighttime charging reproduction, delayed confirmation, stale telemetry, service failures, bounded retries and observe mode.
