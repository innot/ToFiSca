# Copyright 2025  Thomas Holland

# License: MIT

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software
# and associated documentation files (the “Software”), to deal in the Software without
# restriction, including without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


import enum
import logging
import os
import re
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path

import lgpio
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PWMDriverType(enum.Enum):
    """
    The types of pwm generation a gpio pin supports
    """
    HARDWARE = "pwm"
    PIO = "pwm-pio"
    GPIO = "pwm-gpio"
    LGPIO = "lgpio"
    UNKNOWN = "unknown"


class PWMPinInfo(BaseModel):
    """
    Storage for a gpio pin number and the :class:`PWMDriverType` that generates the pwm signal.

    Technically a pin could be driven by more than one driver. However we only use the "best" driver available.
    """
    gpio: int = Field(ge=0, le=255)
    driver: PWMDriverType = Field()


class SysfsPWMPinInfo(PWMPinInfo):
    """
    Additional information about pin that is accessed through the sysfs at '/sys/class/pwm'

    It containes the chip number '...pwmchip[n]' and the channel number '...pwmchip[n]/pwm[n]'.
    """
    chip: int = Field(ge=0, le=255)
    channel: int = Field(ge=0, le=255)


class PWMChipInfo(BaseModel):
    """
    Information about 'pwmchip_'.
    It has the channels still available (not used by the system) and the :class:`PWMDriver` class required for
    accessing the pin.

    """
    chip: int = Field(ge=0, le=255)
    channels: list[int] = Field()
    driver: PWMDriverType = Field()
    assigned_pin: int | None = Field(default=None, ge=0, le=255)


class PWMAlreadyInUse(RuntimeError):

    def __init__(self, pwm_pin: PWMPinInfo):
        msg = f"PWMPin Pin {pwm_pin.gpio} already allocated."
        super().__init__(msg)


class PWMAllocationTimeout(RuntimeError):

    def __init__(self, pwm_pin: PWMPinInfo):
        msg = f"Allocating Pin {pwm_pin.gpio} timed out after 1s"
        super().__init__(msg)


class PWMPin(ABC):
    """
    Class to control a single PWM gpio pin.

    There are several properties to control the pwm output:

        - :attr:`enable` to switch to pwn output on or off
        - :attr:`frequency` to set the pwm frequency, and
        - :attr:`dutycycle` to set the pwm dutycycle.
        - :attr:`invert` to invert the signal polarity.

    This class should not be instantiated directly. Instead use :meth:`PWMManager.allocate` to get a
    `PWMPin` instance for a given port.
    The PWMManager keeps track of all allocated pins, assures that a pin can only be allocated once and
    frees the associated resources upon exit.
    """

    def __init__(self, pin: PWMPinInfo):
        self._pin = pin
        self._frequency: float = 1000
        self._dutycycle: float = 0.5
        self._inverted: bool = False
        self._is_on: bool = False
        self._is_allocated: bool = False

    @property
    def frequency(self) -> float:
        """
        The frequency of the PWM in Hz.
        The maximum and minimum frequency depends on the PWM type.
        """
        return self._frequency

    @frequency.setter
    def frequency(self, hz: float) -> None:
        self._frequency = hz

    @property
    def dutycycle(self) -> float:
        """
        The dutycycle of the PWM in percent (0-100).
        """
        return self._dutycycle

    @dutycycle.setter
    def dutycycle(self, percent: float) -> None:
        self._dutycycle = percent

    @property
    def invert(self) -> bool:
        """
        If `True` the polarity of the pwm signal is inverted, i.e. for dutycycle
            -   100% : the pin is always low
            -   0% : the pin is always hight

        Default is `False`, i.e. pin high for 100% and pin low for 0%
        """
        return self._inverted

    @invert.setter
    def invert(self, value: bool = False) -> None:
        self._inverted = value

    @property
    def enable(self) -> bool:
        """
        Switches the PWM on or off.
        Set to `True`to start the pwm output, `False`to stop it.
        """
        return self._is_on

    @enable.setter
    def enable(self, enable: bool) -> None:
        self._is_on = enable

    @property
    def is_allocated(self) -> bool:
        """
        `True` if the associated GPIO pin has been allocated for this pwm.
        This property is read-only.
        """
        return self._is_allocated

    @property
    def gpio(self) -> int:
        """
        The gpio used by this pwm.
        This property is read-only.
        """
        return self._pin.gpio

    @abstractmethod
    def _allocate(self):
        """
        Abstract method to allocate the PWM pin.
        This should only be called from the PWMManager which keeps a list of allocated pwm pins.
        """
        self._is_allocated = True

    @abstractmethod
    def _free(self):
        """
        Abstract method to free the PWM pin.
        This should only be called from the PWMManager which keeps a list of allocated pwm pins.
        """
        self._is_allocated = False


class SysfsPWMPin(PWMPin):
    """
    Implements the :class:`PWMPin` interface for a pin that is accessed through the kernel sysfs.
    """

    def __init__(self, pin: PWMPinInfo):
        super().__init__(pin)

        if not isinstance(pin, SysfsPWMPinInfo):
            raise TypeError("Pin is not a HardwarePWMPinInfo")

        self._pin: SysfsPWMPinInfo = pin
        self._is_allocated = False

        self._chip_path = Path(f"/sys/class/pwm/pwmchip{pin.chip}/")
        self._pwm_path = self._chip_path / f"pwm{pin.channel}/"

    def __del__(self):
        if self._is_allocated:
            self._free()  # hopefully do not leave any allocated pins behind

    @PWMPin.dutycycle.setter
    def dutycycle(self, percent: float) -> None:
        if not (0 <= percent <= 100):
            raise ValueError(f"Duty cycle must be between 0% and 100% (inclusive), was {percent}%")

        if self._inverted:
            percent = 100 - percent

        self._dutycycle = percent

        # get the current frequency and convert to nanoseconds
        period = int(1_000_000_000 / self.frequency)
        dutycycle_ns = int(period * percent / 100)

        # set the new dutycycle in the sysfs
        self.echo(self._pwm_path / "duty_cycle", dutycycle_ns)

    @PWMPin.frequency.setter
    def frequency(self, hz: int) -> None:
        self._frequency = hz

        # change Hz to nanoseconds
        period = int(1_000_000_000 / hz)

        # calculate the duty_cycle for the new period
        dutycycle_ns = int(period * self.dutycycle / 100)

        self.echo(self._pwm_path / "duty_cycle", 0)  # in case the new dutycycle is longer than the old period
        self.echo(self._pwm_path / "period", period)
        self.echo(self._pwm_path / "duty_cycle", dutycycle_ns)

    @PWMPin.enable.setter
    def enable(self, enable: bool) -> None:
        if enable:
            self.echo(self._pwm_path / "enable", "1")
        else:
            self.echo(self._pwm_path / "enable", "0")
        self._is_on = enable

    def _allocate(self):
        # activate the channel
        try:
            self.echo(self._chip_path / "export", self._pin.channel)
            self._is_allocated = True
            # Immediately setting any pwm value caused PermissionErrors
            # Wait until the node exists (or timeout if it takes too long)
            time_start = time.time_ns()
            while not os.access(self._pwm_path / "duty_cycle", os.W_OK):
                logger.info("Waiting for pwm_/duty_cycle to appear")
                time.sleep(0.01)
                if time.time_ns() - time_start > 1_000_000_000:  # More than 1 second
                    raise PWMAllocationTimeout(self._pin)
        except OSError:
            raise PWMAlreadyInUse(self._pin)

    def _free(self):
        # release the channel
        try:
            self._is_allocated = False
            self.echo(self._chip_path / "unexport", self._pin.channel)
        except OSError:
            # For now, ignore error
            logger.warning(f"Free PWMPin pin {self._pin} was freed again")

    @staticmethod
    def echo(file: Path, value: any):
        with open(file, "w") as f:
            f.write(f"{value}\n")


class LgpioPWMPin(PWMPin):
    """
    Implements the :class:`PWMPin` interface for a pin that is accessed via the `lgpio` library.
    """

    def __init__(self, pin: PWMPinInfo):
        super().__init__(pin)

        self._pin: PWMPinInfo = pin
        self._is_allocated = False

        self._handle = None

    def __del__(self):
        if self._is_allocated:
            self._free()  # hopefully do not leave any allocated pins behind

    @PWMPin.dutycycle.setter
    def dutycycle(self, percent: float) -> None:
        if not (0 <= percent <= 100):
            raise ValueError(f"Duty cycle must be between 0% and 100% (inclusive), was {percent}%")

        if self._inverted:
            percent = 100 - percent

        self._dutycycle = percent

        if self._is_on:
            # update immediatly when the pwm is alread running
            lgpio.tx_pwm(self._handle, self._pin.gpio, self._frequency, percent, 0, 0)

    @PWMPin.frequency.setter
    def frequency(self, hz: int) -> None:
        if not 0.1 <= hz <= 10000:
            raise ValueError("Frequency for Software PWMPin must be between 0.1 and 10.000 Hz.")

        self._frequency = hz

        if self._is_on:
            # update immediatly when the pwm is alread running
            lgpio.tx_pwm(self._handle, self._pin.gpio, hz, self._dutycycle, 0, 0)

    @PWMPin.enable.setter
    def enable(self, enable: bool) -> None:
        if enable:
            lgpio.gpio_claim_output(self._handle, self.gpio, 0)
            lgpio.tx_pwm(self._handle, self.gpio, self._frequency, self._dutycycle, 0, 0)
        else:
            lgpio.gpio_claim_input(self._handle, self.gpio, lgpio.SET_PULL_NONE)
        self._is_on = enable

    def _allocate(self):
        # allocate the pin for pwm output
        handle = lgpio.gpiochip_open(0)  # todo: 0 is ok for raspi, might be something else for other sbc's
        if handle < 0:
            raise RuntimeError("Failed to open gpiochip handle.")

        # until enabled set the pin to hi-z
        lgpio.gpio_claim_input(handle, self._pin.gpio, lgpio.SET_PULL_NONE)

        self._handle = handle
        self._is_allocated = True

    def _free(self):

        # return the pin to a hi-z state
        result = 0
        result += lgpio.gpio_claim_input(self._handle, self._pin.gpio, lgpio.SET_PULL_NONE)
        result += lgpio.gpio_free(self._handle, self._pin.gpio)
        result += lgpio.gpiochip_close(self._handle)
        if result != 0:
            logger.warning("Failed to free the PWMPin Driver.")
        self._is_allocated = False


class PWMManager:
    """
    Manages access to the pwm pins of the system.

    A list of all available pwm pins can be retrieved from the :prop:`available_pwm_pins` property.

    Some of these pins support hardware pwm, where an on-chip unit generates a jitter-free pwm signal.

    All other pins support software pwm, where the pwm signal is generated in software, usually
    having a certain amount of jitter.

    Once a pin has been selected, it must be allocated with the :meth:`allocate` method. The returned
    :class:`PWMPin` can then be used to switch pwm on or off and control the frequency and dutycycle.

    If the pwm pin is not needed anymore, it should be returned to the :meth:`free` method so it can be
    allocated again.

    """

    def __init__(self) -> None:

        self._pwmchips: list[PWMChipInfo] | None = None
        self._allpwmpins: list[PWMPinInfo] | None = None
        self._all_allocated: dict[int, PWMPin] = {}

    def __del__(self):
        self.close()  # last chance to free any allocated pwm pins upon system exit. Better call `close()` directly.

    @property
    def pwmchips(self) -> list[PWMChipInfo]:
        """
        The list of pwmchip instances found on the system.
        This property is read-only.
        """
        if not self._pwmchips:
            self._pwmchips = self._parse_pwmchips()
        return self._pwmchips

    @property
    def available_pwm(self) -> list[PWMPinInfo]:
        """
        The list of all pins supporting pwm on the current platform.
        This list includes both hardware pwm pins and software pwm pins.

        They can be differentiated by the :attr:`PWMPinInfo.type` field.

        This property is read-only.
        """
        if not self._allpwmpins:
            self._allpwmpins = self._list_available()
        return list(self._allpwmpins)

    @property
    def available_hardware_pwm(self) -> list[PWMPinInfo]:
        """
        The list of all pins supporting hardware pwm on the current platform.
        """
        hw_drivers = [PWMDriverType.HARDWARE, PWMDriverType.PIO]
        return [pin for pin in self.available_pwm if pin.driver in hw_drivers]

    @property
    def available_software_pwm(self) -> list[PWMPinInfo]:
        """
        The list of all pins supporting software pwm on the current platform.
        """
        sw_drivers = [PWMDriverType.GPIO, PWMDriverType.LGPIO]
        return [pin for pin in self.available_pwm if pin.driver in sw_drivers]

    def allocate(self, pwmpin: int | PWMPinInfo) -> PWMPin:
        """
        Allocate the given pin for usage.

        The returned :class:`PWMPin` can be used to control the pwm output.
        :raises PWMAlreadyInUse: If the pwmpin is already allocated.
        """

        if isinstance(pwmpin, int):
            # get the PWMPin from the gpio number
            pin = [p for p in self.available_pwm if p.gpio == pwmpin]
            if len(pin) != 1:
                raise ValueError(f"PWMPin pin {pwmpin} is not available for pwm")

            pininfo = pin[0]
        else:
            pininfo = pwmpin

        if pininfo.gpio in self._all_allocated:
            raise PWMAlreadyInUse(pininfo)

        if pininfo.driver == PWMDriverType.LGPIO:
            pindrv = LgpioPWMPin(pininfo)
        else:
            pindrv = SysfsPWMPin(pininfo)

        pindrv._allocate()
        self._all_allocated[pininfo.gpio] = pindrv

        return pindrv

    def free(self, pwmpin: int | PWMPin) -> None:
        """
        Free the given pin and release the associated hardware resources.

        A freed pwmpin can be allocated again if required.
        """

        if isinstance(pwmpin, int):
            # find the driver in the list of allocated pins
            try:
                pindrv = self._all_allocated[pwmpin]
            except KeyError:
                logger.warning(f"Tried to free the non-allocated pin {pwmpin}")
                return
        else:
            pindrv = pwmpin

        pindrv._free()
        self._all_allocated.pop(pindrv.gpio, None)

    def close(self) -> None:
        """
        Close the PWMManager instance.

        Any still allocated pwmpins are freed and can not be used afterwards.
        """
        for pin in self._all_allocated.values():
            pin._free()
        self._all_allocated.clear()

    def _list_available(self) -> list[PWMPinInfo]:
        """
        Parses the output of the `pinctrl` shell command, looking for GPIO pins usable for either
        hardware or software pwm.
        """
        result: list[PWMPinInfo] = []

        matchctrls = re.compile(r'.*\sGPIO(\d+)\s*=\s*(\w+)')
        matchchipchannel = re.compile(r'PWM(\d)_CHAN(\d)')

        # get the pins that are supported by pwm_pio or pwm_gpio
        pio_pins: dict[int, tuple[int, PWMDriverType]] = {}
        for chip in self.pwmchips:
            if chip.assigned_pin is not None:
                pio_pins[chip.assigned_pin] = (chip.chip, chip.driver)

        # get the output of "pinctrl" and parse it
        gpiolist = subprocess.getoutput("pinctrl").split("\n")
        for gpio in gpiolist:
            ctrlsmatch = matchctrls.match(gpio)
            if ctrlsmatch:
                gpio = int(ctrlsmatch.group(1))

                chipchannel_match = matchchipchannel.match(ctrlsmatch.group(2))
                if chipchannel_match:
                    # The pin is a Hardware PWMPin pin
                    result.append(SysfsPWMPinInfo(gpio=gpio,
                                                  driver=PWMDriverType.HARDWARE,
                                                  chip=int(chipchannel_match.group(1)),
                                                  channel=int(chipchannel_match.group(2)),
                                                  )
                                  )
                    continue

                # check if this is either a pwm_pio or pwm_gpio
                if gpio in pio_pins:
                    result.append(SysfsPWMPinInfo(gpio=gpio,
                                                  driver=pio_pins[gpio][1],
                                                  chip=pio_pins[gpio][0],
                                                  channel=0,
                                                  )
                                  )
                    pio_pins.pop(gpio, None)  # hack to remove the pin as there are more pins named "GPIO[n]"
                    continue

                # check that the pin is free for lgpio software pwm
                if ctrlsmatch.group(2) == "none":
                    result.append(PWMPinInfo(gpio=gpio, driver=PWMDriverType.LGPIO))
        return result

    @staticmethod
    def _parse_pwmchips() -> list[PWMChipInfo]:
        """
        Parses `/sys/kernel/debug/pwm` to get a list of all pwmchip instances supported by the platform hardware.
        """

        result: list[PWMChipInfo] = []

        chipnumber_re = re.compile(r'(\d+):.*(\d)\sPWM.*')
        channelnumber_re = re.compile(r'\s*pwm-(\d+)\s*\((\S*).*\)')
        pin_re = re.compile(r'.*pwm_(\w+)@(\w+),.*')

        pwmfile = Path("/sys/kernel/debug/pwm")
        with (open(pwmfile, "r") as f):
            lines = f.read().splitlines()
            while len(lines) > 0:
                line = lines.pop(0)
                if chipmatch := chipnumber_re.match(line):
                    # start of a new chip.
                    chip_number = chipmatch.group(1)  # the number of the chip, e.g. 0 for pwmchip0

                    # check if this a pwm_pio or pwm_gpio driver
                    pin_match = pin_re.match(line)
                    if pin_match:
                        # this is a pwm_pio or pwm_gpio "chip" driver
                        pin = int(pin_match.group(2), 16)  # pin number is in hex
                        driver = pin_match.group(1)
                        if driver == "gpio":
                            driver_type = PWMDriverType.GPIO
                        elif driver == "pio":
                            driver_type = PWMDriverType.PIO
                        else:
                            # unknown driver
                            logger.warning(f"Found unknown driver type '{driver}' in line: {line}")
                            driver_type = PWMDriverType.UNKNOWN
                        chip = PWMChipInfo(chip=chip_number, channels=[], driver=driver_type, assigned_pin=pin)

                    else:
                        # This is neither a pwm_pio nor a pwm_gpio driver. Assume it is a hardware driver.
                        pwm_driver = PWMDriverType.HARDWARE  # if not pio then it is a plain hardware chip
                        chip = PWMChipInfo(chip=chip_number, channels=[], driver=pwm_driver)

                    result.append(chip)

                    # get all channels of the chip, but only add then if they are unsed
                    channels = int(chipmatch.group(2))
                    for i in range(channels):
                        if channelmatch := channelnumber_re.match(lines.pop(0)):
                            channel = int(channelmatch.group(1))
                            owner = channelmatch.group(2)
                            if "null" in owner or owner == "sysfs":
                                chip.channels.append(channel)
        return result
