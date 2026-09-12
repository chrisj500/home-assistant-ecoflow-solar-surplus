from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import Platform
from homeassistant.core import State, callback
from homeassistant.helpers import selector

from .const import (
    CONF_AC1_CHANNEL,
    CONF_AC1_FORCE,
    CONF_AC1_SOC,
    CONF_AC2_CHANNEL,
    CONF_AC2_FORCE,
    CONF_AC2_SOC,
    CONF_AC3_CHANNEL,
    CONF_AC3_FORCE,
    CONF_AC3_SOC,
    CONF_CHARGE_LIMIT,
    CONF_CHARGING_POWER,
    CONF_LEGACY_MASK,
    CONF_LEGACY_RATE,
    CONF_SHP_GRID_POWER,
    CONF_SHP_HOME_POWER,
    CONF_SITE_GRID_POWER,
    CONF_SOLAR_POWER,
    DEFAULT_OPTIONS,
    DOMAIN,
    LEGACY_MASK_ENTITY,
    LEGACY_RATE_ENTITY,
    MODE_CONTROL,
    MODE_OBSERVE,
    OPT_EXPORT_GAIN,
    OPT_IMPORT_GAIN,
    OPT_IMPORT_HOLD_HIGH_W,
    OPT_MAXIMUM_RATE_INCREASE_W,
    OPT_MAXIMUM_RATE_W,
    OPT_METER_MAX_AGE_SECONDS,
    OPT_MINIMUM_RATE_W,
    OPT_MINIMUM_SOLAR_W,
    OPT_MODERATE_IMPORT_DECREASE_W,
    OPT_MODERATE_IMPORT_THRESHOLD_W,
    OPT_OPERATING_MODE,
    OPT_PHYSICAL_METER_MAX_AGE_SECONDS,
    OPT_PHYSICAL_RECOVERY_SECONDS,
    OPT_PREFERRED_IMPORT_W,
    OPT_RATE_STEP_W,
    OPT_SEVERE_IMPORT_THRESHOLD_W,
    OPT_SLOW_IMPORT_DECREASE_W,
    OPT_START_2_W,
    OPT_START_3_W,
    OPT_START_EXPORT_W,
    OPT_STOP_2_W,
    OPT_STOP_3_W,
    OPT_STOP_ALL_W,
)

SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=Platform.SENSOR)
)
NUMBER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=Platform.NUMBER)
)
SWITCH_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=Platform.SWITCH)
)


def _number(
    minimum: float,
    maximum: float,
    step: float,
    unit: str | None = None,
) -> selector.NumberSelector:
    """Build a number selector without serializing an invalid null unit."""
    if unit is None:
        config = selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
        )
    else:
        config = selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
        )
    return selector.NumberSelector(config)


def _basic_options_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(OPT_OPERATING_MODE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[MODE_OBSERVE, MODE_CONTROL],
                    translation_key="operating_mode",
                )
            ),
            vol.Required(OPT_PREFERRED_IMPORT_W): _number(-1000, 2000, 50, "W"),
            vol.Required(OPT_START_EXPORT_W): _number(0, 5000, 50, "W"),
            vol.Required(OPT_MAXIMUM_RATE_W): _number(500, 7200, 100, "W"),
            vol.Required(OPT_MINIMUM_SOLAR_W): _number(0, 5000, 50, "W"),
        }
    )


def _advanced_options_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(OPT_MINIMUM_RATE_W): _number(100, 7200, 100, "W"),
            vol.Required(OPT_RATE_STEP_W): _number(1, 1000, 1, "W"),
            vol.Required(OPT_MAXIMUM_RATE_INCREASE_W): _number(100, 5000, 100, "W"),
            vol.Required(OPT_SLOW_IMPORT_DECREASE_W): _number(0, 5000, 50, "W"),
            vol.Required(OPT_MODERATE_IMPORT_DECREASE_W): _number(0, 5000, 50, "W"),
            vol.Required(OPT_IMPORT_HOLD_HIGH_W): _number(0, 5000, 50, "W"),
            vol.Required(OPT_MODERATE_IMPORT_THRESHOLD_W): _number(0, 10000, 100, "W"),
            vol.Required(OPT_SEVERE_IMPORT_THRESHOLD_W): _number(0, 15000, 100, "W"),
            vol.Required(OPT_EXPORT_GAIN): _number(0.1, 2.0, 0.1),
            vol.Required(OPT_IMPORT_GAIN): _number(0.1, 2.0, 0.1),
            vol.Required(OPT_STOP_ALL_W): _number(0, 5000, 50, "W"),
            vol.Required(OPT_START_2_W): _number(0, 15000, 100, "W"),
            vol.Required(OPT_STOP_2_W): _number(0, 15000, 100, "W"),
            vol.Required(OPT_START_3_W): _number(0, 20000, 100, "W"),
            vol.Required(OPT_STOP_3_W): _number(0, 20000, 100, "W"),
            vol.Required(OPT_METER_MAX_AGE_SECONDS): _number(30, 900, 10, "s"),
            vol.Required(OPT_PHYSICAL_METER_MAX_AGE_SECONDS): _number(30, 900, 10, "s"),
            vol.Required(OPT_PHYSICAL_RECOVERY_SECONDS): _number(30, 900, 10, "s"),
        }
    )


def _required(
    key: str,
    selector_value: selector.Selector,
    defaults: Mapping[str, Any] | None,
) -> tuple[Any, selector.Selector]:
    if defaults is not None and (default := defaults.get(key)) is not None:
        return vol.Required(key, default=default), selector_value
    return vol.Required(key), selector_value


def _site_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    return vol.Schema(
        dict(
            (
                _required(CONF_SITE_GRID_POWER, SENSOR_SELECTOR, defaults),
                _required(CONF_SOLAR_POWER, SENSOR_SELECTOR, defaults),
            )
        )
    )


def _ecoflow_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    return vol.Schema(
        dict(
            (
                _required(CONF_SHP_GRID_POWER, SENSOR_SELECTOR, defaults),
                _required(CONF_SHP_HOME_POWER, SENSOR_SELECTOR, defaults),
                _required(CONF_CHARGING_POWER, NUMBER_SELECTOR, defaults),
                _required(CONF_CHARGE_LIMIT, NUMBER_SELECTOR, defaults),
            )
        )
    )


def _channels_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    items = (
        (CONF_AC1_SOC, SENSOR_SELECTOR),
        (CONF_AC1_CHANNEL, SWITCH_SELECTOR),
        (CONF_AC1_FORCE, SWITCH_SELECTOR),
        (CONF_AC2_SOC, SENSOR_SELECTOR),
        (CONF_AC2_CHANNEL, SWITCH_SELECTOR),
        (CONF_AC2_FORCE, SWITCH_SELECTOR),
        (CONF_AC3_SOC, SENSOR_SELECTOR),
        (CONF_AC3_CHANNEL, SWITCH_SELECTOR),
        (CONF_AC3_FORCE, SWITCH_SELECTOR),
    )
    return vol.Schema(dict(_required(key, value, defaults) for key, value in items))


def _full_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    merged: dict[Any, Any] = {}
    for schema in (
        _site_schema(defaults),
        _ecoflow_schema(defaults),
        _channels_schema(defaults),
    ):
        merged.update(schema.schema)
    return vol.Schema(merged)


class EcoFlowSurplusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure EcoFlow Solar Surplus Controller."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect authoritative site power entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_entity_group(
                user_input,
                (CONF_SITE_GRID_POWER, CONF_SOLAR_POWER),
                power_keys=(CONF_SITE_GRID_POWER, CONF_SOLAR_POWER),
            )
            if not errors:
                self._data.update(user_input)
                return await self.async_step_ecoflow()
        return self.async_show_form(
            step_id="user", data_schema=_site_schema(), errors=errors
        )

    async def async_step_ecoflow(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect EcoFlow panel and charging-control entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_entity_group(
                user_input,
                (
                    CONF_SHP_GRID_POWER,
                    CONF_SHP_HOME_POWER,
                    CONF_CHARGING_POWER,
                    CONF_CHARGE_LIMIT,
                ),
                power_keys=(CONF_SHP_GRID_POWER, CONF_SHP_HOME_POWER),
            )
            if not errors:
                self._data.update(user_input)
                return await self.async_step_channels()
        return self.async_show_form(
            step_id="ecoflow", data_schema=_ecoflow_schema(), errors=errors
        )

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the three DPU SOC, channel, and Force Charge entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {**self._data, **user_input}
            errors = self._validate_entities(candidate)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                self._add_legacy_migration_entities(candidate)
                return self.async_create_entry(
                    title="EcoFlow Solar Surplus",
                    data=candidate,
                    options=dict(DEFAULT_OPTIONS),
                )
        return self.async_show_form(
            step_id="channels", data_schema=_channels_schema(), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow entity mappings to be changed without reinstalling."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_entities(user_input)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_mismatch()
                replacement = dict(user_input)
                self._add_legacy_migration_entities(replacement)
                return self.async_update_reload_and_abort(
                    entry,
                    data=replacement,
                    reload_even_if_entry_is_unchanged=False,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_full_schema(entry.data),
            errors=errors,
        )

    def _validate_entity_group(
        self,
        data: Mapping[str, Any],
        required: tuple[str, ...],
        *,
        power_keys: tuple[str, ...] = (),
    ) -> dict[str, str]:
        if any(self.hass.states.get(data[key]) is None for key in required):
            return {"base": "entity_not_found"}
        for key in power_keys:
            state = self.hass.states.get(data[key])
            if state is not None and not _has_power_unit(state):
                return {"base": "invalid_power_unit"}
        return {}

    def _validate_entities(self, data: Mapping[str, Any]) -> dict[str, str]:
        required = (
            CONF_SITE_GRID_POWER,
            CONF_SOLAR_POWER,
            CONF_SHP_GRID_POWER,
            CONF_SHP_HOME_POWER,
            CONF_CHARGING_POWER,
            CONF_CHARGE_LIMIT,
            CONF_AC1_SOC,
            CONF_AC2_SOC,
            CONF_AC3_SOC,
            CONF_AC1_CHANNEL,
            CONF_AC2_CHANNEL,
            CONF_AC3_CHANNEL,
            CONF_AC1_FORCE,
            CONF_AC2_FORCE,
            CONF_AC3_FORCE,
        )
        if any(
            key not in data or self.hass.states.get(data[key]) is None for key in required
        ):
            return {"base": "entity_not_found"}

        groups = (
            (CONF_AC1_SOC, CONF_AC2_SOC, CONF_AC3_SOC),
            (CONF_AC1_CHANNEL, CONF_AC2_CHANNEL, CONF_AC3_CHANNEL),
            (CONF_AC1_FORCE, CONF_AC2_FORCE, CONF_AC3_FORCE),
        )
        if any(len({data[key] for key in group}) != 3 for group in groups):
            return {"base": "duplicate_channel_entities"}

        for key in (
            CONF_SITE_GRID_POWER,
            CONF_SOLAR_POWER,
            CONF_SHP_GRID_POWER,
            CONF_SHP_HOME_POWER,
        ):
            state = self.hass.states.get(data[key])
            if state is not None and not _has_power_unit(state):
                return {"base": "invalid_power_unit"}
        return {}

    def _add_legacy_migration_entities(self, data: dict[str, Any]) -> None:
        if self.hass.states.get(LEGACY_MASK_ENTITY) is not None:
            data[CONF_LEGACY_MASK] = LEGACY_MASK_ENTITY
        if self.hass.states.get(LEGACY_RATE_ENTITY) is not None:
            data[CONF_LEGACY_RATE] = LEGACY_RATE_ENTITY

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the controller options flow."""
        return EcoFlowSurplusOptionsFlow()


class EcoFlowSurplusOptionsFlow(OptionsFlowWithReload):
    """Controller tuning options with automatic reload."""

    def __init__(self) -> None:
        self._pending: dict[str, Any] = {}

    @property
    def _current(self) -> dict[str, Any]:
        return {**DEFAULT_OPTIONS, **self.config_entry.options}

    @override
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure normal-use options."""
        if user_input is not None:
            self._pending = dict(user_input)
            return await self.async_step_advanced()
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _basic_options_schema(), self._current
            ),
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure advanced controller tuning."""
        current = self._current
        current.update(self._pending)
        if user_input is not None:
            options = {**current, **user_input}
            errors = _validate_options(options)
            if not errors:
                return self.async_create_entry(data=options)
            current = options
            return self.async_show_form(
                step_id="advanced",
                data_schema=self.add_suggested_values_to_schema(
                    _advanced_options_schema(), current
                ),
                errors=errors,
            )
        return self.async_show_form(
            step_id="advanced",
            data_schema=self.add_suggested_values_to_schema(
                _advanced_options_schema(), current
            ),
        )


def _has_power_unit(state: State) -> bool:
    unit = str(state.attributes.get("unit_of_measurement", "")).strip().lower()
    return unit in {"w", "kw"}


def _validate_options(options: Mapping[str, Any]) -> dict[str, str]:
    if float(options[OPT_MAXIMUM_RATE_W]) < float(options[OPT_MINIMUM_RATE_W]):
        return {"base": "max_rate_below_min"}
    if float(options[OPT_MODERATE_IMPORT_THRESHOLD_W]) <= float(
        options[OPT_IMPORT_HOLD_HIGH_W]
    ):
        return {"base": "moderate_threshold_too_low"}
    if float(options[OPT_SEVERE_IMPORT_THRESHOLD_W]) <= float(
        options[OPT_MODERATE_IMPORT_THRESHOLD_W]
    ):
        return {"base": "severe_threshold_too_low"}
    if not (
        float(options[OPT_STOP_2_W]) < float(options[OPT_START_2_W])
        and float(options[OPT_STOP_3_W]) < float(options[OPT_START_3_W])
    ):
        return {"base": "invalid_hysteresis"}
    return {}
