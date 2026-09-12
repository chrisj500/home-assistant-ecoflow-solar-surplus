from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControllerSettings:
    minimum_rate_w: float = 500
    maximum_rate_w: float = 3900
    rate_step_w: float = 100
    maximum_rate_increase_w: float = 800
    slow_import_decrease_w: float = 200
    moderate_import_decrease_w: float = 500
    preferred_import_w: float = 250
    import_hold_high_w: float = 350
    moderate_import_threshold_w: float = 1000
    severe_import_threshold_w: float = 2000
    start_export_w: float = 150
    export_gain: float = 1.0
    import_gain: float = 0.8
    minimum_solar_w: float = 150
    stop_all_w: float = 250
    start_2_w: float = 1800
    stop_2_w: float = 1100
    start_3_w: float = 3300
    stop_3_w: float = 2400


@dataclass(frozen=True, slots=True)
class ControlInputs:
    daylight: bool
    site_grid_ok: bool
    solar_ok: bool
    soc_ok: bool
    site_grid_w: float
    solar_w: float
    ac_socs: tuple[float, float, float]
    eligible: tuple[bool, bool, bool]
    commanded_mask: int
    commanded_rate_w: float


@dataclass(frozen=True, slots=True)
class ControlDecision:
    control_ok: bool
    safe_to_start: bool
    expected_command_w: float
    target_command_w: float
    desired_count: int
    desired_mask: int
    retained_mask: int
    turn_off_mask: int
    turn_on_mask: int
    ideal_rate_w: int
    command_rate_w: int
    rate_policy: str
    rate_change_needed: bool
    mask_change_needed: bool


def mask_count(mask: int) -> int:
    """Return the number of active DPU bits in a three-bit mask."""
    return sum(1 for bit in (1, 2, 4) if mask & bit)


def mask_entities(mask: int) -> tuple[int, ...]:
    """Return active bit values in deterministic AC1/AC2/AC3 order."""
    return tuple(bit for bit in (1, 2, 4) if mask & bit)


def _round_to_step(value: float, step: float) -> int:
    step = step if step > 0 else 100.0
    return int(round(value / step) * step)


def _select_mask(
    eligible: tuple[bool, bool, bool],
    socs: tuple[float, float, float],
    desired_count: int,
    commanded_mask: int,
) -> int:
    if desired_count <= 0:
        return 0

    commanded_count = mask_count(commanded_mask)
    commanded_valid = all(
        not (commanded_mask & bit) or eligible[index]
        for index, bit in enumerate((1, 2, 4))
    )
    if desired_count == commanded_count and commanded_valid:
        return commanded_mask

    candidates = [
        (socs[index], index, bit)
        for index, bit in enumerate((1, 2, 4))
        if eligible[index]
    ]
    candidates.sort(key=lambda item: (item[0], item[1]))
    return sum(bit for _, _, bit in candidates[:desired_count])


def decide(inputs: ControlInputs, settings: ControllerSettings) -> ControlDecision:
    """Port the deployed v2.3 Home Assistant automation decision logic to Python.

    This function is intentionally side-effect free so the control math can be unit-tested
    independently from Home Assistant service calls and EcoFlow cloud latency.
    """
    commanded_count = mask_count(inputs.commanded_mask)
    eligible_count = sum(1 for value in inputs.eligible if value)

    control_ok = (
        inputs.daylight
        and inputs.site_grid_ok
        and inputs.solar_ok
        and inputs.soc_ok
        and eligible_count > 0
        and inputs.solar_w >= settings.minimum_solar_w
    )
    safe_to_start = control_ok and inputs.site_grid_w <= -settings.start_export_w
    expected_command_w = commanded_count * inputs.commanded_rate_w
    in_import_hold = 0 <= inputs.site_grid_w <= settings.import_hold_high_w

    if not control_ok:
        target_command_w = 0.0
    elif in_import_hold:
        target_command_w = float(expected_command_w)
    else:
        gain = settings.export_gain if inputs.site_grid_w < 0 else settings.import_gain
        raw = expected_command_w + gain * (
            settings.preferred_import_w - inputs.site_grid_w
        )
        target_command_w = min(
            max(raw, 0.0), settings.maximum_rate_w * eligible_count
        )

    near_min = inputs.commanded_rate_w <= (
        settings.minimum_rate_w + settings.slow_import_decrease_w
    )

    if not control_ok:
        desired_count_pre = 0
    elif inputs.site_grid_w > settings.severe_import_threshold_w:
        if target_command_w < settings.stop_all_w:
            desired_count_pre = 0
        elif target_command_w < settings.start_2_w:
            desired_count_pre = 1
        elif target_command_w < settings.start_3_w:
            desired_count_pre = 2
        else:
            desired_count_pre = 3
    elif commanded_count == 0:
        desired_count_pre = 1 if safe_to_start else 0
    elif in_import_hold:
        desired_count_pre = commanded_count
    elif commanded_count == 1:
        if near_min and (
            target_command_w < settings.stop_all_w
            or inputs.site_grid_w > settings.import_hold_high_w
        ):
            desired_count_pre = 0
        elif target_command_w >= settings.start_2_w:
            desired_count_pre = 2
        else:
            desired_count_pre = 1
    elif commanded_count == 2:
        if target_command_w >= settings.start_3_w:
            desired_count_pre = 3
        elif target_command_w < settings.stop_2_w and near_min:
            desired_count_pre = 1
        else:
            desired_count_pre = 2
    else:
        if target_command_w < settings.stop_3_w and near_min:
            desired_count_pre = 2
        else:
            desired_count_pre = 3

    desired_count = min(desired_count_pre, eligible_count)
    desired_mask = _select_mask(
        inputs.eligible, inputs.ac_socs, desired_count, inputs.commanded_mask
    )
    retained_mask = inputs.commanded_mask & desired_mask
    turn_off_mask = inputs.commanded_mask & ~desired_mask & 0b111
    turn_on_mask = desired_mask & ~inputs.commanded_mask & 0b111

    if desired_count <= 0:
        ideal_rate_w = int(settings.minimum_rate_w)
    else:
        raw_rate = target_command_w / desired_count
        limited = min(
            max(raw_rate, settings.minimum_rate_w), settings.maximum_rate_w
        )
        ideal_rate_w = _round_to_step(limited, settings.rate_step_w)

    if inputs.site_grid_w > settings.severe_import_threshold_w:
        decrease_cap_w = 99999.0
    elif inputs.site_grid_w > settings.moderate_import_threshold_w:
        decrease_cap_w = settings.moderate_import_decrease_w
    else:
        decrease_cap_w = settings.slow_import_decrease_w

    if inputs.site_grid_w < 0:
        rate_policy = "export_capture"
    elif in_import_hold:
        rate_policy = "import_hold"
    elif inputs.site_grid_w > settings.severe_import_threshold_w:
        rate_policy = "emergency_import_brake"
    elif inputs.site_grid_w > settings.moderate_import_threshold_w:
        rate_policy = "moderate_import_brake"
    else:
        rate_policy = "slow_import_trim"

    if desired_count <= 0:
        command_rate_w = int(settings.minimum_rate_w)
    elif desired_count != commanded_count:
        command_rate_w = ideal_rate_w
    elif ideal_rate_w > inputs.commanded_rate_w:
        command_rate_w = int(
            min(
                ideal_rate_w,
                inputs.commanded_rate_w + settings.maximum_rate_increase_w,
            )
        )
    elif ideal_rate_w < inputs.commanded_rate_w:
        if inputs.site_grid_w > settings.severe_import_threshold_w:
            command_rate_w = ideal_rate_w
        else:
            command_rate_w = int(
                max(
                    ideal_rate_w,
                    inputs.commanded_rate_w - decrease_cap_w,
                )
            )
    else:
        command_rate_w = int(inputs.commanded_rate_w)

    rate_change_needed = (
        abs(inputs.commanded_rate_w - command_rate_w)
        >= settings.rate_step_w / 2
    )
    mask_change_needed = desired_mask != inputs.commanded_mask

    return ControlDecision(
        control_ok=control_ok,
        safe_to_start=safe_to_start,
        expected_command_w=expected_command_w,
        target_command_w=target_command_w,
        desired_count=desired_count,
        desired_mask=desired_mask,
        retained_mask=retained_mask,
        turn_off_mask=turn_off_mask,
        turn_on_mask=turn_on_mask,
        ideal_rate_w=ideal_rate_w,
        command_rate_w=command_rate_w,
        rate_policy=rate_policy,
        rate_change_needed=rate_change_needed,
        mask_change_needed=mask_change_needed,
    )
