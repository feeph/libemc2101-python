#!/usr/bin/env python3
"""
"""

from enum import Enum

class RpmControlMode(Enum):
    DC  = 1  # use supply voltage to control fan speed (2 and 3 pin fans)
    PWM = 2  # use pulse width modulation to control fan speed (4 pin fans)

# basically a dataclass/attrs, but attrs are not available on CircuitPython
class FanConfig:

    def __init__(self, rpm_control_mode: RpmControlMode, minimum_duty_cycle: int, maximum_duty_cycle: int, minimum_rpm: int, maximum_rpm: int):
        self.rpm_control_mode = rpm_control_mode
        if minimum_duty_cycle > maximum_duty_cycle:
            raise ValueError("minimum duty cycle must be smaller than maximum duty cycle")
        if minimum_duty_cycle >= 0:
            self.minimum_duty_cycle = minimum_duty_cycle
        else:
            raise ValueError("minimum duty cycle can't be negative")
        if maximum_duty_cycle <= 100:
            self.maximum_duty_cycle = maximum_duty_cycle
        else:
            raise ValueError("maximum duty cycle can't exceed 100%")
        self.minimum_rpm = minimum_rpm
        self.maximum_rpm = maximum_rpm

# provide reasonable default configurations for DC and PWM fans

# probably a bad idea to provide less than 50% supply voltage (fan might fail to start properly)
generic_dc_fan = FanConfig(rpm_control_mode=RpmControlMode.DC, minimum_duty_cycle=50, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000)

# some fans treat a duty cycle of less than 20% as 'no signal' and go full speed instead
generic_pwm_fan = FanConfig(rpm_control_mode=RpmControlMode.PWM, minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000)
