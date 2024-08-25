#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring

import math
import os
import unittest

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
    # configuration
    # ---------------------------------------------------------------------

    @unittest.skipIf(HAS_HARDWARE, "Skipping external sensor test.")
    def test_configure_ets(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x17, 0x12)
            bh.write_register(0x18, 0x08)
        ets_config = sut.ExternalTemperatureSensorConfig(ideality_factor=0x11, beta_factor=0x07)
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_ets(ets_config=ets_config)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x17), 0x11)
            self.assertEqual(bh.read_register(0x18), 0x07)

    @unittest.skipIf(HAS_HARDWARE, "Skipping forced failure test.")
    def test_configure_ets_missing(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x02, 0b0000_0100)
            bh.write_register(0x17, 0x12)
            bh.write_register(0x18, 0x08)
        ets_config = sut.ExternalTemperatureSensorConfig(ideality_factor=0x11, beta_factor=0x07)
        # -----------------------------------------------------------------
        computed = self.emc2101.configure_ets(ets_config=ets_config)
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x17), 0x12)
            self.assertEqual(bh.read_register(0x18), 0x08)

    # ---------------------------------------------------------------------
    # temperature measurements
    # ---------------------------------------------------------------------

    @unittest.skipIf(HAS_HARDWARE, "Skipping external sensor test.")
    def test_diode_present(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x02, 0b0000_0000)
            bh.write_register(0x01, 0b0000_1111)
            bh.write_register(0x10, 0b0000_0000)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_ets_state()
        expected = feeph.emc2101.core.ExternalSensorStatus.OK
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    @unittest.skipIf(HAS_HARDWARE, "Skipping external sensor test.")
    def test_diode_fault_1(self):
        """
        open circuit between DP-DN or short circuit to VDD
         - 0x02 = 0b...._.1..
         - 0x01 = 0b0111_1111
         - 0x10 = 0b0000_0000
        """
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x02, 0b0000_0100)
            bh.write_register(0x01, 0b0111_1111)
            bh.write_register(0x10, 0b0000_0000)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_ets_state()
        expected = feeph.emc2101.core.ExternalSensorStatus.FAULT1
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    @unittest.skipIf(HAS_HARDWARE, "Skipping external sensor test.")
    def test_diode_fault_2(self):
        """"
        short circuit across DP-DN or short circuit to GND
         - 0x02 = 0b...._.0..
         - 0x01 = 0b0111_1111
         - 0x10 = 0b1110_0000
        """
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x02, 0b0000_0000)
            bh.write_register(0x01, 0b0111_1111)
            bh.write_register(0x10, 0b1110_0000)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_ets_state()
        expected = feeph.emc2101.core.ExternalSensorStatus.FAULT2
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        # with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
        #     self.assertFalse(bool(bh.read_register(0x02) & 0b0000_0100))
        #     self.assertEqual(bh.read_register(0x01), 0b0111_1111)
        #     self.assertEqual(bh.read_register(0x10), 0b1110_0000)

    def test_has_ets(self):
        computed = self.emc2101.has_ets()
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            value = bh.read_register(0x01)
        if value == 0b0111_1111:
            expected = False
        else:
            expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_ets_temperature(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_ets_temperature()
        # -----------------------------------------------------------------
        if self.emc2101.has_ets():
            # absolute maximum representable range is -64°C ≤ x < 127°C
            # (nominal operating temperature range is 0°C ≤ x ≤ 85°C)
            self.assertGreaterEqual(computed, -64.0, f"Got unexpected sensor temperature '{computed}'.")
            self.assertLess(computed, 127.0, f"Got unexpected sensor temperature '{computed}'.")
        else:
            self.assertTrue(math.isnan(computed))

    @unittest.skipIf(HAS_HARDWARE, "Skipping forced failure test.")
    def test_ets_state_invalid(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x01, 0b0111_1111)
            bh.write_register(0x10, 0b1110_0100)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(RuntimeError, self.emc2101.get_ets_state)

    @unittest.skipIf(HAS_HARDWARE, "Skipping forced failure test.")
    def test_ets_temperature_invalid(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x01, 0b0111_1111)
            bh.write_register(0x10, 0b1110_0000)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_ets_temperature()
        # -----------------------------------------------------------------
        self.assertTrue(math.isnan(computed))

    # ---------------------------------------------------------------------
    # temperature limits
    # ---------------------------------------------------------------------

    def test_get_ets_low_temperature_limit(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x08, 0x12)         # external sensor low limit (decimal)
            bh.write_register(0x14, 0b1110_0000)  # external sensor low limit (fraction)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_ets_low_temperature_limit()
        expected = 18.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_set_ets_low_temperature_limit(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_ets_low_temperature_limit(5.91)
        expected = 5.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x08), 0x05)
            self.assertEqual(bh.read_register(0x14), 0b1110_0000)

    def test_set_ets_low_temperature_limit_invalid(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_ets_low_temperature_limit, -10)

    def test_get_ets_high_temperature_limit(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x07, 0x54)         # external sensor low limit (decimal)
            bh.write_register(0x13, 0b1110_0000)  # external sensor low limit (fraction)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_ets_high_temperature_limit()
        expected = 84.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_set_ets_high_temperature_limit(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_ets_high_temperature_limit(84.91)
        expected = 84.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x07), 0x54)
            self.assertEqual(bh.read_register(0x13), 0b1110_0000)

    def test_set_ets_high_temperature_limit_invalid(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_ets_high_temperature_limit, 120)
