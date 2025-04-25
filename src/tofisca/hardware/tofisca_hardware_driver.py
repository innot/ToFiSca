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
import re
import subprocess

import lgpio

from pwm_manager import PWMManager


class TofiscaHardwareDriver:
    LED_PIN = 18
    LED_PWM_CHAN = 2
    LED_PWM_FREQ = 300

    FAN_MOTOR_PIN = 19
    FAN_MOTOR_PWM_CHAN = 3
    FAN_MOTOR_PWM_FREQ = 25000

    REEL_MOTOR_PIN = 26
    FEED_SWITCH_PIN = 16

    def __init__(self):
        self._pwm_fan = None
        self._pwm_led = None
        self.handle: int | None = None
        self._auto_pickup_task: asyncio.Task | None = None
        self._pwm_running: dict = {}

#        self.allocate_gpio()
        self.allocate_pwm()

    def allocate_gpio(self):
        self.handle = lgpio.gpiochip_open(0)
        # lgpio.gpio_claim_output(self.handle, self.LED_PIN, 0)
        # lgpio.gpio_claim_output(self.handle, self.FAN_MOTOR_PIN, 0)
        lgpio.gpio_claim_output(self.handle, self.REEL_MOTOR_PIN, 0)
        lgpio.gpio_claim_alert(self.handle, self.FEED_SWITCH_PIN, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)

    def release_gpio(self):
        # lgpio.gpio_free(self.handle, self.LED_PIN)
        # lgpio.gpio_free(self.handle, self.FAN_MOTOR_PIN)
        lgpio.gpio_free(self.handle, self.REEL_MOTOR_PIN)
        lgpio.gpio_free(self.handle, self.FEED_SWITCH_PIN)
        lgpio.gpiochip_close(self.handle)

    def allocate_pwm(self):
        led_chan = self._get_pwm_channel_for_pin(self.LED_PIN)
        self._pwm_led = PWMManager(led_chan, self.LED_PWM_FREQ)

        fan_chan = self._get_pwm_channel_for_pin(self.FAN_MOTOR_PIN)
        self._pwm_fan = PWMManager(fan_chan, self.FAN_MOTOR_PWM_FREQ)

    @property
    def pickup_switch(self) -> int:
        return lgpio.gpio_read(self.handle, self.FEED_SWITCH_PIN)

    @property
    def reel_motor_running(self) -> bool:
        return lgpio.gpio_read(self.handle, self.REEL_MOTOR_PIN)

    def led_on(self, brightness: int = 75):
        if brightness > 100 or brightness < 0:
            raise ValueError(f"Invalid brightness value: {brightness} (must be between 0 and 100)")
        else:
            self._pwm_led.change_frequency(300)
            self._pwm_led.change_duty_cycle(brightness)
            self._pwm_led.start()
            #self._pwm_on(self.LED_PIN, 300, brightness)

    def led_off(self) -> None:
        self._pwm_led.stop()
        # self._pwm_off(self.LED_PIN)

    def reel_on(self, speed: int = 100) -> None:
        if speed > 100 or speed < 0:
            raise ValueError(f"Invalid speed value: {speed} (must be between 0 and 100)")
        else:
            self._pwm_on(self.REEL_MOTOR_PIN, 300, speed)

    def reel_off(self) -> None:
        self._pwm_off(self.REEL_MOTOR_PIN)

    def _pwm_on(self, pin: int, frequency: int, duty_cycle: int):
        lgpio.tx_pwm(self.handle, pin, frequency, duty_cycle)
        self._pwm_running[pin] = True

    def _pwm_off(self, pin: int):
        if lgpio.tx_busy(self.handle, pin, lgpio.TX_PWM):
            lgpio.tx_pwm(self.handle, pin, 0, 0)
        lgpio.gpio_write(self.handle, pin, 0)
        self._pwm_running[pin] = False

    async def start_auto_pickup(self) -> None:
        self._auto_pickup_task = asyncio.create_task(self._auto_pickup_task_runner())

    async def stop_auto_pickup(self) -> None:
        if self._auto_pickup_task is not None:
            self._auto_pickup_task.cancel()
        self.reel_off()

    async def _auto_pickup_task_runner(self) -> None:

        def feed_switch_callback(chip: int, gpio: int, level: int, timestamp: int):
            if gpio != self.FEED_SWITCH_PIN:
                return
            if level == 0:
                # switch is on = pickup is complete
                self.reel_off()
            else:
                # switch is off = more film to pick up
                self.reel_on()

        cb = lgpio.callback(self.handle, self.FEED_SWITCH_PIN, lgpio.BOTH_EDGES, feed_switch_callback)

        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            cb.cancel()
            raise

    def _get_pwm_channel_for_pin(self, pin: int) -> int:
        result = subprocess.run(['pinctrl', f'get {pin}'], capture_output=True, text=True).stdout
        m = re.search(r"CHAN(\d)", result)
        chan = int(m.group(1))
        return chan
