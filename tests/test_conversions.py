#!/usr/bin/env python3
"""
"""

import unittest

import i2c.emc2101


class TestDutycycleConversions(unittest.TestCase):
    """
    test the logic for converting the duty cycle raw value (0..63) to percentages (0..100%)
     - since the effective range is limited it does not make sense to pretend the duty cycle
       can be set to an exact percentage, all percentage values are rounded to nearest integer
     - unfortunately it's not possible to set duty cycle to exactly 50% due to the internal
       value's resolution (31 rounds down to 49%, 32 rounds up to 51%)
    """

    def setUp(self) -> None:
        # generate a mapping of raw values to percentages (0 -> 0%, ..., 63 -> 100%)
        self.mappings = [ (x, x * 100 / 63) for x in range(64)]

    def test_convert_percentage2raw(self):
        for raw_value, percentage in self.mappings:
            computed = i2c.emc2101._convert_dutycycle_percentage2raw(round(percentage))
            expected = raw_value
            # -------------------------------------------------------------
            self.assertIsInstance(computed, int)
            self.assertEqual(computed, expected, f"percentage {percentage} -> computed: {computed} != expected: {expected}")

    def test_convert_percentage2raw_oor(self):
        # percentage must be in range 0..100
        self.assertRaises(ValueError, i2c.emc2101._convert_dutycycle_percentage2raw, -1)
        self.assertRaises(ValueError, i2c.emc2101._convert_dutycycle_percentage2raw, 101)

    def test_convert_raw2percentage(self):
        for raw_value, percentage in self.mappings:
            computed = i2c.emc2101._convert_dutycycle_raw2percentage(raw_value)
            expected = round(percentage)
            # -------------------------------------------------------------
            self.assertIsInstance(computed, int)
            self.assertEqual(computed, expected, f"raw value: {raw_value} -> computed: {computed} != expected: {expected}")

    def test_convert_raw2percentage_oor(self):
        # raw value must be in range 0..63
        self.assertRaises(ValueError, i2c.emc2101._convert_dutycycle_raw2percentage, -1)
        self.assertRaises(ValueError, i2c.emc2101._convert_dutycycle_raw2percentage, 64)
