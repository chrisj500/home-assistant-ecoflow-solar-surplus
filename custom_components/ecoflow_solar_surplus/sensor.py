from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcoFlowSurplusConfigEntry
from .entity import EcoFlowSurplusEntity
from .logic import mask_count


@dataclass(frozen=True, kw_only=True)
class EcoFlowSurplusSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Any], Any]


def _decision_value(controller, key: str):
    decision = controller.last_decision
    return getattr(decision, key) if decision is not None else None


SENSORS: tuple[EcoFlowSurplusSensorDescription, ...] = (
    EcoFlowSurplusSensorDescription(
        key="status",
        translation_key="status",
        value_fn=lambda controller: controller.status,
    ),
    EcoFlowSurplusSensorDescription(
        key="operating_mode",
        translation_key="operating_mode",
        value_fn=lambda controller: controller.operating_mode,
    ),
    EcoFlowSurplusSensorDescription(
        key="commanded_rate",
        translation_key="commanded_rate",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda controller: controller.command.rate_w,
    ),
    EcoFlowSurplusSensorDescription(
        key="proposed_rate",
        translation_key="proposed_rate",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda controller: _decision_value(controller, "command_rate_w"),
    ),
    EcoFlowSurplusSensorDescription(
        key="commanded_dpu_count",
        translation_key="commanded_dpu_count",
        value_fn=lambda controller: mask_count(controller.command.mask),
    ),
    EcoFlowSurplusSensorDescription(
        key="desired_dpu_count",
        translation_key="desired_dpu_count",
        value_fn=lambda controller: _decision_value(controller, "desired_count"),
    ),
    EcoFlowSurplusSensorDescription(
        key="last_action",
        translation_key="last_action",
        value_fn=lambda controller: controller.last_action,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcoFlowSurplusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up controller diagnostic sensors."""
    controller = entry.runtime_data.controller
    async_add_entities(
        EcoFlowSurplusSensor(entry, controller, description)
        for description in SENSORS
    )


class EcoFlowSurplusSensor(EcoFlowSurplusEntity, SensorEntity):
    """Diagnostic sensor backed by the controller runtime."""

    entity_description: EcoFlowSurplusSensorDescription

    def __init__(self, entry, controller, description) -> None:
        super().__init__(entry, controller, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.controller)
