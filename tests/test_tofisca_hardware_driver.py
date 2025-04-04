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

import pytest

try:
    import lgpio

    from hardware.tofisca_hardware_driver import TofiscaHardwareDriver


    @pytest.fixture
    def driver():
        driver = TofiscaHardwareDriver()
        yield driver
        driver.release_gpio()


    @pytest.mark.asyncio
    async def test_led(driver):
        driver.led_on(100)
        await asyncio.sleep(0.1)
        assert 1 == lgpio.gpio_read(driver.handle, driver.LED_PIN)
        driver.led_off()
        assert 0 == lgpio.gpio_read(driver.handle, driver.LED_PIN)

        driver.led_on(50)
        await asyncio.sleep(0.1)
        samples = []
        for i in range(100):
            samples.append(lgpio.gpio_read(driver.handle, driver.LED_PIN))
            await asyncio.sleep(0.01)

        assert round(samples.count(1) / 10) == round(samples.count(0) / 10)

        driver.led_off()


    @pytest.mark.asyncio
    async def test_reel_motor(driver):
        driver.reel_on()
        await asyncio.sleep(0.1)
        assert 1 == lgpio.gpio_read(driver.handle, driver.REEL_MOTOR_PIN)
        driver.reel_off()
        assert 0 == lgpio.gpio_read(driver.handle, driver.REEL_MOTOR_PIN)


    @pytest.mark.asyncio
    async def test_reel_pwm(driver):
        driver.reel_on(30)
        await asyncio.sleep(30)
        driver.reel_off()


    async def test_auto_pickup(driver):
        handler = driver.handle
        reel = driver.REEL_MOTOR_PIN
        # requires connection between GPIO16 (FEED_SW) and GPIO20
        switch = 20
        lgpio.gpio_claim_output(handler, switch, 1)

        assert 0 == lgpio.gpio_read(handler, reel)
        await driver.start_auto_pickup()
        await asyncio.sleep(0.1)

        for i in range(10):
            lgpio.gpio_write(handler, switch, 0)
            await asyncio.sleep(0.05)  # need to wait for the callback to complete
            assert 0 == lgpio.gpio_read(handler, reel)
            lgpio.gpio_write(handler, switch, 1)
            await asyncio.sleep(0.05)
            assert 1 == lgpio.gpio_read(handler, reel)

        await driver.stop_auto_pickup()

except ImportError:
    # lgpio not available
    pass
