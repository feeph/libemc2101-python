#!/usr/bin/env python3
"""
"""

# a reimplementation of https://github.com/adafruit/Adafruit_CircuitPython_EMC2101
# Datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf

import logging
import math
import time

from typing import Dict, Optional

import adafruit_emc2101
import busio

from .fan_configs import FanConfig, generic_pwm_fan


LH = logging.getLogger(__name__)


class I2cDevice:

    def __init__(self, i2c_bus: busio.I2C, i2c_address: int = 0x4c):
        self._i2c_bus = i2c_bus
        self._i2c_adr = i2c_address

    def read_register(self, register: int) -> Optional[int]:
        """
        read a single byte register and return its content as an integer value
        """
        buf_r = bytearray(1)
        buf_r[0] = register
        buf_w = bytearray(1)
        try:
            self._i2c_bus.writeto_then_readfrom(address=self._i2c_adr, buffer_out=buf_r, buffer_in=buf_w)
            return buf_w[0]
        except RuntimeError as e:
            logging.error("[%s] Unable to read register 0x%02x: %s", __name__, register, e)
            return

    def write_register(self, register: int, value: int):
        buf = bytearray(2)
        buf[0] = register
        buf[1] = value & 0xFF
        # function does not return any values
        self._i2c_bus.writeto(address=self._i2c_adr, buffer=buf)


class Emc2101:

    def __init__(self, i2c_bus: busio.I2C, i2c_address: int = 0x4c, fan_config: FanConfig = generic_pwm_fan):
        # -- use Adafruit EMC2101 during development --
        if i2c_bus is not None and i2c_address is not None:
            self._emc2101 = adafruit_emc2101.EMC2101(i2c_bus=i2c_bus)
        # -- our own internals --
        self._i2c_device = I2cDevice(i2c_bus=i2c_bus, i2c_address=i2c_address)
        self._duty_min = fan_config.minimum_duty_cycle
        self._duty_max = fan_config.maximum_duty_cycle
        self._rpm_min = fan_config.minimum_rpm
        self._rpm_max = fan_config.maximum_rpm


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

    def get_current_rpm(self) -> int:
        # count = 0
        # count |= self._i2c_device.read_register(0x46, 1)         # lower 8 bits
        # count |= (self._i2c_device.read_register(0x47, 1) << 1)  # upper 8 bits
        # count &= 0b1100000000000000                          # mask bits 14 & 15
        # return int(5400000/count)
        return int(self._emc2101.fan_speed)

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

    def get_config(self) -> int:
        # the register is described in datasheet section 6.16 "Fan Configuration Register"
        # 0b00000000
        #         ^^-- tachometer input mode
        #        ^---- clock frequency override
        #       ^----- clock select
        #      ^------ polarity (0 = 100->0, 1 = 0->100)
        #     ^------- configure lookup table (0 = on, 1 = off)
        return self._i2c_device.read_register(0x4A)

    def get_dutycycle(self) -> int:
        return self._i2c_device.read_register(0x4C)

    # the PWM driver included in the EMC2101 has, at most, 64 steps equalling 1.5% resolution
    def set_dutycycle(self, value: int) -> int | None:
        """
        set the fan duty cycle
         - clamp to minimum/maximum as defined by the fan configuration
         - returns the effective, clamped value or 'None' if no value was set
        """
        # clamp to desired min/max
        if value < self._duty_min:
            value = self._duty_min
        if value > self._duty_max:
            value = self._duty_max
        # TODO decide whether an active lookup table should take precedence and prevent setting
        config_register = self._i2c_device.read_register(0x4A)
        if not config_register & 0b00010000:
            LH.debug("Disabling lookup table.")
            config_register |= 0b00010000
            self._i2c_device.write_register(0x4A, config_register)
        else:
            LH.debug("Lookup table is already disabled.")
        # set duty cycle (range: 0 <= x <= 64 ??)
        self._i2c_device.write_register(0x4C, value)
        return value

    def get_minimum_dutycycle(self) -> int:
        return self._duty_min

    def get_maximum_dutycycle(self) -> int:
        return self._duty_max

    def get_chip_temperature(self) -> float:
        return float(self._i2c_device.read_register(0x00))

    def get_chip_temperature_limit(self) -> float:
        return float(self._i2c_device.read_register(0x05))

    def set_chip_temperature_limit(self, value: float):
        self._i2c_device.write_register(0x05, int(value))

    def get_sensor_temperature(self) -> float:
        # 0x01 high byte
        # 0x10 low byte
        return math.nan

    def get_sensor_temperature_limit(self) -> float:
        # External Temp High Limit
        #   0x07 high byte
        #   0x13 low byte
        # External Temp Low Limit
        #   0x08 high byte
        #   0x14 low byte
        return 60.0

    def set_sensor_temperature_limit(self, value: float):
        # External Temp High Limit
        #   0x07 high byte
        #   0x13 low byte
        # External Temp Low Limit
        #   0x08 high byte
        #   0x14 low byte
        pass

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
            rpm_cur = self.get_current_rpm()
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
            rpm = self.get_current_rpm()
            LH.debug("duty cycle: %2i rpm: %4i", duty_cycle, rpm)
            # TODO determine cut-off threshold was reached and set self._duty_min
        fan_config = FanConfig(minimum_duty_cycle=self._duty_min, maximum_duty_cycle=self._duty_max, minimum_rpm=self._rpm_min, maximum_rpm=self._rpm_max)
        return fan_config
