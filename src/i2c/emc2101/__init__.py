#!/usr/bin/env python3
"""
"""

# a reimplementation of https://github.com/adafruit/Adafruit_CircuitPython_EMC2101
# Datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf

import logging
import time

from enum import Enum
from typing import Dict, Optional

import busio

from i2c.i2c_device import I2cDevice
from .fan_configs import FanConfig, RpmControlMode, generic_pwm_fan


LH = logging.getLogger(__name__)

MANUFACTURER_IDS = {
    0x5D: "SMSC",
}

PRODUCT_IDS = {
    0x16: "EMC2101",
    0x28: "EMC2101R",
}

# number of temperature conversions per second
CONVERSIONS_PER_SECOND = {
    "1/16": 0b0000,
    "1/8":  0b0001,
    "1/4":  0b0010,
    "1/2":  0b0011,
    "1":    0b0100,
    "2":    0b0101,
    "4":    0b0110,
    "8":    0b0111,
    "16":   0b1000,
    "32":   0b1001, # and all unlisted values
}

class DutyCycleControlMode(Enum):
    MANUAL      = 1  # use manual control
    LOOKUPTABLE = 2  # use lookup table


class DutyCycleValue(Enum):
    RAW_VALUE  = 1
    PERCENTAGE = 2


class LimitType(Enum):
    LOWER = 1
    UPPER = 2


class PinSixMode(Enum):
    """
    Pin 6 is dualpurpose. It can either be used to send an interrupt or
    for reading the fan's tacho signal.
    """
    ALERT = 1  # assert if temperature range is exceeded
    TACHO = 2  # receive fan tacho signal


class SpinUpStrength(Enum):
    BYPASS       = 0b0000_0000  # bypass spin-up cycle
    STRENGTH_50  = 0b0000_1000  # drive at 50% speed
    STRENGTH_75  = 0b0001_0000  # drive at 75% speed
    STRENGTH_100 = 0b0001_1000  # drive at 100% speed (default)


class SpinUpDuration(Enum):
    TIME_0_00 = 0b0000_0000  # bypass spin-up cycle
    TIME_0_05 = 0b0000_0001  # 0.05s
    TIME_0_10 = 0b0000_0010  # 0.10s
    TIME_0_20 = 0b0000_0011  # 0.20s
    TIME_0_40 = 0b0000_0100  # 0.40s
    TIME_0_80 = 0b0000_0101  # 0.80s
    TIME_1_60 = 0b0000_0110  # 1.60s
    TIME_3_20 = 0b0000_0111  # 3.20s (default)


class DeviceConfig:

    def __init__(self, rpm_control_mode: RpmControlMode, pin_six_mode: PinSixMode, ideality_factor: int, beta_factor: int):
        """
        configure hardware-specific settings

        These settings depend on the EMC2101 and its supporting electric circuit.
        """
        self.i2c_address              = 0x4C              # address is hardcoded
        self.rpm_control_mode         = rpm_control_mode  # supply voltage or PWM
        self.pin_six_mode             = pin_six_mode      # interrupt pin or tacho sense
        self.diode_ideality_factor    = ideality_factor   # datasheet section 6.12
        self.beta_compensation_factor = beta_factor       # datasheet section 6.13


emc2101_default_config = DeviceConfig(rpm_control_mode=RpmControlMode.VOLTAGE, pin_six_mode=PinSixMode.ALERT, ideality_factor=0x12, beta_factor=0x08)


def _convert_dutycycle_percentage2raw(value: int) -> int:
    """
    convert the provided value from percentage to the internal value
    used by EMC2101 (0% -> 0x00, 100% -> 0x3F)
    """
    # 0x3F = 63
    if 0 <= value <= 100:
        return round(value * 63 / 100)
    else:
        raise ValueError("Percentage value must be in range 0 ≤ x ≤ 100!")


def _convert_dutycycle_raw2percentage(value: int) -> int:
    """
    convert the provided value from the internal value to percentage
    used by EMC2101 (0x00 -> 0%, 0x3F -> 100%)
    """
    # 0x3F = 63
    if 0 <= value <= 63:
        return round(value * 100 / 63)
    else:
        raise ValueError("Raw value must be in range 0 ≤ x ≤ 63!")


def _convert_temperature_raw2value(msb: int, lsb:int) -> float:
    """
    convert the provided temperature from internal value to float
    (0x0C + 0xE0 -> 13.9)
    """
    temp = float(msb)
    if lsb & 0b1000_0000:
        temp += 0.50
    if lsb & 0b0100_0000:
        temp += 0.25
    if lsb & 0b0010_0000:
        temp += 0.15
    return temp


def _convert_temperature_value2raw(value: float) -> tuple[int, int]:
    """
    convert the provided temperature from float to the internal value
    (13.9 -> 0x0C + 0xE0)
    """
    msb = int(value)
    lsb = 0x00
    fraction = value - msb  # 0.00..0.99
    if fraction >= 0.5:
        lsb |= 0b1000_0000
        fraction -= 0.5
    if fraction >= 0.25:
        lsb |= 0b0100_0000
        fraction -= 0.25
    if fraction >= 0.15:
        lsb |= 0b0010_0000
        fraction -= 0.15
    return (msb, lsb)


def _convert_rpm2tach(rpm: int) -> tuple[int, int]:
    # due to the way the conversion works the RPM can never
    # be less than 82
    if rpm < 82:
        raise ValueError("RPM can't be lower than 82")
    tach = int(5_400_000/rpm)
    tach = 4096
    msb = (tach & 0xFF00) >> 8
    lsb = tach & 0x00FF
    return (msb, lsb)


def _convert_tach2rpm(msb: int, lsb: int) -> int | None:
    """
    convert the raw values to an RPM value

    returns 'None' if the reading is invalid
    """
    tach = (msb << 8) + lsb
    # 0xFFFF = invalid value
    if tach < 0xFFFF:
        rpm = int(5_400_000/tach)
        return rpm
    else:
        return


def _verify_value_range(value: int, value_range: tuple[int, int]):
    lower_limit = value_range[0]
    upper_limit = value_range[1]
    if value < lower_limit or value > upper_limit:
        raise ValueError(f"provided value {value} is out of range ({lower_limit} ≤ x ≤ {upper_limit})")


def _clamp_to_range(value: int, value_range: tuple[int, int]) -> int:
    value = max(value, value_range[0])
    value = min(value, value_range[1])
    return value


DEFAULTS = {
    #     value           purpose                             section
    # -----------------------------------------------------------------
    0x03: 0b0000_0000,  # configuration register               6.5
    0x04: 0b0000_1000,  # conversion register                  6.6
    # temperature limit registers                              6.7
    0x05: 0b0100_0110,  # internal sensor
    0x07: 0b0100_0110,  # external diode, high limit, MSB
    0x08: 0b0000_0000,  # external diode, low limit,  MSB
    0x13: 0b0000_0000,  # external diode, high limit, LSB
    0x14: 0b0000_0000,  # external diode, low limit,  LSB
    0x19: 0b0101_0101,  # critical temperature threshold
    0x21: 0b0000_1010,  # critical temperature hysteresis
    # -------------------------
    0x0C: 0b0000_0000,  # external temperature (forced)        6.8
    0x11: 0b0000_0000,  # scratchpad #1                        6.10
    0x12: 0b0000_0000,  # scratchpad #2                        6.10
    0x16: 0b1010_0100,  # alert mask                           6.11
    0x17: 0b0001_0010,  # external ideality                    6.12
    0x18: 0b0000_1000,  # beta compensation                    6.13
    0x48: 0b1111_1111,  # tach limit, LSB                      6.15
    0x49: 0b1111_1111,  # tach limit, MSB                      6.15
    0x4A: 0b0010_0000,  # fan configuration                    6.16
    0x4B: 0b0011_1111,  # fan spinup configuration             6.17
    0x4C: 0b0000_0000,  # fan setting                          6.18
    0x4D: 0b0001_0111,  # pwm frequency                        6.19
    0x4E: 0b0000_0001,  # pwm frequency divide                 6.20
    0x4F: 0b0000_0100,  # fan control lookup table hysteresis  6.21
    # fan control lookup table                                 6.22
    # -------------------------
    0xBF: 0b0000_0000,  # averaging filter                     6.23
}


class Emc2101:

    def __init__(self, i2c_bus: busio.I2C, device_config: DeviceConfig = emc2101_default_config, fan_config: FanConfig = generic_pwm_fan):
        if not is_fan_compatible(device_config=device_config, fan_config=fan_config):
            raise RuntimeError("fan is not compatible with this device")
        self._i2c_device   = I2cDevice(i2c_bus=i2c_bus, i2c_address=device_config.i2c_address)
        self._control_mode = _configure_control_mode(self._i2c_device, device_config.rpm_control_mode)
        self._pin_six_mode = _configure_pin_six_mode(self._i2c_device, device_config.pin_six_mode)
        self._duty_min     = _convert_dutycycle_percentage2raw(fan_config.minimum_duty_cycle)
        self._duty_max     = _convert_dutycycle_percentage2raw(fan_config.maximum_duty_cycle)
        # configure lowest expected RPM value
        _configure_minimum_rpm(self._i2c_device, minimum_rpm=fan_config.minimum_rpm)

    def get_manufacturer_id(self) -> Optional[int]:
        """
        read the manufacturer ID
        (0x5d for SMSC)
        """
        return self._i2c_device.read_register(0xFE)

    def get_product_id(self):
        """
        read the product ID
        (0x16 for EMC2101, 0x28 for EMC2101-R)
        """
        return self._i2c_device.read_register(0xFD)

    def get_product_revision(self):
        return self._i2c_device.read_register(0xFF)

    def describe_device(self):
        manufacturer_id   = self._i2c_device.read_register(0xFE)
        manufacturer_name = MANUFACTURER_IDS.get(manufacturer_id, "<unknown manufacturer>")
        product_id        = self._i2c_device.read_register(0xFD)
        product_name      = PRODUCT_IDS.get(product_id, "<unknown product>")
        product_revision  = self._i2c_device.read_register(0xFF)
        return f"{manufacturer_name} (0x{manufacturer_id:02X}) {product_name} (0x{product_id:02X}) (rev: {product_revision})"

    # ---------------------------------------------------------------------
    # fan speed control
    # ---------------------------------------------------------------------

    def get_rpm_control_mode(self) -> RpmControlMode:
        """
        is fan speed controlled by DAC or PWM?
        """
        cfg_register_value = self._i2c_device.read_register(0x03)
        if cfg_register_value & 0b0001_0000:
            return RpmControlMode.VOLTAGE
        else:
            return RpmControlMode.PWM

    def set_rpm_control_mode(self, mode: RpmControlMode):
        """
        choose between DAC or PWM to control fan speed
        """
        self._control_mode = _configure_control_mode(self._i2c_device, mode)

    def configure_spinup_behaviour(self, spinup_strength: SpinUpStrength, spinup_duration: SpinUpDuration, fast_mode: bool):
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
        value = 0x00
        # configure spin up time
        value |= spinup_duration.value
        # configure spin up strength (dutycycle)
        value |= spinup_strength.value
        if fast_mode:
            value |= 0b0010_0000
        self._i2c_device.write_register(0x4B, value)

    def get_rpm(self) -> int | None:
        # check if tacho mode is enabled
        if self._pin_six_mode != PinSixMode.TACHO:
            LH.warning("Pin six is not configured for tacho mode. Please enable tacho mode.")
            return
        # get tacho readings
        tach_lsb = self._i2c_device.read_register(0x46)  # TACH Reading Low Byte
        tach_msb = self._i2c_device.read_register(0x47)  # TACH Reading High Byte
        LH.debug("tach readings: LSB=0x%02X MSB=0x%02X", tach_lsb, tach_msb)
        return _convert_tach2rpm(msb=tach_msb, lsb=tach_lsb)

    def read_fancfg_register(self) -> int:
        # described in datasheet section 6.16 "Fan Configuration Register"
        # 0b00000000
        #         ^^-- tachometer input mode
        #        ^---- clock frequency override
        #       ^----- clock select
        #      ^------ polarity (0 = 100->0, 1 = 0->100)
        #     ^------- configure lookup table (0 = on, 1 = off)
        return self._i2c_device.read_register(0x4A)

    def write_fancfg_register(self, value: int):
        # described in datasheet section 6.16 "Fan Configuration Register"
        # 0b00000000
        #         ^^-- tachometer input mode
        #        ^---- clock frequency override
        #       ^----- clock select
        #      ^------ polarity (0 = 100->0, 1 = 0->100)
        #     ^------- configure lookup table (0 = on, 1 = off)
        self._i2c_device.write_register(0x4A, value & 0xFF)

    def get_dutycycle(self, value_type: DutyCycleValue = DutyCycleValue.PERCENTAGE) -> int:
        value = self._i2c_device.read_register(0x4C)
        if value_type == DutyCycleValue.PERCENTAGE:
            return _convert_dutycycle_raw2percentage(value)
        else:
            return value

    # the PWM driver included in the EMC2101 has, at most, 64 steps equalling ~1.5% resolution
    def set_dutycycle(self, value: int, value_type: DutyCycleValue = DutyCycleValue.PERCENTAGE, disable_lut: bool = False) -> int | None:
        """
        set the fan duty cycle
         - clamp to minimum/maximum as defined by the fan configuration
         - returns the effective, clamped value or 'None' if no value was set
        """
        if value_type == DutyCycleValue.PERCENTAGE:
            _verify_value_range(value, (0, 100))
            LH.debug("Converting percentage value to internal value.")
            value = _convert_dutycycle_percentage2raw(value)
        elif value_type == DutyCycleValue.RAW_VALUE:
            _verify_value_range(value, (0, 63))
        else:
            raise ValueError("unsupported value type")
        # clamp provided value to desired minimum/maximum
        value = _clamp_to_range(value, (self._duty_min, self._duty_max))
        # step 1) change programming mode and enable updates
        #   0b..0._.... = use lookup table
        #   0b..1._.... = use manual control
        # please note: must be set to 0b..1._.... before lut or pwm setting
        config_register = self._i2c_device.read_register(0x4A)
        if not config_register & 0b0010_0000:
            if disable_lut:
                LH.info("Lookup table is enabled and 'disable_lut' is set. Disabling.")
                self._i2c_device.write_register(0x4A, config_register | 0b0010_0000)
            else:
                LH.warning("Lookup table is enabled. Use 'disable_lut=True' to override.")
                return
        else:
            LH.debug("Lookup table is already disabled. Using fan setting register.")
        # step 2) set new duty cycle (range: 0 ≤ x ≤ 63)
        self._i2c_device.write_register(0x4C, value)
        # # step 3) restore
        # self._i2c_device.write_register(0x4A, config_register & 0b0000_0000)
        if value_type == DutyCycleValue.PERCENTAGE:
            return _convert_dutycycle_raw2percentage(value)
        else:
            return value

    def get_minimum_dutycycle(self) -> int:
        return _convert_dutycycle_raw2percentage(self._duty_min)

    def get_maximum_dutycycle(self) -> int:
        return _convert_dutycycle_raw2percentage(self._duty_max)

    def update_lookup_table(self, values: Dict[int, int]):
        if len(values) > 8:
            raise ValueError("Temperature lookup table must have at most 8 entries!")
        # TODO send I²C command to update the lookup table
        # 0x50..0x5f (8 x 2 registers; temp->duty)

    def delete_lookup_table(self):
        buf = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        return self._i2c_device.write_register(0x50, 16, buf)

    # ---------------------------------------------------------------------
    # temperature measurements
    # ---------------------------------------------------------------------

    def get_temperature_conversion_rate(self) -> str:
        """
        get the number of temperature conversions per second
        """
        value = self._i2c_device.read_register(0x04)
        value = min(value, 0b1001)  # all values larger than 0b1001 map to 0b1001
        return [k for k, v in CONVERSIONS_PER_SECOND.items() if v == value][0]

    def get_temperature_conversion_rates(self) -> list[str]:
        """
        returns all available temperature conversion rates
        """
        return CONVERSIONS_PER_SECOND.keys()

    def set_temperature_conversion_rate(self, conversion_rate: str) -> bool:
        """
        set the number of temperature conversions per second
        """
        value = CONVERSIONS_PER_SECOND.get(conversion_rate)
        if value is not None:
            self._i2c_device.write_register(0x04, value)
            return True
        else:
            return False

    def get_chip_temperature(self) -> float:
        return float(self._i2c_device.read_register(0x00))

    def get_chip_temperature_limit(self) -> float:
        return float(self._i2c_device.read_register(0x05))

    def set_chip_temperature_limit(self, value: float):
        self._i2c_device.write_register(0x05, int(value))

    def get_sensor_temperature(self) -> float:
        """
        set external sensor temperature in °C
        """
        msb = self._i2c_device.read_register(0x01)  # 0x01 high byte
        lsb = self._i2c_device.read_register(0x10)  # 0x10 low byte
        return _convert_temperature_raw2value(msb, lsb)

    def get_sensor_temperature_limit(self, limit_type: LimitType) -> float:
        """
        set upper/lower temperature alerting limit in °C
        """
        if limit_type == LimitType.LOWER:
            msb = self._i2c_device.read_register(0x08)
            lsb = self._i2c_device.read_register(0x14)
            return _convert_temperature_raw2value(msb, lsb)
        elif limit_type == LimitType.UPPER:
            msb = self._i2c_device.read_register(0x07)
            lsb = self._i2c_device.read_register(0x13)
            return _convert_temperature_raw2value(msb, lsb)
        else:
            raise ValueError("invalid limit type")

    def set_sensor_temperature_limit(self, value: float, limit_type: LimitType):
        """
        set upper/lower temperature alerting limit in °C

        The fractional part has limited precision and will be clamped to the
        nearest available step. The clamped value is returned to the caller.
        """
        if value < 0 or value > 85:
            raise ValueError("temperature limit out of range (0 ≤ x ≤ 85°C)")
        (msb, lsb) = _convert_temperature_value2raw(value)
        if limit_type == LimitType.LOWER:
            reg_msb = 0x08
            reg_lsb = 0x14
        elif limit_type == LimitType.UPPER:
            reg_msb = 0x07
            reg_lsb = 0x13
        else:
            raise ValueError("invalid limit type")
        self._i2c_device.write_register(reg_msb, msb)
        self._i2c_device.write_register(reg_lsb, lsb)
        return _convert_temperature_raw2value(msb, lsb)

    # convenience functions

    def calibrate(self) -> FanConfig:
        """
        walk through various duty cycle settings and determine the fan's
        configuration parameters
        """
        LH.info("Calibrating fan parameters. This will take a few seconds.")
        # remove all limits
        self._duty_min = 0
        self._duty_max = 100
        self._rpm_min = 0
        self._rpm_max = -1
        # TODO verify that duty cycle changes influence the fan's speed
        # ...
        # determine maximum RPM
        self.set_dutycycle(100)
        has_settled = False
        rpm_ref = -1
        rpm_cur = 0
        while not has_settled:
            time.sleep(1)
            rpm_cur = self.get_rpm()
            if (rpm_ref/10) != (rpm_cur/10):  # RPM will never be exactly the same
                LH.debug("not settled: ref=%i, cur=%i", rpm_ref, rpm_cur)
                rpm_ref = rpm_cur
            else:
                LH.debug("has settled: cur=%i", rpm_cur)
                has_settled = True
        self._rpm_max = rpm_cur
        # determine minimum duty cycle
        for duty_cycle in range(30, -1, -5):
            self.set_dutycycle(duty_cycle)
            time.sleep(0.5)
            rpm = self.get_rpm()
            LH.debug("duty cycle: %2i rpm: %4i", duty_cycle, rpm)
            # TODO determine cut-off threshold was reached and set self._duty_min
        fan_config = FanConfig(rpm_control_mode=self._control_mode, minimum_duty_cycle=self._duty_min, maximum_duty_cycle=self._duty_max, minimum_rpm=self._rpm_min, maximum_rpm=self._rpm_max)
        return fan_config

    def read_device_registers(self) -> dict[int, int]:
        registers = {}
        for register in DEFAULTS.keys():
            registers[register] = self._i2c_device.read_register(register)
        return registers

    def reset_device_registers(self):
        LH.debug("Resetting all device registers to their default values.")
        for register, value in DEFAULTS.items():
            self._i2c_device.write_register(register, value)


def is_fan_compatible(device_config: DeviceConfig, fan_config: FanConfig) -> bool:
    """
    The supporting circuit for EMC2101 is wired for a specific configuration.
    If we connect a fan that expects a different configuration it won't work.
    """
    is_compatible = False
    if device_config.rpm_control_mode == RpmControlMode.VOLTAGE:
        # emc2101: supply voltage, fan: supply voltage -> works
        if fan_config.rpm_control_mode == RpmControlMode.VOLTAGE:
            LH.info("EMC2101 and connected fan both use supply voltage to control fan speed. Good.")
            is_compatible = True
        # emc2101: supply voltage, fan: PWM -> may work
        elif fan_config.rpm_control_mode == RpmControlMode.PWM:
            LH.warning("EMC2101 uses supply voltage but fan expects PWM. RPM control kind of works.")
            is_compatible = True
        else:
            raise ValueError("fan has unsupported rpm control mode")
    elif device_config.rpm_control_mode == RpmControlMode.PWM:
        # emc2101: PWM, fan: supply voltage -> will not work
        if fan_config.rpm_control_mode == RpmControlMode.VOLTAGE:
            LH.error("EMC2101 uses PWM but fan is controlled via supply voltage! RPM control will not work as expected!")
            is_compatible = False
        # emc2101: PWM, fan: PWM -> works
        elif device_config.rpm_control_mode == RpmControlMode.PWM:
            LH.info("EMC2101 and connected fan both use PWM to control fan speed. Good.")
            is_compatible = True
        else:
            raise ValueError("fan has unsupported rpm control mode")
    else:
        raise ValueError("device has unsupported rpm control mode")
    return is_compatible


def parse_fanconfig_register(value: int) -> dict[str, str]:
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


def _configure_control_mode(i2c_device: I2cDevice, control_mode: RpmControlMode) -> RpmControlMode:
    if control_mode == RpmControlMode.VOLTAGE:
        # set 0x03.4 to 1
        cfg_register_value = i2c_device.read_register(0x03)
        i2c_device.write_register(0x03, cfg_register_value | 0b0001_0000)
        return RpmControlMode.VOLTAGE
    elif control_mode == RpmControlMode.PWM:
        # set 0x03.4 to 0
        cfg_register_value = i2c_device.read_register(0x03)
        i2c_device.write_register(0x03, cfg_register_value & 0b1110_1111)
        return RpmControlMode.PWM
    else:
        raise NotImplementedError("unsupported RPM control mode")


def _configure_pin_six_mode(i2c_device: I2cDevice, pin_six_mode: PinSixMode) -> PinSixMode:
    if pin_six_mode == PinSixMode.ALERT:
        # set 0x03.2 to 0
        cfg_register_value = i2c_device.read_register(0x03)
        i2c_device.write_register(0x03, cfg_register_value & 0b1111_1011)
        return PinSixMode.ALERT
    elif pin_six_mode == PinSixMode.TACHO:
        # set 0x03.2 to 1
        cfg_register_value = i2c_device.read_register(0x03)
        i2c_device.write_register(0x03, cfg_register_value | 0b0000_0100)
        return PinSixMode.TACHO
    else:
        raise NotImplementedError("unsupported pin 6 mode")


def _configure_minimum_rpm(i2c_device: I2cDevice, minimum_rpm: int):
    """
    configure the expected minimum RPM value

    if the measured RPM is below this RPM the fan is considered to be
    not spinning and the TACH bit is set

    due to the way the RPM is measured the lowest possible value is 82 RPM
    """
    (msb, lsb) = _convert_rpm2tach(minimum_rpm)
    i2c_device.write_register(0x48, lsb)  # TACH Limit Low Byte
    i2c_device.write_register(0x49, msb)  # TACH Limit High Byte
