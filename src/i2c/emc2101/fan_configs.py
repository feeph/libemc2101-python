#!/usr/bin/env python3
"""
"""

# basically a dataclass/attrs, but attrs are not available on CircuitPython
class FanConfig:

    def __init__(self, minimum_duty_cycle: int, maximum_duty_cycle: int, minimum_rpm: int, maximum_rpm: int):
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

# a reasonable configuration
# (some fans treat a duty cycle of less than 20% as no signal and go full power)
generic_pwm_fan = FanConfig(minimum_duty_cycle=20, maximum_duty_cycle=100, minimum_rpm=100, maximum_rpm=2000)
