#!/usr/bin/env python3
"""
perform PWM related tests

use simulated device:
  pdm run pytest
use hardware device:
  TEST_EMC2101_CHIP=y pdm run pytest
"""

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
    # control fan speed (manually)
    # ---------------------------------------------------------------------

    def test_configure_spinup_behaviour(self):
        spinup_duration = sut.SpinUpDuration.TIME_0_80    # 0b...._.101
        spinup_strength = sut.SpinUpStrength.STRENGTH_50  # 0b...0_1...
        fast_mode = True                                  # 0b..1._....
        # -----------------------------------------------------------------
        self.emc2101.configure_spinup_behaviour(spinup_strength=spinup_strength, spinup_duration=spinup_duration, fast_mode=fast_mode)
        # -----------------------------------------------------------------
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x4B), 0b0010_1101)

    # control duty cycle using manual control

    def test_duty_cycle_read_steps(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x4A, 0b0010_0000)  # enable manual control
            bh.write_register(0x4C, 0x08)         # number of steps depends on pwm frequency
        # -----------------------------------------------------------------
        computed = self.emc2101.get_fixed_speed(unit=sut.FanSpeedUnit.STEP)
        expected = 8
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_duty_cycle_write_steps(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_fixed_speed(8, unit=sut.FanSpeedUnit.STEP)  # number of steps depends on pwm frequency
        expected = 8                                                            # same unit as input
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertTrue(bh.read_register(0x4A) & 0b0010_0000)  # manual control is enabled
            self.assertEqual(bh.read_register(0x4C), 0x08)         # number of steps depends on pwm frequency

    def test_duty_cycle_write_steps_oor(self):
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, 20, unit=sut.FanSpeedUnit.STEP)

    def test_duty_cycle_read_percent(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x4A, 0b0010_0000)  # enable manual control
            bh.write_register(0x4C, 0x08)         # number of steps depends on pwm frequency
        # -----------------------------------------------------------------
        computed = self.emc2101.get_fixed_speed(unit=sut.FanSpeedUnit.PERCENT)
        expected = 58
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_duty_cycle_write_percent(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_fixed_speed(72)  # 0..100 percent
        expected = 72                                # same unit as input
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertTrue(bh.read_register(0x4A) & 0b0010_0000)  # manual control is enabled
            self.assertEqual(bh.read_register(0x4C), 0x0A)         # number of steps depends on pwm frequency

    def test_duty_cycle_write_percent_oor(self):
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, 105)

    def test_duty_cycle_read_rpm(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x4A, 0b0010_0000)  # enable manual control
            bh.write_register(0x4C, 0x08)         # number of steps depends on pwm frequency
        # -----------------------------------------------------------------
        computed = self.emc2101.get_fixed_speed(unit=sut.FanSpeedUnit.RPM)
        expected = self.fan_config.maximum_rpm
        # -----------------------------------------------------------------
        self.assertLessEqual(computed, expected)

    def test_duty_cycle_write_rpm(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_fixed_speed(868, unit=sut.FanSpeedUnit.RPM)  # 0..max_rpm
        expected = 868                                                           # same unit as input
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertTrue(bh.read_register(0x4A) & 0b0010_0000)  # manual control is enabled
            self.assertEqual(bh.read_register(0x4C), 0x0A)         # number of steps depends on pwm frequency

    def test_duty_cycle_write_rpm_oor(self):
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, 2500)

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
    # temperature measurements (internal sensor)
    # ---------------------------------------------------------------------

    def test_chip_temperature(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature()
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            expected = bh.read_register(0x00)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature '{computed}'.")

    # ---------------------------------------------------------------------
    # temperature limits
    # ---------------------------------------------------------------------

    def test_chip_temperature_limit_read(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x05, 0x46)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature_limit()
        expected = 70
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature limit '{computed}'.")

    def test_sensor_temperature_limit_read_lower(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x08, 0x12)         # external sensor low limit (decimal)
            bh.write_register(0x14, 0b1110_0000)  # external sensor low limit (fraction)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature_limit(limit_type=sut.TemperatureLimitType.TO_COLD)
        expected = 18.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_sensor_temperature_limit_write_lower(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_sensor_temperature_limit(5.91, limit_type=sut.TemperatureLimitType.TO_COLD)
        expected = 5.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x08), 0x05)
            self.assertEqual(bh.read_register(0x14), 0b1110_0000)

    def test_sensor_temperature_limit_read_upper(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x07, 0x54)         # external sensor low limit (decimal)
            bh.write_register(0x13, 0b1110_0000)  # external sensor low limit (fraction)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature_limit(limit_type=sut.TemperatureLimitType.TO_HOT)
        expected = 84.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_sensor_temperature_limit_write_upper(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_sensor_temperature_limit(84.91, limit_type=sut.TemperatureLimitType.TO_HOT)
        expected = 84.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x07), 0x54)
            self.assertEqual(bh.read_register(0x13), 0b1110_0000)

    # ---------------------------------------------------------------------
    # temperature measurements (external sensor)
    # ---------------------------------------------------------------------

    @unittest.skipIf(HAS_HARDWARE, "Skipping external sensor test.")
    def test_diode_present(self):
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            bh.write_register(0x02, 0b0000_0000)
            bh.write_register(0x01, 0b0000_1111)
            bh.write_register(0x10, 0b0000_0000)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_external_sensor_state()
        expected = sut.ExternalSensorStatus.OK
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
        computed = self.emc2101.get_external_sensor_state()
        expected = sut.ExternalSensorStatus.FAULT1
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
        computed = self.emc2101.get_external_sensor_state()
        expected = sut.ExternalSensorStatus.FAULT2
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        # with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
        #     self.assertFalse(bool(bh.read_register(0x02) & 0b0000_0100))
        #     self.assertEqual(bh.read_register(0x01), 0b0111_1111)
        #     self.assertEqual(bh.read_register(0x10), 0b1110_0000)

    def test_has_sensor(self):
        computed = self.emc2101.has_external_sensor()
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            value = bh.read_register(0x01)
        if value == 0b0111_1111:
            expected = False
        else:
            expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_sensor_temperature(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature()
        # -----------------------------------------------------------------
        if self.emc2101.has_external_sensor():
            # absolute maximum representable range is -64°C ≤ x < 127°C
            # (nominal operating temperature range is 0°C ≤ x ≤ 85°C)
            self.assertGreaterEqual(computed, -64.0, f"Got unexpected sensor temperature '{computed}'.")
            self.assertLess(computed, 127.0, f"Got unexpected sensor temperature '{computed}'.")
        else:
            self.assertTrue(math.isnan(computed))

    # ---------------------------------------------------------------------
    # control fan speed (lookup table)
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
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.STEP)
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
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.STEP)
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
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.STEP)
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
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values, unit=sut.FanSpeedUnit.STEP)

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
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.STEP)
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
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values, unit=sut.FanSpeedUnit.STEP)

    def test_update_lookup_table_too_high(self):
        values = {
            16: 250,  # max temp is 126
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values, unit=sut.FanSpeedUnit.STEP)

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
