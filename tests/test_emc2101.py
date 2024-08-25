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
        self.emc2101 = sut.Emc2101(i2c_bus=self.i2c_bus, config=sut.ConfigRegister())
        # restore original state after each run
        # (hardware is not stateless)
        self.emc2101.reset_device_registers()

    def tearDown(self):
        # nothing to do
        pass

    # ---------------------------------------------------------------------
    # hardware details
    # ---------------------------------------------------------------------

    def test_manufacturer_id(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_manufacturer_id()
        expected = [
            0x5D,  # SMSC
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected manufacturer ID '{computed}'.")

    def test_product_id(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_product_id()
        expected = [
            0x16,  # EMC2101
            0x28,  # EMC2101R
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")

    def test_product_revision(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_product_revision()
        expected = range(0x00, 0x17)  # assuming 0..22 are valid values for revision
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")

    def test_describe_product(self):
        mid = self.emc2101.get_manufacturer_id()
        pid = self.emc2101.get_product_id()
        rev = self.emc2101.get_product_revision()
        # -----------------------------------------------------------------
        computed = self.emc2101.describe_device()
        expected = f"SMSC (0x{mid:02X}) EMC2101 (0x{pid:02X}) (rev: {rev})"
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")

    # ---------------------------------------------------------------------
    # circuit-dependent settings
    # ---------------------------------------------------------------------

    def test_pin_get_rpm_in_alert_mode(self):
        # if pin 6 is used as an interrupt pin (alert mode) we can't read
        # fan speed
        self.emc2101.set_config_register(sut.ConfigRegister(alt_tach=False))
        # -----------------------------------------------------------------
        computed = self.emc2101.get_rpm()
        expected = None
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    # ---------------------------------------------------------------------
    # fan speed settings
    # ---------------------------------------------------------------------

    def test_configure_pwm_control_1(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x03, 0b0000_0000)  # pwm
            bh.write_register(0x4D, 0b0001_0111)  # default (0x17)
            bh.write_register(0x4E, 0b0000_0001)  # default (0x01)
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_pwm_control(pwm_d=0x12, pwm_f=0x34, step_max=15)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x03), 0b0000_0000)
            self.assertEqual(bh.read_register(0x4D), 0x34)
            self.assertEqual(bh.read_register(0x4E), 0x12)

    def test_configure_pwm_control_2(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x03, 0b0001_0000)  # dac
            bh.write_register(0x4D, 0b0001_0111)  # default (0x17)
            bh.write_register(0x4E, 0b0000_0001)  # default (0x01)
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_pwm_control(pwm_d=0x12, pwm_f=0x34, step_max=15)
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x03), 0b0001_0000)
            self.assertEqual(bh.read_register(0x4D), 0x17)
            self.assertEqual(bh.read_register(0x4E), 0x01)

    def test_configure_spinup_behaviour_1(self):
        spinup_duration = sut.SpinUpDuration.TIME_0_80    # 0b...._.101
        spinup_strength = sut.SpinUpStrength.STRENGTH_50  # 0b...0_1...
        fast_mode = False                                 # 0b..0._....
        self.emc2101.set_config_register(config=sut.ConfigRegister(alt_tach=True))
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_spinup_behaviour(spinup_strength=spinup_duration, spinup_duration=spinup_strength, fast_mode=fast_mode)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x4B), 0b0000_1101)

    def test_configure_spinup_behaviour_2(self):
        spinup_duration = sut.SpinUpDuration.TIME_0_80    # 0b...._.101
        spinup_strength = sut.SpinUpStrength.STRENGTH_50  # 0b...0_1...
        fast_mode = True                                  # 0b..1._....
        self.emc2101.set_config_register(config=sut.ConfigRegister(alt_tach=True))
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_spinup_behaviour(spinup_strength=spinup_duration, spinup_duration=spinup_strength, fast_mode=fast_mode)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x4B), 0b0010_1101)

    def test_configure_spinup_behaviour_3(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x03, 0b0000_0000)  # alert mode
            bh.write_register(0x4B, 0b0011_1111)  # default (0x3F)
        spinup_duration = sut.SpinUpDuration.TIME_0_80    # 0b...._.101
        spinup_strength = sut.SpinUpStrength.STRENGTH_50  # 0b...0_1...
        fast_mode = True                                  # 0b..1._....
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_spinup_behaviour(spinup_strength=spinup_duration, spinup_duration=spinup_strength, fast_mode=fast_mode)
        expected = False  # ignore request, pin 6 is configured for alert mode
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x03), 0b0000_0000)
            self.assertEqual(bh.read_register(0x4B), 0b0011_1111)

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

    def test_update_lookup_table_step_too_low(self):
        lut = {
            20: -1,
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=lut)

    def test_update_lookup_table_step_too_high(self):
        lut = {
            20: 64,
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=lut)

    def test_update_lookup_table_temp_too_low(self):
        lut = {
            -1: 40,
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=lut)

    def test_update_lookup_table_temp_too_high(self):
        lut = {
            101: 40,
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=lut)

    # ---------------------------------------------------------------------
    # convenience functions
    # ---------------------------------------------------------------------

    def test_read_fancfg_register(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.read_fancfg_register()
        expected = 0b0010_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_write_fancfg_register(self):
        self.emc2101.write_fancfg_register(0b0110_0000)
        # -----------------------------------------------------------------
        computed = self.emc2101.read_fancfg_register()
        expected = 0b0110_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_read_device_registers(self):
        # this test is sloppy and only compares if we get the right keys, it
        # does not check if the values are correct (could be random junk)
        # -----------------------------------------------------------------
        computed = self.emc2101.read_device_registers().keys()
        expected = sut.DEFAULTS.keys()
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
