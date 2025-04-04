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
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import os.path
import re
import time


class HardwarePWMException(Exception):
    pass


# copied from https://github.com/Pioreactor/rpi_hardware_pwm
# License is also GPL v3, so this is ok.


class HardwarePWM:
    """
    Control the hardware PWM on the Raspberry Pi.

    To enable Hardware PWM `dtoverlay=pwm-2chan` must be added to `/boot/firmware/config.txt`.

    pwm0 is GPIO pin 18 (dtoverlay can be deployed to use GPIO 12 instead)
    pwm1 is GPIO pin 19 (dtoverlay can be deployed to use GPIO 13 instead)

    Example
    ----------
    >pwm = HardwarePWM(0, hz=20)
    >pwm.start(100)
    >
    >pwm.change_duty_cycle(50)
    >pwm.change_frequency(50)
    >
    >pwm.stop()

    Notes
    --------
     - For Rpi 1,2,3,4 only channels 0 and 1 are available
     - For Rpi 5 only channels 2 and 3 are available
     - If you get "write error: Invalid argument" - you have to set duty_cycle to 0 before changing period

    """

    _duty_cycle: float
    _hz: float

    def __init__(self, pwm_channel: int, hz: float = 1000) -> None:

        rpi_version = self._get_pi_rev()

        if rpi_version >= 5 and pwm_channel not in (2, 3):
            raise HardwarePWMException("Only channels 2 and 3 are available on the Rpi 5.")
        if rpi_version < 5 and pwm_channel not in (0, 1):
            raise HardwarePWMException("Only channels 0 and 1 are available on the Rpi 1,2,3 and 4.")

        if not self.is_overlay_loaded():
            raise HardwarePWMException(
                "Need to add 'dtoverlay=pwm-2chan' to /boot/firmware/config.txt and reboot"
            )

        self.chippath: str = self.get_chippath()
        self.pwm_channel = pwm_channel
        self.pwm_dir = f"{self.chippath}/pwm{self.pwm_channel}"
        self._duty_cycle = 0

        if not self.is_export_writable():
            raise HardwarePWMException(f"Need write access to files in '{self.chippath}'")
        if not self.does_pwmX_exists():
            self.create_pwmX()

        while True:
            try:
                self.change_frequency(hz)
                break
            except PermissionError:
                continue

    def get_chippath(self) -> str | None:
        for chip in [2, 0]:
            chippath: str = f"/sys/class/pwm/pwmchip{chip}"
            if os.path.exists(chippath):
                return chippath

    def is_overlay_loaded(self) -> bool:
        try:
            content = os.listdir("/sys/class/pwm")
            for dir in content:
                # todo:
                pass

        except FileNotFoundError:
            return False

    def is_export_writable(self) -> bool:
        return os.access(os.path.join(self.chippath, "export"), os.W_OK)

    def does_pwmX_exists(self) -> bool:
        return os.path.isdir(self.pwm_dir)

    def echo(self, message: int, file: str) -> None:
        with open(file, "w") as f:
            f.write(f"{message}\n")

    def create_pwmX(self) -> None:
        self.echo(self.pwm_channel, os.path.join(self.chippath, "export"))

    def start(self, initial_duty_cycle: float) -> None:
        self.change_duty_cycle(initial_duty_cycle)
        self.echo(1, os.path.join(self.pwm_dir, "enable"))

    def stop(self) -> None:
        self.change_duty_cycle(0)
        self.echo(0, os.path.join(self.pwm_dir, "enable"))

    def change_duty_cycle(self, duty_cycle: float) -> None:
        """
        a value between 0 and 100
        0 represents always low.
        100 represents always high.
        """
        if not (0 <= duty_cycle <= 100):
            raise HardwarePWMException("Duty cycle must be between 0 and 100 (inclusive).")
        self._duty_cycle = duty_cycle
        per = 1 / float(self._hz)
        per *= 1000  # now in milliseconds
        per *= 1_000_000  # now in nanoseconds
        dc = int(per * duty_cycle / 100)
        self.echo(dc, os.path.join(self.pwm_dir, "duty_cycle"))

    def change_frequency(self, hz: float) -> None:
        if hz < 0.1:
            raise HardwarePWMException("Frequency can't be lower than 0.1 on the Rpi.")

        self._hz = hz

        # we first have to change duty cycle, since https://stackoverflow.com/a/23050835/1895939
        original_duty_cycle = self._duty_cycle
        if self._duty_cycle:
            self.change_duty_cycle(0)

        per = 1 / float(self._hz)
        per *= 1000  # now in milliseconds
        per *= 1_000_000  # now in nanoseconds
        self.echo(int(per), os.path.join(self.pwm_dir, "period"))

        self.change_duty_cycle(original_duty_cycle)

    def _get_pi_rev(self) -> int:
        try:
            with open("/proc/device-tree/model", "r") as f:
                content = f.readline()
                if not content.startswith("Raspberry Pi"):
                    raise NotImplementedError("HardwarePWM is currently only supported on a Raspberry Pi.")
                x = re.search(r'[0-9]+', content)
                version = x.group(0)
                return int(version)
        except FileNotFoundError:
            raise NotImplementedError("HardwarePWM is currently only supported on a Raspberry Pi.")


if __name__ == "__main__":
    pwm = HardwarePWM(3, 300)
    pwm.start(0)
    for i in range(101):
        pwm.change_duty_cycle(i)
        time.sleep(0.1)

    pwm.stop()
