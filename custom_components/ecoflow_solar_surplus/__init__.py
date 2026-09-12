from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .controller import EcoFlowSurplusController


@dataclass(slots=True)
class EcoFlowSurplusRuntimeData:
    """Runtime data attached to the config entry."""

    controller: EcoFlowSurplusController


type EcoFlowSurplusConfigEntry = ConfigEntry[EcoFlowSurplusRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: EcoFlowSurplusConfigEntry
) -> bool:
    """Set up EcoFlow Solar Surplus Controller from a config entry."""
    controller = EcoFlowSurplusController(hass, entry)
    await controller.async_setup()
    entry.runtime_data = EcoFlowSurplusRuntimeData(controller=controller)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await controller.async_shutdown()
        raise
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EcoFlowSurplusConfigEntry
) -> bool:
    """Unload EcoFlow Solar Surplus Controller."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.controller.async_shutdown()
    return unload_ok
