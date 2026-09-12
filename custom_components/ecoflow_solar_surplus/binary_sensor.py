from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcoFlowSurplusConfigEntry
from .entity import EcoFlowSurplusEntity


@dataclass(frozen=True, kw_only=True)
class EcoFlowSurplusBinarySensorDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[object], bool]


BINARY_SENSORS: tuple[EcoFlowSurplusBinarySensorDescription, ...] = (
    EcoFlowSurplusBinarySensorDescription(
        key="control_ready",
        translation_key="control_ready",
        is_on_fn=lambda controller: controller.control_ready,
    ),
    EcoFlowSurplusBinarySensorDescription(
        key="control_active",
        translation_key="control_active",
        is_on_fn=lambda controller: controller.is_control_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcoFlowSurplusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up controller binary sensors."""
    controller = entry.runtime_data.controller
    async_add_entities(
        EcoFlowSurplusBinarySensor(entry, controller, description)
        for description in BINARY_SENSORS
    )


class EcoFlowSurplusBinarySensor(EcoFlowSurplusEntity, BinarySensorEntity):
    """Binary diagnostic state backed by the controller runtime."""

    entity_description: EcoFlowSurplusBinarySensorDescription

    def __init__(self, entry, controller, description) -> None:
        super().__init__(entry, controller, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.controller)
