#!/usr/bin/env python3
"""
"""

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import board
import busio
import colorama
import coloredlogs
import i2c.emc2101


LH = logging.getLogger('main')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Test1', description='test & development script')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        verbosity = 'DEBUG'
    else:
        verbosity = 'INFO'

    colorama.init()
    coloredlogs.install(level=verbosity, fmt='%(levelname).1s: %(message)s')

    i2c_bus = busio.I2C(scl=board.SCL, sda=board.SDA)
    emc2101 = i2c.emc2101.Emc2101(i2c_bus=i2c_bus)
    LH.debug("id: 0x%02x, revision: %i", emc2101.get_product_id(), emc2101.get_product_revision())
    # ---------------------------------------------------------------------
    emc2101.reset_device_registers()
    emc2101.set_rpm_control_mode(mode=i2c.emc2101.RpmControlMode.PWM)
    emc2101.enable_tacho_pin()
    # ---------------------------------------------------------------------
    cfg_register = emc2101._i2c_device.read_register(0x03)
    LH.info("config register:              0x%02x (0b%s)", cfg_register, format(cfg_register, '08b'))

    emc2101._i2c_device.write_register(0x4b, 0x1f)

    fancfg_register = emc2101.read_fancfg_register()
    LH.info("fan config register:          0x%02x (0b%s)", fancfg_register, format(fancfg_register, '08b'))
    # ---------------------------------------------------------------------
    LH.info("chip temperature:       %4.1f°C", emc2101.get_chip_temperature())
    emc2101.set_chip_temperature_limit(70.5)
    LH.info("chip temperature limit: %4.1f°C", emc2101.get_chip_temperature_limit())
    emc2101.set_dutycycle(50, disable_lut=True)
    LH.info("duty cycle:             %4i%% (min: %i%%, max: %i%%)", emc2101.get_dutycycle(), emc2101.get_minimum_dutycycle(), emc2101.get_maximum_dutycycle())
    emc2101.set_dutycycle(60, disable_lut=True)
    LH.info("duty cycle:             %4i%% (min: %i%%, max: %i%%)", emc2101.get_dutycycle(), emc2101.get_minimum_dutycycle(), emc2101.get_maximum_dutycycle())

    while True:
        rpm = emc2101.get_rpm()
        if rpm is not None:
            LH.info("current fan speed: %4iRPM", rpm)
        else:
            LH.info("current fan speed: <n/a>")
        time.sleep(2)
mc
    # fan_config = emc2101.calibrate()
    # LH.info("minimum duty cycle: %4i%%", fan_config.minimum_duty_cycle)
    # LH.info("maximum fan speed:  %4iRPM", fan_config.maximum_rpm)

    # emc2101.set_dutycycle(100, disable_lut=True)
    # time.sleep(2)
    # emc2101.get_fan_speed()

    # emc2101._i2c_device.read_register()
