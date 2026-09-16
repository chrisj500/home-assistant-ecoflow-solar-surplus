from __future__ import annotations

from pathlib import Path
import sys
import unittest

COMPONENT_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ecoflow_solar_surplus"
)
sys.path.insert(0, str(COMPONENT_DIR))

from metrics import ControllerMetrics, TimingStats  # noqa: E402


class TimingStatsTests(unittest.TestCase):
    def test_timing_stats_accumulate(self) -> None:
        stats = TimingStats()
        stats.record(10.0)
        stats.record(30.0)
        self.assertEqual(stats.count, 2)
        self.assertEqual(stats.last_ms, 30.0)
        self.assertEqual(stats.max_ms, 30.0)
        self.assertEqual(stats.average_ms, 20.0)


class ControllerMetricsTests(unittest.TestCase):
    def test_service_calls_are_grouped_by_kind(self) -> None:
        metrics = ControllerMetrics()
        metrics.record_service_call("number.set_value", 25.0)
        metrics.record_service_call("number.set_value", 35.0)
        metrics.record_service_call("switch.turn_on", 50.0)

        data = metrics.as_dict()
        rate = data["service_calls"]["number.set_value"]
        turn_on = data["service_calls"]["switch.turn_on"]
        self.assertEqual(rate["count"], 2)
        self.assertEqual(rate["average_ms"], 30.0)
        self.assertEqual(turn_on["count"], 1)
        self.assertEqual(turn_on["max_ms"], 50.0)

    def test_grid_and_mqtt_counters_are_exported(self) -> None:
        metrics = ControllerMetrics()
        metrics.mqtt_messages_received = 12
        metrics.mqtt_messages_valid = 11
        metrics.mqtt_payload_errors = 1
        metrics.grid_evaluations_scheduled = 8
        metrics.grid_evaluations_coalesced = 4
        metrics.grid_evaluations_completed = 7
        metrics.grid_evaluations_skipped_busy = 1

        data = metrics.as_dict()
        self.assertEqual(data["mqtt"]["messages_received"], 12)
        self.assertEqual(data["mqtt"]["messages_valid"], 11)
        self.assertEqual(data["mqtt"]["payload_errors"], 1)
        self.assertEqual(data["grid_evaluations"]["scheduled"], 8)
        self.assertEqual(data["grid_evaluations"]["coalesced"], 4)
        self.assertEqual(data["grid_evaluations"]["completed"], 7)
        self.assertEqual(data["grid_evaluations"]["skipped_busy"], 1)


if __name__ == "__main__":
    unittest.main()
