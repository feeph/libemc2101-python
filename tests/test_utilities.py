#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import unittest

import feeph.emc2101.utilities as sut  # sytem under test


class TestFanConfigs(unittest.TestCase):

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
            computed = sut.calculate_pwm_factors(pwm_frequency=pwm_frequency)
            expected = pwm_settings
            self.assertEqual(computed, expected)

    def test_pwm_factors_invalid(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.calculate_pwm_factors, pwm_frequency=-1)
