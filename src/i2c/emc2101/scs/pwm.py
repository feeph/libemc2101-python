#!/usr/bin/env python3
"""
"""

import logging
import math

from i2c.emc2101.scs.base_class import SpeedControlSetter


LH = logging.getLogger("i2c.emc2101")


class PWM(SpeedControlSetter):

    # TODO decide what to do with this block
    # ---------------------------------------------------------------------
    # override CLK_SEL and use Frequency Divide Register (PWM_F) to determine base frequency
    # fancfg_register = self._i2c_device.read_register(0x4A)
    # self._i2c_device.write_register(0x4A, fancfg_register | 0b0000_0100)
    # ---------------------------------------------------------------------

    def __init__(self, pwm_frequency: int, minimum_duty_cycle: int, maximum_duty_cycle: int):
        # configure duty cycle limits
        self._duty_min = _convert_dutycycle_percentage2raw(minimum_duty_cycle)
        self._duty_max = _convert_dutycycle_percentage2raw(maximum_duty_cycle)
        # calculate and configure PWM_D and PWM_F settings
        (pwm_d, pwm_f) = calculate_pwm_factors(pwm_frequency=pwm_frequency)
        LH.debug("PWM frequency: %dHz -> PWM_D: %i PWM_F: %i", pwm_frequency, pwm_d, pwm_f)
        self._pwm_d = pwm_d
        self._pwm_f = pwm_f
        self._pwm_steps = pwm_f * 2
        # calculate speed mappings
        # TODO derive mapping from fan config
        self._steps = {
            #     RPM     %
            3:	( 409,	 34),
            4:	( 479,	 40),
            5:	( 526,	 44),
            6:	( 591,	 49),
            7:	( 629,	 52),
            8:	( 697,	 58),
            9:	( 785,	 65),
            10:	( 868,	 72),
            11:	( 950,	 79),
            12:	(1040,	 87),
            13:	(1113,	 93),
            14:	(1194,	100),
        }

    def is_valid_step(self, value: int) -> bool:
        return value in self._steps.keys()

    def get_pwm_settings(self):
        return (self._pwm_d, self._pwm_f)

    def get_steps(self) -> list[int]:
        """
        define available control steps and their resulting fan speeds
        """
        return list(self._steps.keys())

    def convert_percent2step(self, percent: int) -> int:
        """
        find the closest step for the provided value
        """
        step_cur = None
        deviation_cur = None
        for step_new, record in self._steps.items():
            percent_step = record[1]
            if percent_step == 0:
                percent_step = 1
            deviation_new = abs(1-percent/percent_step)
            if deviation_cur is None or deviation_new < deviation_cur:
                step_cur = step_new
                deviation_cur = deviation_new
        return step_cur

    def convert_step2percent(self, step: int) -> int:
        return self._steps[step][1]

    def convert_rpm2step(self, rpm: int) -> int:
        """
        find the closest step for the provided value
        """
        step_cur = None
        deviation_cur = None
        for step_new, record in self._steps.items():
            rpm_step = record[0]
            if rpm_step == 0:
                rpm_step = 1
            deviation_new = abs(1-rpm/rpm_step)
            if deviation_cur is None or deviation_new < deviation_cur:
                step_cur = step_new
                deviation_cur = deviation_new
        return step_cur

    def convert_step2rpm(self, step: int) -> int:
        return self._steps[step][0]


# TODO decide what to do with this block
# -------------------------------------------------------------------------
# def calculate_pwm_frequency(pwm_f: int, pwm_d: int) -> float:
#     """
#     calculate PWM frequency for provided PWM_D and PWM_F
#     """
#     pwm_frequency = 360000/(2*pwm_f*pwm_d)
#     return pwm_frequency
# -------------------------------------------------------------------------


def calculate_pwm_factors(pwm_frequency: int) -> tuple[int, int]:
    """
    calculate PWM_D and PWM_F for provided frequency
     - this function minimizes PWM_D to allow for maximum resolution (PWM_F)
     - PWM_F maxes out at 31 (0x1F)
    """
    if 0 <= pwm_frequency <= 180000:
        value1 = 360000/(2*pwm_frequency)
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
