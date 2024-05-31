#!/usr/bin/env python3
"""
"""

import os
import unittest

#import adafruit_emc2101
import board
import busio
import i2c.emc2101

from i2c.emc2101 import DeviceConfig, PinSixMode, RpmControlMode, generic_pwm_fan
from i2c.emc2101.fan_configs import generic_pwm_fan

@unittest.skipUnless(os.environ.get('TEST_EMC2101_CHIP', 'n') == 'y', "Skipping physical device test.")
class TestUsingPhysicalDevice(unittest.TestCase):

    def setUp(self):
        i2c_scl_pin = os.environ.get('I2C_SCL_PIN', board.SCL)
        i2c_sda_pin = os.environ.get('I2C_SDA_PIN', board.SDA)
        i2c_bus = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin)
        device_config = DeviceConfig(rpm_control_mode=RpmControlMode.PWM, pin_six_mode=PinSixMode.TACHO, ideality_factor=0x12, beta_factor=0x08)
        self.emc2101 = i2c.emc2101.Emc2101(i2c_bus=i2c_bus, device_config=device_config, fan_config=generic_pwm_fan)

    def tearDown(self):
        # nothing to do
        pass

    # ---------------------------------------------------------------------

    def test_manufacturer_id(self):
        computed = self.emc2101.get_manufacturer_id()
        expected = [
            0x5D,  # SMSC
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected manufacturer ID '{computed}'.")

    def test_product_id(self):
        computed = self.emc2101.get_product_id()
        expected = [
            0x16,  # EMC2101
            0x28,  # EMC2101R
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")

    def test_product_revision(self):
        computed = self.emc2101.get_product_revision()
        expected = range(0x00, 0x17)  # assuming 0..22 are valid values for revision
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")

    def test_chip_temperature(self):
        computed = self.emc2101.get_chip_temperature()
        # -----------------------------------------------------------------
        self.assertGreaterEqual(computed, 0, f"Chip temperature is less than 0°C?! {computed}")
        self.assertLessEqual(computed, 100.0, f"Chip temperature is higher than 100°C?! {computed}")

    def test_chip_temperature_limit_read(self):
        computed = self.emc2101.get_chip_temperature_limit()
        # -----------------------------------------------------------------
        self.assertGreaterEqual(computed, 0, f"Chip temperature limit is less than 0°C?! {computed}")
        self.assertLessEqual(computed, 100.0, f"Chip temperature limit is higher than 100°C?! {computed}")

    def test_current_rpm(self):
        computed = self.emc2101.get_rpm()
        # -----------------------------------------------------------------
        self.assertGreaterEqual(computed, 0, f"Current fan speed is less than 0 RPM?! {computed}")
        self.assertLessEqual(computed, 50000.0, f"Current fan speed is higher than 50000 RPM?! {computed}")  # too high (even for Delta fans)

    def test_duty_cycle(self):
        self.emc2101.set_dutycycle(100)  # in percent
        # -----------------------------------------------------------------
        computed = self.emc2101.get_dutycycle()
        expected = 100
        # -----------------------------------------------------------------
        self.assertGreaterEqual(computed, 0.0, f"Duty cycle is less than zero percent?! {computed}")
        self.assertLessEqual(computed, 100.0, f"Duty cycle is higher than hundred percent?! {computed}")
        self.assertAlmostEqual(computed, expected)