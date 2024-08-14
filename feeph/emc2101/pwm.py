#!/usr/bin/env python3
"""
"""

# a reimplementation of https://github.com/adafruit/Adafruit_CircuitPython_EMC2101
# Datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf

import logging
from enum import Enum
from typing import Any

# module busio provides no type hints
import busio  # type: ignore

import feeph.emc2101.utilities
from feeph.emc2101.core import CONVERSIONS_PER_SECOND, Emc2101_core, ExternalSensorStatus, SpinUpDuration, SpinUpStrength
from feeph.emc2101.fan_configs import FanConfig, RpmControlMode, generic_pwm_fan

LH = logging.getLogger(__name__)


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


class ExternalTemperatureSensorConfig:

    def __init__(self, ideality_factor: int, beta_factor: int):
        """
        configure hardware-specific settings

        These settings depend on the external temperature sensor's characteristics.
        """
        self.diode_ideality_factor    = ideality_factor   # datasheet section 6.12
        self.beta_compensation_factor = beta_factor       # datasheet section 6.13


# temperature sensitive transistors
ets_2n3904 = ExternalTemperatureSensorConfig(ideality_factor=0x12, beta_factor=0x08)  # 2N3904 (NPN)
ets_2n3906 = ExternalTemperatureSensorConfig(ideality_factor=0x12, beta_factor=0x08)  # 2N3906 (PNP)


class TemperatureLimitType(Enum):
    TO_COLD = 1
    TO_HOT  = 2


# TODO add convenience function to refresh state
# TODO auto-refresh state every x seconds (if desired)
class Emc2101_PWM:

    def __init__(self, i2c_bus: busio.I2C, device_config: DeviceConfig = emc2101_default_config, fan_config: FanConfig = generic_pwm_fan, ets_config: ExternalTemperatureSensorConfig = ets_2n3904):
        # -- initialize --
        emc2101 = Emc2101_core(i2c_bus=i2c_bus)
        # configure pin 6
        #   choose between alert and tacho mode
        if device_config.pin_six_mode == PinSixMode.ALERT:
            emc2101.configure_pin_six_as_alert()
            pin_six_mode = PinSixMode.ALERT
        elif device_config.pin_six_mode == PinSixMode.TACHO:
            emc2101.configure_pin_six_as_tacho()
            pin_six_mode = PinSixMode.TACHO
        else:
            raise NotImplementedError("unsupported pin 6 mode")
        emc2101.configure_minimum_rpm(minimum_rpm=fan_config.minimum_rpm)
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
            emc2101.configure_pwm_control(pwm_d=pwm_d, pwm_f=pwm_f, step_max=max(scs.get_steps()))
        else:
            raise ValueError("fan has unsupported rpm control mode")
        # configure external temperature sensor
        dif = ets_config.diode_ideality_factor
        bcf = ets_config.beta_compensation_factor
        emc2101.configure_external_temperature_sensor(dif=dif, bcf=bcf)
        # -- all good: set internal state --
        self._emc2101 = emc2101
        self._scs = scs
        self._pin_six_mode = pin_six_mode

    def get_manufacturer_id(self) -> int:
        return self._emc2101.get_manufacturer_id()

    def get_product_id(self) -> int:
        return self._emc2101.get_product_id()

    def get_product_revision(self) -> int | None:
        return self._emc2101.get_product_revision()

    def describe_device(self):
        return self._emc2101.describe_device()

    # ---------------------------------------------------------------------
    # fan speed control
    # ---------------------------------------------------------------------

    def configure_spinup_behaviour(self, spinup_strength: SpinUpStrength, spinup_duration: SpinUpDuration, fast_mode: bool) -> bool:
        """
        configure the spin-up behavior for the attached fan (duration and
        strength). This helps to ensure the fan has sufficient power
        available to be able to start spinning the rotor.
         - EMC2101 enters the spin-up routine any time it transitions
           from a minimum fan setting (00h) to a higher fan setting
         - EMC2101 does not invoke the spin-up routine upon power up
         - setting a strength of 0% or duration of 0s disables spin-up entirely

        Once spin-up has completed the fan speed is reduced to the programmed setting.

        Please note: Fast_mode is ignored if pin 6 is in alert mode.
        """
        if self._pin_six_mode == PinSixMode.TACHO:
            self._emc2101.configure_spinup_behaviour(spinup_strength=spinup_strength, spinup_duration=spinup_duration, fast_mode=fast_mode)
            return True
        elif self._pin_six_mode == PinSixMode.ALERT:
            LH.warning("Pin 6 is in alert mode. Can't configure spinup behavior.")
            return False
        else:
            raise NotImplementedError("unsupported pin 6 mode")

    def get_rpm(self) -> int | None:
        return self._emc2101.get_rpm()

    def get_fixed_speed(self, unit: FanSpeedUnit = FanSpeedUnit.PERCENT) -> int | None:
        step = self._emc2101.get_driver_strength()
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
                    step_cur = self._emc2101.get_driver_strength()
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
                    step_cur = self._emc2101.get_driver_strength()
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
        self._emc2101.set_driver_strength(step)
        # convert applied value back to original unit and return
        if unit == FanSpeedUnit.PERCENT:
            return self._scs.convert_step2percent(step)
        elif unit == FanSpeedUnit.RPM:
            return self._scs.convert_step2rpm(step)
        else:
            return step

    def is_lookup_table_enabled(self) -> bool:
        return self._emc2101.is_lookup_table_enabled()

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
        return self._emc2101.update_lookup_table(values=lut_table)

    def reset_lookup_table(self):
        self._emc2101.reset_lookup_table()

    # ---------------------------------------------------------------------
    # temperature measurements
    # ---------------------------------------------------------------------

    def get_temperature_conversion_rate(self) -> str:
        """
        get the number of temperature conversions per second
        """
        return self._emc2101.get_temperature_conversion_rate()

    def get_temperature_conversion_rates(self) -> list[str]:
        """
        returns all available temperature conversion rates
        """
        return list(CONVERSIONS_PER_SECOND.keys())

    def set_temperature_conversion_rate(self, conversion_rate: str) -> bool:
        """
        set the number of temperature conversions per second
        """
        return self._emc2101.set_temperature_conversion_rate(conversion_rate=conversion_rate)

    def get_chip_temperature(self) -> float:
        """
        get internal sensor temperature in °C

        the datasheet guarantees a precision of +/- 2°C
        """
        return self._emc2101.get_chip_temperature()

    def get_chip_temperature_limit(self) -> float:
        return self._emc2101.get_chip_temperature_limit()

    def set_chip_temperature_limit(self, value: float):
        self._emc2101.set_chip_temperature_limit(value=value)

    def get_external_sensor_state(self) -> ExternalSensorStatus:
        return self._emc2101.get_external_sensor_state()

    def has_external_sensor(self) -> bool:
        return self._emc2101.has_external_sensor()

    def get_sensor_temperature(self) -> float:
        """
        get external sensor temperature in °C

        the datasheet guarantees a precision of +/- 1°C
        """
        return self._emc2101.get_sensor_temperature()

    def get_sensor_temperature_limit(self, limit_type: TemperatureLimitType) -> float:
        """
        get upper/lower temperature alerting limit in °C
        """
        if limit_type == TemperatureLimitType.TO_COLD:
            return self._emc2101.get_sensor_low_temperature_limit()
        elif limit_type == TemperatureLimitType.TO_HOT:
            return self._emc2101.get_sensor_high_temperature_limit()
        else:
            raise ValueError("invalid limit type")

    def set_sensor_temperature_limit(self, value: float, limit_type: TemperatureLimitType) -> float:
        """
        set upper/lower temperature alerting limit in °C

        The fractional part has limited precision and will be clamped to the
        nearest available step. The clamped value is returned to the caller.
        """
        if limit_type == TemperatureLimitType.TO_COLD:
            return self._emc2101.set_sensor_low_temperature_limit(value=value)
        elif limit_type == TemperatureLimitType.TO_HOT:
            return self._emc2101.set_sensor_high_temperature_limit(value=value)
        else:
            raise ValueError("invalid limit type")

    def force_temperature_conversion(self):
        """
        performs a one-shot conversion
        """
        self._emc2101.force_temperature_conversion()

    def force_temperature(self, temperature: float):
        """
        force external sensor to read a specific temperature

        (this is useful to debug the lookup table)
        """
        self._emc2101.force_temperature(temperature=temperature)

    def clear_temperature(self):
        """
        clear a previously forced temperature reading
        """
        self._emc2101.clear_temperature()

    # ---------------------------------------------------------------------
    # convenience functions
    # ---------------------------------------------------------------------

    def read_fancfg_register(self) -> int:
        # described in datasheet section 6.16 "Fan Configuration Register"
        # 0b00000000
        #         ^^-- tachometer input mode
        #        ^---- clock frequency override
        #       ^----- clock select
        #      ^------ polarity (0 = 100->0, 1 = 0->100)
        #     ^------- configure lookup table (0 = on, 1 = off)
        return self._emc2101.read_fancfg_register()

    def write_fancfg_register(self, value: int):
        # described in datasheet section 6.16 "Fan Configuration Register"
        # 0b00000000
        #         ^^-- tachometer input mode
        #        ^---- clock frequency override
        #       ^----- clock select
        #      ^------ polarity (0 = 100->0, 1 = 0->100)
        #     ^------- configure lookup table (0 = on, 1 = off)
        self._emc2101.write_fancfg_register(value=value)

    def read_device_registers(self) -> dict[int, int]:
        return self._emc2101.read_device_registers()

    def reset_device_registers(self):
        return self._emc2101.reset_device_registers()

    def configure_external_temperature_sensor(self, ets_config: ExternalTemperatureSensorConfig):
        dif = ets_config.diode_ideality_factor
        bcf = ets_config.beta_compensation_factor
        self._emc2101.configure_external_temperature_sensor(dif=dif, bcf=bcf)


def parse_fanconfig_register(value: int) -> dict[str, Any]:
    # 0b00000000
    #         ^^-- tachometer input mode
    #        ^---- clock frequency override
    #       ^----- clock select
    #      ^------ polarity (0 = 100->0, 1 = 0->100)
    #     ^------- configure lookup table (0 = on, 1 = off)
    config = {
        "tachometer input mode":    value & 0b0000_0011,
        "clock frequency override":     'use frequency divider' if value & 0b0000_0100 else 'use clock select',
        "clock select base frequency":  '1.4kHz' if value & 0b0000_1000 else '360kHz',
        "polarity":                     '0x00 = 100%, 0xFF = 0%' if value & 0b0001_0000 else '0x00 = 0%, 0xFF = 100%',
        "configure lookup table":       'allow dutycycle update' if value & 0b0010_0000 else 'disable dutycycle update',
        "external temperature setting": 'override external temperature' if value & 0b0100_0000 else 'measure external temperature',
        # the highest bit is unused
    }
    return config
