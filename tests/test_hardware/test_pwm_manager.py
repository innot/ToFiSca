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
import time
from pathlib import Path

import pytest

try:
    import lgpio
except ImportError:
    lgpio = None
    pass

from hardware.pwm_manager import PWMManager, PWMChipInfo,PWMAlreadyInUse, PWMDriverType


@pytest.fixture()
def pwm_manager():
    pwm = PWMManager()
    yield pwm
    pwm.close()


@pytest.mark.skipif(not Path("/sys/kernel/debug/pwm").exists(), reason="requires /sys/kernel/debug/pwm")
def test_parse_pwmchips(pwm_manager):
    result = pwm_manager._parse_pwmchips()
    assert result
    assert isinstance(result[0], PWMChipInfo)


@pytest.mark.skipif(not Path("/sys/kernel/debug/pwm").exists(), reason="requires /sys/kernel/debug/pwm")
def test_all_pwm_gpio(pwm_manager):
    result = pwm_manager.available_pwm
    assert len(result) > 10

    # test the filtered versions
    hardware = pwm_manager.available_hardware_pwm
    assert len(hardware) > 1

    software = pwm_manager.available_software_pwm
    assert len(software) > 1

    assert len(hardware) + len(software) == len(result)


@pytest.mark.skipif(not Path("/sys/class/pwm").exists(), reason="requires /sys/class/pwm")
def test_hardware_pwm(pwm_manager):
    all_pwm = pwm_manager.available_hardware_pwm

    # pwm_pio crashes hard on my system. so ignore it for now and use a normal hardware pwm
    all_hardware = [pin for pin in all_pwm if pin.driver == PWMDriverType.HARDWARE]
    if len(all_hardware) == 0:
        # no hardware pwm found, end test
        pytest.fail()

    pwmpin = pwm_manager.allocate(all_hardware[0])

    # go thru one cycle and check that it does not raise any errors
    pwmpin.frequency = 100
    pwmpin.dutycycle = 50
    pwmpin.enable = True
    pwmpin.enable = False

    with pytest.raises(PWMAlreadyInUse):
        pwm_manager.allocate(pwmpin.gpio)

    # check properties in detail
    for enable in [True, False]:
        pwmpin.enable = enable
        assert pwmpin.enable == enable

        pwmpin.dutycycle = 0
        assert pwmpin.dutycycle == 0
        pwmpin.dutycycle = 100
        assert pwmpin.dutycycle == 100
        with pytest.raises(ValueError):
            pwmpin.dutycycle = -0.1
        with pytest.raises(ValueError):
            pwmpin.dutycycle = 100.1

        pwmpin.frequency = 1000
        assert pwmpin.frequency == 1000

    assert pwmpin.is_allocated
    pwm_manager.free(pwmpin.gpio)
    assert not pwmpin.is_allocated


@pytest.mark.skipif(not lgpio, reason="lgpio not install on this system")
def test_software_pwm(pwm_manager):
    all_pwm = pwm_manager.available_software_pwm

    pwmpin = pwm_manager.allocate(all_pwm[0].gpio)

    # go thru one cycle and check that it does not raise any errors
    pwmpin.frequency = 100
    pwmpin.dutycycle = 50
    pwmpin.enable = True
    pwmpin.enable = False

    with pytest.raises(PWMAlreadyInUse):
        pwm_manager.allocate(pwmpin.gpio)

    # check properties in detail
    for enable in [True, False]:
        pwmpin.enable = enable
        assert pwmpin.enable == enable

        pwmpin.dutycycle = 0
        assert pwmpin.dutycycle == 0
        pwmpin.dutycycle = 100
        assert pwmpin.dutycycle == 100
        with pytest.raises(ValueError):
            pwmpin.dutycycle = -0.1
        with pytest.raises(ValueError):
            pwmpin.dutycycle = 100.1

        pwmpin.frequency = 1000
        assert pwmpin.frequency == 1000

    assert pwmpin.is_allocated
    pwm_manager.free(pwmpin.gpio)
    assert not pwmpin.is_allocated

def test_foobar():
    pwm = PWMManager()
    pin = pwm.allocate(23)

    pin.frequency = 1000
    pin.dutycycle = 50
    pin.enable = True

    pwm.free(pin)

    return

    for dc in range(101):
        pin.dutycycle = dc
        time.sleep(0.1)

    for dc in range(100, 0, -10):
        pin.dutycycle = dc
        time.sleep(1)


