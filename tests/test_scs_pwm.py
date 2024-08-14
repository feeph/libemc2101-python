#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import unittest

import feeph.emc2101.scs.pwm as sut
from feeph.emc2101.fan_configs import FanConfig, RpmControlMode


# pylint: disable=protected-access
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
        self.pwm = sut.PWM(fan_config=self.fan_config)

    # ---------------------------------------------------------------------

    def test_init_no_dutycycle(self):
        fan_config = FanConfig(model="fan", rpm_control_mode=RpmControlMode.PWM, pwm_frequency=22500, minimum_duty_cycle=None, maximum_duty_cycle=None, minimum_rpm=100, maximum_rpm=2000, steps=self.steps)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.PWM, fan_config=fan_config)

    def test_init_no_steps(self):
        fan_config = FanConfig(model="fan", rpm_control_mode=RpmControlMode.PWM, pwm_frequency=22500, minimum_duty_cycle=0, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps={})
        pwm = sut.PWM(fan_config=fan_config)
        # -----------------------------------------------------------------
        computed = pwm.get_steps()
        expected = list()
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    # ---------------------------------------------------------------------

    def test_valid_steps(self):
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
            computed = self.pwm.is_valid_step(pwm_step)
            expected = is_valid
            self.assertEqual(computed, expected)

    def test_pwm_settings(self):
        # -----------------------------------------------------------------
        computed = self.pwm.get_pwm_settings()
        expected = (1, 8)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_pwm_frequency(self):
        # -----------------------------------------------------------------
        computed = self.pwm.get_pwm_frequency()
        expected = 22500.0
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_pwm_steps(self):
        # -----------------------------------------------------------------
        computed = self.pwm.get_steps()
        expected = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_convert_percent2step(self):
        values = {
            # exact matches
            34: 3,
            40: 4,
            # approximated matches
            36: 3,
            37: 4,
        }
        for duty_cycle, pwm_step in values.items():
            computed = self.pwm.convert_percent2step(duty_cycle)
            expected = pwm_step
            self.assertEqual(computed, expected)

    def test_convert_percent2step_zero(self):
        # inject a step with a 0% duty cycle to test the special handling
        # of this value (prevent division by zero)
        self.pwm._steps[0] = (0, 400)
        # -----------------------------------------------------------------
        computed = self.pwm.convert_percent2step(1)
        expected = 0
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_convert_step2percent(self):
        values = {
            3: 34,
            4: 40,
        }
        for pwm_step, duty_cycle in values.items():
            computed = self.pwm.convert_step2percent(pwm_step)
            expected = duty_cycle
            self.assertEqual(computed, expected)

    def test_convert_rpm2step(self):
        values = {
            # exact matches
            409: 3,
            479: 4,
            # approximated matches
            440: 3,
            450: 4,
        }
        for rpm, pwm_step in values.items():
            computed = self.pwm.convert_rpm2step(rpm)
            expected = pwm_step
            self.assertEqual(computed, expected)

    def test_convert_rpm2step_zero(self):
        # inject a step with 0 RPM to test the special handling
        # of this value (prevent division by zero)
        self.pwm._steps[1] = (10, 0)
        # -----------------------------------------------------------------
        computed = self.pwm.convert_rpm2step(1)
        expected = 1
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_convert_rpm2step_unknown(self):
        # inject a step with unknown RPM to test the special handling
        # of this value
        self.pwm._steps[2] = (10, None)
        # -----------------------------------------------------------------
        computed = self.pwm.convert_rpm2step(1)
        expected = 3  # step 2 is defined but has no RPM, pick next
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_convert_step2rpm(self):
        values = {
            3: 409,
            4: 479,
        }
        for pwm_step, rpm in values.items():
            computed = self.pwm.convert_step2rpm(pwm_step)
            expected = rpm
            self.assertEqual(computed, expected)
