#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import unittest

import feeph.emc2101.scs.dac as sut


# pylint: disable=protected-access
class TestScsDac(unittest.TestCase):

    def setUp(self):
        self.dac = sut.DAC(minimum_duty_cycle=5, maximum_duty_cycle=90)

    # ---------------------------------------------------------------------

    def test_init_dutycycle_too_small(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.DAC, minimum_duty_cycle=-1, maximum_duty_cycle=100)

    def test_init_dutycycle_too_high(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.DAC, minimum_duty_cycle=0, maximum_duty_cycle=101)

    # ---------------------------------------------------------------------

    def test_is_valid_step(self):
        # -----------------------------------------------------------------
        computed = self.dac.is_valid_step(3)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_is_valid_step_oor(self):
        # -----------------------------------------------------------------
        computed = self.dac.is_valid_step(-1)
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

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
        for dac_step, is_valid in values.items():
            computed = self.dac.is_valid_step(dac_step)
            expected = is_valid
            self.assertEqual(computed, expected)

    def test_dac_steps(self):
        # -----------------------------------------------------------------
        computed = self.dac.get_steps()
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
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        for duty_cycle, dac_step in values.items():
            computed = self.dac.convert_percent2step(duty_cycle)
            expected = dac_step
            self.assertEqual(computed, expected)

            # 0:  ( 0,   0),  # noqa: 201
            # 1:  (22, 299),  # noqa: 201
            # 2:  (28, 349),  # noqa: 201

    def test_convert_percent2step_zero(self):
        # inject a step with a 0% duty cycle to test the special handling
        # of this value (prevent division by zero)
        self.dac._steps[1] = (0, 400)
        # -----------------------------------------------------------------
        computed = self.dac.convert_percent2step(1)
        expected = 1
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_convert_step2percent(self):
        values = {
            3: 34,
            4: 40,
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        for dac_step, duty_cycle in values.items():
            computed = self.dac.convert_step2percent(dac_step)
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
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        for rpm, dac_step in values.items():
            computed = self.dac.convert_rpm2step(rpm)
            expected = dac_step
            self.assertEqual(computed, expected)

    def test_convert_rpm2step_zero(self):
        # inject a step with 0 RPM to test the special handling
        # of this value (prevent division by zero)
        self.dac._steps[1] = (10, 0)
        # -----------------------------------------------------------------
        computed = self.dac.convert_rpm2step(1)
        expected = 1
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_convert_step2rpm(self):
        values = {
            3: 409,
            4: 479,
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        for dac_step, rpm in values.items():
            computed = self.dac.convert_step2rpm(dac_step)
            expected = rpm
            self.assertEqual(computed, expected)
