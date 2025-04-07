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
import cv2 as cv
import numpy as np
from poetry.console.commands import self

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
#
from film_generator import TestFrameGenerator


class MockPiCamera2:
    """
    A mock of the Picamera2 library that simulates just enough functionallity to make
    ToFiSca run its test without running on real hardware.
    """

    def __init__(self, camera: str = None):
        self._frame_count: int = 0
        self.tfg = TestFrameGenerator()

        self.camera = camera
        self.camera_config: dict | None= None

    def create_still_configuration(self) -> dict:
        return {"main": {"format": "BGR888", "size": (4056, 3040), "preserve_ar": True}}

    def create_video_configuration(self) -> dict:
        return {"main": {"format": "XBGR8888", "size": (1280, 720), "preserve_ar": True}}

    def start(self, config: dict = None):
        if self.camera_config is None and config is None:
            raise NotImplementedError("preview is not supported")
        if config is not None:
            self.configure(config)

    def configure(self, config: dict):
        self.camera_config = config

    def switch_mode_and_capture_array(self, camera_config) -> np.ndarray:
        """Switch the camera into a new (capture) mode, capture the image array data.

        Then return back to the initial camera mode.
        """
        self.tfg.image_size = camera_config.main.size
        img = self.tfg.render_image()

        h, w, _ = img.shape
        x_offset = int(w / 2)
        font = cv.FONT_HERSHEY_SIMPLEX
        cv.putText(img, f"{self._frame_count}", (x_offset, 50), font, 2, (200, 200, 0), 2, cv.LINE_AA)
        cv.putText(img, f"{w}x{h}", (x_offset, 100), font, 2, (200, 200, 0), 2, cv.LINE_AA)
        self._frame_count += 1

        return img

