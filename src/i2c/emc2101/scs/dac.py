#!/usr/bin/env python3
"""
"""

from i2c.emc2101.scs.base_class import SpeedControlSetter


class DAC(SpeedControlSetter):

    def __init__(self, minimum_duty_cycle: int, maximum_duty_cycle: int):
        # configure duty cycle limits
        self._duty_min = _convert_percentage2step(minimum_duty_cycle)
        self._duty_max = _convert_percentage2step(maximum_duty_cycle)
        # TODO derive mapping from fan config
        self._steps = {
            # fmt: off
            #     RPM    %
            3:  ( 409,  34),  # noqa: 201
            4:  ( 479,  40),  # noqa: 201
            5:  ( 526,  44),  # noqa: 201
            6:  ( 591,  49),  # noqa: 201
            7:  ( 629,  52),  # noqa: 201
            8:  ( 697,  58),  # noqa: 201
            9:  ( 785,  65),  # noqa: 201
            10: ( 868,  72),  # noqa: 201
            11: ( 950,  79),  # noqa: 201
            12: (1040,  87),
            13: (1113,  93),
            14: (1194, 100),
            # fmt: on
        }

    def is_valid_step(self, value: int) -> bool:
        return value in self._steps.keys()

    def get_steps(self) -> list[int]:
        """
        define available control steps and their resulting fan speeds
        """
        return list(self._steps.keys())

    def convert_percent2step(self, percent: int) -> int | None:
        """
        find the closest step for the provided value
        """
        step_cur = None
        deviation_cur = None
        for step_new, (_, percent_step) in self._steps.items():
            if percent_step == 0:
                percent_step = 1
            deviation_new = abs(1 - percent / percent_step)
            if deviation_cur is None or deviation_new < deviation_cur:
                step_cur = step_new
                deviation_cur = deviation_new
        return step_cur

    def convert_step2percent(self, step: int) -> int:
        return self._steps[step][1]

    def convert_rpm2step(self, rpm: int) -> int | None:
        """
        find the closest step for the provided value
        """
        step_cur = None
        deviation_cur = None
        for step_new, (rpm_step, _) in self._steps.items():
            if rpm_step == 0:
                rpm_step = 1
            deviation_new = abs(1 - rpm / rpm_step)
            if deviation_cur is None or deviation_new < deviation_cur:
                step_cur = step_new
                deviation_cur = deviation_new
        return step_cur

    def convert_step2rpm(self, step: int) -> int | None:
        return self._steps[step][0]


def _convert_percentage2step(value: int) -> int:
    """
    convert the provided value from percentage to the internal value
    used by EMC2101 (0% -> 0x00, 100% -> 0x3F)
    """
    # 0x3F = 63
    if 0 <= value <= 100:
        return round(value * 63 / 100)
    else:
        raise ValueError("Percentage value must be in range 0 ≤ x ≤ 100!")


def _convert_step2percentage(value: int) -> int:
    """
    convert the provided value from the internal value to percentage
    used by EMC2101 (0x00 -> 0%, 0x3F -> 100%)
    """
    # 0x3F = 63
    if 0 <= value <= 63:
        return round(value * 100 / 63)
    else:
        raise ValueError("Raw value must be in range 0 ≤ x ≤ 63!")
