#!/usr/bin/env python3
"""
a reimplementation of https://github.com/adafruit/Adafruit_CircuitPython_EMC2101

The main design goal is to hide as many low-level details as possible while
making the code comprehensible. Additionally we want to leverage as much
tool-based development support as possible.
"""

# typical usage scenarios
# =======================

# calibrate an unknown PWM fan
# -> automatically identify the fan's parameters and create a fan profile
# -------------------------------------------------------------------------
# import board
# import busio
# import yaml
#
# from i2c.emc2101.emc2101_pwm import DeviceConfig, Emc2101_PWM, PinSixMode, RpmControlMode
# from i2c.emc2101.fan_config import export_fan_config
#
# i2c_bus = busio.I2C(scl=board.SCL, sda=board.SDA)
#
# device_config = DeviceConfig(rpm_control_mode=RpmControlMode.PWM, pin_six_mode=PinSixMode.TACHO)
# emc2101 = Emc2101_PWM(i2c_bus=i2c_bus, device_config=device_config, fan_config=generic_pwm_fan)
# my_fan = emc2101.calibrate_pwm_fan(model="My fan", pwm_frequency=22500)
#
# with open('fan_config.yaml', 'w') as fh:
#   yaml.dump(export_fan_config(my_fan), fh)
# -------------------------------------------------------------------------

# control a PWM fan
# -> load a fan profile and manage the fan
# -------------------------------------------------------------------------
# import board
# import busio
#
# from i2c.emc2101.emc2101_pwm import DeviceConfig, Emc2101_PWM, PinSixMode, RpmControlMode
#
# with open('fan_config.yaml', 'r') as fh:
#   my_fan = import_fan_config(yaml.load(fh))
#
# device_config = DeviceConfig(rpm_control_mode=RpmControlMode.PWM, pin_six_mode=PinSixMode.TACHO)
# emc2101 = Emc2101_PWM(i2c_bus=i2c_bus, device_config=device_config, fan_config=my_fan)
# print("RPM:", emc2101.get_rpm()
# -------------------------------------------------------------------------

# the following imports are provided for user convenience
# flake8: noqa: F401
from i2c.emc2101.emc2101_core import CONVERSIONS_PER_SECOND, DEFAULTS, SpinUpDuration, SpinUpStrength
from i2c.emc2101.emc2101_pwm import DeviceConfig, Emc2101_PWM, ExternalTemperatureSensorConfig, FanSpeedUnit, PinSixMode, TemperatureLimitType, emc2101_default_config, ets_2n3904, ets_2n3906
from i2c.emc2101.fan_configs import FanConfig, RpmControlMode, Steps, generic_pwm_fan
