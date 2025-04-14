#  This file is part of the ToFiSca application.
#
#  ToFiSca is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ToFiSca is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ToFiSca.  If not, see <http://www.gnu.org/licenses/>.
#
#  Copyright (c) 2025 by Thomas Holland, thomas@innot.de
#

import enum
import logging
import re
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

import lgpio
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PWMType(enum.Enum):
    """
    The types of pwm generation a gpio pin supports
    """
    HARDWARE = "hardware"
    PIO = "pio"
    LGPIO = "software"


class PWMPinInfo(BaseModel):
    """
    Storage for a gpio pin number and the :class:`PWMType` it supports.

    Technically, a pin could support multiple types (hardware and software), but
    only the 'best' type is stored.
    """
    gpio: int = Field(ge=0, le=255)
    type: PWMType = Field()


class HardwarePWMPinInfo(PWMPinInfo):
    """
    Additional information about a hardware pin. The 'pwmchip_' number and its channel.
    """
    chip: int = Field(ge=0, le=255)
    channel: int = Field(ge=0, le=255)


class PWMChipInfo(BaseModel):
    """
    Information about 'pwmchip_'.
    It has the channels still available (not used by the system) and the type of chip
    (currently only `PWMType.HARDWARE` and `PWMType.PIO` - the latter only available on the
    Raspberry Pi 5 and higher).
    """
    chip: int = Field(ge=0, le=255)
    channels: list[int] = Field()
    type: PWMType = Field()


class PioPWMChipInfo(PWMChipInfo):
    """
    Additional information required for the `PWMType.PIO` chips, where each chip is associated with a single pin.
    """
    pio_gpio: Union[int, None] = Field(default=None, ge=0, le=255)


class PWMAlreadyInUse(RuntimeError):

    def __init__(self, pwm_pin: PWMPinInfo):
        msg = f"PWMPin Pin {pwm_pin.gpio} already allocated."
        super().__init__(msg)


class PWMPin(ABC):
    """
    Class to control a single PWM gpio pin.

    There are several properties to control the pwm output:

        - :meth:`enable` to switch to pwn output on or off
        - :meth:`frequency` to set the pwm frequency, and
        - :meth:`dutycycle` to set the pwm dutycycle.

    This class should not be instantiated directly. Instead use :meth:`PWMManager.allocate` to get a
    `PWMPin` instance for a given port.
    The PWMManager keeps track of all allocated pins, assures that a pin can only be allocated once and
    frees the associated resources upon exit.
    """

    def __init__(self, pin: PWMPinInfo):
        self._pin = pin
        self._frequency: float = 1000
        self._dutycycle: float = 0.5
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


class HardwarePWMPin(PWMPin):

    def __init__(self, pin: PWMPinInfo):
        super().__init__(pin)

        if not isinstance(pin, HardwarePWMPinInfo):
            raise TypeError("Pin is not a HardwarePWMPinInfo")

        self._pin: HardwarePWMPinInfo = pin
        self._is_allocated = False

        self._pwm_chip_path = Path(f"/sys/class/pwm/pwmchip{pin.chip}/")
        self._pwm_pwm_path = self._pwm_chip_path / f"pwm{pin.channel}/"

    def __del__(self):
        if self._is_allocated:
            self._free()  # hopefully do not leave any allocated pins behind

    @PWMPin.dutycycle.setter
    def dutycycle(self, percent: float) -> None:
        if not (0 <= percent <= 100):
            raise ValueError(f"Duty cycle must be between 0% and 100% (inclusive), was {percent}%")
        self._dutycycle = percent

        # get the current frequency and convert to nanoseconds
        period = int(1_000_000_000 / self.frequency)
        dutycycle_ns = int(period * percent / 100)

        # set the new dutycycle in the sysfs
        self.echo(self._pwm_pwm_path / "duty_cycle", dutycycle_ns)

    @PWMPin.frequency.setter
    def frequency(self, hz: int) -> None:
        self._frequency = hz

        # change Hz to ns
        period = int(1_000_000_000 / hz)

        # calculate the duty_cycle for the new period
        dutycycle_ns = int(period * self.dutycycle / 100)

        self.echo(self._pwm_pwm_path / "duty_cycle", 0)  # in case the new dutycycle is longer than the old period
        self.echo(self._pwm_pwm_path / "period", period)
        self.echo(self._pwm_pwm_path / "duty_cycle", dutycycle_ns)

    @PWMPin.enable.setter
    def enable(self, enable: bool) -> None:
        if enable:
            self.echo(self._pwm_pwm_path / "enable", "1")
        else:
            self.echo(self._pwm_pwm_path / "enable", "0")
        self._is_on = enable

    def _allocate(self):
        # activate the channel
        try:
            self.echo(self._pwm_chip_path / "export", self._pin.channel)
            self._is_allocated = True
            # Immediatly setting any pwm value caused PermissionErrors
            # Give the os some time to set up the pwm_ node in the sysfs
            time.sleep(0.1)
        except OSError:
            raise PWMAlreadyInUse(self._pin)

    def _free(self):
        # release the channel
        try:
            self.echo(self._pwm_chip_path / "unexport", self._pin.channel)
            self._is_allocated = False
        except OSError:
            # For now, ignore error
            logger.warning(f"Free PWMPin pin {self._pin} was freed again")

    @staticmethod
    def echo(file: Path, value: any):
        with open(file, "w") as f:
            f.write(f"{value}\n")


class SoftwarePWMPin(PWMPin):
    """
    Generate a pwm signal using the `lgpio` library
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
    def available_hardware_pwm(self) -> list[HardwarePWMPinInfo]:
        """
        The list of all pins supporting hardware pwm on the current platform.
        """
        return [pin for pin in self.available_pwm if isinstance(pin, HardwarePWMPinInfo)]

    @property
    def available_software_pwm(self) -> list[PWMPinInfo]:
        """
        The list of all pins supporting software pwm on the current platform.
        """
        return [pin for pin in self.available_pwm if pin.type == PWMType.LGPIO]

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

        if pininfo.type == PWMType.LGPIO:
            pindrv = SoftwarePWMPin(pininfo)
        else:
            pindrv = HardwarePWMPin(pininfo)

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
        gpiolist = subprocess.getoutput("pinctrl").split("\n")
        for gpio in gpiolist:
            ctrlsmatch = matchctrls.match(gpio)
            if ctrlsmatch:
                gpio = int(ctrlsmatch.group(1))

                chipchannel = matchchipchannel.match(ctrlsmatch.group(2))
                if chipchannel:
                    # The pin is a Hardware PWMPin pin
                    result.append(HardwarePWMPinInfo(gpio=gpio,
                                                     type=PWMType.HARDWARE,
                                                     chip=int(chipchannel.group(1)),
                                                     channel=int(chipchannel.group(2)),
                                                     )
                                  )
                    continue
                if ctrlsmatch.group(2).startswith("PIO"):
                    # The pin is a PIO pin. Get the pwmchip from the number
                    pwmchips = self.pwmchips
                    for chip in pwmchips:
                        if isinstance(chip, PioPWMChipInfo) and chip.pio_gpio == gpio:
                            result.append(HardwarePWMPinInfo(gpio=gpio,
                                                             type=PWMType.PIO,
                                                             chip=chip.chip,
                                                             channel=0,
                                                             )
                                          )
                    continue
                if ctrlsmatch.group(2) == "none":
                    # The pin can be used for software pwm
                    result.append(PWMPinInfo(gpio=gpio, type=PWMType.LGPIO))
        return result

    @staticmethod
    def _parse_pwmchips() -> list[PWMChipInfo]:
        """
        Parses `/sys/kernel/debug/pwm` to get a list of all pwmchip instances supported by the platform hardware.
        """

        result: list[PWMChipInfo] = []

        chipnumber_re = re.compile(r'(\d+):.*(\d)\sPWM.*')
        channelnumber_re = re.compile(r'\s*pwm-(\d+)\s*\((\S*).*\)')
        piopin_re = re.compile(r'.*pwm_pio@(\d+).*')

        pwmfile = Path("/sys/kernel/debug/pwm")
        with (open(pwmfile, "r") as f):
            lines = f.read().splitlines()
            while len(lines) > 0:
                line = lines.pop(0)
                if chipmatch := chipnumber_re.match(line):
                    # start of a new chip.
                    chip_number = chipmatch.group(1)  # the number of the chip, e.g. 0 for pwmchip0

                    if "pwm_pio" in line:
                        pwm_type = PWMType.PIO  # this chip is a raspi 5 pio chip
                        match = piopin_re.match(line)
                        piopin = int(match.group(1))
                        chip = PioPWMChipInfo(chip=chip_number, channels=[], type=pwm_type, pio_gpio=piopin)

                    else:
                        pwm_type = PWMType.HARDWARE  # if not pio then it is a plain hardware chip
                        chip = PWMChipInfo(chip=chip_number, channels=[], type=pwm_type)
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
