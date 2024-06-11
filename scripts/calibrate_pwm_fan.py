#!/usr/bin/env python3
"""
determine the fan configuration for the connected fan

usage:
  - scripts/calibrate_pwm_fan.py "Lian-Li UniFan SL140"
  - scripts/calibrate_pwm_fan.py -f 22500 "Lian-Li UniFan SL140"
"""

import argparse
import logging
import sys

import board
import busio
import yaml

from i2c.emc2101 import calibrate_pwm_fan, export_fan_config

LH = logging.getLogger("main")


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname).1s: %(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser(prog="Test1", description="identify fan parameters")
    parser.add_argument("-f", "--pwm-frequency", type=int, default=22500)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("model", type=str)
    args = parser.parse_args()

    if args.verbose:
        LH.setLevel(level=logging.DEBUG)

    i2c_bus = busio.I2C(scl=board.SCL, sda=board.SDA)
    fan_profile = calibrate_pwm_fan(i2c_bus=i2c_bus, model=args.model, pwm_frequency=args.pwm_frequency)
    if fan_profile is not None:
        LH.info("minimum RPM:        %4iRPM", fan_profile.minimum_rpm)
        LH.info("maximum RPM:        %4iRPM", fan_profile.maximum_rpm)
        LH.info("minimum duty cycle: %4i%%", fan_profile.minimum_duty_cycle)
        LH.info("maximum duty cycle: %4i%%", fan_profile.maximum_duty_cycle)

        data = export_fan_config(fan_config=fan_profile)
        print("---")
        print(yaml.dump(data, indent=4))
        sys.exit(0)
    else:
        LH.warning("Unable to calibrate the fan!")
        sys.exit(0)
