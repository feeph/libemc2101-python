#!/usr/bin/env python3

import logging

import adafruit_emc2101
import board
import busio
import colorama
import coloredlogs
import i2c.emc2101


LH = logging.getLogger('main')

# wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/libgpiod.py
# .venv/bin/python3 libgpiod.py

if __name__ == '__main__':
    colorama.init()
    coloredlogs.install(level='INFO', fmt='%(levelname).1s: %(message)s')

    i2c_bus = busio.I2C(scl=board.SCL, sda=board.SDA)
    emc2101 = i2c.emc2101.Emc2101(i2c_bus=i2c_bus)
    LH.debug("id: 0x%02x, revision: %i", emc2101.get_product_id(), emc2101.get_product_revision())
    LH.info("config register:          0x%02x", emc2101.get_config())
    LH.info("chip temperature:       %4.1f°C", emc2101.get_chip_temperature())
    emc2101.set_chip_temperature_limit(70.5)
    LH.info("chip temperature limit: %4.1f°C", emc2101.get_chip_temperature_limit())
    emc2101.set_dutycycle(50)
    LH.info("duty cycle:             %4i%%", emc2101.get_dutycycle())
    emc2101.set_dutycycle(60)
    LH.info("duty cycle:             %4i%% (min: %i%%, max: %i%%)", emc2101.get_dutycycle(), emc2101.get_minimum_dutycycle(), emc2101.get_maximum_dutycycle())
    LH.info("current fan speed:      %4iRPM", emc2101.get_current_rpm())
    fan_config = emc2101.calibrate()
    LH.info("minimum duty cycle: %4i%%", fan_config.minimum_duty_cycle)
    LH.info("maximum fan speed:  %4iRPM", fan_config.maximum_rpm)
