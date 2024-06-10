#!/usr/bin/env python3
"""
"""

import logging
import math

from i2c.emc2101.fan_configs import FanConfig
from i2c.emc2101.scs.base_class import SpeedControlSetter

LH = logging.getLogger("i2c.emc2101")


class PWM(SpeedControlSetter):

    # TODO decide what to do with this block
    # ---------------------------------------------------------------------
    # override CLK_SEL and use Frequency Divide Register (PWM_F) to determine base frequency
    # fancfg_register = self._i2c_device.read_register(0x4A)
    # self._i2c_device.write_register(0x4A, fancfg_register | 0b0000_0100)
    # ---------------------------------------------------------------------

    def __init__(self, fan_config: FanConfig):
        # configure duty cycle limits
        self._duty_min = _convert_dutycycle_percentage2raw(fan_config.minimum_duty_cycle)
        self._duty_max = _convert_dutycycle_percentage2raw(fan_config.maximum_duty_cycle)
        # calculate and configure PWM_D and PWM_F settings
        (pwm_d, pwm_f) = calculate_pwm_factors(pwm_frequency=fan_config.pwm_frequency)
        LH.debug("PWM frequency: %dHz -> PWM_D: %i PWM_F: %i", fan_config.pwm_frequency, pwm_d, pwm_f)
        self._pwm_d = pwm_d
        self._pwm_f = pwm_f
        if fan_config.steps is not None:
            self._steps = fan_config.steps
        else:
            self._steps = {}
            max_step = (pwm_f * 2) - 1
            for step in range(pwm_f * 2):
                dutycycle = int(step * 100 / max_step)
                self._steps[step] = (dutycycle, None)

    def is_valid_step(self, value: int) -> bool:
        return value in self._steps.keys()

    def get_pwm_settings(self):
        return (self._pwm_d, self._pwm_f)

    def get_pwm_frequency(self):
        return calculate_pwm_frequency(pwm_d=self._pwm_d, pwm_f=self._pwm_f)

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
        for step_new, record in self._steps.items():
            percent_step = record[0]
            if percent_step == 0:
                percent_step = 1
            deviation_new = abs(1 - percent / percent_step)
            if deviation_cur is None or deviation_new < deviation_cur:
                step_cur = step_new
                deviation_cur = deviation_new
        return step_cur

    def convert_step2percent(self, step: int) -> int:
        return self._steps[step][0]

    def convert_rpm2step(self, rpm: int) -> int | None:
        """
        find the closest step for the provided value
        """
        step_cur = None
        deviation_cur = None
        for step_new, record in self._steps.items():
            rpm_step = record[1]
            if rpm_step is not None:
                if rpm_step == 0:
                    rpm_step = 1
                deviation_new = abs(1 - rpm / rpm_step)
                if deviation_cur is None or deviation_new < deviation_cur:
                    step_cur = step_new
                    deviation_cur = deviation_new
        return step_cur

    def convert_step2rpm(self, step: int) -> int:
        return self._steps[step][1]


def calculate_pwm_frequency(pwm_d: int, pwm_f: int) -> float:
    """
    calculate PWM frequency for provided PWM_D and PWM_F
    """
    pwm_frequency = 360000 / (2 * pwm_f * pwm_d)
    return pwm_frequency


def calculate_pwm_factors(pwm_frequency: int) -> tuple[int, int]:
    """
    calculate PWM_D and PWM_F for provided frequency
     - this function minimizes PWM_D to allow for maximum resolution (PWM_F)
     - PWM_F maxes out at 31 (0x1F)
    """
    if 0 <= pwm_frequency <= 180000:
        value1 = 360000 / (2 * pwm_frequency)
        pwm_d = math.ceil(value1 / 31)
        pwm_f = round(value1 / pwm_d)
        return (pwm_d, pwm_f)
    else:
        raise ValueError("provided frequency is out of range")


def _convert_dutycycle_percentage2raw(value: int) -> int:
    """
    convert the provided value from percentage to the internal value
    used by EMC2101 (0% -> 0x00, 100% -> 0x3F)
    """
    # 0x3F = 63
    if 0 <= value <= 100:
        return round(value * 63 / 100)
    else:
        raise ValueError("Percentage value must be in range 0 ≤ x ≤ 100!")


# TODO decide what to do with this block
# -------------------------------------------------------------------------
# def _convert_dutycycle_raw2percentage(value: int) -> int:
#     """
#     convert the provided value from the internal value to percentage
#     used by EMC2101 (0x00 -> 0%, 0x3F -> 100%)
#     """
#     # 0x3F = 63
#     if 0 <= value <= 63:
#         return round(value * 100 / 63)
#     else:
#         raise ValueError("Raw value must be in range 0 ≤ x ≤ 63!")
# -------------------------------------------------------------------------
