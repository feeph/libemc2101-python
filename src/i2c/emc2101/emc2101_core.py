#!/usr/bin/env python3
"""
low-level interface to the EMC2101 chip

datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf

You probably don't want to use this one. Use Emc2101_DAC / Emc2101_PWM instead.
"""

import logging
from enum import Enum

# module busio provides no type hints
import busio  # type: ignore

from i2c.emc2101.conversions import convert_bytes2temperature, convert_temperature2bytes
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
    # fan control lookup table (0x50..0x5F)                    6.22
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
    "32":   0b1001,  # and all unlisted values
}


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


# class StatusRegister:
#     """
#     ```
#     self.tach      the TACH count has exceeded the TACH Limit
#     self.tcrit     external diode temperature has met or exceeded the TCRIT limit
#     self.fault     a diode fault has occurred on the external diode
#     self.ext_low   external diode temperature has fallen below the low limit
#     self.ext_high  external diode temperature has exceeded the high limit
#     self.eeprom    indicates that the EEPROM could not be found
#     self.int_high  internal temperature has met or exceeded the high limit
#     self.busy      indicates that the ADC is converting - does not trigger an interrupt
#     ```
#     """

#     def __init__(self, i2c_device: I2cDevice, register: int = 0x02):
#         self._register = register
#         self.update(i2c_device)

#     def update(self, i2c_device: I2cDevice):
#         value = i2c_device.read_register(self._register)
#         if value is not None:
#             self.tach     = value & 0b0000_0001
#             self.tcrit    = value & 0b0000_0010
#             self.fault    = value & 0b0000_0100
#             self.ext_low  = value & 0b0000_1000
#             self.ext_high = value & 0b0001_0000
#             self.eeprom   = value & 0b0010_0000
#             self.int_high = value & 0b0100_0000
#             self.busy     = value & 0b1000_0000


class Emc2101_core:
    """
    low-level interface to the EMC2101 chip

    You probably don't want to use this one. Use Emc2101_DAC / Emc2101_PWM instead.
    """

    def __init__(self, i2c_bus: busio.I2C):
        """
        initialize the object

        Configure pin 6 and the control mode before use.
        These settings MUST match the electric circuit!
         - emc2101.configure_pin_six_as_alert()
         - emc2101.configure_pin_six_as_tacho()
         - emc2101.configure_dac_control()
         - emc2101.configure_pwm_control()

        If you don't set these values correctly you won't get sensible
        readings!
        """
        self._i2c_address = 0x4c  # the I²C bus address is hardcoded
        self._i2c_device = I2cDevice(i2c_bus=i2c_bus, i2c_address=self._i2c_address)
        # allowed steps can be lower if PWM is used
        self._step_min = 0
        self._step_max = 63
        # minimum and maximum operation temperature
        self._temp_min = 0
        self._temp_max = 100

    def get_manufacturer_id(self) -> int:
        """
        read the manufacturer ID
        (0x5d for SMSC)
        """
        return self._i2c_device.read_register(0xFE)

    def get_product_id(self) -> int:
        """
        read the product ID
        (0x16 for EMC2101, 0x28 for EMC2101-R)
        """
        return self._i2c_device.read_register(0xFD)

    def get_product_revision(self) -> int:
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

    def configure_pin_six_as_alert(self) -> bool:
        # set 0x03.2 to 0
        cfg_register_value = self._i2c_device.read_register(0x03)
        if cfg_register_value is not None:
            self._i2c_device.write_register(0x03, cfg_register_value & 0b1111_1011)
            # clear spin up behavior settings
            # (spin up is unavailable when pin 6 is in alert mode)
            self._i2c_device.write_register(0x4B, 0b0000_0000)
            return True
        else:
            LH.error("Unable to read config register!")
            return False

    def configure_pin_six_as_tacho(self) -> bool:
        # set 0x03.2 to 1
        cfg_register_value = self._i2c_device.read_register(0x03)
        if cfg_register_value is not None:
            self._i2c_device.write_register(0x03, cfg_register_value | 0b0000_0100)
            return True
        else:
            LH.error("Unable to read config register!")
            return False

    def configure_dac_control(self, step_max: int):
        # enable DAC control (set 0x03.4 to 1)
        cfg_register_value = self._i2c_device.read_register(0x03)
        self._i2c_device.write_register(0x03, cfg_register_value | 0b0001_0000)
        # configure maximum allowed step
        self._step_max = step_max

    def configure_pwm_control(self, pwm_d: int, pwm_f: int, step_max: int):
        # enable PWM control (set 0x03.4 to 0)
        cfg_register_value = self._i2c_device.read_register(0x03)
        self._i2c_device.write_register(0x03, cfg_register_value & 0b1110_1111)
        # configure pwm frequency divider settings
        self._i2c_device.write_register(0x4D, pwm_f)
        self._i2c_device.write_register(0x4E, pwm_d)
        # configure maximum allowed step
        self._step_max = step_max

    def configure_spinup_behaviour(self, spinup_strength: SpinUpStrength, spinup_duration: SpinUpDuration, fast_mode: bool):
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
        value = 0x00
        # configure spin up time
        value |= spinup_duration.value
        # configure spin up strength (dutycycle)
        value |= spinup_strength.value
        if fast_mode:
            value |= 0b0010_0000
        self._i2c_device.write_register(0x4B, value)

    def configure_minimum_rpm(self, minimum_rpm: int):
        """
        configure the expected minimum RPM value

        if the measured RPM is below this RPM the fan is considered to be
        not spinning and the TACH bit is set

        due to the way the RPM is measured the lowest possible value is 82 RPM
        """
        (msb, lsb) = _convert_rpm2tach(minimum_rpm)
        self._i2c_device.write_register(0x48, lsb)  # TACH Limit Low Byte
        self._i2c_device.write_register(0x49, msb)  # TACH Limit High Byte

    def get_rpm(self) -> int | None:
        """
        get current fan speed

        (pin 6 must be configured for tacho mode)
        """
        status_register = self._i2c_device.read_register(0x02)
        if status_register & 0b0000_0001:
            # get tacho readings
            # (the order of is important; see datasheet section 6.1 for details)
            lsb = self._i2c_device.read_register(0x46)  # TACH Reading Low Byte, must be read first!
            msb = self._i2c_device.read_register(0x47)  # TACH Reading High Byte
            LH.debug("tach readings: LSB=0x%02X MSB=0x%02X", lsb, msb)
            return _convert_tach2rpm(msb=msb, lsb=lsb)
        else:
            LH.warning("Pin six is not configured for tacho mode. Please enable tacho mode.")
            return None

    def get_driver_strength(self) -> int:
        """
        get the configured fan speed (raw value)
        """
        return self._i2c_device.read_register(0x4C)

    def set_driver_strength(self, step: int, disable_lut: bool = False) -> bool:
        """
        set the configured fan speed (raw value)
         - clamp to minimum/maximum as defined by the fan configuration
        """
        if self._step_min <= step <= self._step_max:
            self._i2c_device.write_register(0x4C, step)
        # confirm the register was set to desired value
        return step == self._i2c_device.read_register(0x4C)

    def enable_lookup_table(self) -> bool:
        """
        The Fan Setting register (0x4C) and Fan Control Look-Up Table
        registers (0x50-0x5F) are writeable and the Fan Setting
        register will be used.

        An external temperature sensor must be connected to use this feature.
        """
        if not self._has_sensor_fault():
            value = self._i2c_device.read_register(0x4A)
            self._i2c_device.write_register(0x4A, value | 0b0010_0000)
            return True
        else:
            return False

    def disable_lookup_table(self):
        """
        the Fan Setting register (0x4C) and Fan Control Look-Up Table
        registers (0x50-0x5F) are read-only and the Fan Control Look-Up
        Table registers will be used.
        """
        value = self._i2c_device.read_register(0x4A)
        self._i2c_device.write_register(0x4A, value & 0b1101_1111)

    def is_lookup_table_enabled(self) -> bool:
        return bool(self._i2c_device.read_register(0x4A) & 0b1101_1111)

    def update_lookup_table(self, values: dict[int, int]) -> bool:
        """
        populate the lookup table with the provided values and
        sets all unused values to zero

        returns 'True' if the lookup table was updated and 'False' if it wasn't.
        """
        if not self._has_sensor_fault():
            if len(values) > 8:
                raise ValueError("too many entries in lookup table (max: 8)")
            for temp, step in values.items():
                if not self._temp_min <= temp <= self._temp_max:
                    raise ValueError("temperature is out of range")
                if not self._step_min <= step <= self._step_max:
                    raise ValueError("step is out of range")
            # -------------------------------------------------------------
            # must disable lookup table to make it writeable
            if self.is_lookup_table_enabled():
                LH.error("Lookup table is enabled. Disabling.")
                self.disable_lookup_table()
                reenable_lut = True
            else:
                LH.error("Lookup table is not enabled. Good.")
                reenable_lut = False
            # 0x50..0x5f (8 x 2 registers; temp->step)
            offset = 0
            # set provided value
            for temp, step in values.items():
                self._i2c_device.write_register(0x50 + offset, temp)
                self._i2c_device.write_register(0x51 + offset, step)
                offset += 2
            # fill remaining slots
            for offset in range(offset, 16, 2):
                self._i2c_device.write_register(0x50 + offset, 0x00)
                self._i2c_device.write_register(0x51 + offset, 0x00)
            # reenable lookup table if it was previously enabled
            if reenable_lut:
                self.enable_lookup_table()
            return True
        else:
            LH.warning("Using the lookup table requires an external temperature sensor!")
            return False

    def reset_lookup_table(self):
        # must disable lookup table to make it writeable
        self.disable_lookup_table()
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
        return not self._has_sensor_fault()

    def get_sensor_temperature(self) -> float:
        """
        get external sensor temperature in °C

        the datasheet guarantees a precision of +/- 1°C
        """
        msb = self._i2c_device.read_register(0x01)  # high byte, must be read first!
        lsb = self._i2c_device.read_register(0x10)  # low byte
        return convert_bytes2temperature(msb, lsb)

    def get_sensor_low_temperature_limit(self) -> float:
        """
        get upper/lower temperature alerting limit in °C
        """
        msb = self._i2c_device.read_register(0x08)
        lsb = self._i2c_device.read_register(0x14)
        return convert_bytes2temperature(msb, lsb)

    def set_sensor_low_temperature_limit(self, value: float) -> float:
        """
        set upper/lower temperature alerting limit in °C

        The fractional part has limited precision and will be clamped to the
        nearest available step. The clamped value is returned to the caller.
        """
        if self._temp_min <= value <= self._temp_max:
            (msb, lsb) = convert_temperature2bytes(value)
            self._i2c_device.write_register(0x08, msb)
            self._i2c_device.write_register(0x14, lsb)
            return convert_bytes2temperature(msb, lsb)
        else:
            raise ValueError(f"temperature limit out of range ({self._temp_min} ≤ x ≤ {self._temp_max}°C)")

    def get_sensor_high_temperature_limit(self) -> float:
        """
        get upper/lower temperature alerting limit in °C
        """
        msb = self._i2c_device.read_register(0x07)
        lsb = self._i2c_device.read_register(0x13)
        return convert_bytes2temperature(msb, lsb)

    def set_sensor_high_temperature_limit(self, value: float) -> float:
        """
        set upper/lower temperature alerting limit in °C

        The fractional part has limited precision and will be clamped to the
        nearest available step. The clamped value is returned to the caller.
        """
        if self._temp_min <= value <= self._temp_max:
            (msb, lsb) = convert_temperature2bytes(value)
            self._i2c_device.write_register(0x07, msb)
            self._i2c_device.write_register(0x13, lsb)
            return convert_bytes2temperature(msb, lsb)
        else:
            raise ValueError("temperature limit out of range (0 ≤ x ≤ 85°C)")

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
        # write to register
        self._i2c_device.write_register(0x0C, round(temperature))
        # force chip take readings from register instead of sensor
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

    def configure_external_temperature_sensor(self, dif: int, bcf: int) -> bool:
        """
        configure diode_ideality_factor and beta_compensation_factor

        parameters:
         - dif = diode_ideality_factor
         - bcf = beta_compensation_factor
        """
        dev_status = self._i2c_device.read_register(0x02)
        if not dev_status & 0b0000_0100:
            LH.debug("The diode fault bit is clear.")
            self._i2c_device.write_register(0x12, dif)
            self._i2c_device.write_register(0x18, bcf)
            return True
        else:
            LH.error("The diode fault bit is set: Sensor is faulty or missing.")
            return False

    def _has_sensor_fault(self):
        return self._i2c_device.read_register(0x02) & 0b0000_0100


# def parse_fanconfig_register(value: int) -> dict[str, Any]:
#     # 0b00000000
#     #         ^^-- tachometer input mode
#     #        ^---- clock frequency override
#     #       ^----- clock select
#     #      ^------ polarity (0 = 100->0, 1 = 0->100)
#     #     ^------- configure lookup table (0 = on, 1 = off)
#     config = {
#         "tachometer input mode":    value & 0b0000_0011,
#         "clock frequency override":     'use frequency divider' if value & 0b0000_0100 else 'use clock select',
#         "clock select base frequency":  '1.4kHz' if value & 0b0000_1000 else '360kHz',
#         "polarity":                     '0x00 = 100%, 0xFF = 0%' if value & 0b0001_0000 else '0x00 = 0%, 0xFF = 100%',
#         "configure lookup table":       'allow dutycycle update' if value & 0b0010_0000 else 'disable dutycycle update',
#         "external temperature setting": 'override external temperature' if value & 0b0100_0000 else 'measure external temperature',
#         # the highest bit is unused
#     }
#     return config


def _convert_rpm2tach(rpm: int) -> tuple[int, int]:
    # due to the way the conversion works the RPM can never
    # be less than 82
    if rpm < 82:
        raise ValueError("RPM can't be lower than 82")
    tach = int(5_400_000 / rpm)
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
        rpm = int(5_400_000 / tach)
        return rpm
    else:
        return None
