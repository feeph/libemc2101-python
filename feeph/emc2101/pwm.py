#!/usr/bin/env python3

# a reimplementation of https://github.com/adafruit/Adafruit_CircuitPython_EMC2101
# Datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf

import logging
from enum import Enum

# module busio provides no type hints
import busio  # type: ignore

import feeph.emc2101.utilities
from feeph.emc2101.config_register import ConfigRegister
from feeph.emc2101.core import Emc2101
from feeph.emc2101.ets_config import ExternalTemperatureSensorConfig, ets_2n3904
from feeph.emc2101.fan_configs import FanConfig, RpmControlMode, generic_pwm_fan

LH = logging.getLogger('feeph.emc2101')


class FanSpeedUnit(Enum):
    STEP    = 1  # steps       0..15
    RPM     = 2  # rpm       100..2000RPM
    PERCENT = 3  # dutycycle  20..100%


class PinSixMode(Enum):
    """
    Pin 6 is dualpurpose. It can either be used to send an interrupt or
    for reading the fan's tacho signal.
    """
    ALERT = 1  # assert if temperature range is exceeded
    TACHO = 2  # receive fan tacho signal


class DeviceConfig:

    def __init__(self, rpm_control_mode: RpmControlMode, pin_six_mode: PinSixMode):
        """
        configure hardware-specific settings

        These settings depend on the EMC2101 and its supporting electric circuit.
        """
        self.i2c_address      = 0x4C              # address is hardcoded
        self.rpm_control_mode = rpm_control_mode  # supply voltage or PWM
        self.pin_six_mode     = pin_six_mode      # interrupt pin or tacho sense


emc2101_default_config = DeviceConfig(rpm_control_mode=RpmControlMode.VOLTAGE, pin_six_mode=PinSixMode.ALERT)


# TODO add convenience function to refresh state
# TODO auto-refresh state every x seconds (if desired)
class Emc2101_PWM(Emc2101):

    def __init__(self, i2c_bus: busio.I2C, device_config: DeviceConfig = emc2101_default_config, fan_config: FanConfig = generic_pwm_fan, ets_config: ExternalTemperatureSensorConfig = ets_2n3904):
        # -- initialize --
        config = ConfigRegister()
        # configure pin 6
        #   choose between alert and tacho mode
        if device_config.pin_six_mode == PinSixMode.ALERT:
            config.alt_tach = False
        elif device_config.pin_six_mode == PinSixMode.TACHO:
            config.alt_tach = True
        else:
            raise NotImplementedError("unsupported pin 6 mode")
        super().__init__(i2c_bus=i2c_bus, config=config)
        self.configure_minimum_rpm(minimum_rpm=fan_config.minimum_rpm)
        self._max_rpm = fan_config.maximum_rpm
        # configure PWM-related settings
        #   The supporting electric circuit, the EMC2101's configuration
        #   and the fan's control mode must be align with each other.
        if fan_config.rpm_control_mode == RpmControlMode.VOLTAGE:
            # emc2101: PWM, fan: supply voltage -> will not work
            raise ValueError("EMC2101 uses PWM mode but fan is controlled via supply voltage!")
        elif fan_config.rpm_control_mode == RpmControlMode.PWM:
            # emc2101: PWM, fan: PWM -> works
            LH.info("EMC2101 and connected fan both use PWM to control fan speed. Good.")
            from feeph.emc2101.scs import PWM
            scs = PWM(fan_config=fan_config)
            pwm_d, pwm_f = feeph.emc2101.utilities.calculate_pwm_factors(pwm_frequency=fan_config.pwm_frequency)
            self.configure_pwm_control(pwm_d=pwm_d, pwm_f=pwm_f, step_max=max(scs.get_steps()))
        else:
            raise ValueError("fan has unsupported rpm control mode")
        # configure external temperature sensor
        self.configure_ets(ets_config)
        # -- all good: set internal state --
        self._scs = scs

    # ---------------------------------------------------------------------
    # fan speed control
    # ---------------------------------------------------------------------

    def get_fixed_speed(self, unit: FanSpeedUnit = FanSpeedUnit.PERCENT) -> int | None:
        step = self.get_driver_strength()
        if unit == FanSpeedUnit.PERCENT:
            return self._scs.convert_step2percent(step)
        elif unit == FanSpeedUnit.RPM:
            return self._scs.convert_step2rpm(step)
        else:
            return step

    def set_fixed_speed(self, value: int, unit: FanSpeedUnit = FanSpeedUnit.PERCENT, disable_lut: bool = False) -> int | None:
        """
        set the fan speed
         - clamp to minimum/maximum as defined by the fan configuration
         - returns the effective, clamped value or 'None' if no value was set
        """
        # calculate step (driver strength)
        if unit == FanSpeedUnit.PERCENT:
            if 0 <= value <= 100:
                LH.debug("Converting percentage to internal value.")
                result = self._scs.convert_percent2step(value)
                if result is not None:
                    step = result
                else:
                    LH.error("Unable to process provided percentage value '%i'!", value)
                    # read current value and return ()
                    step_cur = self.get_driver_strength()
                    return self._scs.convert_step2percent(step_cur)
            else:
                raise ValueError(f"provided value {value} is out of range (0 ≤ x ≤ 100%)")
        elif unit == FanSpeedUnit.RPM:
            if 0 <= value <= self._max_rpm:
                LH.debug("Converting RPM to internal value.")
                result = self._scs.convert_rpm2step(value)
                if result is not None:
                    step = result
                else:
                    LH.error("Unable to process provided RPM value '%i'!", value)
                    # read current value and return ()
                    step_cur = self.get_driver_strength()
                    return self._scs.convert_step2rpm(step_cur)
            else:
                raise ValueError(f"provided value {value} is out of range (0 ≤ x ≤ {self._max_rpm}RPM)")
        elif unit == FanSpeedUnit.STEP:
            if self._scs.is_valid_step(value):
                step = value
            else:
                raise ValueError(f"provided value {value} is not a valid step")
        else:
            raise ValueError("unsupported value type")
        # apply step
        self.set_driver_strength(step)
        # convert applied value back to original unit and return
        if unit == FanSpeedUnit.PERCENT:
            return self._scs.convert_step2percent(step)
        elif unit == FanSpeedUnit.RPM:
            return self._scs.convert_step2rpm(step)
        else:
            return step

    def update_lookup_table(self, values: dict[int, int], unit: FanSpeedUnit = FanSpeedUnit.PERCENT) -> bool:
        """
        populate the lookup table with the provided values and
        sets all unused values to zero

        returns 'True' if the lookup table was updated and 'False' if it wasn't.
        """
        lut_table = {}
        for temp, value in values.items():
            if unit == FanSpeedUnit.PERCENT:
                step = self._scs.convert_percent2step(value)
            elif unit == FanSpeedUnit.RPM:
                step = self._scs.convert_rpm2step(value)
            elif unit == FanSpeedUnit.STEP:
                step = value
            else:
                raise ValueError("unknown value type")
            if step is not None:
                lut_table[temp] = step
            else:
                LH.error("Unable to process provided value '%i'! Skipping.", value)
        # -------------------------------------------------------------
        return super().update_lookup_table(values=lut_table)
