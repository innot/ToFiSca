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
import pytest

from mock_picamera2.picamera2 import Picamera2


@pytest.fixture
def picam2():
    return Picamera2()


def test_create_configurations(picam2):
    config = picam2.create_still_configuration()
    assert config['use_case'] == 'still'
    assert config['main'] is not None

    config = picam2.create_video_configuration()
    assert config['use_case'] == 'video'
    assert config['main'] is not None


def test_start(picam2):
    picam2.start()
    assert picam2.started == True

    # can be started again
    picam2.start()

    picam2.stop()
    assert picam2.started == False


def test_configure(picam2):
    assert picam2.camera_config is None

    config = picam2.create_still_configuration()
    picam2.configure(config)
    assert picam2.camera_config is config


def test_capture_array(picam2):
    config = picam2.create_still_configuration()
    picam2.start(config)
    image = picam2.capture_array()
    assert image is not None
    height, width, planes = image.shape
    assert planes == 3
    assert width == config['main']['size'][0]
    assert height == config['main']['size'][1]

    # try a different resolution
    config['main']['size'] = (640, 480)
    picam2.configure(config)
    image = picam2.capture_array()
    height, width, _ = image.shape
    assert width == config['main']['size'][0]
    assert height == config['main']['size'][1]


def test_switch_mode_and_capture_array(picam2):
    config1 = picam2.create_video_configuration()
    picam2.configure(config1)
    picam2.start()
    config2 = picam2.create_still_configuration()
    image = picam2.switch_mode_and_capture_array(config2)
    height, width, _ = image.shape
    assert width == config2['main']['size'][0]
    assert height == config2['main']['size'][1]

    # check that the previous config is still active
    assert picam2.camera_config is config1
