from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import EcoFlowSurplusConfigEntry
from .const import DOMAIN, NAME
from .controller import EcoFlowSurplusController


class EcoFlowSurplusEntity(Entity):
    """Base entity for the EcoFlow Solar Surplus Controller."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: EcoFlowSurplusConfigEntry,
        controller: EcoFlowSurplusController,
        key: str,
    ) -> None:
        self._entry = entry
        self.controller = controller
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Community",
            model=NAME,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to controller updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal,
                self._handle_controller_update,
            )
        )

    def _handle_controller_update(self) -> None:
        self.async_write_ha_state()
