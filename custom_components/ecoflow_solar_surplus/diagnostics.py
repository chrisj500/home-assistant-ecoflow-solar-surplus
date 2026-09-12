from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import EcoFlowSurplusConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: EcoFlowSurplusConfigEntry,
) -> dict[str, Any]:
    """Return controller diagnostics for troubleshooting and parity validation."""
    return {
        "config": dict(entry.data),
        "options": dict(entry.options),
        "controller": entry.runtime_data.controller.diagnostic_data(),
    }
