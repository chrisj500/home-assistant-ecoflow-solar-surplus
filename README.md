# EcoFlow Solar Surplus Controller

A Home Assistant custom integration for controlling EcoFlow Smart Home Panel 2 Force Charge from measured solar surplus.

## What it does

The integration watches an authoritative whole-site grid-power sensor and adjusts EcoFlow Force Charge so available solar surplus is directed into battery storage while minimizing unintended grid import. It supports three EcoFlow battery channels, runtime charging-rate limits, stale-data safety, sunrise/sunset handling, one-way recovery, retained-channel protection, lowest-SOC DPU selection, import braking, and rate damping.

When `sensor.envoy_realtime_grid_power` is available, the controller automatically prefers that high-frequency local Envoy reading for grid decisions. The configured site/grid power sensor remains the fallback and is used automatically whenever the realtime sensor is missing, unavailable, invalid, or stale. High-frequency updates are coalesced into a one-second control cadence so a continuously updating MQTT feed cannot starve the controller's decision loop.

The controller also exposes diagnostic entities and keeps a persistent rolling history of the most recent 50 fresh-grid decisions. Decision history survives integration reloads and Home Assistant restarts and includes session timestamps so troubleshooting can distinguish activity across controller sessions. Downloaded diagnostics include the active grid-source label in each controller snapshot.

## Operating modes

- **Observe only** computes controller decisions without issuing EcoFlow service calls. Use it when validating configuration or troubleshooting without changing charging state.
- **Control EcoFlow** allows the integration to set charging power and Force Charge switches.

Only one controller should write to the EcoFlow charging controls at a time.

## Requirements

- Home Assistant 2026.6 or newer
- A site/grid power sensor reporting import/export in W or kW
- A solar-production power sensor
- EcoFlow Smart Home Panel 2 entities exposed to Home Assistant, including charging power, charging limit, battery SOC, channel switches, and Force Charge switches for three battery channels
- Optional: `sensor.envoy_realtime_grid_power` for high-frequency local grid telemetry; the configured site/grid sensor remains the fallback

## HACS installation

Until the repository is submitted to the default HACS catalog, add this repository as a custom repository in HACS with category **Integration**, install **EcoFlow Solar Surplus Controller**, restart Home Assistant, and then add it from **Settings → Devices & services**.

## Diagnostics

The integration exposes controller health, command and desired masks, target and physical charging power, decision policy, last decision time, and related telemetry. Home Assistant's downloaded integration diagnostics include the persistent 50-entry decision history plus the realtime and fallback grid-source configuration and the source selected for each current snapshot.

## Development principles

The controller intentionally separates pure decision logic from Home Assistant service calls. New control behavior should be covered by regression tests before it can affect live devices. Observe mode remains available as a no-write diagnostic mode.

## License

MIT
