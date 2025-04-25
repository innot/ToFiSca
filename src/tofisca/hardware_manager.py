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
import asyncio
from asyncio import Task

from pydantic import Field, BaseModel

from app import App
from configuration.config_item import ConfigItem
from hardware.pwm_manager import PWMPin
from pwm_manager import PWMManager


class PinInfo(BaseModel):
    gpio: int = Field(ge=0, le=27)  # 28 pins on the standard raspberry pi
    hardware_pwm: bool = Field(default=False)
    software_pwm: bool = Field(default=False)
    assigned_to: str | None = Field(default=None)


class BacklightController(ConfigItem):
    gpio: int = Field(default=18, ge=0, le=27)
    frequency: int = Field(default=300, ge=1, le=1_000_000)
    dutycycle: float = Field(default=50, ge=0.0, le=100.0)
    invert: bool = Field(default=False)
    enable: bool = Field(default=False, exclude=True)  # enable is not stored in the database.

    _pwm_manager: PWMManager | None = None
    _pwm_pin: PWMPin | None = None

    @property
    def pwm_manager(self) -> PWMManager:
        return self._pwm_manager

    @pwm_manager.setter
    def pwm_manager(self, manager: PWMManager) -> None:
        self._pwm_manager = manager

    def __setattr__(self, name, value):
        if name == "enable":
            self._pwm_pin.enable = value
        if name == "frequency":
            self._pwm_pin.frequency = value
        if name == "dutycycle":
            self._pwm_pin.dutycycle = value
        if name == "invert":
            self._pwm_pin.invert = value
        if name == "gpio":
            # need to change the pwm pin instance, but only if the value has actually changed
            if value != self.gpio or self._pwm_pin is None:
                # allocate the new pin and copy the existing values
                new_pwm = self._pwm_manager.allocate(self.gpio)
                new_pwm.frequency = self.frequency
                new_pwm.dutycycle = self.dutycycle
                new_pwm.polarity = self.invert
                new_pwm.enable = self.enable

                # setup successful, we can now deallocate the old pin and store the new pin
                if self._pwm_pin is not None:
                    self._pwm_manager.free(self._pwm_pin)
                self._pwm_pin = new_pwm

        super().__setattr__(name, value)


class HardwareManager:

    def __init__(self, app: App):
        self.app = app

        self._pwm_manager = PWMManager()

        self._gpio_list: list[PinInfo] = []

        self._backlight_controller: BacklightController = BacklightController(invert=False, enable=False)
        self._backlight_controller.pwm_manager = self._pwm_manager

        self._shutdown_task: Task | None = None

    async def init(self):

        # generate the list of all available gpios
        self._gpio_list = []
        for i in range(28):  # 28 pins on the standard raspberry pi. todo: autodetect the number of pins
            self._gpio_list.append(PinInfo(gpio=i))

        for pin in self._pwm_manager.available_hardware_pwm:
            if pin.gpio <= 27:
                self._gpio_list[pin.gpio].hardware_pwm = True

        for pin in self._pwm_manager.available_software_pwm:
            if pin.gpio <= 27:
                self._gpio_list[pin.gpio].software_pwm = True

        self._backlight_controller = BacklightController(invert=False, enable=False)
        self._backlight_controller.pwm_manager = self._pwm_manager
        await self._backlight_controller.retrieve(self.app.config_database)

        # The Default setup of a pydantic model does not go through the __setattr__ method.
        # So set the gpio once to itself to allocate the gpio
        self._backlight_controller.gpio = self._backlight_controller.gpio

        # listen for shutdown events to free any allocated resources
        self._shutdown_task = asyncio.create_task(self._shutdown_waiter())

    async def _shutdown_waiter(self):
        await self.app.shutdown_event.wait()
        self._pwm_manager.close()

    @property
    def backlight(self) -> BacklightController:
        """
        The :class:`BacklightController` instance to set and change the backlight parameters.
        :return:
        """
        return self._backlight_controller

    @property
    def all_gpios(self) -> list[PinInfo]:
        result = self._gpio_list.copy()

        # change the assigned_to field here as it would be too burdensome to track any changes within the class
        result[self._backlight_controller.gpio].assigned_to = "backlight"

        return result
