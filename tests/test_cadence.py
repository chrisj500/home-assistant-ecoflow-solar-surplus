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

from cadence import (  # noqa: E402
    NORMAL_GRID_EVALUATION_SECONDS,
    URGENT_GRID_EVALUATION_SECONDS,
    grid_evaluation_delay_seconds,
)


class GridCadenceTests(unittest.TestCase):
    def test_normal_import_uses_smoothed_cadence(self) -> None:
        self.assertEqual(
            grid_evaluation_delay_seconds(250.0),
            NORMAL_GRID_EVALUATION_SECONDS,
        )

    def test_missing_grid_uses_smoothed_cadence(self) -> None:
        self.assertEqual(
            grid_evaluation_delay_seconds(None),
            NORMAL_GRID_EVALUATION_SECONDS,
        )

    def test_material_export_is_urgent(self) -> None:
        self.assertEqual(
            grid_evaluation_delay_seconds(-500.0),
            URGENT_GRID_EVALUATION_SECONDS,
        )

    def test_large_import_is_urgent(self) -> None:
        self.assertEqual(
            grid_evaluation_delay_seconds(1000.0),
            URGENT_GRID_EVALUATION_SECONDS,
        )

    def test_small_export_remains_smoothed(self) -> None:
        self.assertEqual(
            grid_evaluation_delay_seconds(-150.0),
            NORMAL_GRID_EVALUATION_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
