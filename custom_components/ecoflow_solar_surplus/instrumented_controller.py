from __future__ import annotations

from time import perf_counter
from typing import Any

from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from .cadence import grid_evaluation_delay_seconds
from .controller import EcoFlowSurplusController, TelemetrySnapshot
from .metrics import ControllerMetrics


class InstrumentedEcoFlowSurplusController(EcoFlowSurplusController):
    """Controller with session-scoped performance instrumentation."""

    def __init__(self, hass, entry) -> None:
        super().__init__(hass, entry)
        self.metrics = ControllerMetrics()
        self._metrics_last_site_grid_source: str | None = None
        self._metrics_last_solar_source: str | None = None
        self._grid_delay_due_monotonic: float | None = None
        self._reconcile_requested = False

    @callback
    def _on_envoy_mqtt(self, message: ReceiveMessage) -> None:
        self.metrics.mqtt_messages_received += 1
        before_error = self._mqtt_payload_error
        before_grid_at = self._realtime_grid_at
        before_solar_at = self._realtime_solar_at
        super()._on_envoy_mqtt(message)
        if (
            self._realtime_grid_at != before_grid_at
            or self._realtime_solar_at != before_solar_at
        ):
            self.metrics.mqtt_messages_valid += 1
        elif self._mqtt_payload_error and self._mqtt_payload_error != before_error:
            self.metrics.mqtt_payload_errors += 1
        elif self._mqtt_payload_error:
            self.metrics.mqtt_payload_errors += 1

    @callback
    def _schedule_grid_evaluation(self, *, restart_window: bool = False) -> None:
        """Schedule latest-value control with normal and urgent reaction windows.

        ``restart_window`` deliberately discards any timer created while an EcoFlow
        command was still in flight. This makes the post-command decision use a full
        fresh adaptive window after the actuator is free, while still retaining the
        newest Envoy telemetry received during the command.
        """
        grid_w = self.realtime_grid_w
        delay = grid_evaluation_delay_seconds(
            grid_w,
            charging_active=self.command.mask != 0,
        )
        now = self.hass.loop.time()
        candidate_due = now + delay

        if self._grid_delay_cancel is not None:
            current_due = self._grid_delay_due_monotonic
            if (
                not restart_window
                and (current_due is None or candidate_due >= current_due - 0.001)
            ):
                self.metrics.grid_evaluations_coalesced += 1
                return
            self._grid_delay_cancel()
            self._grid_delay_cancel = None
            self._grid_delay_due_monotonic = None
            if not restart_window:
                self.metrics.grid_evaluations_accelerated += 1
        else:
            self.metrics.grid_evaluations_scheduled += 1

        @callback
        def _fire(_now) -> None:
            self._grid_delay_cancel = None
            self._grid_delay_due_monotonic = None
            self.hass.async_create_task(self.async_handle_trigger("grid"))

        self._grid_delay_due_monotonic = candidate_due
        self._grid_delay_cancel = async_call_later(self.hass, delay, _fire)

    async def async_handle_trigger(self, trigger_id: str) -> None:
        """Collapse busy-time triggers into one fresh scheduled reconciliation.

        EcoFlow service calls can take several seconds. While one command transaction is
        in flight, incoming telemetry is still accepted but no additional command is
        queued. Instead, remember that the world changed. When the transaction finishes,
        discard any timer that began while the actuator was busy and start one fresh
        adaptive grid-evaluation window. Intermediate decisions are deliberately
        discarded; the newest telemetry is retained.
        """
        if self._lock.locked():
            if trigger_id == "grid":
                self.metrics.grid_evaluations_skipped_busy += 1
            self._reconcile_requested = True
            return

        started = perf_counter()
        await super().async_handle_trigger(trigger_id)
        if trigger_id == "grid":
            elapsed_ms = (perf_counter() - started) * 1000.0
            self.metrics.grid_evaluations_completed += 1
            self.metrics.grid_evaluation_timing.record(elapsed_ms)

        if self._reconcile_requested and not self._shutdown:
            self._reconcile_requested = False
            self._schedule_grid_evaluation(restart_window=True)

    def _snapshot(self) -> TelemetrySnapshot:
        snapshot = super()._snapshot()
        self._record_source_switches(snapshot)
        return snapshot

    def _record_source_switches(self, snapshot: TelemetrySnapshot) -> None:
        grid_source = snapshot.site_grid_source
        solar_source = snapshot.solar_source

        if self._metrics_last_site_grid_source is None:
            self._metrics_last_site_grid_source = grid_source
        elif grid_source != self._metrics_last_site_grid_source:
            self.metrics.site_grid_source_switches += 1
            if grid_source == "configured_entity":
                self.metrics.site_grid_fallback_activations += 1
            self._metrics_last_site_grid_source = grid_source

        if self._metrics_last_solar_source is None:
            self._metrics_last_solar_source = solar_source
        elif solar_source != self._metrics_last_solar_source:
            self.metrics.solar_source_switches += 1
            if solar_source == "configured_entity":
                self.metrics.solar_fallback_activations += 1
            self._metrics_last_solar_source = solar_source

    async def _async_set_rate(self, rate_w: int) -> None:
        started = perf_counter()
        try:
            await super()._async_set_rate(rate_w)
        finally:
            self.metrics.record_service_call(
                "number.set_value", (perf_counter() - started) * 1000.0
            )

    async def _async_switch_mask(self, service: str, mask: int) -> None:
        started = perf_counter()
        try:
            await super()._async_switch_mask(service, mask)
        finally:
            self.metrics.record_service_call(
                f"switch.{service}", (perf_counter() - started) * 1000.0
            )

    async def _async_turn_off_all(self) -> None:
        started = perf_counter()
        try:
            await super()._async_turn_off_all()
        finally:
            self.metrics.record_service_call(
                "switch.turn_off_all", (perf_counter() - started) * 1000.0
            )

    def diagnostic_data(self) -> dict[str, Any]:
        data = super().diagnostic_data()
        data["performance"] = self.metrics.as_dict()
        return data
