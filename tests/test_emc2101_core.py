#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import os
import unittest

# modules board and busio provide no type hints
import board  # type: ignore
import busio  # type: ignore
from feeph.i2c import BurstHandler, EmulatedI2C

import feeph.emc2101.core as sut  # sytem under test

if os.environ.get('TEST_EMC2101_CHIP', 'n') == 'y':
    HAS_HARDWARE = True
else:
    HAS_HARDWARE = False


# pylint: disable=protected-access
class TestEmc2101(unittest.TestCase):

    def setUp(self):
        self.i2c_adr = 0x4C
        if HAS_HARDWARE:
            self.i2c_bus = busio.I2C(scl=board.SCL, sda=board.SDA)
        else:
            # initialize read/write registers
            registers = sut.DEFAULTS.copy()
            # add readonly registers
            registers[0x00] = 0x14  # chip temperature
            registers[0x01] = 0x1B  # external sensor temperature (high byte)
            registers[0x02] = 0x00  # status register
            registers[0x0F] = 0x00  # write only register, trigger temperature conversion
            registers[0x10] = 0xE0  # external sensor temperature (low byte)
            registers[0x46] = 0xFF  # tacho reading (low byte)
            registers[0x47] = 0xFF  # tacho reading (high byte)
            registers[0xFD] = 0x16  # product id
            registers[0xFE] = 0x5D  # manufacturer id
            registers[0xFF] = 0x02  # revision
            self.i2c_bus = EmulatedI2C(state={self.i2c_adr: registers})
        self.emc2101 = sut.Emc2101_core(i2c_bus=self.i2c_bus)
        # restore original state after each run
        # (hardware is not stateless)
        self.emc2101.reset_device_registers()

    def tearDown(self):
        # nothing to do
        pass

    # ---------------------------------------------------------------------
    # circuit-dependent settings
    # ---------------------------------------------------------------------

    def test_pin_six_as_alert(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_pin_six_as_alert()
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, "Failed to enable alert mode.")
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x03), 0b0000_0000)
            self.assertEqual(bh.read_register(0x4B), 0b0000_0000)

    @unittest.skipIf(HAS_HARDWARE, "Skipping forced failure test.")
    def test_pin_six_as_alert_failure(self):
        self.i2c_bus._lock_chance = 0
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_pin_six_as_alert()
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_pin_six_as_tacho(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_pin_six_as_tacho()
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, "Failed to enable tacho mode.")
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x03), 0b0000_0100)
            self.assertEqual(bh.read_register(0x4B), 0b0011_1111)

    @unittest.skipIf(HAS_HARDWARE, "Skipping forced failure test.")
    def test_pin_six_as_tacho_failure(self):
        self.i2c_bus._lock_chance = 0
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_pin_six_as_tacho()
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_pin_get_rpm_in_alert_mode(self):
        self.emc2101.configure_pin_six_as_alert()
        # -----------------------------------------------------------------
        computed = self.emc2101.get_rpm()
        expected = None
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_configure_dac_control(self):
        self.emc2101.configure_dac_control(15)
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            computed = bh.read_register(0x03) & 0b0001_0000
        expected = 0b0001_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        self.assertEqual(self.emc2101._step_max, 15)

    def test_configure_pwm_control(self):
        self.emc2101.configure_pwm_control(pwm_d=0x12, pwm_f=0x34, step_max=15)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertFalse(bh.read_register(0x03) & 0b0001_0000)
            self.assertEqual(bh.read_register(0x4D), 0x34)
            self.assertEqual(bh.read_register(0x4E), 0x12)

    def test_configure_spinup_behaviour(self):
        spinup_duration = sut.SpinUpDuration.TIME_0_80    # 0b...._.101
        spinup_strength = sut.SpinUpStrength.STRENGTH_50  # 0b...0_1...
        fast_mode = False                                 # 0b..0._....
        self.emc2101.configure_spinup_behaviour(spinup_strength=spinup_duration, spinup_duration=spinup_strength, fast_mode=fast_mode)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x4B), 0b00001101)

    def test_set_minimum_rpm_too_low(self):
        # due to the way EMC2101's registers are implemented the measured
        # RPM can never be lower than 82 RPM
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.configure_minimum_rpm, 80)

    def test_get_driver_strength(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_driver_strength()
        expected = 0
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_set_driver_strength(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_driver_strength(2)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x4C), 2)

    def test_set_driver_strength_oor(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_driver_strength(64)
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x4C), 0)

    def test_set_sensor_low_temperature_limit(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_sensor_low_temperature_limit, -50)

    def test_set_sensor_high_temperature_limit(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_sensor_high_temperature_limit, 150)

    @unittest.skipIf(HAS_HARDWARE, "Skipping forced failure test.")
    def test_force_external_temperature_sensor_failure(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x02, 0b0000_0100)
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_external_temperature_sensor(dif=0x12, bcf=0x34)
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    # ---------------------------------------------------------------------
    # usage errors
    # ---------------------------------------------------------------------

    def test_invalid_conversion_rate(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_temperature_conversion_rate("invalid-value")
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
