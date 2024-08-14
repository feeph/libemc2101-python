#!/usr/bin/env python3
"""
perform PWM related tests

use simulated device:
  pdm run pytest
use hardware device:
  TEST_EMC2101_CHIP=y pdm run pytest
"""

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
