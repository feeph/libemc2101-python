#!/usr/bin/env python3
"""
"""

import os
import unittest

# modules board and busio provide no type hints
import board  # type: ignore
import busio  # type: ignore

import i2c.emc2101
from i2c.emc2101 import DeviceConfig, FanConfig, FanSpeedUnit, PinSixMode, RpmControlMode, SpinUpDuration, SpinUpStrength, TemperatureLimitType  # NOQA


@unittest.skipUnless(os.environ.get('TEST_EMC2101_CHIP', 'n') == 'y', "Skipping physical device test.")
class TestUsingMockedDevice(unittest.TestCase):

    def setUp(self):
        i2c_scl_pin = os.environ.get('I2C_SCL_PIN', board.SCL)
        i2c_sda_pin = os.environ.get('I2C_SDA_PIN', board.SDA)
        i2c_bus = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin)
        device_config = DeviceConfig(rpm_control_mode=RpmControlMode.PWM, pin_six_mode=PinSixMode.TACHO)
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
        self.fan_config = FanConfig(model="generic PWM fan", pwm_frequency=22500, rpm_control_mode=RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps=steps)
        self.emc2101 = i2c.emc2101.Emc2101(i2c_bus=i2c_bus, device_config=device_config, fan_config=self.fan_config)

    def tearDown(self):
        # nothing to do
        pass

    # ---------------------------------------------------------------------
    # helpers
    # ---------------------------------------------------------------------

    def read_device_register(self, register: int):
        return self.emc2101._i2c_device.read_register(register)

    def write_device_register(self, register: int, value: int):
        self.emc2101._i2c_device.write_register(register, value)

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
    # control fan speed
    # ---------------------------------------------------------------------

    def test_configure_spinup_behaviour(self):
        spinup_duration = SpinUpDuration.TIME_0_80    # 0b...._.101
        spinup_strength = SpinUpStrength.STRENGTH_50  # 0b...0_1...
        fast_mode = True                              # 0b..1._....
        # -----------------------------------------------------------------
        self.emc2101.configure_spinup_behaviour(spinup_strength=spinup_strength, spinup_duration=spinup_duration, fast_mode=fast_mode)
        # -----------------------------------------------------------------
        self.assertEqual(self.read_device_register(0x4B), 0b0010_1101)

    # control duty cycle using manual control

    def test_duty_cycle_read_steps(self):
        self.write_device_register(0x4A, 0b0010_0000)  # enable manual control
        self.write_device_register(0x4C, 0x08)         # number of steps depends on pwm frequency
        # -----------------------------------------------------------------
        computed = self.emc2101.get_fixed_speed(unit=FanSpeedUnit.STEP)
        expected = 8
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_duty_cycle_write_steps(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_fixed_speed(8, unit=FanSpeedUnit.STEP)  # number of steps depends on pwm frequency
        expected = 8                                                        # same unit as input
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        self.assertTrue(self.read_device_register(0x4A) & 0b0010_0000)  # manual control is enabled
        self.assertEqual(self.read_device_register(0x4C), 0x08)         # number of steps depends on pwm frequency

    def test_duty_cycle_write_steps_oor(self):
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, 20, unit=FanSpeedUnit.STEP)

    def test_duty_cycle_read_percent(self):
        self.write_device_register(0x4A, 0b0010_0000)  # enable manual control
        self.write_device_register(0x4C, 0x08)         # number of steps depends on pwm frequency
        # -----------------------------------------------------------------
        computed = self.emc2101.get_fixed_speed(unit=FanSpeedUnit.PERCENT)
        expected = 58
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_duty_cycle_write_percent(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_fixed_speed(72)  # 0..100 percent
        expected = 72                                # same unit as input
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        self.assertTrue(self.read_device_register(0x4A) & 0b0010_0000)  # manual control is enabled
        self.assertEqual(self.read_device_register(0x4C), 0x0A)         # number of steps depends on pwm frequency

    def test_duty_cycle_write_percent_oor(self):
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, 105)

    def test_duty_cycle_read_rpm(self):
        self.write_device_register(0x4A, 0b0010_0000)  # enable manual control
        self.write_device_register(0x4C, 0x08)         # number of steps depends on pwm frequency
        # -----------------------------------------------------------------
        computed = self.emc2101.get_fixed_speed(unit=FanSpeedUnit.RPM)
        expected = self.fan_config.maximum_rpm
        # -----------------------------------------------------------------
        self.assertLessEqual(computed, expected)

    def test_duty_cycle_write_rpm(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_fixed_speed(868, unit=FanSpeedUnit.RPM)  # 0..max_rpm
        expected = 868                                                       # same unit as input
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
        self.assertTrue(self.emc2101._i2c_device.read_register(0x4A) & 0b0010_0000)  # manual control is enabled
        self.assertEqual(self.emc2101._i2c_device.read_register(0x4C), 0x0A)         # number of steps depends on pwm frequency

    def test_duty_cycle_write_rpm_oor(self):
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, 2500)

    # control duty cycle using temperature sensor and lookup table

    def test_update_lookup_table_empty(self):
        values = {
        }
        # -----------------------------------------------------------------
        self.emc2101.update_lookup_table(values=values, unit=FanSpeedUnit.STEP)
        # -----------------------------------------------------------------
        self.assertEqual(self.read_device_register(0x50), 0)
        self.assertEqual(self.read_device_register(0x51), 0x00)
        self.assertEqual(self.read_device_register(0x52), 0)
        self.assertEqual(self.read_device_register(0x53), 0x00)
        self.assertEqual(self.read_device_register(0x54), 0)
        self.assertEqual(self.read_device_register(0x55), 0x00)
        self.assertEqual(self.read_device_register(0x56), 0)
        self.assertEqual(self.read_device_register(0x57), 0x00)
        self.assertEqual(self.read_device_register(0x58), 0)
        self.assertEqual(self.read_device_register(0x59), 0x00)
        self.assertEqual(self.read_device_register(0x5A), 0)
        self.assertEqual(self.read_device_register(0x5B), 0x00)
        self.assertEqual(self.read_device_register(0x5C), 0)
        self.assertEqual(self.read_device_register(0x5D), 0x00)
        self.assertEqual(self.read_device_register(0x5E), 0)
        self.assertEqual(self.read_device_register(0x5F), 0x00)

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
        self.emc2101.update_lookup_table(values=values, unit=FanSpeedUnit.STEP)
        # -----------------------------------------------------------------
        self.assertEqual(self.read_device_register(0x50), 16)
        self.assertEqual(self.read_device_register(0x51), 0x03)
        self.assertEqual(self.read_device_register(0x52), 24)
        self.assertEqual(self.read_device_register(0x53), 0x04)
        for offset in range(4, 16):
            self.assertEqual(self.read_device_register(0x50 + offset), 0x00)

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
        self.emc2101.update_lookup_table(values=values, unit=FanSpeedUnit.STEP)
        # -----------------------------------------------------------------
        self.assertEqual(self.read_device_register(0x50), 16)
        self.assertEqual(self.read_device_register(0x51), 0x03)
        self.assertEqual(self.read_device_register(0x52), 24)
        self.assertEqual(self.read_device_register(0x53), 0x04)
        self.assertEqual(self.read_device_register(0x54), 32)
        self.assertEqual(self.read_device_register(0x55), 0x05)
        self.assertEqual(self.read_device_register(0x56), 40)
        self.assertEqual(self.read_device_register(0x57), 0x06)
        self.assertEqual(self.read_device_register(0x58), 48)
        self.assertEqual(self.read_device_register(0x59), 0x07)
        self.assertEqual(self.read_device_register(0x5A), 56)
        self.assertEqual(self.read_device_register(0x5B), 0x08)
        self.assertEqual(self.read_device_register(0x5C), 64)
        self.assertEqual(self.read_device_register(0x5D), 0x09)
        self.assertEqual(self.read_device_register(0x5E), 72)
        self.assertEqual(self.read_device_register(0x5F), 0x0A)

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
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values, unit=FanSpeedUnit.STEP)

    def test_reset_lookup(self):
        # populate with some non-zero values
        values = {
            20: 0x03,  # temp+speed #1
            24: 0x04,  # temp+speed #2
            32: 0x05,  # temp+speed #3
            40: 0x06,  # temp+speed #4
            48: 0x07,  # temp+speed #5
            56: 0x08,  # temp+speed #6
            64: 0x09,  # temp+speed #7
            72: 0x0A,  # temp+speed #8
        }
        self.emc2101.update_lookup_table(values=values, unit=FanSpeedUnit.STEP)
        # -----------------------------------------------------------------
        self.emc2101.reset_lookup_table()
        # -----------------------------------------------------------------
        for offset in range(0, 16):
            self.assertEqual(self.read_device_register(0x50 + offset), 0x00)

    # ---------------------------------------------------------------------
    # measure temperatures
    # ---------------------------------------------------------------------

    def test_get_temperature_conversion_rate(self):
        self.write_device_register(0x04, 0b0000_0111)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_temperature_conversion_rate()
        expected = "8"
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected temperature conversion rate '{computed}'.")

    def test_set_temperature_conversion_rate(self):
        # -----------------------------------------------------------------
        self.assertTrue(self.emc2101.set_temperature_conversion_rate("1/8"))
        # -----------------------------------------------------------------
        self.assertEqual(self.read_device_register(0x04), 0b0000_0001)

    def test_get_temperature_conversion_rates(self):
        # -----------------------------------------------------------------
        computed = sorted(self.emc2101.get_temperature_conversion_rates())
        expected = sorted(["1/16", "1/8", "1/4", "1/2", "1", "2", "4", "8", "16", "32"])
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected temperature conversion rates '{computed}'.")

    def test_chip_temperature(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature()
        expected = self.read_device_register(0x00)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature '{computed}'.")

    def test_chip_temperature_limit_read(self):
        self.write_device_register(0x05, 0x46)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_chip_temperature_limit()
        expected = 70
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected chip temperature limit '{computed}'.")

    def test_has_sensor(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.has_external_sensor()
        expected = not self.read_device_register(0x02) & 0b0000_0100
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    @unittest.skipUnless(os.environ.get('TEST_EMC2101_SENSOR', 'n') == 'y', "Skipping external sensor test.")
    def test_sensor_temperature(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature()
        # -----------------------------------------------------------------
        self.assertGreaterEqual(computed, 0, f"Got unexpected sensor temperature '{computed}'.")
        self.assertLessEqual(computed, 85, f"Got unexpected sensor temperature '{computed}'.")

    def test_sensor_temperature_limit_read_lower(self):
        self.write_device_register(0x08, 0x12)         # external sensor low limit (decimal)
        self.write_device_register(0x14, 0b1110_0000)  # external sensor low limit (fraction)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature_limit(limit_type=TemperatureLimitType.TO_COLD)
        expected = 18.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_sensor_temperature_limit_write_lower(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_sensor_temperature_limit(5.91, limit_type=TemperatureLimitType.TO_COLD)
        expected = 5.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")
        self.assertEqual(self.read_device_register(0x08), 0x05)
        self.assertEqual(self.read_device_register(0x14), 0b1110_0000)

    def test_sensor_temperature_limit_read_upper(self):
        self.write_device_register(0x07, 0x54)         # external sensor low limit (decimal)
        self.write_device_register(0x13, 0b1110_0000)  # external sensor low limit (fraction)
        # -----------------------------------------------------------------
        computed = self.emc2101.get_sensor_temperature_limit(limit_type=TemperatureLimitType.TO_HOT)
        expected = 84.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")

    def test_sensor_temperature_limit_write_upper(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.set_sensor_temperature_limit(84.91, limit_type=TemperatureLimitType.TO_HOT)
        expected = 84.9
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected, f"Got unexpected sensor temperature limit '{computed}'.")
        self.assertEqual(self.read_device_register(0x07), 0x54)
        self.assertEqual(self.read_device_register(0x13), 0b1110_0000)
