# Development state — 0.1.13

## Evidence and scope
0.1.12 corrected force-charge shutdown skipped by an internally off command mask. Subsequent physical observation showed the off command succeeded while cached EcoFlow telemetry remained on/charging; independent site import fell. Reload later showed off/zero charging. The precise native integration reporting delay is not yet diagnosed.

## Correction
Shutdown checks now use HA last_reported timestamps (last_updated fallback), bounded by physical meter age, relative to the latest off request. All force switches and both panel power readings must be fresh/post-command to confirm off. A fresh on switch or a fresh panel pair reporting charging may justify a retry, at least 30 seconds apart, at most three requests. Old or incomplete evidence yields awaiting_fresh_telemetry without retries or a failure error. Later fresh off reports recover through normal grid/watchdog triggers without restarting. HA report time is not proof of transport acknowledgement; source telemetry may still contain cached device values.

Diagnostics retain per-source timestamps and freshness flags with shutdown event history. Observe mode remains read-only. Reserve settings, limits and channel enablement remain unchanged. No unsupported device refresh services are invoked.

## Validation and handoff
46 tests exercise actual controller methods with fake HA states/services, including the stale-report reproduction and automatic confirmation recovery. Run the GitHub regression/Hassfest/HACS checks before merge. Prepared as v0.1.13; release workflow on main publishes ZIP and tag only after all checks succeed. After installation, verify delayed native reports produce a waiting state, then confirmation when new reports arrive. Native EcoFlow transport debugging is a separate remaining investigation if reports stall indefinitely.
