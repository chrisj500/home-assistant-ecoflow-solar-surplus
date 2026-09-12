from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_sunrise,
    async_track_sunset,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store

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
    CONF_SHP_GRID_POWER,
    CONF_SHP_HOME_POWER,
    CONF_SITE_GRID_POWER,
    CONF_SOLAR_POWER,
    DEFAULT_OPTIONS,
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
    SIGNAL_UPDATE,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .logic import ControlDecision, ControlInputs, ControllerSettings, decide, mask_count

_LOGGER = logging.getLogger(__name__)
INVALID_STATES = {"unknown", "unavailable", "none", ""}


@dataclass(slots=True)
class CommandState:
    mask: int
    rate_w: int
    owned: bool = False


@dataclass(slots=True)
class TelemetrySnapshot:
    daylight: bool
    site_grid_ok: bool
    solar_ok: bool
    shp_power_ok: bool
    soc_ok: bool
    site_grid_w: float
    solar_w: float
    shp_grid_w: float
    shp_home_w: float
    physical_charge_w: float
    ac_socs: tuple[float, float, float]
    charge_limit: float
    eligible: tuple[bool, bool, bool]

    @property
    def eligible_count(self) -> int:
        return sum(1 for value in self.eligible if value)


class EcoFlowSurplusController:
    """Event-driven EcoFlow solar-surplus controller."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )
        self.command = CommandState(mask=0, rate_w=500, owned=False)
        self._lock = asyncio.Lock()
        self._unsubs: list[Callable[[], None]] = []
        self._grid_delay_cancel: Callable[[], None] | None = None
        self._physical_recovery_cancel: Callable[[], None] | None = None
        self._last_decision: ControlDecision | None = None
        self._last_snapshot: TelemetrySnapshot | None = None
        self._last_trigger = "startup"
        self._last_action = "initialized"
        self._last_error: str | None = None
        self._last_action_at: datetime | None = None

    @property
    def signal(self) -> str:
        return SIGNAL_UPDATE.format(self.entry.entry_id)

    @property
    def operating_mode(self) -> str:
        return str(self.entry.options.get(OPT_OPERATING_MODE, MODE_OBSERVE))

    @property
    def is_control_mode(self) -> bool:
        return self.operating_mode == MODE_CONTROL

    def _option_float(self, key: str) -> float:
        return float(self.entry.options.get(key, DEFAULT_OPTIONS[key]))

    def _effective_settings(self) -> ControllerSettings:
        configured_min = self._option_float(OPT_MINIMUM_RATE_W)
        configured_max = self._option_float(OPT_MAXIMUM_RATE_W)
        configured_step = self._option_float(OPT_RATE_STEP_W)

        charging_state = self.hass.states.get(self.entry.data[CONF_CHARGING_POWER])
        hardware_min = _attr_float(charging_state, "min")
        hardware_max = _attr_float(charging_state, "max")
        hardware_step = _attr_float(charging_state, "step")

        minimum = max(configured_min, hardware_min or configured_min)
        maximum = min(configured_max, hardware_max or configured_max)
        if maximum < minimum:
            maximum = minimum
        step = hardware_step if hardware_step and hardware_step > 0 else configured_step
        if step <= 0:
            step = 100.0

        return ControllerSettings(
            minimum_rate_w=minimum,
            maximum_rate_w=maximum,
            rate_step_w=step,
            maximum_rate_increase_w=self._option_float(OPT_MAXIMUM_RATE_INCREASE_W),
            slow_import_decrease_w=self._option_float(OPT_SLOW_IMPORT_DECREASE_W),
            moderate_import_decrease_w=self._option_float(OPT_MODERATE_IMPORT_DECREASE_W),
            preferred_import_w=self._option_float(OPT_PREFERRED_IMPORT_W),
            import_hold_high_w=self._option_float(OPT_IMPORT_HOLD_HIGH_W),
            moderate_import_threshold_w=self._option_float(OPT_MODERATE_IMPORT_THRESHOLD_W),
            severe_import_threshold_w=self._option_float(OPT_SEVERE_IMPORT_THRESHOLD_W),
            start_export_w=self._option_float(OPT_START_EXPORT_W),
            export_gain=self._option_float(OPT_EXPORT_GAIN),
            import_gain=self._option_float(OPT_IMPORT_GAIN),
            minimum_solar_w=self._option_float(OPT_MINIMUM_SOLAR_W),
            stop_all_w=self._option_float(OPT_STOP_ALL_W),
            start_2_w=self._option_float(OPT_START_2_W),
            stop_2_w=self._option_float(OPT_STOP_2_W),
            start_3_w=self._option_float(OPT_START_3_W),
            stop_3_w=self._option_float(OPT_STOP_3_W),
        )

    async def async_setup(self) -> None:
        await self._async_load_command_state()

        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                [self.entry.data[CONF_SITE_GRID_POWER]],
                self._on_grid_state_change,
            )
        )
        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                [
                    self.entry.data[CONF_SHP_GRID_POWER],
                    self.entry.data[CONF_SHP_HOME_POWER],
                ],
                self._on_physical_state_change,
            )
        )
        self._unsubs.append(async_track_sunrise(self.hass, self._on_sunrise))
        self._unsubs.append(async_track_sunset(self.hass, self._on_sunset))
        self._unsubs.append(
            async_track_time_change(self.hass, self._on_watchdog, second=20)
        )
        self._unsubs.append(
            async_track_time_change(self.hass, self._on_reassert_tick, second=40)
        )

        self._last_snapshot = self._snapshot()
        self._last_action = (
            "observing_without_service_calls"
            if not self.is_control_mode
            else "startup_preserved_awaiting_fresh_grid"
        )
        self._last_action_at = datetime.now(UTC)
        self._evaluate_physical_recovery_timer()
        self._notify()

    async def async_shutdown(self) -> None:
        if self._grid_delay_cancel is not None:
            self._grid_delay_cancel()
            self._grid_delay_cancel = None
        if self._physical_recovery_cancel is not None:
            self._physical_recovery_cancel()
            self._physical_recovery_cancel = None
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def _on_grid_state_change(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        if not isinstance(new_state, State):
            return
        if self._grid_delay_cancel is not None:
            self._grid_delay_cancel()
        expected_last_updated = new_state.last_updated

        @callback
        def _fire(_now: datetime) -> None:
            self._grid_delay_cancel = None
            current = self.hass.states.get(self.entry.data[CONF_SITE_GRID_POWER])
            if current is None or current.last_updated != expected_last_updated:
                return
            self.hass.async_create_task(self.async_handle_trigger("grid"))

        self._grid_delay_cancel = async_call_later(self.hass, 2, _fire)

    @callback
    def _on_physical_state_change(self, _event: Event) -> None:
        self._evaluate_physical_recovery_timer()

    @callback
    def _on_sunrise(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_handle_trigger("sunrise"))

    @callback
    def _on_sunset(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_handle_trigger("sunset"))

    @callback
    def _on_watchdog(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_handle_trigger("watchdog"))

    @callback
    def _on_reassert_tick(self, now: datetime) -> None:
        if now.minute % 5 == 0:
            self.hass.async_create_task(self.async_handle_trigger("reassert"))

    async def async_handle_trigger(self, trigger_id: str) -> None:
        """Handle one controller trigger with mode-single semantics."""
        if self._lock.locked():
            _LOGGER.debug("Skipping %s trigger because controller is busy", trigger_id)
            return

        async with self._lock:
            self._last_trigger = trigger_id
            self._last_error = None
            try:
                if self.operating_mode == MODE_OBSERVE:
                    self._sync_observed_command_state()

                snapshot = self._snapshot()
                self._last_snapshot = snapshot
                settings = self._effective_settings()
                self._normalize_command_rate(settings)

                if trigger_id == "grid":
                    await self._async_handle_grid(snapshot, settings)
                elif trigger_id == "sunset":
                    await self._async_handle_sunset(settings)
                elif trigger_id == "watchdog":
                    await self._async_handle_watchdog(snapshot, settings)
                elif trigger_id in {"reassert", "physical_recovery"}:
                    await self._async_handle_reassert(trigger_id)
                elif trigger_id == "sunrise":
                    self._record_action("sunrise_observed_no_recalculation")
                else:
                    self._record_action("trigger_ignored")
            except (HomeAssistantError, ValueError, TypeError) as err:
                self._last_error = str(err)
                self._record_action("error")
                _LOGGER.exception("EcoFlow solar surplus controller trigger failed")
            finally:
                self._evaluate_physical_recovery_timer()
                self._notify()

    async def _async_handle_grid(
        self, snapshot: TelemetrySnapshot, settings: ControllerSettings
    ) -> None:
        inputs = ControlInputs(
            daylight=snapshot.daylight,
            site_grid_ok=snapshot.site_grid_ok,
            solar_ok=snapshot.solar_ok,
            soc_ok=snapshot.soc_ok,
            site_grid_w=snapshot.site_grid_w,
            solar_w=snapshot.solar_w,
            ac_socs=snapshot.ac_socs,
            eligible=snapshot.eligible,
            commanded_mask=self.command.mask,
            commanded_rate_w=self.command.rate_w,
        )
        decision = decide(inputs, settings)
        self._last_decision = decision

        if not self.is_control_mode:
            if decision.desired_count <= 0 and self.command.mask != 0:
                action = "observe_would_stop_force_charge"
            elif decision.desired_count > 0 and decision.mask_change_needed:
                action = "observe_would_change_force_configuration"
            elif decision.desired_count > 0 and decision.rate_change_needed:
                action = "observe_would_adjust_rate"
            else:
                action = "observe_would_hold_command"
            self._record_action(action)
            return

        if decision.desired_count <= 0 and self.command.mask != 0:
            await self._async_turn_off_all()
            await self._async_set_command_state(0, int(settings.minimum_rate_w), owned=True)
            self._record_action("fresh_grid_stopped_force_charge")
            return

        if decision.desired_count > 0 and decision.mask_change_needed:
            if decision.turn_off_mask:
                await self._async_switch_mask("turn_off", decision.turn_off_mask)
                await self._async_set_command_state(
                    decision.retained_mask, self.command.rate_w, owned=True
                )

            await self._async_set_rate(decision.command_rate_w)
            await self._async_set_command_state(
                self.command.mask, decision.command_rate_w, owned=True
            )

            if decision.turn_on_mask:
                await self._async_switch_mask("turn_on", decision.turn_on_mask)

            await self._async_set_command_state(
                decision.desired_mask, decision.command_rate_w, owned=True
            )
            self._record_action("fresh_grid_changed_force_configuration")
            return

        if (
            decision.desired_count > 0
            and not decision.mask_change_needed
            and decision.rate_change_needed
        ):
            await self._async_set_rate(decision.command_rate_w)
            await self._async_set_command_state(
                self.command.mask, decision.command_rate_w, owned=True
            )
            self._record_action("fresh_grid_adjusted_rate")
            return

        self._record_action("fresh_grid_held_command")

    async def _async_handle_sunset(self, settings: ControllerSettings) -> None:
        if not self.is_control_mode:
            self._record_action(
                "observe_would_shutdown_at_sunset"
                if self.command.mask
                else "observe_sunset_idle"
            )
            return
        if self.command.mask:
            await self._async_turn_off_all()
            await self._async_set_command_state(0, int(settings.minimum_rate_w), owned=True)
        self._record_action("sunset_shutdown_complete")

    async def _async_handle_watchdog(
        self, snapshot: TelemetrySnapshot, settings: ControllerSettings
    ) -> None:
        unsafe = self.command.mask != 0 and (
            not snapshot.daylight
            or not snapshot.site_grid_ok
            or not snapshot.solar_ok
            or snapshot.solar_w < settings.minimum_solar_w
            or snapshot.eligible_count <= 0
        )
        if unsafe:
            if not self.is_control_mode:
                self._record_action("observe_watchdog_would_safety_stop")
                return
            await self._async_turn_off_all()
            await self._async_set_command_state(0, int(settings.minimum_rate_w), owned=True)
            self._record_action("watchdog_safety_stop")
            return

        recovery_floor = max(200.0, mask_count(self.command.mask) * self.command.rate_w * 0.25)
        mismatch = (
            self.command.mask != 0
            and snapshot.shp_power_ok
            and snapshot.physical_charge_w < recovery_floor
        )
        if mismatch:
            if not self.is_control_mode:
                self._record_action("observe_watchdog_would_reassert")
                return
            await self._async_reassert_existing_command()
            self._record_action("watchdog_reasserted_existing_command")
            return

        self._record_action("watchdog_healthy_no_recalculation")

    async def _async_handle_reassert(self, trigger_id: str) -> None:
        if self.command.mask <= 0:
            self._record_action(f"{trigger_id}_idle")
            return
        if not self.is_control_mode:
            self._record_action(f"observe_{trigger_id}_would_reassert")
            return
        await self._async_reassert_existing_command()
        self._record_action(f"{trigger_id}_reasserted_existing_command")

    async def _async_reassert_existing_command(self) -> None:
        await self._async_set_rate(self.command.rate_w)
        await self._async_switch_mask("turn_on", self.command.mask)
        self.command.owned = True
        await self._async_save_command_state()

    async def _async_turn_off_all(self) -> None:
        await self.hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": list(self.force_entities)},
            blocking=True,
        )

    async def _async_switch_mask(self, service: str, mask: int) -> None:
        entities = [
            entity_id
            for bit, entity_id in zip((1, 2, 4), self.force_entities, strict=True)
            if mask & bit
        ]
        if not entities:
            return
        await self.hass.services.async_call(
            "switch", service, {"entity_id": entities}, blocking=True
        )

    async def _async_set_rate(self, rate_w: int) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entry.data[CONF_CHARGING_POWER], "value": int(rate_w)},
            blocking=True,
        )

    async def _async_set_command_state(self, mask: int, rate_w: int, *, owned: bool) -> None:
        self.command = CommandState(mask=int(mask) & 0b111, rate_w=int(rate_w), owned=owned)
        await self._async_save_command_state()

    async def _async_load_command_state(self) -> None:
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            try:
                candidate = CommandState(
                    mask=int(stored.get("mask", 0)) & 0b111,
                    rate_w=int(stored.get("rate_w", 500)),
                    owned=bool(stored.get("owned", False)),
                )
            except (TypeError, ValueError):
                candidate = None
            if candidate is not None:
                self.command = candidate
                if candidate.owned:
                    return

        self._sync_observed_command_state()
        if self.is_control_mode:
            self.command.owned = False
        await self._async_save_command_state()

    def _sync_observed_command_state(self) -> None:
        """Infer the physical EcoFlow command state without issuing service calls."""
        inferred_mask = 0
        for bit, entity_id in zip((1, 2, 4), self.force_entities, strict=True):
            if self.hass.states.is_state(entity_id, "on"):
                inferred_mask |= bit
        rate = _state_float(
            self.hass.states.get(self.entry.data[CONF_CHARGING_POWER])
        )
        self.command = CommandState(
            mask=inferred_mask,
            rate_w=int(rate if rate is not None else self.command.rate_w),
            owned=False,
        )

    async def _async_save_command_state(self) -> None:
        await self._store.async_save(
            {
                "mask": self.command.mask,
                "rate_w": self.command.rate_w,
                "owned": self.command.owned,
            }
        )

    def _normalize_command_rate(self, settings: ControllerSettings) -> None:
        limited = min(max(self.command.rate_w, settings.minimum_rate_w), settings.maximum_rate_w)
        rounded = int(round(limited / settings.rate_step_w) * settings.rate_step_w)
        if rounded != self.command.rate_w:
            self.command.rate_w = rounded

    def _snapshot(self) -> TelemetrySnapshot:
        meter_age = self._option_float(OPT_METER_MAX_AGE_SECONDS)
        physical_age = self._option_float(OPT_PHYSICAL_METER_MAX_AGE_SECONDS)

        site_state = self.hass.states.get(self.entry.data[CONF_SITE_GRID_POWER])
        solar_state = self.hass.states.get(self.entry.data[CONF_SOLAR_POWER])
        shp_grid_state = self.hass.states.get(self.entry.data[CONF_SHP_GRID_POWER])
        shp_home_state = self.hass.states.get(self.entry.data[CONF_SHP_HOME_POWER])

        site_grid_w = _power_w(site_state)
        solar_w = _power_w(solar_state)
        shp_grid_w = _power_w(shp_grid_state)
        shp_home_w = _power_w(shp_home_state)

        site_grid_ok = site_grid_w is not None and _fresh(site_state, meter_age)
        solar_ok = solar_w is not None and _fresh(solar_state, meter_age)
        shp_power_ok = (
            shp_grid_w is not None
            and shp_home_w is not None
            and _fresh(shp_grid_state, physical_age)
            and _fresh(shp_home_state, physical_age)
        )

        soc_states = tuple(
            self.hass.states.get(entity_id)
            for entity_id in (
                self.entry.data[CONF_AC1_SOC],
                self.entry.data[CONF_AC2_SOC],
                self.entry.data[CONF_AC3_SOC],
            )
        )
        soc_values = tuple(_state_float(state) for state in soc_states)
        soc_ok = all(value is not None and 0 <= value <= 100 for value in soc_values)
        safe_socs = tuple(float(value if value is not None else 101) for value in soc_values)

        charge_limit_value = _state_float(
            self.hass.states.get(self.entry.data[CONF_CHARGE_LIMIT])
        )
        charge_limit = float(charge_limit_value if charge_limit_value is not None else 100)
        channel_states = tuple(
            self.hass.states.is_state(entity_id, "on") for entity_id in self.channel_entities
        )
        eligible = tuple(
            bool(channel_states[index] and soc_ok and safe_socs[index] < charge_limit)
            for index in range(3)
        )
        physical_charge_w = (
            max(0.0, float(shp_grid_w) - float(shp_home_w)) if shp_power_ok else 0.0
        )

        return TelemetrySnapshot(
            daylight=self.hass.states.is_state("sun.sun", "above_horizon"),
            site_grid_ok=site_grid_ok,
            solar_ok=solar_ok,
            shp_power_ok=shp_power_ok,
            soc_ok=soc_ok,
            site_grid_w=float(site_grid_w or 0.0),
            solar_w=float(solar_w or 0.0),
            shp_grid_w=float(shp_grid_w or 0.0),
            shp_home_w=float(shp_home_w or 0.0),
            physical_charge_w=physical_charge_w,
            ac_socs=safe_socs,
            charge_limit=charge_limit,
            eligible=eligible,
        )

    @property
    def force_entities(self) -> tuple[str, str, str]:
        return (
            self.entry.data[CONF_AC1_FORCE],
            self.entry.data[CONF_AC2_FORCE],
            self.entry.data[CONF_AC3_FORCE],
        )

    @property
    def channel_entities(self) -> tuple[str, str, str]:
        return (
            self.entry.data[CONF_AC1_CHANNEL],
            self.entry.data[CONF_AC2_CHANNEL],
            self.entry.data[CONF_AC3_CHANNEL],
        )

    def _physical_recovery_condition(self) -> bool:
        if self.command.mask <= 0:
            return False
        snapshot = self._snapshot()
        if not snapshot.shp_power_ok:
            return False
        recovery_floor = max(200.0, mask_count(self.command.mask) * self.command.rate_w * 0.25)
        return snapshot.physical_charge_w < recovery_floor

    @callback
    def _evaluate_physical_recovery_timer(self) -> None:
        should_run = self._physical_recovery_condition()
        if should_run and self._physical_recovery_cancel is None:
            delay = self._option_float(OPT_PHYSICAL_RECOVERY_SECONDS)

            @callback
            def _fire(_now: datetime) -> None:
                self._physical_recovery_cancel = None
                if self._physical_recovery_condition():
                    self.hass.async_create_task(self.async_handle_trigger("physical_recovery"))

            self._physical_recovery_cancel = async_call_later(self.hass, delay, _fire)
        elif not should_run and self._physical_recovery_cancel is not None:
            self._physical_recovery_cancel()
            self._physical_recovery_cancel = None

    def _record_action(self, action: str) -> None:
        self._last_action = action
        self._last_action_at = datetime.now(UTC)
        _LOGGER.info(
            "EcoFlow solar surplus: trigger=%s action=%s mode=%s mask=%s rate=%sW",
            self._last_trigger,
            action,
            self.operating_mode,
            self.command.mask,
            self.command.rate_w,
        )

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    @property
    def last_decision(self) -> ControlDecision | None:
        """Return the most recent fresh-grid decision, if one exists."""
        return self._last_decision

    @property
    def last_action(self) -> str:
        """Return the last controller action/status message key."""
        return self._last_action

    @property
    def control_ready(self) -> bool:
        snapshot = self._last_snapshot
        settings = self._effective_settings()
        return bool(
            snapshot
            and snapshot.daylight
            and snapshot.site_grid_ok
            and snapshot.solar_ok
            and snapshot.soc_ok
            and snapshot.eligible_count > 0
            and snapshot.solar_w >= settings.minimum_solar_w
        )

    @property
    def status(self) -> str:
        if self._last_error:
            return "error"
        if self.operating_mode == MODE_OBSERVE:
            return "observing"
        if self.command.mask > 0:
            return "charging"
        if self.control_ready:
            return "ready"
        return "idle"

    def diagnostic_data(self) -> dict[str, Any]:
        snapshot = asdict(self._last_snapshot) if self._last_snapshot else None
        decision = asdict(self._last_decision) if self._last_decision else None
        return {
            "operating_mode": self.operating_mode,
            "status": self.status,
            "control_ready": self.control_ready,
            "command": asdict(self.command),
            "last_trigger": self._last_trigger,
            "last_action": self._last_action,
            "last_action_at": self._last_action_at.isoformat() if self._last_action_at else None,
            "last_error": self._last_error,
            "snapshot": snapshot,
            "decision": decision,
            "effective_settings": asdict(self._effective_settings()),
        }


def _state_float(state: State | None) -> float | None:
    if state is None or state.state in INVALID_STATES:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _attr_float(state: State | None, attribute: str) -> float | None:
    if state is None:
        return None
    try:
        value = state.attributes.get(attribute)
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _power_w(state: State | None) -> float | None:
    value = _state_float(state)
    if value is None or state is None:
        return None
    unit = str(state.attributes.get("unit_of_measurement", "")).strip().lower()
    if unit == "kw":
        return value * 1000.0
    if unit == "w":
        return value
    return None


def _fresh(state: State | None, max_age_seconds: float) -> bool:
    if state is None:
        return False
    age = (datetime.now(UTC) - state.last_updated).total_seconds()
    return age <= max_age_seconds
