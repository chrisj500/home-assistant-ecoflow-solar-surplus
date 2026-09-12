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

from logic import ControlInputs, ControllerSettings, decide  # noqa: E402


SETTINGS = ControllerSettings()


def inputs(
    *,
    grid: float,
    solar: float = 8000,
    mask: int = 0,
    rate: float = 500,
    socs: tuple[float, float, float] = (50, 40, 60),
    eligible: tuple[bool, bool, bool] = (True, True, True),
    daylight: bool = True,
    site_grid_ok: bool = True,
    solar_ok: bool = True,
    soc_ok: bool = True,
) -> ControlInputs:
    return ControlInputs(
        daylight=daylight,
        site_grid_ok=site_grid_ok,
        solar_ok=solar_ok,
        soc_ok=soc_ok,
        site_grid_w=grid,
        solar_w=solar,
        ac_socs=socs,
        eligible=eligible,
        commanded_mask=mask,
        commanded_rate_w=rate,
    )


class ControllerParityTests(unittest.TestCase):
    """Golden behavior tests for the deployed v2.3 controller."""

    def test_trace_2026_09_08_slow_import_trim(self) -> None:
        decision = decide(
            inputs(grid=805, mask=3, rate=700, socs=(59, 58, 61)), SETTINGS
        )
        self.assertAlmostEqual(decision.target_command_w, 956.0)
        self.assertEqual(decision.rate_policy, "slow_import_trim")
        self.assertEqual(decision.desired_count, 1)
        self.assertEqual(decision.desired_mask, 2)
        self.assertEqual(decision.command_rate_w, 1000)
        self.assertTrue(decision.mask_change_needed)

    def test_idle_requires_export_threshold(self) -> None:
        below = decide(inputs(grid=-149, mask=0, rate=500), SETTINGS)
        at = decide(inputs(grid=-150, mask=0, rate=500), SETTINGS)
        self.assertFalse(below.safe_to_start)
        self.assertEqual(below.desired_count, 0)
        self.assertTrue(at.safe_to_start)
        self.assertEqual(at.desired_count, 1)
        self.assertEqual(at.command_rate_w, 500)

    def test_import_hold_preserves_command(self) -> None:
        decision = decide(inputs(grid=250, mask=3, rate=1700), SETTINGS)
        self.assertEqual(decision.rate_policy, "import_hold")
        self.assertEqual(decision.target_command_w, 3400)
        self.assertEqual(decision.desired_mask, 3)
        self.assertEqual(decision.command_rate_w, 1700)
        self.assertFalse(decision.mask_change_needed)
        self.assertFalse(decision.rate_change_needed)

    def test_severe_import_can_drop_multiple_dpus_immediately(self) -> None:
        decision = decide(
            inputs(grid=6039, mask=7, rate=1700, socs=(59, 58, 61)), SETTINGS
        )
        self.assertEqual(decision.rate_policy, "emergency_import_brake")
        self.assertEqual(decision.desired_count, 1)
        self.assertEqual(decision.desired_mask, 2)
        self.assertEqual(decision.command_rate_w, 500)

    def test_export_ramp_is_capped_per_fresh_grid_sample(self) -> None:
        decision = decide(inputs(grid=-4000, mask=7, rate=1000), SETTINGS)
        self.assertEqual(decision.desired_count, 3)
        self.assertGreater(decision.ideal_rate_w, 1800)
        self.assertEqual(decision.command_rate_w, 1800)
        self.assertEqual(decision.rate_policy, "export_capture")

    def test_slow_import_decrease_is_capped(self) -> None:
        decision = decide(inputs(grid=900, mask=7, rate=2000), SETTINGS)
        self.assertEqual(decision.desired_count, 3)
        self.assertEqual(decision.command_rate_w, 1800)
        self.assertEqual(decision.rate_policy, "slow_import_trim")

    def test_moderate_import_decrease_uses_larger_cap(self) -> None:
        decision = decide(inputs(grid=1500, mask=7, rate=3000), SETTINGS)
        self.assertEqual(decision.desired_count, 3)
        self.assertEqual(decision.rate_policy, "moderate_import_brake")
        self.assertEqual(decision.command_rate_w, 2700)

    def test_same_dpu_count_retains_existing_mask(self) -> None:
        decision = decide(
            inputs(grid=100, mask=5, rate=1200, socs=(90, 10, 80)), SETTINGS
        )
        self.assertEqual(decision.desired_count, 2)
        self.assertEqual(decision.desired_mask, 5)

    def test_count_change_selects_lowest_soc_eligible_stacks(self) -> None:
        decision = decide(
            inputs(grid=-1800, mask=1, rate=1200, socs=(70, 20, 30)), SETTINGS
        )
        self.assertEqual(decision.desired_count, 2)
        self.assertEqual(decision.desired_mask, 6)
        self.assertEqual(decision.retained_mask, 0)
        self.assertEqual(decision.turn_off_mask, 1)
        self.assertEqual(decision.turn_on_mask, 6)

    def test_ineligible_stack_is_never_selected(self) -> None:
        decision = decide(
            inputs(
                grid=-1800,
                mask=1,
                rate=1200,
                socs=(70, 20, 30),
                eligible=(True, False, True),
            ),
            SETTINGS,
        )
        self.assertEqual(decision.desired_count, 2)
        self.assertEqual(decision.desired_mask, 5)

    def test_night_forces_zero_desired_count(self) -> None:
        decision = decide(inputs(grid=-5000, mask=7, rate=2000, daylight=False), SETTINGS)
        self.assertFalse(decision.control_ok)
        self.assertEqual(decision.desired_count, 0)
        self.assertEqual(decision.desired_mask, 0)
        self.assertEqual(decision.command_rate_w, 500)

    def test_stale_site_meter_forces_zero_desired_count(self) -> None:
        decision = decide(
            inputs(grid=-5000, mask=7, rate=2000, site_grid_ok=False), SETTINGS
        )
        self.assertFalse(decision.control_ok)
        self.assertEqual(decision.desired_count, 0)

    def test_low_solar_forces_zero_desired_count(self) -> None:
        decision = decide(inputs(grid=-5000, solar=149, mask=7, rate=2000), SETTINGS)
        self.assertFalse(decision.control_ok)
        self.assertEqual(decision.desired_count, 0)

    def test_controller_ceiling_applies_to_target(self) -> None:
        decision = decide(inputs(grid=-50000, mask=7, rate=3900), SETTINGS)
        self.assertEqual(decision.target_command_w, 3900 * 3)
        self.assertEqual(decision.command_rate_w, 3900)


if __name__ == "__main__":
    unittest.main()
