#!/usr/bin/env python3
"""
"""

import unittest

from i2c.emc2101.conversions import convert_bytes2temperature, convert_temperature2bytes

class TestConversions(unittest.TestCase):

    def test_convert_bytes2temperature(self):
        values = {
            (0x14, 0b0000_0000): 20.00,
            (0x14, 0b0010_0000): 20.15,
            (0x14, 0b0100_0000): 20.25,
            (0x14, 0b1000_0000): 20.50,
            (0x14, 0b1110_0000): 20.90,
        }
        for bytes, temperature in values.items():
            msb, lsb = bytes
            computed = convert_bytes2temperature(msb, lsb)
            expected = temperature
            # -------------------------------------------------------------
            self.assertEqual(computed, expected)

    def test_convert_temperature2bytes(self):
        values = {
            # exact conversion
            # 20.00: (0x14, 0b0000_0000),
            # 20.15: (0x14, 0b0010_0000),
            # 20.25: (0x14, 0b0100_0000),
            # 20.50: (0x14, 0b1000_0000),
            # 20.90: (0x14, 0b1110_0000),
            # approximations
            # 21.07: (0x15, 0b0000_0000),
            # 21.08: (0x15, 0b0010_0000),
            # 21.19: (0x15, 0b0010_0000),
            # 21.20: (0x15, 0b0100_0000),
            21.37: (0x15, 0b0110_0000),
            21.38: (0x15, 0b1000_0000),
            21.57: (0x15, 0b1000_0000),
            21.58: (0x15, 0b1010_0000),
            21.69: (0x15, 0b1010_0000),
            21.70: (0x15, 0b1100_0000),
            21.82: (0x15, 0b1100_0000),
            21.83: (0x15, 0b1110_0000),
            21.94: (0x15, 0b1110_0000),
            21.95: (0x16, 0b0000_0000),
        }
        for temperature, bytes in values.items():
            computed = convert_temperature2bytes(temperature)
            expected = bytes
            # -------------------------------------------------------------
            self.assertEqual(computed, expected)
