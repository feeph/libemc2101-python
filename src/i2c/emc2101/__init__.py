#!/usr/bin/env python3
"""
"""

# a reimplementation of https://github.com/adafruit/Adafruit_CircuitPython_EMC2101
# Datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf

import logging
import time

from enum import Enum
from typing import Dict, Optional

import busio

from i2c.emc2101.fan_configs import FanConfig, RpmControlMode, generic_pwm_fan
from i2c.emc2101.conversions import convert_bytes2temperature, convert_temperature2bytes
from i2c.emc2101.scs import SpeedControlSetter
from i2c.i2c_device import I2cDevice


LH = logging.getLogger(__name__)


DEFAULTS = {
    #     value           purpose                             section
    # -----------------------------------------------------------------
    0x03: 0b0000_0000,  # configuration register               6.5
    0x04: 0b0000_1000,  # conversion register                  6.6
    # temperature limit registers                              6.7
    0x05: 0b0100_0110,  # internal sensor
    0x07: 0b0100_0110,  # external diode, high limit, MSB
    0x08: 0b0000_0000,  # external diode, low limit,  MSB
    0x13: 0b0000_0000,  # external diode, high limit, LSB
    0x14: 0b0000_0000,  # external diode, low limit,  LSB
    0x19: 0b0101_0101,  # critical temperature threshold
    0x21: 0b0000_1010,  # critical temperature hysteresis
    # -------------------------
    0x0C: 0b0000_0000,  # external temperature (forced)        6.8
    0x11: 0b0000_0000,  # scratchpad #1                        6.10
    0x12: 0b0000_0000,  # scratchpad #2                        6.10
    0x16: 0b1010_0100,  # alert mask                           6.11
    0x17: 0b0001_0010,  # external ideality                    6.12
    0x18: 0b0000_1000,  # beta compensation                    6.13
    0x48: 0b1111_1111,  # tach limit, LSB                      6.15
    0x49: 0b1111_1111,  # tach limit, MSB                      6.15
    0x4A: 0b0010_0000,  # fan configuration                    6.16
    0x4B: 0b0011_1111,  # fan spinup configuration             6.17
    0x4C: 0b0000_0000,  # fan setting                          6.18
    0x4D: 0b0001_0111,  # pwm frequency                        6.19
    0x4E: 0b0000_0001,  # pwm frequency divide                 6.20
    0x4F: 0b0000_0100,  # fan control lookup table hysteresis  6.21
    # fan control lookup table                                 6.22
    # -------------------------
    0xBF: 0b0000_0000,  # averaging filter                     6.23
}


MANUFACTURER_IDS = {
    0x5D: "SMSC",
}


PRODUCT_IDS = {
    0x16: "EMC2101",
    0x28: "EMC2101R",
}


# number of temperature conversions per second
CONVERSIONS_PER_SECOND = {
    "1/16": 0b0000,
    "1/8":  0b0001,
    "1/4":  0b0010,
    "1/2":  0b0011,
    "1":    0b0100,
    "2":    0b0101,
    "4":    0b0110,
    "8":    0b0111,
    "16":   0b1000,
    "32":   0b1001, # and all unlisted values
}


class DutyCycleControlMode(Enum):
    MANUAL      = 1  # use manual control
    LOOKUPTABLE = 2  # use lookup table


class FanSpeedUnit(Enum):
    STEP    = 1  #   0..15
    RPM     = 2  # 100..2000RPM
    PERCENT = 3  #  20..100%


class PinSixMode(Enum):
    """
    Pin 6 is dualpurpose. It can either be used to send an interrupt or
    for reading the fan's tacho signal.
    """
    ALERT = 1  # assert if temperature range is exceeded
    TACHO = 2  # receive fan tacho signal


class SpinUpStrength(Enum):
    BYPASS       = 0b0000_0000  # bypass spin-up cycle
    STRENGTH_50  = 0b0000_1000  # drive at 50% speed
    STRENGTH_75  = 0b0001_0000  # drive at 75% speed
    STRENGTH_100 = 0b0001_1000  # drive at 100% speed (default)


class SpinUpDuration(Enum):
    TIME_0_00 = 0b0000_0000  # bypass spin-up cycle
    TIME_0_05 = 0b0000_0001  # 0.05s
    TIME_0_10 = 0b0000_0010  # 0.10s
    TIME_0_20 = 0b0000_0011  # 0.20s
    TIME_0_40 = 0b0000_0100  # 0.40s
    TIME_0_80 = 0b0000_0101  # 0.80s
    TIME_1_60 = 0b0000_0110  # 1.60s
    TIME_3_20 = 0b0000_0111  # 3.20s (default)


class DeviceConfig:

    def __init__(self, rpm_control_mode: RpmControlMode, pin_six_mode: PinSixMode):
        """
        configure hardware-specific settings

        These settings depend on the EMC2101 and its supporting electric circuit.
        """
        self.i2c_address              = 0x4C              # address is hardcoded
        self.rpm_control_mode         = rpm_control_mode  # supply voltage or PWM
        self.pin_six_mode             = pin_six_mode      # interrupt pin or tacho sense


emc2101_default_config = DeviceConfig(rpm_control_mode=RpmControlMode.VOLTAGE, pin_six_mode=PinSixMode.ALERT)


class ExternalTemperatureSensorConfig:

    def __init__(self, ideality_factor: int, beta_factor: int):
        """
        configure hardware-specific settings

        These settings depend on the external temperature sensor's characteristics.
        """
        self.diode_ideality_factor    = ideality_factor   # datasheet section 6.12
        self.beta_compensation_factor = beta_factor       # datasheet section 6.13


# temperature sensitive transistors
ets_2n3904 = ExternalTemperatureSensorConfig(ideality_factor=0x12, beta_factor=0x08)  # 2N3904 (NPN)
ets_2n3906 = ExternalTemperatureSensorConfig(ideality_factor=0x12, beta_factor=0x08)  # 2N3906 (PNP)

class StatusRegister:
    """
    ```
    self.tach      the TACH count has exceeded the TACH Limit
    self.tcrit     external diode temperature has met or exceeded the TCRIT limit
    self.fault     a diode fault has occurred on the external diode
    self.ext_low   external diode temperature has fallen below the low limit
    self.ext_high  external diode temperature has exceeded the high limit
    self.eeprom    indicates that the EEPROM could not be found
    self.int_high  internal temperature has met or exceeded the high limit
    self.busy      indicates that the ADC is converting - does not trigger an interrupt
    ```
    """

    def __init__(self, i2c_device: I2cDevice, register: int = 0x02):
        self._register = register
        self.update(i2c_device)

    def update(self, i2c_device: I2cDevice):
        value = i2c_device.read_register(self._register)
        self.tach     = value & 0b0000_0001
        self.tcrit    = value & 0b0000_0010
        self.fault    = value & 0b0000_0100
        self.ext_low  = value & 0b0000_1000
        self.ext_high = value & 0b0001_0000
        self.eeprom   = value & 0b0010_0000
        self.int_high = value & 0b0100_0000
        self.busy     = value & 0b1000_0000


class TemperatureLimitType(Enum):
    TO_COLD = 1
    TO_HOT  = 2


# TODO add convenience function to refresh state
# TODO auto-refresh state every x seconds (if desired)
class Emc2101:

    def __init__(self, i2c_bus: busio.I2C, device_config: DeviceConfig = emc2101_default_config, fan_config: FanConfig = generic_pwm_fan, ets_config: ExternalTemperatureSensorConfig = ets_2n3904):
        self._i2c_device = I2cDevice(i2c_bus=i2c_bus, i2c_address=device_config.i2c_address)
        self._status = StatusRegister(i2c_device=self._i2c_device)
        # configure RPM-related settings
        self._pin_six_mode = _configure_pin_six_mode(self._i2c_device, device_config.pin_six_mode)
        _configure_minimum_rpm(self._i2c_device, minimum_rpm=fan_config.minimum_rpm)
        self._max_rpm = fan_config.maximum_rpm
        # configure speed control setter (DAC or PWM)
        self._scs = self._configure_speed_control_setter(i2c_device=self._i2c_device, device_config=device_config, fan_config=fan_config)
        # configure external temperature sensor
        self._i2c_device.write_register(0x12, ets_config.diode_ideality_factor)
        self._i2c_device.write_register(0x18, ets_config.beta_compensation_factor)

    def get_manufacturer_id(self) -> Optional[int]:
        """
        read the manufacturer ID
        (0x5d for SMSC)
        """
        return self._i2c_device.read_register(0xFE)

    def get_product_id(self):
        """
        read the product ID
        (0x16 for EMC2101, 0x28 for EMC2101-R)
        """
        return self._i2c_device.read_register(0xFD)

    def get_product_revision(self):
        return self._i2c_device.read_register(0xFF)

    def describe_device(self):
        manufacturer_id   = self._i2c_device.read_register(0xFE)
        manufacturer_name = MANUFACTURER_IDS.get(manufacturer_id, "<unknown manufacturer>")
        product_id        = self._i2c_device.read_register(0xFD)
        product_name      = PRODUCT_IDS.get(product_id, "<unknown product>")
        product_revision  = self._i2c_device.read_register(0xFF)
        return f"{manufacturer_name} (0x{manufacturer_id:02X}) {product_name} (0x{product_id:02X}) (rev: {product_revision})"

    # ---------------------------------------------------------------------
    # fan speed control
    # ---------------------------------------------------------------------

    def configure_spinup_behaviour(self, spinup_strength: SpinUpStrength, spinup_duration: SpinUpDuration, fast_mode: bool) -> bool:
        """
        configure the spin-up behavior for the attached fan (duration and
        strength). This helps to ensure the fan has sufficient power
        available to be able to start spinning the rotor.
         - EMC2101 enters the spin-up routine any time it transitions
           from a minimum fan setting (00h) to a higher fan setting
         - EMC2101 does not invoke the spin-up routine upon power up
         - setting a strength of 0% or duration of 0s disables spin-up entirely

        Once spin-up has completed the fan speed is reduced to the programmed setting.

        Please note: Fast_mode is ignored if pin 6 is in alert mode.
        """
        if self._pin_six_mode == PinSixMode.TACHO:
            value = 0x00
            # configure spin up time
            value |= spinup_duration.value
            # configure spin up strength (dutycycle)
            value |= spinup_strength.value
            if fast_mode:
                value |= 0b0010_0000
            self._i2c_device.write_register(0x4B, value)
            return True
        elif self._pin_six_mode == PinSixMode.ALERT:
            LH.warning("Pin 6 is in alert mode. Can't configure spinup behavior.")
            return False
        else:
            raise NotImplementedError("unsupported pin 6 mode")

    def get_rpm(self) -> int | None:
        # check if tacho mode is enabled
        if self._pin_six_mode != PinSixMode.TACHO:
            LH.warning("Pin six is not configured for tacho mode. Please enable tacho mode.")
            return
        # get tacho readings
        # (the order of is important; see datasheet section 6.1 for details)
        tach_lsb = self._i2c_device.read_register(0x46)  # TACH Reading Low Byte, must be read first!
        tach_msb = self._i2c_device.read_register(0x47)  # TACH Reading High Byte
        LH.debug("tach readings: LSB=0x%02X MSB=0x%02X", tach_lsb, tach_msb)
        return _convert_tach2rpm(msb=tach_msb, lsb=tach_lsb)

    def get_fixed_speed(self, unit: FanSpeedUnit = FanSpeedUnit.PERCENT) -> int:
        step = self._i2c_device.read_register(0x4C)
        if unit == FanSpeedUnit.PERCENT:
            return self._scs.convert_step2percent(step)
        elif unit == FanSpeedUnit.RPM:
            return self._scs.convert_step2rpm(step)
        else:
            return step

    def set_fixed_speed(self, value: int, unit: FanSpeedUnit = FanSpeedUnit.PERCENT, disable_lut: bool = False) -> int:
        """
        set the fan speed
         - clamp to minimum/maximum as defined by the fan configuration
         - returns the effective, clamped value or 'None' if no value was set
        """
        # calculate step (driver strength)
        if unit == FanSpeedUnit.PERCENT:
            _verify_value_range(value, (0, 100))
            LH.debug("Converting percentage to internal value.")
            step = self._scs.convert_percent2step(value)
        elif unit == FanSpeedUnit.RPM:
            _verify_value_range(value, (0, self._max_rpm)) # minimum & maximum RPM
            LH.debug("Converting RPM to internal value.")
            step = self._scs.convert_rpm2step(value)
        elif unit == FanSpeedUnit.STEP:
            if self._scs.is_valid_step(value):
                step = value
            else:
                raise ValueError(f"provided value {value} is not a valid step")
        else:
            raise ValueError("unsupported value type")
        # apply step
        self._i2c_device.write_register(0x4C, step)
        # convert applied value to original unit and return
        if unit == FanSpeedUnit.PERCENT:
            return self._scs.convert_step2percent(step)
        elif unit == FanSpeedUnit.RPM:
            return self._scs.convert_step2rpm(step)
        else:
            return step

    def update_lookup_table(self, values: Dict[int, int], unit: FanSpeedUnit = FanSpeedUnit.PERCENT) -> bool:
        """
        populate the lookup table with the provided values and
        sets all unused values to zero

        returns 'True' if the lookup table was updated and 'False' if it wasn't.
        """
        if self.has_external_sensor():
            if len(values) > 8:
                raise ValueError("too many entries in lookup table (max: 8)")
            temp_min = 0
            temp_max = 100
            lut_table = {}
            for temp, value in values.items():
                if not temp_min <= temp <= temp_max:
                    raise ValueError("temperature is out of range")
                if unit == FanSpeedUnit.PERCENT:
                    step = self._scs.convert_percent2step(value)
                elif unit == FanSpeedUnit.RPM:
                    step = self._scs.convert_rpm2step(value)
                elif unit == FanSpeedUnit.STEP:
                    if self._scs.is_valid_step(value):
                        step = value
                    else:
                        raise ValueError("invalid step value")
                else:
                    raise ValueError("unknown value type")
                lut_table[temp] = step
            # -------------------------------------------------------------
            # 0x50..0x5f (8 x 2 registers; temp->duty)
            offset = 0
            # TODO do we have to switch to manual mode to be able to update?
            # set provided value
            for temp, step in lut_table.items():
                self._i2c_device.write_register(0x50 + offset, temp)
                self._i2c_device.write_register(0x51 + offset, step)
                offset += 2
            # fill remaining slots
            for offset in range(offset, 16, 2):
                self._i2c_device.write_register(0x50 + offset, 0x00)
                self._i2c_device.write_register(0x51 + offset, 0x00)
            return True
        else:
            LH.warning("Using the lookup table requires an external temperature sensor!")
            return False

    def reset_lookup_table(self):
        # set all slots to zero
        for offset in range(0, 16, 2):
            self._i2c_device.write_register(0x50 + offset, 0x00)
            self._i2c_device.write_register(0x51 + offset, 0x00)

    # ---------------------------------------------------------------------
    # temperature measurements
    # ---------------------------------------------------------------------

    def get_temperature_conversion_rate(self) -> str:
        """
        get the number of temperature conversions per second
        """
        value = self._i2c_device.read_register(0x04)
        value = min(value, 0b1001)  # all values larger than 0b1001 map to 0b1001
        return [k for k, v in CONVERSIONS_PER_SECOND.items() if v == value][0]

    def get_temperature_conversion_rates(self) -> list[str]:
        """
        returns all available temperature conversion rates
        """
        return CONVERSIONS_PER_SECOND.keys()

    def set_temperature_conversion_rate(self, conversion_rate: str) -> bool:
        """
        set the number of temperature conversions per second
        """
        value = CONVERSIONS_PER_SECOND.get(conversion_rate)
        if value is not None:
            self._i2c_device.write_register(0x04, value)
            return True
        else:
            return False

    def get_chip_temperature(self) -> float:
        """
        get internal sensor temperature in °C

        the datasheet guarantees a precision of +/- 2°C
        """
        LH.error("get_chip_temperature(): %0.1f", self._i2c_device.read_register(0x00))
        return float(self._i2c_device.read_register(0x00))

    def get_chip_temperature_limit(self) -> float:
        return float(self._i2c_device.read_register(0x05))

    def set_chip_temperature_limit(self, value: float):
        self._i2c_device.write_register(0x05, int(value))

    def has_external_sensor(self) -> bool:
        self._status.update(i2c_device=self._i2c_device)
        return not self._status.fault

    def get_sensor_temperature(self) -> float:
        """
        get external sensor temperature in °C

        the datasheet guarantees a precision of +/- 1°C
        """
        msb = self._i2c_device.read_register(0x01)  # high byte, must be read first!
        lsb = self._i2c_device.read_register(0x10)  # low byte
        return convert_bytes2temperature(msb, lsb)

    def get_sensor_temperature_limit(self, limit_type: TemperatureLimitType) -> float:
        """
        get upper/lower temperature alerting limit in °C
        """
        if limit_type == TemperatureLimitType.TO_COLD:
            msb = self._i2c_device.read_register(0x08)
            lsb = self._i2c_device.read_register(0x14)
            return convert_bytes2temperature(msb, lsb)
        elif limit_type == TemperatureLimitType.TO_HOT:
            msb = self._i2c_device.read_register(0x07)
            lsb = self._i2c_device.read_register(0x13)
            return convert_bytes2temperature(msb, lsb)
        else:
            raise ValueError("invalid limit type")

    def set_sensor_temperature_limit(self, value: float, limit_type: TemperatureLimitType) -> float:
        """
        set upper/lower temperature alerting limit in °C

        The fractional part has limited precision and will be clamped to the
        nearest available step. The clamped value is returned to the caller.
        """
        if value < 0 or value > 85:
            raise ValueError("temperature limit out of range (0 ≤ x ≤ 85°C)")
        (msb, lsb) = convert_temperature2bytes(value)
        if limit_type == TemperatureLimitType.TO_COLD:
            reg_msb = 0x08
            reg_lsb = 0x14
        elif limit_type == TemperatureLimitType.TO_HOT:
            reg_msb = 0x07
            reg_lsb = 0x13
        else:
            raise ValueError("invalid limit type")
        self._i2c_device.write_register(reg_msb, msb)
        self._i2c_device.write_register(reg_lsb, lsb)
        return convert_bytes2temperature(msb, lsb)

    def force_temperature_conversion(self):
        """
        performs a one-shot conversion
        """
        self._i2c_device.write_register(0x0F, 0x00)

    def force_temperature(self, temperature: float):
        """
        force external sensor to read a specific temperature

        (this is useful to debug the lookup table)
        """
        # write register
        self._i2c_device.write_register(0x0C, temperature)
        # force reading from register
        fan_config = self._i2c_device.read_register(0x4A)
        self._i2c_device.write_register(0x4A, fan_config | 0b0100_0000)

    def clear_temperature(self):
        """
        clear a previously forced temperature reading
        """
        # stop reading from register
        fan_config = self._i2c_device.read_register(0x4A)
        self._i2c_device.write_register(0x4A, fan_config & 0b1011_1111)
        # reset register to default state
        self._i2c_device.write_register(0x0C, 0x00)

    # ---------------------------------------------------------------------
    # convenience functions
    # ---------------------------------------------------------------------

    def calibrate(self) -> FanConfig:
        """
        walk through various duty cycle settings and determine the fan's
        configuration parameters
        """
        LH.info("Calibrating fan parameters. This will take a few seconds.")
        # remove all limits
        self._duty_min = 0
        self._duty_max = 100
        self._rpm_min = 0
        self._rpm_max = -1
        # TODO verify that duty cycle changes influence the fan's speed
        # ...
        # determine maximum RPM
        self.set_dutycycle(100)
        has_settled = False
        rpm_ref = -1
        rpm_cur = 0
        while not has_settled:
            time.sleep(1)
            rpm_cur = self.get_rpm()
            if (rpm_ref/10) != (rpm_cur/10):  # RPM will never be exactly the same
                LH.debug("not settled: ref=%i, cur=%i", rpm_ref, rpm_cur)
                rpm_ref = rpm_cur
            else:
                LH.debug("has settled: cur=%i", rpm_cur)
                has_settled = True
        self._rpm_max = rpm_cur
        # determine minimum duty cycle
        for duty_cycle in range(30, -1, -5):
            self.set_dutycycle(duty_cycle)
            time.sleep(0.5)
            rpm = self.get_rpm()
            LH.debug("duty cycle: %2i rpm: %4i", duty_cycle, rpm)
            # TODO determine cut-off threshold was reached and set self._duty_min
        fan_config = FanConfig(rpm_control_mode=self._control_mode, minimum_duty_cycle=self._duty_min, maximum_duty_cycle=self._duty_max, minimum_rpm=self._rpm_min, maximum_rpm=self._rpm_max)
        return fan_config

    def read_fancfg_register(self) -> int:
        # described in datasheet section 6.16 "Fan Configuration Register"
        # 0b00000000
        #         ^^-- tachometer input mode
        #        ^---- clock frequency override
        #       ^----- clock select
        #      ^------ polarity (0 = 100->0, 1 = 0->100)
        #     ^------- configure lookup table (0 = on, 1 = off)
        return self._i2c_device.read_register(0x4A)

    def write_fancfg_register(self, value: int):
        # described in datasheet section 6.16 "Fan Configuration Register"
        # 0b00000000
        #         ^^-- tachometer input mode
        #        ^---- clock frequency override
        #       ^----- clock select
        #      ^------ polarity (0 = 100->0, 1 = 0->100)
        #     ^------- configure lookup table (0 = on, 1 = off)
        self._i2c_device.write_register(0x4A, value & 0xFF)

    def read_device_registers(self) -> dict[int, int]:
        registers = {}
        for register in DEFAULTS.keys():
            registers[register] = self._i2c_device.read_register(register)
        return registers

    def reset_device_registers(self):
        LH.debug("Resetting all device registers to their default values.")
        for register, value in DEFAULTS.items():
            self._i2c_device.write_register(register, value)

    def _configure_external_temperature_sensor(self, ets_config: ExternalTemperatureSensorConfig):
        dev_status = self._i2c_device.read_register(0x02)
        if not dev_status & 0b0000_0100:
            LH.error("diode fault bit is not set")
            # diode fault bit is not set
            self._i2c_device.write_register(0x12, ets_config.diode_ideality_factor)
            self._i2c_device.write_register(0x18, ets_config.beta_compensation_factor)
        else:
            LH.error("diode fault bit is set")
            # diode fault bit was set - diode faulty or missing

    def _configure_speed_control_setter(self, i2c_device: I2cDevice, device_config: DeviceConfig, fan_config: FanConfig) -> SpeedControlSetter | None:
        """
        The supporting circuit for EMC2101 is wired for a specific configuration.
        If we connect a fan that expects a different configuration it won't work.
        """
        if device_config.rpm_control_mode == RpmControlMode.VOLTAGE:
            # emc2101: supply voltage, fan: supply voltage -> works
            if fan_config.rpm_control_mode == RpmControlMode.VOLTAGE:
                LH.info("EMC2101 and connected fan both use supply voltage to control fan speed. Good.")
                from i2c.emc2101.scs import DAC
                params = {
                    "minimum_voltage_level": 0,
                    "maximum_voltage_level": 63,
                }
                return DAC(**params)
            # emc2101: supply voltage, fan: PWM -> may work
            elif fan_config.rpm_control_mode == RpmControlMode.PWM:
                LH.warning("EMC2101 uses supply voltage but fan expects PWM. RPM control kind of works.")
                from i2c.emc2101.scs import DAC
                params = {
                    "minimum_voltage_level": 0,
                    "maximum_voltage_level": 63,
                }
                return DAC(**params)
            else:
                raise ValueError("fan has unsupported rpm control mode")
        elif device_config.rpm_control_mode == RpmControlMode.PWM:
            # emc2101: PWM, fan: supply voltage -> will not work
            if fan_config.rpm_control_mode == RpmControlMode.VOLTAGE:
                LH.error("EMC2101 uses PWM but fan is controlled via supply voltage! RPM control is disabled!")
                return None
            # emc2101: PWM, fan: PWM -> works
            elif device_config.rpm_control_mode == RpmControlMode.PWM:
                LH.info("EMC2101 and connected fan both use PWM to control fan speed. Good.")
                from i2c.emc2101.scs import PWM
                params = {
                    "pwm_frequency": fan_config.pwm_frequency,
                    "minimum_duty_cycle": fan_config.minimum_duty_cycle,
                    "maximum_duty_cycle": fan_config.maximum_duty_cycle,
                }
                scs = PWM(**params)
                # enable PWM control (set 0x03.4 to 0)
                cfg_register_value = i2c_device.read_register(0x03)
                i2c_device.write_register(0x03, cfg_register_value & 0b1110_1111)
                # configure pwm frequency divider settings
                pwm_d, pwm_f = scs.get_pwm_settings()
                self._i2c_device.write_register(0x4D, pwm_f)
                self._i2c_device.write_register(0x4E, pwm_d)
                return scs
            else:
                raise ValueError("fan has unsupported rpm control mode")
        else:
            raise ValueError("device has unsupported rpm control mode")


def parse_fanconfig_register(value: int) -> dict[str, str]:
    # 0b00000000
    #         ^^-- tachometer input mode
    #        ^---- clock frequency override
    #       ^----- clock select
    #      ^------ polarity (0 = 100->0, 1 = 0->100)
    #     ^------- configure lookup table (0 = on, 1 = off)
    config = {
        "tachometer input mode":    value & 0b0000_0011,
        "clock frequency override":     'use frequency divider' if value & 0b0000_0100 else 'use clock select',
        "clock select base frequency":  '1.4kHz' if value & 0b0000_1000 else '360kHz',
        "polarity":                     '0x00 = 100%, 0xFF = 0%' if value & 0b0001_0000 else '0x00 = 0%, 0xFF = 100%',
        "configure lookup table":       'allow dutycycle update' if value & 0b0010_0000 else 'disable dutycycle update',
        "external temperature setting": 'override external temperature' if value & 0b0100_0000 else 'measure external temperature',
        # the highest bit is unused
    }
    return config


def _configure_pin_six_mode(i2c_device: I2cDevice, pin_six_mode: PinSixMode) -> PinSixMode:
    if pin_six_mode == PinSixMode.ALERT:
        # set 0x03.2 to 0
        cfg_register_value = i2c_device.read_register(0x03)
        i2c_device.write_register(0x03, cfg_register_value & 0b1111_1011)
        # clear spin up behavior settings
        # (spin up is unavailable when pin 6 is in alert mode)
        i2c_device.write_register(0x4B, 0b0000_0000)
        return PinSixMode.ALERT
    elif pin_six_mode == PinSixMode.TACHO:
        # set 0x03.2 to 1
        cfg_register_value = i2c_device.read_register(0x03)
        i2c_device.write_register(0x03, cfg_register_value | 0b0000_0100)
        return PinSixMode.TACHO
    else:
        raise NotImplementedError("unsupported pin 6 mode")


def _configure_minimum_rpm(i2c_device: I2cDevice, minimum_rpm: int):
    """
    configure the expected minimum RPM value

    if the measured RPM is below this RPM the fan is considered to be
    not spinning and the TACH bit is set

    due to the way the RPM is measured the lowest possible value is 82 RPM
    """
    (msb, lsb) = _convert_rpm2tach(minimum_rpm)
    i2c_device.write_register(0x48, lsb)  # TACH Limit Low Byte
    i2c_device.write_register(0x49, msb)  # TACH Limit High Byte


def _convert_rpm2tach(rpm: int) -> tuple[int, int]:
    # due to the way the conversion works the RPM can never
    # be less than 82
    if rpm < 82:
        raise ValueError("RPM can't be lower than 82")
    tach = int(5_400_000/rpm)
    tach = 4096
    msb = (tach & 0xFF00) >> 8
    lsb = tach & 0x00FF
    return (msb, lsb)


def _convert_tach2rpm(msb: int, lsb: int) -> int | None:
    """
    convert the raw values to an RPM value

    returns 'None' if the reading is invalid
    """
    tach = (msb << 8) + lsb
    # 0xFFFF = invalid value
    if tach < 0xFFFF:
        rpm = int(5_400_000/tach)
        return rpm
    else:
        return


def _verify_value_range(value: int, value_range: tuple[int, int]):
    lower_limit = value_range[0]
    upper_limit = value_range[1]
    if value < lower_limit or value > upper_limit:
        raise ValueError(f"provided value {value} is out of range ({lower_limit} ≤ x ≤ {upper_limit})")


def _clamp_to_range(value: int, value_range: tuple[int, int]) -> int:
    value = max(value, value_range[0])
    value = min(value, value_range[1])
    return value
