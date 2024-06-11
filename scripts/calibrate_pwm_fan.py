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

from i2c.emc2101 import DeviceConfig, Emc2101, PinSixMode, RpmControlMode, generic_pwm_fan
from i2c.emc2101.fan_configs import export_fan_config

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

    i2c_scl_pin = board.SCL
    i2c_sda_pin = board.SDA
    i2c_bus = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin)
    device_config = DeviceConfig(rpm_control_mode=RpmControlMode.PWM, pin_six_mode=PinSixMode.TACHO)
    emc2101 = Emc2101(i2c_bus=i2c_bus, device_config=device_config, fan_config=generic_pwm_fan)

    fan_config = emc2101.calibrate_pwm_fan(model=args.model, pwm_frequency=args.pwm_frequency)
    if fan_config is not None:
        LH.info("minimum RPM:        %4iRPM", fan_config.minimum_rpm)
        LH.info("maximum RPM:        %4iRPM", fan_config.maximum_rpm)
        LH.info("minimum duty cycle: %4i%%", fan_config.minimum_duty_cycle)
        LH.info("maximum duty cycle: %4i%%", fan_config.maximum_duty_cycle)

        data = export_fan_config(fan_config=fan_config)
        print("---")
        print(yaml.dump(data, indent=4))
        sys.exit(0)
    else:
        LH.warning("Unable to calibrate the fan!")
        sys.exit(0)
