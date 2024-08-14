#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import unittest

import feeph.emc2101.fan_configs as sut  # sytem under test


class TestFanConfigs(unittest.TestCase):

    def test_pwmfan_without_frequency(self):
        params = {
            # fmt: off
            'model':              'brown matter acceleration device',
            'rpm_control_mode':   sut.RpmControlMode.PWM,
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      None,
            'steps':              {},
            # fmt: on
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.FanConfig, **params)

    def test_dutycycle_min_larger_than_max(self):
        params = {
            # fmt: off
            'model':              'brown matter entropy averaging device',
            'rpm_control_mode':   sut.RpmControlMode.PWM,
            'minimum_duty_cycle': 120,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      22500,
            'steps':              {},
            # fmt: on
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.FanConfig, **params)

    def test_dutycycle_min_too_small(self):
        params = {
            # fmt: off
            'model':              'brown matter impacting device',
            'rpm_control_mode':   sut.RpmControlMode.PWM,
            'minimum_duty_cycle': -1,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      22500,
            'steps':              {},
            # fmt: on
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.FanConfig, **params)

    def test_dutycycle_min_too_large(self):
        params = {
            # fmt: off
            'model':              'brown matter granularity changing device',
            'rpm_control_mode':   sut.RpmControlMode.PWM,  # RpmControlMode,
            'minimum_duty_cycle': 20,  # int | None,
            'maximum_duty_cycle': 101,  # int | None,
            'minimum_rpm':        700,  # int,
            'maximum_rpm':        1400,  # int,
            'pwm_frequency':      22500,  # int | None = None,
            'steps':              {},  # Steps | None = None,
            # fmt: on
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.FanConfig, **params)


# pylint: disable=missing-class-docstring,missing-function-docstring
class TestFanConfigExporter(unittest.TestCase):

    def test_export_dacfan(self):
        params = {
            # fmt: off
            'model':              'Mockinator 2000 (DC)',
            'rpm_control_mode':   sut.RpmControlMode.VOLTAGE,
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      None,
            'steps':              {
                2: (20, None),
                4: (40, None),
            },
            # fmt: on
        }
        fc = sut.FanConfig(**params)
        # -----------------------------------------------------------------
        computed = sut.export_fan_config(fan_config=fc)
        expected = {
            'model': 'Mockinator 2000 (DC)',
            'control_mode': 'VOLTAGE',
            'minimum_rpm': 700,
            'maximum_rpm': 1400,
            'steps': {
                2: {'dutycycle': 20, 'rpm': None},
                4: {'dutycycle': 40, 'rpm': None},
            },
        }
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_export_pwmfan(self):
        params = {
            # fmt: off
            'model':              'Mockinator 2000 (PWM)',
            'rpm_control_mode':   sut.RpmControlMode.PWM,
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      22500,
            'steps':              {
                2: (20, 800),
                4: (40, 1300),
            },
            # fmt: on
        }
        fc = sut.FanConfig(**params)
        # -----------------------------------------------------------------
        computed = sut.export_fan_config(fan_config=fc)
        expected = {
            'model': 'Mockinator 2000 (PWM)',
            'control_mode': 'PWM',
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm': 700,
            'maximum_rpm': 1400,
            'pwm_frequency': 22500,
            'steps': {
                2: {'dutycycle': 20, 'rpm': 800},
                4: {'dutycycle': 40, 'rpm': 1300},
            },
        }
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_export_control_type_invalid(self):
        params = {
            # fmt: off
            'model':              'Mockinator 2000 (DC)',
            'rpm_control_mode':   None,
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      None,
            'steps':              {
                2: (20, None),
                4: (40, None),
            },
            # fmt: on
        }
        fc = sut.FanConfig(**params)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.export_fan_config, fan_config=fc)


# pylint: disable=missing-class-docstring,missing-function-docstring
class TestFanConfigImporter(unittest.TestCase):

    def test_import_dacfan(self):
        data = {
            # fmt: off
            'model':        'Mockinator 2000 (DC)',
            'control_mode': 'VOLTAGE',
            'minimum_rpm':  700,
            'maximum_rpm':  1400,
            'steps': {
                2: {'dutycycle': 20, 'rpm': None},
                4: {'dutycycle': 40, 'rpm': None},
            },
            # fmt: on
        }
        fc = sut.import_fan_config(fan_config=data)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertEqual(fc.model, 'Mockinator 2000 (DC)')
        self.assertEqual(fc.rpm_control_mode, sut.RpmControlMode.VOLTAGE)
        self.assertEqual(fc.minimum_duty_cycle, None)
        self.assertEqual(fc.maximum_duty_cycle, None)
        self.assertEqual(fc.minimum_rpm, 700)
        self.assertEqual(fc.maximum_rpm, 1400)
        self.assertEqual(fc.pwm_frequency, 0)
        self.assertEqual(fc.steps, {2: (20, None), 4: (40, None)})

    def test_import_pwmfan(self):
        data = {
            # fmt: off
            'model':              'Mockinator 2000 (PWM)',
            'control_mode':       'PWM',
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      22500,
            'steps': {
                2: {'dutycycle': 20, 'rpm': 800},
                4: {'dutycycle': 40, 'rpm': 1300},
            },
            # fmt: on
        }
        fc = sut.import_fan_config(fan_config=data)
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertEqual(fc.model, 'Mockinator 2000 (PWM)')
        self.assertEqual(fc.rpm_control_mode, sut.RpmControlMode.PWM)
        self.assertEqual(fc.minimum_duty_cycle, 20)
        self.assertEqual(fc.maximum_duty_cycle, 100)
        self.assertEqual(fc.minimum_rpm, 700)
        self.assertEqual(fc.maximum_rpm, 1400)
        self.assertEqual(fc.pwm_frequency, 22500)
        self.assertEqual(fc.steps, {2: (20, 800), 4: (40, 1300)})

    def test_import_control_type_invalid(self):
        data = {
            # fmt: off
            'model':              'Mockinator 2000 (INVALID)',
            'control_mode':       None,
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      None,
            'steps':              {},
            # fmt: on
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.import_fan_config, fan_config=data)

    def test_import_step_invalid_data(self):
        data = {
            # fmt: off
            'model':              'Mockinator 2000 (INVALID)',
            'control_mode':       'PWM',
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      None,
            'steps':              {
                2: {'dutycycle': None, 'rpm': 800},
            },
            # fmt: on
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.import_fan_config, fan_config=data)

    def test_import_step_invalid_type(self):
        data = {
            # fmt: off
            'model':              'Mockinator 2000 (INVALID)',
            'control_mode':       'PWM',
            'minimum_duty_cycle': 20,
            'maximum_duty_cycle': 100,
            'minimum_rpm':        700,
            'maximum_rpm':        1400,
            'pwm_frequency':      None,
            'steps':              [],
            # fmt: on
        }
        # -----------------------------------------------------------------
        # -----------------------------------------------------------------
        self.assertRaises(ValueError, sut.import_fan_config, fan_config=data)
