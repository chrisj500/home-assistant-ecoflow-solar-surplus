from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class TimingStats:
    """Accumulate bounded timing statistics without retaining every sample."""

    count: int = 0
    total_ms: float = 0.0
    last_ms: float = 0.0
    max_ms: float = 0.0

    def record(self, elapsed_ms: float) -> None:
        value = max(0.0, float(elapsed_ms))
        self.count += 1
        self.total_ms += value
        self.last_ms = value
        self.max_ms = max(self.max_ms, value)

    @property
    def average_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "count": self.count,
            "last_ms": round(self.last_ms, 3),
            "average_ms": round(self.average_ms, 3),
            "max_ms": round(self.max_ms, 3),
        }


@dataclass(slots=True)
class ControllerMetrics:
    """Session-scoped instrumentation for the realtime control path."""

    session_started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    mqtt_messages_received: int = 0
    mqtt_messages_valid: int = 0
    mqtt_payload_errors: int = 0
    grid_evaluations_scheduled: int = 0
    grid_evaluations_coalesced: int = 0
    grid_evaluations_completed: int = 0
    grid_evaluations_skipped_busy: int = 0
    site_grid_source_switches: int = 0
    site_grid_fallback_activations: int = 0
    solar_source_switches: int = 0
    solar_fallback_activations: int = 0
    grid_evaluation_timing: TimingStats = field(default_factory=TimingStats)
    service_calls: dict[str, TimingStats] = field(default_factory=dict)

    def record_service_call(self, kind: str, elapsed_ms: float) -> None:
        stats = self.service_calls.setdefault(str(kind), TimingStats())
        stats.record(elapsed_ms)

    def as_dict(self) -> dict[str, object]:
        return {
            "session_started_at": self.session_started_at.isoformat(),
            "mqtt": {
                "messages_received": self.mqtt_messages_received,
                "messages_valid": self.mqtt_messages_valid,
                "payload_errors": self.mqtt_payload_errors,
            },
            "grid_evaluations": {
                "scheduled": self.grid_evaluations_scheduled,
                "coalesced": self.grid_evaluations_coalesced,
                "completed": self.grid_evaluations_completed,
                "skipped_busy": self.grid_evaluations_skipped_busy,
                "timing_ms": self.grid_evaluation_timing.as_dict(),
            },
            "source_switches": {
                "site_grid": self.site_grid_source_switches,
                "site_grid_fallback_activations": self.site_grid_fallback_activations,
                "solar": self.solar_source_switches,
                "solar_fallback_activations": self.solar_fallback_activations,
            },
            "service_calls": {
                kind: stats.as_dict() for kind, stats in sorted(self.service_calls.items())
            },
        }
