from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .controller import EcoFlowSurplusController

HISTORY_LIMIT = 50


class EcoFlowSurplusObservability:
    """Track controller telemetry and fresh-grid decisions without changing control."""

    def __init__(
        self, hass: HomeAssistant, controller: EcoFlowSurplusController
    ) -> None:
        self.hass = hass
        self.controller = controller
        self._unsub = None
        self._history: deque[dict[str, Any]] = deque(maxlen=HISTORY_LIMIT)
        self._last_command: dict[str, Any] = {}
        self._last_decision: dict[str, Any] | None = None
        self._last_decision_snapshot: dict[str, Any] | None = None
        self._current_snapshot: dict[str, Any] | None = None
        self._last_decision_at: datetime | None = None
        self._last_seen_grid_action_at: str | None = None
        self._last_error: str | None = None
        self._refresh(record_history=False)

    def setup(self) -> None:
        """Subscribe to controller state publications."""
        self._unsub = async_dispatcher_connect(
            self.hass, self.controller.signal, self._handle_controller_update
        )

    def shutdown(self) -> None:
        """Unsubscribe from controller updates."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_controller_update(self) -> None:
        self._refresh(record_history=True)

    def _refresh(self, *, record_history: bool) -> None:
        data = self.controller.diagnostic_data()
        snapshot = data.get("snapshot")
        decision = data.get("decision")
        command = data.get("command")

        self._current_snapshot = dict(snapshot) if isinstance(snapshot, dict) else None
        self._last_decision = dict(decision) if isinstance(decision, dict) else None
        self._last_error = data.get("last_error")
        current_command = dict(command) if isinstance(command, dict) else {}

        action_at = data.get("last_action_at")
        is_new_grid_decision = bool(
            record_history
            and data.get("last_trigger") == "grid"
            and isinstance(decision, dict)
            and isinstance(snapshot, dict)
            and isinstance(action_at, str)
            and action_at != self._last_seen_grid_action_at
        )

        if is_new_grid_decision:
            self._last_seen_grid_action_at = action_at
            self._last_decision_snapshot = dict(snapshot)
            try:
                self._last_decision_at = datetime.fromisoformat(action_at)
            except ValueError:
                self._last_decision_at = None

            self._history.append(
                {
                    "timestamp": action_at,
                    "site_grid_w": snapshot.get("site_grid_w"),
                    "solar_w": snapshot.get("solar_w"),
                    "physical_charge_w": snapshot.get("physical_charge_w"),
                    "ac_socs": list(snapshot.get("ac_socs", ())),
                    "charge_limit": snapshot.get("charge_limit"),
                    "eligible": list(snapshot.get("eligible", ())),
                    "command_before": dict(self._last_command),
                    "decision": dict(decision),
                    "command_after": dict(current_command),
                    "action": data.get("last_action"),
                }
            )

        self._last_command = current_command

    @property
    def last_decision_at(self) -> datetime | None:
        """Return when the most recent fresh-grid decision completed."""
        return self._last_decision_at

    @property
    def decision_site_grid_w(self) -> float | None:
        snapshot = self._last_decision_snapshot
        if not snapshot or not snapshot.get("site_grid_ok"):
            return None
        return float(snapshot["site_grid_w"])

    @property
    def decision_solar_w(self) -> float | None:
        snapshot = self._last_decision_snapshot
        if not snapshot or not snapshot.get("solar_ok"):
            return None
        return float(snapshot["solar_w"])

    @property
    def physical_charge_w(self) -> float | None:
        snapshot = self._current_snapshot
        if not snapshot or not snapshot.get("shp_power_ok"):
            return None
        return float(snapshot["physical_charge_w"])

    @property
    def target_charge_w(self) -> float | None:
        if self._last_decision is None:
            return None
        value = self._last_decision.get("target_command_w")
        return None if value is None else float(value)

    @property
    def desired_mask(self) -> int | None:
        if self._last_decision is None:
            return None
        value = self._last_decision.get("desired_mask")
        return None if value is None else int(value)

    @property
    def decision_policy(self) -> str | None:
        if self._last_decision is None:
            return None
        value = self._last_decision.get("rate_policy")
        return None if value is None else str(value)

    @property
    def charge_power_difference_w(self) -> float | None:
        physical = self.physical_charge_w
        if physical is None:
            return None
        expected = self.controller.command.mask.bit_count() * self.controller.command.rate_w
        return physical - float(expected)

    @property
    def last_error(self) -> str:
        """Return a bounded state-friendly error string."""
        return "none" if not self._last_error else str(self._last_error)[:250]

    @property
    def controller_healthy(self) -> bool:
        """Return whether required telemetry is fresh and no controller error exists."""
        snapshot = self._current_snapshot
        return bool(
            snapshot
            and not self._last_error
            and snapshot.get("site_grid_ok")
            and snapshot.get("solar_ok")
            and snapshot.get("shp_power_ok")
            and snapshot.get("soc_ok")
        )

    def diagnostic_data(self) -> dict[str, Any]:
        """Return derived observability data and the rolling decision history."""
        return {
            "history_limit": HISTORY_LIMIT,
            "history_count": len(self._history),
            "last_decision_at": (
                self._last_decision_at.isoformat() if self._last_decision_at else None
            ),
            "controller_healthy": self.controller_healthy,
            "charge_power_difference_w": self.charge_power_difference_w,
            "last_decision_snapshot": self._last_decision_snapshot,
            "decision_history": list(self._history),
        }
