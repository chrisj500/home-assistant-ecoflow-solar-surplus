# EcoFlow Solar Surplus Controller

A Home Assistant custom integration for controlling EcoFlow Smart Home Panel 2 Force Charge from measured solar surplus.

## What it does

The integration watches whole-site grid power and solar production and adjusts EcoFlow Force Charge so available solar surplus is directed into battery storage while minimizing unintended grid import. It supports three EcoFlow battery channels, runtime charging-rate limits, stale-data safety, sunrise/sunset handling, one-way recovery, retained-channel protection, lowest-SOC DPU selection, import braking, and rate damping.

When Home Assistant MQTT is available, the integration subscribes directly to `/envoy/json`, the topic published by the local Envoy bridge. It parses meter EID `704643328` as solar production and EID `704643584` as signed net-grid power. Fresh realtime MQTT data is preferred automatically for both grid and solar; the configured Home Assistant site-grid and solar entities remain automatic fallbacks. No separate MQTT YAML sensor package is required.

High-frequency MQTT packets remain inside the integration runtime and are coalesced into approximately one-second controller evaluations. This avoids the previous resettable debounce problem while also avoiding a raw sub-second Home Assistant state for every MQTT message.

The controller exposes diagnostic entities for the coalesced Envoy grid and solar readings and for the active grid and solar source. It also keeps a persistent rolling history of the most recent 50 fresh-grid decisions. Decision history survives integration reloads and Home Assistant restarts and includes session timestamps so troubleshooting can distinguish activity across controller sessions.

## Operating modes

- **Observe only** computes controller decisions without issuing EcoFlow service calls. Use it when validating configuration or troubleshooting without changing charging state.
- **Control EcoFlow** allows the integration to set charging power and Force Charge switches.

Only one controller should write to the EcoFlow charging controls at a time.

## Requirements

- Home Assistant 2026.6 or newer
- A site/grid power sensor reporting import/export in W or kW for fallback operation
- A solar-production power sensor for fallback operation
- EcoFlow Smart Home Panel 2 entities exposed to Home Assistant, including charging power, charging limit, battery SOC, channel switches, and Force Charge switches for three battery channels
- Optional but preferred for realtime control: Home Assistant MQTT plus a local Envoy bridge publishing `/ivp/meters/readings` JSON to `/envoy/json`

## Realtime Envoy behavior

The native realtime path is optional. If valid MQTT data is received within five seconds, the controller uses it. If MQTT is absent, malformed, missing the required meter EIDs, or becomes stale, the controller automatically uses the configured Home Assistant grid and solar entities instead. Existing installations therefore keep their current entity mappings as fallbacks.

## HACS installation

Until the repository is submitted to the default HACS catalog, add this repository as a custom repository in HACS with category **Integration**, install **EcoFlow Solar Surplus Controller**, restart Home Assistant, and then add it from **Settings → Devices & services**.

## Diagnostics

The integration exposes controller health, command and desired masks, target and physical charging power, decision policy, last decision time, realtime Envoy grid and solar power, and the selected grid and solar source. Downloaded integration diagnostics include the persistent 50-entry decision history, realtime receive timestamps, the MQTT topic, payload errors, and configured fallback entities.

## Development principles

The controller intentionally separates pure decision logic from Home Assistant service calls. New control behavior should be covered by regression tests before it can affect live devices. Observe mode remains available as a no-write diagnostic mode.

## License

MIT
