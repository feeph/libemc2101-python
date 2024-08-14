#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import os
import unittest

# modules board and busio provide no type hints
import board  # type: ignore
import busio  # type: ignore
from feeph.i2c import EmulatedI2C

import feeph.emc2101.calibration as sut  # sytem under test
import feeph.emc2101.core

if os.environ.get('TEST_EMC2101_CHIP', 'n') == 'y':
    HAS_HARDWARE = True
else:
    HAS_HARDWARE = False


# pylint: disable=protected-access
class TestCalibration(unittest.TestCase):

    def setUp(self):
        self.i2c_adr = 0x4C
        if HAS_HARDWARE:
            self.i2c_bus = busio.I2C(scl=board.SCL, sda=board.SDA)
        else:
            # initialize read/write registers
            registers = feeph.emc2101.core.DEFAULTS.copy()
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

    # def tearDown(self):
    #     # restore original state after each run
    #     # (hardware is not stateless)
    #     self.emc2101.reset_device_registers()

    def test_unresponsive_device(self):
        # -----------------------------------------------------------------
        computed = sut.calibrate_pwm_fan(i2c_bus=self.i2c_bus, model="fan")
        expected = None
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_insufficient_steps(self):
        # -----------------------------------------------------------------
        computed = sut.calibrate_pwm_fan(i2c_bus=self.i2c_bus, model="fan", pwm_frequency=180000)
        expected = None
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_fixed_speed_fan(self):
        self.i2c_bus._state[self.i2c_adr][0x46] = 0b0000_0000
        self.i2c_bus._state[self.i2c_adr][0x47] = 0x12
        # -----------------------------------------------------------------
        computed = sut.calibrate_pwm_fan(i2c_bus=self.i2c_bus, model="fan")
        expected = None
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
