from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfPower
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


@dataclass(frozen=True, kw_only=True)
class EcoFlowSurplusObservabilitySensorDescription(SensorEntityDescription):
    value_fn: Callable[[Any, Any], Any]


OBSERVABILITY_SENSORS: tuple[EcoFlowSurplusObservabilitySensorDescription, ...] = (
    EcoFlowSurplusObservabilitySensorDescription(
        key="decision_site_grid_power",
        translation_key="decision_site_grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.decision_site_grid_w,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="decision_solar_power",
        translation_key="decision_solar_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.decision_solar_w,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="physical_charge_power",
        translation_key="physical_charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.physical_charge_w,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="target_charge_power",
        translation_key="target_charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.target_charge_w,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="commanded_mask",
        translation_key="commanded_mask",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: controller.command.mask,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="desired_mask",
        translation_key="desired_mask",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.desired_mask,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="decision_policy",
        translation_key="decision_policy",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.decision_policy,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="last_decision_time",
        translation_key="last_decision_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.last_decision_at,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="charge_power_difference",
        translation_key="charge_power_difference",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.charge_power_difference_w,
    ),
    EcoFlowSurplusObservabilitySensorDescription(
        key="last_error",
        translation_key="last_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda controller, observability: observability.last_error,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcoFlowSurplusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up controller diagnostic sensors."""
    controller = entry.runtime_data.controller
    observability = entry.runtime_data.observability
    async_add_entities(
        [
            *(EcoFlowSurplusSensor(entry, controller, description) for description in SENSORS),
            *(
                EcoFlowSurplusObservabilitySensor(
                    entry, controller, observability, description
                )
                for description in OBSERVABILITY_SENSORS
            ),
        ]
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


class EcoFlowSurplusObservabilitySensor(EcoFlowSurplusEntity, SensorEntity):
    """Read-only observability sensor backed by controller diagnostics."""

    entity_description: EcoFlowSurplusObservabilitySensorDescription

    def __init__(self, entry, controller, observability, description) -> None:
        super().__init__(entry, controller, description.key)
        self.observability = observability
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.controller, self.observability)
