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

from power_source import select_power_source  # noqa: E402


class PowerSourceSelectionTests(unittest.TestCase):
    """Regression tests for primary/fallback power-source selection."""

    def test_primary_is_preferred_when_valid(self) -> None:
        selection = select_power_source(
            primary_w=-425.0,
            primary_ok=True,
            fallback_w=-500.0,
            fallback_ok=True,
            primary_source="envoy_mqtt",
            fallback_source="configured_entity",
        )
        self.assertEqual(selection.source, "envoy_mqtt")
        self.assertEqual(selection.value_w, -425.0)

    def test_fallback_is_used_when_primary_is_invalid(self) -> None:
        selection = select_power_source(
            primary_w=None,
            primary_ok=False,
            fallback_w=650.0,
            fallback_ok=True,
            primary_source="envoy_mqtt",
            fallback_source="configured_entity",
        )
        self.assertEqual(selection.source, "configured_entity")
        self.assertEqual(selection.value_w, 650.0)

    def test_fallback_is_used_when_primary_is_stale(self) -> None:
        selection = select_power_source(
            primary_w=-900.0,
            primary_ok=False,
            fallback_w=-850.0,
            fallback_ok=True,
            primary_source="envoy_mqtt",
            fallback_source="configured_entity",
        )
        self.assertEqual(selection.source, "configured_entity")
        self.assertEqual(selection.value_w, -850.0)

    def test_unavailable_when_neither_source_is_valid(self) -> None:
        selection = select_power_source(
            primary_w=None,
            primary_ok=False,
            fallback_w=None,
            fallback_ok=False,
        )
        self.assertEqual(selection.source, "unavailable")
        self.assertIsNone(selection.value_w)


if __name__ == "__main__":
    unittest.main()
