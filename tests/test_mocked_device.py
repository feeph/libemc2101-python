#!/usr/bin/env python3
"""
"""

import unittest

from unittest.mock import MagicMock

import i2c.emc2101


class TestUsingPhysicalDevice(unittest.TestCase):

    def setUp(self):
        # instantiate an object with dummy inputs
        # (we will mock the I²C bus during testing)
        self.emc2101 = i2c.emc2101.Emc2101(i2c_bus=None, i2c_address=None)

    def tearDown(self):
        # nothing to do
        pass

    # ---------------------------------------------------------------------

    def test_manufacturer_id(self):
        self.emc2101._i2c_device.read_register = MagicMock(return_value=0x5D, spec=True)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_manufacturer_id()
        expected = [
            0x5D,  # SMSC
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected manufacturer ID '{computed}'.")
        self.emc2101._i2c_device.read_register.assert_called_with(0xFE)

    def test_product_id(self):
        self.emc2101._i2c_device.read_register = MagicMock(return_value=0x16, spec=True)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_product_id()
        expected = [
            0x16,  # EMC2101
            0x28,  # EMC2101R
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")
        self.emc2101._i2c_device.read_register.assert_called_with(0xFD)

    def test_product_revision(self):
        self.emc2101._i2c_device.read_register = MagicMock(return_value=0x14, spec=True)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_product_revision()
        expected = range(0x00, 0x17)  # assuming 0..22 are valid values for revision
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")
        self.emc2101._i2c_device.read_register.assert_called_with(0xFF)

    def test_chip_temperature(self):
        self.emc2101._i2c_device.read_register = MagicMock(return_value=20, spec=True)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature()
        expected = 20
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature '{computed}'.")
        self.emc2101._i2c_device.read_register.assert_called_with(0x00)

    def test_chip_temperature_limit_read(self):
        self.emc2101._i2c_device.read_register = MagicMock(return_value=70, spec=True)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature_limit()
        expected = 70
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature limit '{computed}'.")
        self.emc2101._i2c_device.read_register.assert_called_with(0x05)

    def test_duty_cycle_read(self):
        self.emc2101._i2c_device.read_register = MagicMock(return_value=80, spec=True)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_dutycycle()
        expected = 80.0
        # -----------------------------------------------------------------
        self.assertAlmostEqual(computed, expected)
        self.emc2101._i2c_device.read_register.assert_called_with(0x4C)

    def test_duty_cycle_write(self):
        self.emc2101._i2c_device.read_register = MagicMock(return_value=80, spec=True)
        self.emc2101._i2c_device.write_register = MagicMock(spec=True)
        # -----------------------------------------------------------------
        self.emc2101.set_dutycycle(80)
        # -----------------------------------------------------------------
        self.emc2101._i2c_device.write_register.assert_called_with(0x4C, 80)
