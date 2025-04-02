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
import unittest

import lgpio

from hardware.tofisca_hardware_driver import TofiscaHardwareDriver


class MyTestCase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.driver = TofiscaHardwareDriver()

    async def asyncTearDown(self) -> None:
        self.driver.release_gpio()

    async def test_led(self):
        hardware = self.driver
        hardware.led_on(100)
        await asyncio.sleep(0.1)
        self.assertEqual(1, lgpio.gpio_read(hardware.handle, hardware.LED_PIN))
        hardware.led_off()
        self.assertEqual(0, lgpio.gpio_read(hardware.handle, hardware.LED_PIN))

        hardware.led_on(50)
        await asyncio.sleep(0.1)
        samples = []
        for i in range(100):
            samples.append(lgpio.gpio_read(hardware.handle, hardware.LED_PIN))
            await asyncio.sleep(0.01)

        self.assertEqual(round(samples.count(1) / 10), round(samples.count(0) / 10))

        hardware.led_off()

    async def test_led_2(self):
        hardware = self.driver

        for i in range(101):
            hardware.led_on(i)
            await asyncio.sleep(0.1)

        hardware.led_off()

    async def test_reel_motor(self):
        hardware = self.driver
        hardware.reel_on()
        await asyncio.sleep(0.1)
        self.assertEqual(1, lgpio.gpio_read(hardware.handle, hardware.REEL_MOTOR_PIN))
        hardware.reel_off()
        self.assertEqual(0, lgpio.gpio_read(hardware.handle, hardware.REEL_MOTOR_PIN))

    async def test_reel_pwm(self):

        hardware = self.driver
        hardware.reel_on(30)
        await asyncio.sleep(30)
        hardware.reel_off()

    async def test_auto_pickup(self):
        hardware = self.driver
        handler = hardware.handle
        reel = hardware.REEL_MOTOR_PIN
        # requires connection between GPIO16 (FEED_SW) and GPIO20
        switch = 20
        lgpio.gpio_claim_output(handler, switch, 1)

        self.assertEqual(0, lgpio.gpio_read(handler, reel))
        await hardware.start_auto_pickup()
        await asyncio.sleep(0.1)

        for i in range(10):
            lgpio.gpio_write(handler, switch, 0)
            await asyncio.sleep(0.05)  # need to wait for the callback to complete
            self.assertEqual(0, lgpio.gpio_read(handler, reel))
            lgpio.gpio_write(handler, switch, 1)
            await asyncio.sleep(0.05)
            self.assertEqual(1, lgpio.gpio_read(handler, reel))

        await hardware.stop_auto_pickup()


if __name__ == '__main__':
    unittest.main()
