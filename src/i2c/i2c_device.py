#!/usr/bin/env python3
"""
"""

import logging

# module busio provides no type hints
import busio  # type: ignore

LH = logging.getLogger("i2c")


class I2cDevice:

    def __init__(self, i2c_bus: busio.I2C, i2c_address: int):
        self._i2c_bus = i2c_bus
        self._i2c_adr = i2c_address

    def read_register(self, register: int, max_tries: int = 3) -> int:
        """
        read a single byte register and return its content as an integer value
         - may raise a RuntimeError if there were too many errors
        """
        buf_r = bytearray(1)
        buf_r[0] = register
        buf_w = bytearray(1)
        for cur_try in range(1, 1 + max_tries):
            try:
                self._i2c_bus.writeto_then_readfrom(address=self._i2c_adr, buffer_out=buf_r, buffer_in=buf_w)
                return buf_w[0]
            except OSError as e:
                # [Errno 121] Remote I/O error
                LH.debug("[%s] Failed to read register 0x%02X (%i/%i): %s",  __name__, register, cur_try, max_tries, e)
            except RuntimeError as e:
                LH.debug("[%s] Unable to read register 0x%02X (%i/%i): %s", __name__, register, cur_try, max_tries, e)
        else:
            raise RuntimeError(f"Unable to read register 0x{register:02X} after {cur_try} attempts. Giving up.")

    def write_register(self, register: int, value: int, max_tries: int = 3):
        """
        write a single byte register and return
         - may raise a RuntimeError if there were too many errors
        """
        buf = bytearray(2)
        buf[0] = register
        buf[1] = value & 0xFF
        for cur_try in range(1, 1 + max_tries):
            try:
                # function does not return any values
                self._i2c_bus.writeto(address=self._i2c_adr, buffer=buf)
                return
            except OSError as e:
                # [Errno 121] Remote I/O error
                LH.warning("[%s] Failed to write register 0x%02X (%i/%i): %s",  __name__, register, cur_try, max_tries, e)
        else:
            raise RuntimeError(f"Unable to write register 0x{register:02X} after {cur_try} attempts. Giving up.")
