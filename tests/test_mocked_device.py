#!/usr/bin/env python3
"""
"""

import unittest

import i2c.emc2101

from i2c.emc2101 import DutyCycleValue, LimitType


class SimulatedI2cBus:
    """
    simulate an I²C bus

    This simulation is useful to ensure the right values are read and written.
    It is unable to simulate device-specific behavior! (e.g. duplicated registers)
    """

    def __init__(self, state: dict[int, dict[int, dict[str, int]]]):
        """
        initialize a simulated I2C bus

        ```
        state = {
            <device>: {
              "rw": {
                  <register>: <value>,
              },
              "ro": {
                  <register>: <value>,
              }
            }
        }
        ```
        """
        self._state = state

    def _set_ro_register(self, device_address: int, device_register: int, value: int):
        self._state[device_address]["ro"][device_register] = value

    def _get_rw_register(self, device_address: int, device_register: int) -> int:
        return self._state[device_address]["rw"][device_register]

    def _set_rw_register(self, device_address: int, device_register: int, value: int):
        self._state[device_address]["rw"][device_register] = value


    def readfrom_into(self, address, buffer, *, start=0, end=None):
        raise RuntimeError("Not implemented!")

    def writeto(self, address, buffer, *, start=0, end=None):
        i2c_device_address  = address
        i2c_device_register = buffer[0]
        self._state[i2c_device_address]["rw"][i2c_device_register] = buffer[1]

    def writeto_then_readfrom(self, address: int, buffer_out: bytearray, buffer_in: bytearray, *, out_start=0, out_end=None, in_start=0, in_end=None, stop=False):
        i2c_device_address  = address
        i2c_device_register = buffer_out[0]
        if i2c_device_register in self._state[i2c_device_address]["rw"]:
            buffer_in[0] = self._state[i2c_device_address]["rw"][i2c_device_register]
        else:
            buffer_in[0] = self._state[i2c_device_address]["ro"][i2c_device_register]


class TestUsingMockedDevice(unittest.TestCase):

    def setUp(self):
        # initialize read/write registers
        rw_registers = i2c.emc2101.DEFAULTS.copy()
        rw_registers[0x0F] = 0x00  # write only register, trigger temperature conversion
        ro_registers = {
            0x02: 0x00,  # status register
            0x46: 0xFF,  # tacho reading (low byte)
            0x47: 0xFF,  # tacho reading (high byte)
        }
        # add readonly registers
        self.i2c_bus = SimulatedI2cBus(state={0x4C: {"rw": rw_registers, "ro": ro_registers}})
        # instantiate an object with a simulated I²C bus
        self.emc2101 = i2c.emc2101.Emc2101(i2c_bus=self.i2c_bus)

    def tearDown(self):
        # nothing to do
        pass

    # ---------------------------------------------------------------------

    def test_manufacturer_id(self):
        self.i2c_bus._set_ro_register(0x4C, 0xFE, 0x5D)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_manufacturer_id()
        expected = [
            0x5D,  # SMSC
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected manufacturer ID '{computed}'.")

    def test_product_id(self):
        self.i2c_bus._set_ro_register(0x4C, 0xFD, 0x16)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_product_id()
        expected = [
            0x16,  # EMC2101
            0x28,  # EMC2101R
        ]
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")

    def test_product_revision(self):
        self.i2c_bus._set_ro_register(0x4C, 0xFF, 0x02)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_product_revision()
        expected = range(0x00, 0x17)  # assuming 0..22 are valid values for revision
        # -----------------------------------------------------------------
        self.assertIn(computed, expected, f"Got unexpected product ID '{computed}'.")

    def test_chip_temperature(self):
        self.i2c_bus._set_ro_register(0x4C, 0x00, 0x14)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature()
        expected = 20
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature '{computed}'.")

    def test_chip_temperature_limit_read(self):
        self.i2c_bus._set_rw_register(0x4C, 0x05, 0x46)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature_limit()
        expected = 70
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature limit '{computed}'.")

    def test_sensor_temperature(self):
        self.i2c_bus._set_ro_register(0x4C, 0x01, 0x1B)  # external sensor temperature (decimal)
        self.i2c_bus._set_ro_register(0x4C, 0x10, 0xE0)  # external sensor temperature (fraction)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature()
        expected = 27.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature '{computed}'.")

    def test_sensor_temperature_limit_read_lower(self):
        self.i2c_bus._set_rw_register(0x4C, 0x08, 0x12)  # external sensor low limit (MSB)
        self.i2c_bus._set_rw_register(0x4C, 0x14, 0xE0)  # external sensor low limit (LSB)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature_limit(limit_type=LimitType.LOWER)
        expected = 18.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_sensor_temperature_limit_write_lower(self):
        self.emc2101.set_sensor_temperature_limit(5.95, limit_type=LimitType.LOWER)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature_limit(limit_type=LimitType.LOWER)
        expected = 5.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_sensor_temperature_limit_read_upper(self):
        self.emc2101.set_sensor_temperature_limit(84.95, limit_type=LimitType.UPPER)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature_limit(limit_type=LimitType.UPPER)
        expected = 84.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_duty_cycle_read(self):
        # TODO read from lookup table if lookup table is used
        self.i2c_bus._set_rw_register(0x4C, 0x4C, 0x20)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_dutycycle(value_type=DutyCycleValue.RAW_VALUE)
        expected = 32
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_duty_cycle_write_percent(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_dutycycle(75)  # in percent
        expected = 75                              # in percent
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        self.assertTrue(self.i2c_bus._get_rw_register(0x4C, 0x4A) & 0b0010_0000)  # manual control is enabled
        self.assertEqual(self.i2c_bus._get_rw_register(0x4C, 0x4C), 0x2F)         # 64 steps (0x00 = 0%, 0x3F = 100%)

    def test_duty_cycle_write_steps(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_dutycycle(16, value_type=DutyCycleValue.RAW_VALUE)  # steps
        expected = 16                                                                   # steps
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        self.assertTrue(self.i2c_bus._get_rw_register(0x4C, 0x4A) & 0b0010_0000)  # manual control is enabled
        self.assertEqual(self.i2c_bus._get_rw_register(0x4C, 0x4C), 0x10)         # 64 steps (0x00 = 0%, 0x3F = 100%)
