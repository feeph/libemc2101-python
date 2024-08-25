#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring

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
    # initialization
    # ---------------------------------------------------------------------

    def test_configure_pin6_alert(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.ALERT)
        emc2101 = sut.Emc2101_PWM(i2c_bus=self.i2c_bus, device_config=device_config, fan_config=self.fan_config)
        # -----------------------------------------------------------------
        computed = emc2101.get_config_register()
        expected = sut.ConfigRegister(alt_tach=False)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_configure_pin6_tacho(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.TACHO)
        emc2101 = sut.Emc2101_PWM(i2c_bus=self.i2c_bus, device_config=device_config, fan_config=self.fan_config)
        # -----------------------------------------------------------------
        computed = emc2101.get_config_register()
        expected = sut.ConfigRegister(alt_tach=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_configure_pin6_invalid(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=None)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(NotImplementedError, sut.Emc2101_PWM, i2c_bus=self.i2c_bus, device_config=device_config, fan_config=self.fan_config)

    def test_configure_control_mode_mismatch(self):
        # fan device and controller must both agree on how to control the
        # fan's speed
        fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=sut.RpmControlMode.VOLTAGE, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps={})
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.TACHO)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.Emc2101_PWM, i2c_bus=self.i2c_bus, device_config=device_config, fan_config=fan_config)

    def test_configure_control_mode_unknown(self):
        fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=None, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps={})
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.TACHO)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.Emc2101_PWM, i2c_bus=self.i2c_bus, device_config=device_config, fan_config=fan_config)

    def test_no_steps_defined(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.TACHO)
        # no steps defined in fan config
        fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=sut.RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.Emc2101_PWM, i2c_bus=self.i2c_bus, device_config=device_config, fan_config=fan_config)

    # ---------------------------------------------------------------------
    # control fan speed (manually)
    # ---------------------------------------------------------------------

    def test_get_fixed_speed(self):
        # -----------------------------------------------------------------
        computed = self.emc2101.get_fixed_speed(unit=sut.FanSpeedUnit.STEP)
        expected = 0
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_set_fixed_speed_invalid(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, value=0, unit=None)

    def test_set_fixed_speed_percent_zero(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.TACHO)
        steps = {
            0: (0, 0),
        }
        fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=sut.RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps=steps)
        emc2101 = sut.Emc2101_PWM(i2c_bus=self.i2c_bus, device_config=device_config, fan_config=fan_config)
        # -----------------------------------------------------------------
        computed = emc2101.set_fixed_speed(1, unit=sut.FanSpeedUnit.PERCENT)
        expected = 0
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_set_fixed_speed_percent_invalid(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, value=101, unit=sut.FanSpeedUnit.PERCENT)

    def test_set_fixed_speed_rpm_zero(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.TACHO)
        steps = {
            0: (0, 0),
        }
        fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=sut.RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps=steps)
        emc2101 = sut.Emc2101_PWM(i2c_bus=self.i2c_bus, device_config=device_config, fan_config=fan_config)
        # -----------------------------------------------------------------
        computed = emc2101.set_fixed_speed(1, unit=sut.FanSpeedUnit.RPM)
        expected = 0
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_set_fixed_speed_rpm_none(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.ALERT)
        steps = {
            0: (0, None),
        }
        fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=sut.RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps=steps)
        emc2101 = sut.Emc2101_PWM(i2c_bus=self.i2c_bus, device_config=device_config, fan_config=fan_config)
        # -----------------------------------------------------------------
        computed = emc2101.set_fixed_speed(1, unit=sut.FanSpeedUnit.RPM)
        expected = None
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_set_fixed_speed_rpm_invalid(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, value=-1, unit=sut.FanSpeedUnit.RPM)

    def test_set_fixed_speed_step_invalid(self):
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.set_fixed_speed, value=-1, unit=sut.FanSpeedUnit.STEP)

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
    # lookup table - extended functionality
    # ---------------------------------------------------------------------

    def test_update_lookup_table_step(self):
        values = {
            16: 0x03,  # temp+speed #1
            40: 0x08,  # temp+speed #2
            72: 0x0D,  # temp+speed #3
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.STEP)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x03)
            self.assertEqual(bh.read_register(0x52), 40)
            self.assertEqual(bh.read_register(0x53), 0x08)
            self.assertEqual(bh.read_register(0x54), 72)
            self.assertEqual(bh.read_register(0x55), 0x0D)

    def test_update_lookup_table_step_invalid(self):
        values = {
            16: 0x03,  # temp+speed #1
            40: 0xff,  # invalid step - will be skipped
            72: 0x0D,  # temp+speed #3
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.STEP)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x03)
            self.assertEqual(bh.read_register(0x52), 72)
            self.assertEqual(bh.read_register(0x53), 0x0D)

    def test_update_lookup_table_percent(self):
        values = {
            16: 20,  # temp+speed #1
            40: 60,  # temp+speed #2
            72: 90,  # temp+speed #3
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.PERCENT)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x03)
            self.assertEqual(bh.read_register(0x52), 40)
            self.assertEqual(bh.read_register(0x53), 0x08)
            self.assertEqual(bh.read_register(0x54), 72)
            self.assertEqual(bh.read_register(0x55), 0x0D)

    # TODO properly validate the percentage range and perform suitable action
    def test_update_lookup_table_percent_too_low(self):
        values = {
            16: -1,
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.PERCENT)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x0E)

    # TODO properly validate the percentage range and perform suitable action
    def test_update_lookup_table_percent_too_high(self):
        values = {
            16: 101,
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.PERCENT)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x0E)

    def test_update_lookup_table_rpm(self):
        values = {
            16: 700,  # temp+speed #1
            40: 800,  # temp+speed #2
            72: 900,  # temp+speed #3
        }
        # -----------------------------------------------------------------
        computed = self.emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.RPM)
        expected = True
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 16)
            self.assertEqual(bh.read_register(0x51), 0x08)
            self.assertEqual(bh.read_register(0x52), 40)
            self.assertEqual(bh.read_register(0x53), 0x09)
            self.assertEqual(bh.read_register(0x54), 72)
            self.assertEqual(bh.read_register(0x55), 0x0A)

    def test_update_lookup_table_rpm_none(self):
        device_config = sut.DeviceConfig(rpm_control_mode=sut.RpmControlMode.PWM, pin_six_mode=sut.PinSixMode.ALERT)
        steps = {
            0x03: (0, None),
            0x08: (0, None),
            0x0D: (0, None),
        }
        fan_config = sut.FanConfig(model="Mockinator 2000", pwm_frequency=22500, rpm_control_mode=sut.RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000, steps=steps)
        emc2101 = sut.Emc2101_PWM(i2c_bus=self.i2c_bus, device_config=device_config, fan_config=fan_config)
        emc2101.reset_lookup_table()
        values = {
            16: 0x03,  # no RPM availble - will be skipped
            40: 0x08,  # no RPM availble - will be skipped
        }
        # -----------------------------------------------------------------
        computed = emc2101.update_lookup_table(values=values, unit=sut.FanSpeedUnit.RPM)
        expected = False
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)  # update was performed
        with BurstHandler(i2c_bus=self.i2c_bus, i2c_adr=self.i2c_adr) as bh:
            self.assertEqual(bh.read_register(0x50), 00)
            self.assertEqual(bh.read_register(0x51), 0x00)
            self.assertEqual(bh.read_register(0x52), 00)
            self.assertEqual(bh.read_register(0x53), 0x00)

    def test_update_lookup_table_invalid_unit(self):
        values = {
            16: -65,  # min temp is -64
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, self.emc2101.update_lookup_table, values=values, unit=None)
