# 0.1.13 — Post-command shutdown telemetry

A successful off request could leave cached EcoFlow switch and panel readings unchanged. Version 0.1.12 retried against those old values and reported shutdown unconfirmed even when the physical charger had stopped.

- Require recent HA reports received after the latest off request to verify shutdown or justify another retry.
- Distinguish awaiting fresh telemetry from fresh telemetry still reporting charging. Cached values do not consume retries or produce a shutdown-failure error.
- Verify late fresh off reports on normal controller triggers without reloading the controller.
- Include per-entity report timestamps, freshness and post-command flags in shutdown diagnostics and retained shutdown events.
- Determine report freshness from last_reported, with last_updated fallback, so unchanged values reported again remain valid.

HA report timestamps are evidence of a newly received report, not transport or hardware acknowledgements. No native EcoFlow refresh action is invented or invoked. The three-request limit and 30-second minimum retry interval remain in effect.

Validation: 46 regression tests passed, covering stale cached on/charging readings, late off reports, partially refreshed readings, genuinely fresh contradictory reports, repeated pre-retry readings and unchanged-value reports. Live integration verification follows installation.
