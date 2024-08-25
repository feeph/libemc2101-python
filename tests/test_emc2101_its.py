#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring

import os
import unittest
from unittest.mock import MagicMock, call

# modules board and busio provide no type hints
import board  # type: ignore
import busio  # type: ignore
from feeph.i2c import BurstHandler, EmulatedI2C

import feeph.emc2101.core
import feeph.emc2101.pwm as sut  # sytem under test

if os.environ.get('TEST_EMC2101_CHIP', 'n') == 'y':
    HAS_HARDWARE = True
else:
    HAS_HARDWARE = False


# pylint: disable=too-many-public-methods,protected-access
class TestEmc2101PWM(unittest.TestCase):

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
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.TACHO)
        steps = {
            # fmt: off
            #      %   RPM
            3:  ( 34,  409),  # noqa: E201
            4:  ( 40,  479),  # noqa: E201
            5:  ( 44,  526),  # noqa: E201
            6:  ( 49,  591),  # noqa: E201
            7:  ( 52,  629),  # noqa: E201
            8:  ( 58,  697),  # noqa: E201
            9:  ( 65,  785),  # noqa: E201
            10: ( 72,  868),  # noqa: E201
            11: ( 79,  950),  # noqa: E201
            12: ( 87, 1040),  # noqa: E201
            13: ( 93, 1113),  # noqa: E201
            14: (100, 1194),
            # fmt: on
        }
        self.fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=sut.RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps=steps)
        self.emc2101 = sut.Emc2101_PWM(i2c_bus=self.i2c_bus, device_config=device_config, fan_config=self.fan_config)
        # restore original state after each run
        # (hardware is not stateless)
        self.emc2101.reset_device_registers()

    def tearDown(self):
        # nothing to do
        pass

    # ---------------------------------------------------------------------
    # temperature conversion settings
    # ---------------------------------------------------------------------

    def test_get_temperature_conversion_rate(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x04, 0b0000_0111)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_temperature_conversion_rate()
        expected = "8"
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected temperature conversion rate '{computed}'.")

    def test_set_temperature_conversion_rate(self):
        # -----------------------------------------------------------------
        self.assertTrue(self.emc2101.set_temperature_conversion_rate("1/8"))
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x04), 0b0000_0001)

    def test_get_temperature_conversion_rates(self):
        # -----------------------------------------------------------------
        computed = sorted(self.emc2101.get_temperature_conversion_rates())
        expected = sorted(["1/16", "1/8", "1/4", "1/2", "1", "2", "4", "8", "16", "32"])
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected temperature conversion rates '{computed}'.")

    # ---------------------------------------------------------------------
    # temperature measurements
    # ---------------------------------------------------------------------

    def test_its_temperature(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_its_temperature()
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            expected = bh.read_register(0x00)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature '{computed}'.")

    # One Shot Register (0x0F)
    #   Writing to this register initiates a one shot update of the
    #   temperature data. Data is not relevant and is not stored.
    def test_force_temperature_conversion(self):
        # we use a mock since there is no other way to observe this change
        self.i2c_bus.writeto = MagicMock(name='writeto')
        # -----------------------------------------------------------------
        self.emc2101.force_temperature_conversion()
        computed = self.i2c_bus.writeto.mock_calls
        expected = [
            call(address=self.i2c_adr, buffer=bytearray([0x0F, 0x00])),
        ]
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_force_temperature(self):
        # -----------------------------------------------------------------
        self.emc2101.force_temperature(21.5)
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x0C), 22)
            self.assertEqual(bh.read_register(0x04A), 0b0110_0000)

    def test_clear_temperature(self):
        # -----------------------------------------------------------------
        self.emc2101.force_temperature(21.5)
        self.emc2101.clear_temperature()
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x0C), 0)
            self.assertEqual(bh.read_register(0x04A), 0b0010_0000)

    # ---------------------------------------------------------------------
    # temperature limits
    # ---------------------------------------------------------------------

    def test_its_temperature_limit_read(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x05, 0x46)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_its_temperature_limit()
        expected = 70
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature limit '{computed}'.")

    def test_its_temperature_limit_write(self):
        self.emc2101.set_its_temperature_limit(56)
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            computed = bh.read_register(0x05)
        expected = 56
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
