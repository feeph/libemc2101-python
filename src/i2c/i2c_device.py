#!/usr/bin/env python3
"""
"""

import logging

from typing import Dict, Optional

import busio

class I2cDevice:

    def __init__(self, i2c_bus: busio.I2C, i2c_address: int):
        self._i2c_bus = i2c_bus
        self._i2c_adr = i2c_address

    def read_register(self, register: int) -> int | None:
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
            logging.error("[%s] Unable to read register 0x%02X: %s", __name__, register, e)
            return

    def write_register(self, register: int, value: int):
        buf = bytearray(2)
        buf[0] = register
        buf[1] = value & 0xFF
        # function does not return any values
        self._i2c_bus.writeto(address=self._i2c_adr, buffer=buf)
