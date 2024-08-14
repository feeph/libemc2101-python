#!/usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring

import unittest

import feeph.emc2101.scs.base_class as sut


class IncompleteSpeedControlSetter(sut.SpeedControlSetter):
    # !! DO NOT WRITE CODE LIKE THIS !!
    # The purpose of this class is to disable all safety checks and
    # brute-force the usage of abstract methods so we can test that
    # the code correctly bugs out if this happens
    # !! DO NOT WRITE CODE LIKE THIS !!

    def is_valid_step(self, value: int) -> bool:
        # !! DANGER !!
        return super().is_valid_step(value=value)  # type: ignore [safe-super]

    # pylint: disable=useless-parent-delegation
    def get_steps(self) -> list[int]:
        # !! DANGER !!
        return super().get_steps()  # type: ignore [safe-super]

    def convert_percent2step(self, percent: int) -> int | None:
        # !! DANGER !!
        return super().convert_percent2step(percent=percent)  # type: ignore [safe-super]

    def convert_step2percent(self, step: int) -> int:
        # !! DANGER !!
        return super().convert_step2percent(step=step)  # type: ignore [safe-super]

    def convert_rpm2step(self, rpm: int) -> int | None:
        # !! DANGER !!
        return super().convert_rpm2step(rpm=rpm)  # type: ignore [safe-super]

    def convert_step2rpm(self, step: int) -> int | None:
        # !! DANGER !!
        return super().convert_step2rpm(step=step)  # type: ignore [safe-super]


class TestScsPwm(unittest.TestCase):

    # def test_abstract_base_class(self):
    #     self.assertRaises(TypeError, sut.Ads1x1xConfig)

    def test_abstract_method1(self):
        self.assertRaises(TypeError, IncompleteSpeedControlSetter().is_valid_step(0))

    def test_abstract_method2(self):
        self.assertRaises(TypeError, IncompleteSpeedControlSetter().get_steps())

    def test_abstract_method3(self):
        self.assertRaises(TypeError, IncompleteSpeedControlSetter().convert_percent2step(0))

    def test_abstract_method4(self):
        self.assertRaises(TypeError, IncompleteSpeedControlSetter().convert_step2percent(0))

    def test_abstract_method5(self):
        self.assertRaises(TypeError, IncompleteSpeedControlSetter().convert_rpm2step(0))

    def test_abstract_method6(self):
        self.assertRaises(TypeError, IncompleteSpeedControlSetter().convert_step2rpm(0))
