#!/usr/bin/env python3
"""
"""

# a reimplementation of https://github.com/adafruit/Adafruit_CircuitPython_EMC2101
# Datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf

import logging
import math
import time

from enum import Enum
from typing import Dict, Optional

import adafruit_emc2101
import busio

from i2c.i2c_device import I2cDevice
from .fan_configs import FanConfig, RpmControlMode, generic_pwm_fan


LH = logging.getLogger(__name__)


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


def _convert_dutycycle_percentage2raw(value: int) -> int:
    """
    convert the provided value from percentage to the internal value
    used by EMC2101 (0% -> 0x00, 100% -> 0x3F)
    """
    # 0x3F = 63
    if value >= 0 and value <= 100:
        return round(value * 63 / 100)
    else:
        raise ValueError("Percentage value must be in range 0 <= x <= 100!")


def _convert_dutycycle_raw2percentage(value: int) -> int:
    """
    convert the provided value from the internal value to percentage
    used by EMC2101 (0x00 -> 0%, 0x3F -> 100%)
    """
    # 0x3F = 63
    if value >= 0 and value <= 63:
        return round(value * 100 / 63)
    else:
        raise ValueError("Raw value must be in range 0 <= x <= 63!")


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

    def __init__(self, i2c_bus: busio.I2C, i2c_address: int = 0x4C, fan_config: FanConfig = generic_pwm_fan):
        # -- use Adafruit EMC2101 during development --
        # if i2c_bus is not None and i2c_address is not None:
        #     self._emc2101 = adafruit_emc2101.EMC2101(i2c_bus=i2c_bus)
        # -- our own internals --
        self._i2c_device   = I2cDevice(i2c_bus=i2c_bus, i2c_address=i2c_address)
        self._duty_min     = _convert_dutycycle_percentage2raw(fan_config.minimum_duty_cycle)
        self._duty_max     = _convert_dutycycle_percentage2raw(fan_config.maximum_duty_cycle)
        self._pin_six      = None  # will be initialize when needed
        self._control_mode = None  # will be initialize when needed
        self._rpm_min      = fan_config.minimum_rpm
        self._rpm_max      = fan_config.maximum_rpm

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

    def enable_tacho_pin(self):
        """
        must select between /ALERT and TACHO
        """
        LH.debug("Configuring pin 6 as tacho signal.")
        cfg_register_value = self._i2c_device.read_register(0x03)
        self._i2c_device.write_register(0x03, cfg_register_value | 0b0000_0100)

    def get_rpm_control_mode(self) -> RpmControlMode:
        """
        is fan speed controlled by DAC or PWM?
        """
        cfg_register_value = self._i2c_device.read_register(0x03)
        if cfg_register_value & 0b0001_0000:
            return RpmControlMode.DC
        else:
            return RpmControlMode.PWM

    def set_rpm_control_mode(self, mode: RpmControlMode):
        """
        choose between DAC or PWM to control fan speed
        """
        if mode == RpmControlMode.DAC:
            LH.debug("Using supply voltage to control fan speed.")
            cfg_register_value = self._i2c_device.read_register(0x03)
            self._i2c_device.write_register(0x03, cfg_register_value | 0b0001_0000)
        elif mode == RpmControlMode.PWM:
            LH.debug("Using PWM signal to control fan speed.")
            cfg_register_value = self._i2c_device.read_register(0x03)
            self._i2c_device.write_register(0x03, cfg_register_value & 0b1110_1111)
        else:
            raise ValueError("Usage error. Please provide correct input value.")

    def get_rpm(self) -> int | None:
        # initialize if needed
        if self._pin_six is None:
            if self._i2c_device.read_register(0x03) & 0b0000_0100:
                self._pin_six = PinSixMode.TACHO
            else:
                self._pin_six = PinSixMode.ALERT
        # step 1) verify tacho mode is configured
        if self._pin_six != PinSixMode.TACHO:
            LH.warning("Pin six is not configured for tacho mode. Please enable tacho mode.")
            return
        # step 2) get tach readings
        tach_lsb = self._i2c_device.read_register(0x46)
        tach_msb = self._i2c_device.read_register(0x47)
        LH.debug("tach readings: LSB=0x%02X MSB=0x%02X", tach_lsb, tach_msb)
        tach_total = tach_lsb + (tach_msb << 8)
        LH.debug("tach readings: %i, 0x%04X", tach_total, tach_total)
        # step 3) convert counter value to RPM
        if tach_total != 0xFFFF:
            return 5_400_000 / tach_total
        else:
            # unable to read a meaningful value
            return

    def get_minimum_rpm(self):
        count = 0
        count |= self._i2c_device.read_register(0x48, 1)         # lower 8 bits
        count |= (self._i2c_device.read_register(0x49, 1) << 1)  # upper 8 bits
        return int(5400000/count)

    def set_minimum_rpm(self, value: int):
        """
        This value defines the minimum possible value that the fan can
        spin at. If a value below this limit is detected the fan is
        considered to have stopped.
        """
        # TODO divide by 5400000
        # TODO set lower (0x48) and higher (0x49) 9 bits
        pass

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
    def set_dutycycle(self, value: int, disable_lut: bool = False, value_type: DutyCycleValue = DutyCycleValue.PERCENTAGE) -> int | None:
        """
        set the fan duty cycle
         - clamp to minimum/maximum as defined by the fan configuration
         - returns the effective, clamped value or 'None' if no value was set
        """
        if value_type == DutyCycleValue.PERCENTAGE:
            LH.debug("Converting percentage value to internal value.")
            value = _convert_dutycycle_percentage2raw(value)
        # clamp provide value to desired min/max
        if value < self._duty_min:
            value = self._duty_min
        if value > self._duty_max:
            value = self._duty_max
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
        # step 2) set new duty cycle (range: 0 <= x <= 63)
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
        """
        if value < 0 or value > 85:
            raise ValueError("temperature limit out of range (0 < =x <= 85°C)")
        (msb, lsb) = _convert_temperature_value2raw(value)
        if limit_type == LimitType.LOWER:
            self._i2c_device.write_register(0x08, msb)
            self._i2c_device.write_register(0x14, lsb)
        elif limit_type == LimitType.UPPER:
            self._i2c_device.write_register(0x07, msb)
            self._i2c_device.write_register(0x13, lsb)
            pass
        else:
            raise ValueError("invalid limit type")

    def update_lookup_table(self, values: Dict[int, int]):
        if len(values) > 8:
            raise ValueError("Temperature lookup table must have at most 8 entries!")
        # TODO send I²C command to update the lookup table
        # 0x50..0x5f (8 x 2 registers; temp->duty)

    def delete_lookup_table(self):
        buf = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        return self._i2c_device.write_register(0x50, 16, buf)

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
        fan_config = FanConfig(minimum_duty_cycle=self._duty_min, maximum_duty_cycle=self._duty_max, minimum_rpm=self._rpm_min, maximum_rpm=self._rpm_max)
        return fan_config

    def read_device_registers(self) -> dict[int, int]:
        registers = {}
        for register in DEFAULTS.keys():
            registers[register] = value = self._i2c_device.read_register(register)
        return registers

    def reset_device_registers(self):
        LH.debug("Resetting all device registers to their default values.")
        for register, value in DEFAULTS.items():
            self._i2c_device.write_register(register, value)


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
