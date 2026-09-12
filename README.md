# EcoFlow Solar Surplus Controller

A Home Assistant custom integration for controlling EcoFlow Smart Home Panel 2 Force Charge from measured solar surplus.

> **Status:** pre-release. Install in **Observe only** mode first and validate behavior before enabling control.

## What it does

The integration watches an authoritative whole-site grid-power sensor and adjusts EcoFlow Force Charge so available solar surplus is directed into battery storage while minimizing unintended grid import. It supports three EcoFlow battery channels, runtime charging-rate limits, stale-data safety, sunrise/sunset handling, one-way recovery, and a shadow/observe mode for safe migration from an existing automation.

## Safety-first migration

1. Install the integration through HACS as a custom repository.
2. Configure the required Home Assistant entities.
3. Leave **Operating mode** set to **Observe only**.
4. Compare proposed controller actions with the existing automation under real conditions.
5. Disable the legacy controller only after parity is confirmed.
6. Switch this integration to **Control EcoFlow**.

Returning the integration to **Observe only** provides a simple rollback path.

## Requirements

- Home Assistant 2026.6 or newer
- A site/grid power sensor reporting import/export in W or kW
- A solar-production power sensor
- EcoFlow Smart Home Panel 2 entities exposed to Home Assistant, including charging power, charging limit, battery SOC, channel switches, and Force Charge switches for three battery channels

## HACS installation

Until the repository is submitted to the default HACS catalog, add this repository as a custom repository in HACS with category **Integration**, install **EcoFlow Solar Surplus Controller**, restart Home Assistant, and then add it from **Settings → Devices & services**.

## Development principles

The controller intentionally separates pure decision logic from Home Assistant service calls. New control behavior should be covered by regression tests before it can affect live devices. The integration also starts in observe mode by default so installing it does not immediately take control of charging.

## License

MIT
