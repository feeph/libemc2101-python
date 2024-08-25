#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring

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


# pylint: disable=too-many-public-methods,protected-access
class TestEmc2101LookupTable(unittest.TestCase):

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
    # lookup table - common functionality
    # ---------------------------------------------------------------------

    def test_update_lookup_table_is_disabled(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x4A, 0b0010_0011)
        # -----------------------------------------------------------------
        computed = self.emc2101.is_lookup_table_enabled()
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_update_lookup_table_is_enabled(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x4A, 0b0000_0011)
        # -----------------------------------------------------------------
        computed = self.emc2101.is_lookup_table_enabled()
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_update_lookup_table_empty(self):
        values = {
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 0)
            self.assertEqual(bh.read_register(0x51), 0x00)
            self.assertEqual(bh.read_register(0x52), 0)
            self.assertEqual(bh.read_register(0x53), 0x00)
            self.assertEqual(bh.read_register(0x54), 0)
            self.assertEqual(bh.read_register(0x55), 0x00)
            self.assertEqual(bh.read_register(0x56), 0)
            self.assertEqual(bh.read_register(0x57), 0x00)
            self.assertEqual(bh.read_register(0x58), 0)
            self.assertEqual(bh.read_register(0x59), 0x00)
            self.assertEqual(bh.read_register(0x5A), 0)
            self.assertEqual(bh.read_register(0x5B), 0x00)
            self.assertEqual(bh.read_register(0x5C), 0)
            self.assertEqual(bh.read_register(0x5D), 0x00)
            self.assertEqual(bh.read_register(0x5E), 0)
            self.assertEqual(bh.read_register(0x5F), 0x00)

    def test_update_lookup_table_partial(self):
        # there's nothing specific decimal or hex about these values,
        # using different number systems simply to make it easier to
        # see what's coming from where
        values = {
            16: 0x03,  # temp+speed #1
            24: 0x04,  # temp+speed #2
            # the remaining 6 slots remain unused
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x03)
            self.assertEqual(bh.read_register(0x52), 24)
            self.assertEqual(bh.read_register(0x53), 0x04)
            for offset in range(4, 16):
                self.assertEqual(bh.read_register(0x50 + offset), 0x00)

    def test_update_lookup_table_full(self):
        # there's nothing specific decimal or hex about these values,
        # using different number systems simply to make it easier to
        # see what's coming from where
        values = {
            16: 0x03,  # temp+speed #1
            24: 0x04,  # temp+speed #2
            32: 0x05,  # temp+speed #3
            40: 0x06,  # temp+speed #4
            48: 0x07,  # temp+speed #5
            56: 0x08,  # temp+speed #6
            64: 0x09,  # temp+speed #7
            72: 0x0A,  # temp+speed #8
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x03)
            self.assertEqual(bh.read_register(0x52), 24)
            self.assertEqual(bh.read_register(0x53), 0x04)
            self.assertEqual(bh.read_register(0x54), 32)
            self.assertEqual(bh.read_register(0x55), 0x05)
            self.assertEqual(bh.read_register(0x56), 40)
            self.assertEqual(bh.read_register(0x57), 0x06)
            self.assertEqual(bh.read_register(0x58), 48)
            self.assertEqual(bh.read_register(0x59), 0x07)
            self.assertEqual(bh.read_register(0x5A), 56)
            self.assertEqual(bh.read_register(0x5B), 0x08)
            self.assertEqual(bh.read_register(0x5C), 64)
            self.assertEqual(bh.read_register(0x5D), 0x09)
            self.assertEqual(bh.read_register(0x5E), 72)
            self.assertEqual(bh.read_register(0x5F), 0x0A)

    def test_update_lookup_table_toomany(self):
        # there's nothing specific decimal or hex about these values,
        # using different number systems simply to make it easier to
        # see what's coming from where
        values = {
            16: 0x03,  # temp+speed #1
            24: 0x04,  # temp+speed #2
            32: 0x05,  # temp+speed #3
            40: 0x06,  # temp+speed #4
            48: 0x07,  # temp+speed #5
            56: 0x08,  # temp+speed #6
            64: 0x09,  # temp+speed #7
            72: 0x0A,  # temp+speed #8
            80: 0x0B,  # there is no slot #9
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values)

    def test_update_lookup_table_inuse(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            # allow lookup table update
            bh.write_register(0x4A, 0b0010_0000)
            # clear the table
            for offset in range(0, 16):
                bh.write_register(0x50 + offset, 0x00)
            # reenable lookup table
            bh.write_register(0x4A, 0b0000_0000)
        # there's nothing specific decimal or hex about these values,
        # using different number systems simply to make it easier to
        # see what's coming from where
        values = {
            16: 0x03,  # temp+speed #1
            24: 0x04,  # temp+speed #2
            # the remaining 6 slots remain unused
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x03)
            self.assertEqual(bh.read_register(0x52), 24)
            self.assertEqual(bh.read_register(0x53), 0x04)
            for offset in range(4, 16):
                self.assertEqual(bh.read_register(0x50 + offset), 0x00)
            self.assertEqual(bh.read_register(0x4A), 0b0000_0000)  # lut was re-enabled

    def test_update_lookup_table_too_low(self):
        values = {
            16: -65,  # min temp is -64
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values)

    def test_update_lookup_table_too_high(self):
        values = {
            16: 250,  # max temp is 126
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values)

    def test_reset_lookup(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            # initialize status register
            bh.write_register(0x02, 0x00)
            bh.write_register(0x4A, 0x20)  # allow lookup table update
            # populate lookup table with non-zero values
            for offset in range(0, 16, 2):
                temp = 20 + (offset * 4)
                speed = 3 + (offset * 1)
                bh.write_register(0x50 + offset, temp)
                bh.write_register(0x51 + offset, speed)
            # reenable lookup table
            bh.write_register(0x4A, 0x00)
        # -----------------------------------------------------------------
        self.emc2101.reset_lookup_table()
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            for offset in range(0, 16):
                self.assertEqual(bh.read_register(0x50 + offset), 0x00)
