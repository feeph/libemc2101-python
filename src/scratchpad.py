#!/usr/bin/env python3

import logging
import sys
import time

import board
import busio
import colorama
import coloredlogs
import i2c.emc2101


LH = logging.getLogger('main')


if __name__ == '__main__':
    if len(sys.argv) > 1 and '-v' in sys.argv[1:]:
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
    emc2101.enable_tacho_pin()
    # ---------------------------------------------------------------------
    cfg_register = emc2101._i2c_device.read_register(0x03)
    LH.info("config register:              0x%02x (0b%s)", cfg_register, format(cfg_register, '08b'))

    emc2101._i2c_device.write_register(0x4b, 0x3f)

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
    LH.info("current fan speed:      %4iRPM", emc2101.get_current_rpm())

    # fan_config = emc2101.calibrate()
    # LH.info("minimum duty cycle: %4i%%", fan_config.minimum_duty_cycle)
    # LH.info("maximum fan speed:  %4iRPM", fan_config.maximum_rpm)

    # emc2101.set_dutycycle(100, disable_lut=True)
    # time.sleep(2)
    # emc2101.get_fan_speed()

    # emc2101._i2c_device.read_register()
