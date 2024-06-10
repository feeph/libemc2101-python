#!/usr/bin/env python3
"""
<enter description>
"""

import unittest

from i2c.emc2101.fan_configs import FanConfig, RpmControlMode
from i2c.emc2101.scs.pwm import PWM, calculate_pwm_factors


class TestScsPwm(unittest.TestCase):

    def setUp(self):
        self.steps = {
            # fmt: off
            #      %   RPM
            3:  ( 34,  409),  # noqa: E201
            4:  ( 40,  479),  # noqa: E201
            5:  ( 44,  526),  # noqa: E201
            6:  ( 49,  591),  # noqa: E201
            7:  ( 52,  629),  # noqa: E201
            8:  ( 58,  697),  # noqa: E201
            9:  ( 65,  785),  # noqa: E201
            10: ( 72,  868),  # noqa: E201
            11: ( 79,  950),  # noqa: E201
            12: ( 87, 1040),  # noqa: E201
            13: ( 93, 1113),  # noqa: E201
            14: (100, 1194),
            # fmt: on
        }
        self.fan_config = FanConfig(model="fan", rpm_control_mode=RpmControlMode.PWM, pwm_frequency=22500, minimum_duty_cycle=0, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps=self.steps)

    def test_valid_steps(self):
        pwm = PWM(fan_config=self.fan_config)
        values = {
            0x00: False,
            0x01: False,
            0x02: False,
            0x03: True,
            0x04: True,
            0x05: True,
            0x06: True,
            0x07: True,
            0x08: True,
            0x09: True,
            0x0A: True,
            0x0B: True,
            0x0C: True,
            0x0D: True,
            0x0E: True,
            0x0F: False,
        }
        for pwm_step, is_valid in values.items():
            computed = pwm.is_valid_step(pwm_step)
            expected = is_valid
            self.assertEqual(computed, expected)

    def test_pwm_steps(self):
        pwm = PWM(fan_config=self.fan_config)
        # -----------------------------------------------------------------
        computed = pwm.get_steps()
        expected = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_pwm_calculations(self):
        values = {
            45000: (1,  4),
            22500: (1,  8),
            22000: (1,  8),  # closest match is 22500
             6000: (1, 30),  # noqa: E131
             5500: (2, 16),  # noqa: E131
             1000: (6, 30),  # noqa: E131
        }
        for pwm_frequency, pwm_settings in values.items():
            computed = calculate_pwm_factors(pwm_frequency=pwm_frequency)
            expected = pwm_settings
            self.assertEqual(computed, expected)

    def test_convert_percent2step(self):
        pwm = PWM(fan_config=self.fan_config)
        values = {
            # exact matches
            34: 3,
            40: 4,
            # approximated matches
            36: 3,
            37: 4,
        }
        for duty_cycle, pwm_step in values.items():
            computed = pwm.convert_percent2step(duty_cycle)
            expected = pwm_step
            self.assertEqual(computed, expected)

    def test_convert_step2percent(self):
        pwm = PWM(fan_config=self.fan_config)
        values = {
            3: 34,
            4: 40,
        }
        for pwm_step, duty_cycle in values.items():
            computed = pwm.convert_step2percent(pwm_step)
            expected = duty_cycle
            self.assertEqual(computed, expected)

    def test_convert_rpm2step(self):
        pwm = PWM(fan_config=self.fan_config)
        values = {
            # exact matches
            409: 3,
            479: 4,
            # approximated matches
            440: 3,
            450: 4,
        }
        for rpm, pwm_step in values.items():
            computed = pwm.convert_rpm2step(rpm)
            expected = pwm_step
            self.assertEqual(computed, expected)

    def test_convert_step2rpm(self):
        pwm = PWM(fan_config=self.fan_config)
        values = {
            3: 409,
            4: 479,
        }
        for pwm_step, rpm in values.items():
            computed = pwm.convert_step2rpm(pwm_step)
            expected = rpm
            self.assertEqual(computed, expected)

# class PWM(SpeedControlSetter):
#     def get_speed_mapping(self) -> SpeedMappings:
#         """
#         define available control steps and their resulting fan speeds
#         """
#         return self._steps.copy()

# def calculate_pwm_frequency(pwm_f: int, pwm_d: int) -> float:
#     """
#     calculate PWM frequency for provided PWM_D and PWM_F
#     """
#     pwm_frequency = 360000/(2*pwm_f*pwm_d)
#     return pwm_frequency


# def calculate_pwm_factors(pwm_frequency: int) -> tuple[int, int]:
#     """
#     calculate PWM_D and PWM_F for provided frequency
#      - this function minimizes PWM_D to allow for maximum resolution (PWM_F)
#      - PWM_F maxes out at 31 (0x1F)
#     """
#     if 0 <= pwm_frequency <= 180000:
#         value1 = 360000/(2*pwm_frequency)
#         pwm_d = math.ceil(value1 / 31)
#         pwm_f = round(value1 / pwm_d)
#         return (pwm_d, pwm_f)
#     else:
#         raise ValueError("provided frequency is out of range")


# def _convert_dutycycle_percentage2raw(value: int) -> int:
#     """
#     convert the provided value from percentage to the internal value
#     used by EMC2101 (0% -> 0x00, 100% -> 0x3F)
#     """
#     # 0x3F = 63
#     if 0 <= value <= 100:
#         return round(value * 63 / 100)
#     else:
#         raise ValueError("Percentage value must be in range 0 ≤ x ≤ 100!")


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
