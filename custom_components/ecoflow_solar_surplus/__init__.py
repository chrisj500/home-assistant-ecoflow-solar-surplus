from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .instrumented_controller import InstrumentedEcoFlowSurplusController
from .observability import EcoFlowSurplusObservability


@dataclass(slots=True)
class EcoFlowSurplusRuntimeData:
    """Runtime data attached to the config entry."""

    controller: InstrumentedEcoFlowSurplusController
    observability: EcoFlowSurplusObservability


type EcoFlowSurplusConfigEntry = ConfigEntry[EcoFlowSurplusRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: EcoFlowSurplusConfigEntry
) -> bool:
    """Set up EcoFlow Solar Surplus Controller from a config entry."""
    controller = InstrumentedEcoFlowSurplusController(hass, entry)
    await controller.async_setup()
    observability = EcoFlowSurplusObservability(hass, controller)
    await observability.async_setup()
    entry.runtime_data = EcoFlowSurplusRuntimeData(
        controller=controller,
        observability=observability,
    )
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await observability.async_shutdown()
        await controller.async_shutdown()
        raise
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EcoFlowSurplusConfigEntry
) -> bool:
    """Unload EcoFlow Solar Surplus Controller."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.observability.async_shutdown()
        await entry.runtime_data.controller.async_shutdown()
    return unload_ok
