#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import unittest

import feeph.emc2101.config_register as sut


class TestConfigRegister(unittest.TestCase):

    def test_init_with_defaults(self):
        config = sut.ConfigRegister()
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0000_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_mask(self):
        config = sut.ConfigRegister(mask=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b1000_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_standby(self):
        config = sut.ConfigRegister(standby=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0100_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_fan_standby(self):
        config = sut.ConfigRegister(fan_standby=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0010_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_dac(self):
        config = sut.ConfigRegister(dac=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0001_0000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_dis_to(self):
        config = sut.ConfigRegister(dis_to=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0000_1000
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_alt_tach(self):
        config = sut.ConfigRegister(alt_tach=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0000_0100
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_trcit_ovrd(self):
        config = sut.ConfigRegister(trcit_ovrd=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0000_0010
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_init_queue(self):
        config = sut.ConfigRegister(queue=True)
        # -----------------------------------------------------------------
        computed = config.as_int()
        expected = 0b0000_0001
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)


class TestParseConfigRegister(unittest.TestCase):

    def test_parse_defaults(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0000_0000)
        expected = sut.ConfigRegister()
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_mask(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b1000_0000)
        expected = sut.ConfigRegister(mask=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_standby(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0100_0000)
        expected = sut.ConfigRegister(standby=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_fan_standby(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0010_0000)
        expected = sut.ConfigRegister(fan_standby=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_dac(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0001_0000)
        expected = sut.ConfigRegister(dac=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_dis_to(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0000_1000)
        expected = sut.ConfigRegister(dis_to=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_alt_tach(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0000_0100)
        expected = sut.ConfigRegister(alt_tach=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_trcit_ovrd(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0000_0010)
        expected = sut.ConfigRegister(trcit_ovrd=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)

    def test_parse_queue(self):
        # -----------------------------------------------------------------
        computed = sut.parse_config_register(0b0000_0001)
        expected = sut.ConfigRegister(queue=True)
        # -----------------------------------------------------------------
        self.assertEqual(computed, expected)
