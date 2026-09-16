from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import Event, State, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .controller import (
    EcoFlowSurplusController as BaseEcoFlowSurplusController,
    TelemetrySnapshot,
    _fresh,
    _power_w,
)
from .grid_input import select_grid_source

REALTIME_GRID_ENTITY = "sensor.envoy_realtime_grid_power"
REALTIME_GRID_MAX_AGE_SECONDS = 5.0
REALTIME_GRID_CONTROL_INTERVAL_SECONDS = 2.0


class EcoFlowSurplusController(BaseEcoFlowSurplusController):
    """Controller that prefers the local realtime Envoy grid feed when available."""

    def __init__(self, hass, entry) -> None:
        super().__init__(hass, entry)
        self._realtime_grid_cancel = None
        self._grid_source = "configured_fallback"

    async def async_setup(self) -> None:
        await super().async_setup()
        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                [REALTIME_GRID_ENTITY],
                self._on_realtime_grid_state_change,
            )
        )

    async def async_shutdown(self) -> None:
        if self._realtime_grid_cancel is not None:
            self._realtime_grid_cancel()
            self._realtime_grid_cancel = None
        await super().async_shutdown()

    @callback
    def _on_realtime_grid_state_change(self, event: Event) -> None:
        """Coalesce the sub-second MQTT feed into a stable control cadence.

        The legacy controller uses a 2-second debounce because its configured
        meter updates slowly. A continuously updating realtime feed would keep
        resetting that debounce forever. Instead, schedule one evaluation and
        let subsequent MQTT updates replace the sampled value naturally; the
        snapshot taken at fire time always sees the newest reading.
        """
        new_state = event.data.get("new_state")
        if not isinstance(new_state, State):
            return
        if _power_w(new_state) is None:
            return
        if self._realtime_grid_cancel is not None:
            return

        @callback
        def _fire(_now: datetime) -> None:
            self._realtime_grid_cancel = None
            self.hass.async_create_task(self.async_handle_trigger("grid"))

        self._realtime_grid_cancel = async_call_later(
            self.hass, REALTIME_GRID_CONTROL_INTERVAL_SECONDS, _fire
        )

    def _snapshot(self) -> TelemetrySnapshot:
        snapshot = super()._snapshot()

        preferred_state = self.hass.states.get(REALTIME_GRID_ENTITY)
        preferred_w = _power_w(preferred_state)
        preferred_fresh = (
            preferred_w is not None
            and _fresh(preferred_state, REALTIME_GRID_MAX_AGE_SECONDS)
        )

        selection = select_grid_source(
            preferred_w=preferred_w,
            preferred_fresh=preferred_fresh,
            fallback_w=snapshot.site_grid_w if snapshot.site_grid_ok else None,
            fallback_fresh=snapshot.site_grid_ok,
        )
        snapshot.site_grid_w = selection.value_w
        snapshot.site_grid_ok = selection.ok
        self._grid_source = selection.source
        return snapshot

    def diagnostic_data(self) -> dict[str, Any]:
        data = super().diagnostic_data()
        data["grid_source"] = self._grid_source
        data["preferred_realtime_grid_entity"] = REALTIME_GRID_ENTITY
        data["preferred_realtime_grid_max_age_seconds"] = REALTIME_GRID_MAX_AGE_SECONDS
        data["realtime_grid_control_interval_seconds"] = (
            REALTIME_GRID_CONTROL_INTERVAL_SECONDS
        )
        return data
