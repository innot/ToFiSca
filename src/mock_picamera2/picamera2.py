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
import logging
import time
from datetime import datetime
from threading import Thread, Event, Lock

import cv2 as cv
import numpy as np
from PIL import Image

from film_generator import FilmFrameGenerator
from mock_picamera2.encoders.jpeg_encoder import JpegEncoder

logger = logging.getLogger(__name__)

class Picamera2:
    """
    A mock of the Picamera2 library that simulates just enough functionality to make
    ToFiSca run its test without running on real hardware.
    """

    def __init__(self, camera: str = None):

        self.started = False

        self.camera = MockCamera()
        self.camera_config: dict | None = None

        self._stream_thread: Thread | None = None
        self.lock = Lock()
        self._encoders: set = set()

    @staticmethod
    def create_still_configuration() -> dict:
        default = {
            'use_case': 'still',
            'transform': "libcamera.Transform 'identity'",
            'colour_space': "libcamera.ColorSpace 'sYCC'",
            'buffer_count': 1,
            'queue': True,
            'main': {
                'format': 'BGR888',
                'size': (4056, 3040),
                'preserve_ar': True},
            'lores': None,
            'raw': {
                'format': 'SRGGB12_CSI2P',
                'size': (4056, 3040)},
            'controls': {
                'NoiseReductionMode': "NoiseReductionModeEnum.HighQuality: 2",
                'FrameDurationLimits': (100, 1000000000)},
            'sensor': {},
            'display': None,
            'encode': None}

        return default

    def create_video_configuration(self) -> dict:
        default = {
            'use_case': 'video',
            'transform': "libcamera.Transform 'identity'",
            'colour_space': "libcamera.ColorSpace 'Rec709'",
            'buffer_count': 6,
            'queue': True,
            'main': {
                'format': 'XBGR8888',
                'size': (1280, 720),
                'preserve_ar': True},
            'lores': None,
            'raw': {
                'format': 'SRGGB12_CSI2P',
                'size': (1280, 720)},
            'controls': {
                'NoiseReductionMode': "NoiseReductionModeEnum.Fast: 1",
                'FrameDurationLimits': (33333, 33333)},
            'sensor': {},
            'display': 'main',
            'encode': 'main'}
        return default

    def create_preview_configuration(self) -> dict:
        config = {'use_case': 'preview',
                  'transform': "libcamera.Transform 'identity'",
                  'colour_space': "libcamera.ColorSpace 'sYCC'",
                  'buffer_count': 4,
                  'queue': True,
                  'main': {
                      'format': 'XBGR8888',
                      'size': (640, 480),
                      'preserve_ar': True},
                  'lores': None,
                  'raw': {
                      'format': 'SRGGB12_CSI2P',
                      'size': (640, 480)},
                  'controls': {
                      'NoiseReductionMode': "NoiseReductionModeEnum.Minimal: 3",
                      'FrameDurationLimits': (100, 83333)},
                  'sensor': {},
                  'display': 'main',
                  'encode': 'main'}
        return config

    def start(self, config: dict = None, show_preview: bool = False) -> None:

        if self.camera_config is None and config is None:
            config = "preview"
        if config is not None:
            self.configure(config)
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        if show_preview is not None:
            pass  # self.start_preview(show_preview)

        self.camera.start()
        self.started = True

    def stop(self) -> None:
        self.started = False
        self.camera.stop()

    def configure(self, config: dict):
        self.camera_config = config

    def capture_array(self, name: str = "main"):
        return self.camera.generate_image(name, self.camera_config)

    def capture_image(self, name: str = "main") -> Image.Image:
        array = self.capture_array(name)
        image = Image.fromarray(array)
        return image

    def switch_mode_and_capture_array(self, camera_config: dict, name="main") -> np.ndarray:
        """Switch the camera into a new (capture) mode, capture the image array data.

        Then return back to the initial camera mode.
        """
        current_config = self.camera_config  # save the current camera_config to restore it later
        self.camera_config = camera_config
        image = self.camera.generate_image(name, self.camera_config)
        self.camera_config = current_config  # restore camera_config
        return image

    def start_recording(self, encoder, output, pts=None, config=None, quality=None, name=None) -> None:
        if self.camera_config is None and config is None:
            config = self.create_video_configuration()
        if config is not None:
            self.configure(config)

        self._encoder = encoder

        if output is not None:
            encoder.output = output

        encoder.config = self.camera_config
        encoder.start()
        self.camera.start_streaming(encoder, self.camera_config)

        self.start()

        with self.lock:
            self._encoders.add(encoder)

        logger.debug("recording started")

    def stop_recording(self):
        self.camera.stop_streaming()
        with self.lock:
            remove = self._encoders.copy()
            for encoder in remove:
                encoder.stop()
                self._encoders.remove(encoder)
        self.stop()

        logger.debug("recording stoped")


    def start_preview(self):
        raise NotImplementedError()


class MockCamera:

    def __init__(self, ):
        self._ffg = FilmFrameGenerator()
        self._stream_thread: Thread | None = None

        self._controls = None

        self.stop_signal = Event()

    def start(self, controls = None):
        self._controls = controls

    def stop(self):
        if self._stream_thread is not None:
            self.stop_streaming()

    def generate_image(self, name: str, config: dict) -> np.ndarray:
        self._ffg.image_size = config[name]['size']

        image = self._ffg.render_image()

        # Stamp the current resolution on the image.
        h, w, _ = image.shape
        x_offset = int(w / 4)
        font = cv.FONT_HERSHEY_SIMPLEX
        cv.putText(image, f"{w}x{h}", (x_offset, 50), font, 1, (200, 200, 0), 2, cv.LINE_AA)

        return image

    def _stream_runner(self, target: JpegEncoder, name: str, config: dict):
        frame_count = 0
        last_ts = datetime.now().timestamp()
        while not self.stop_signal.is_set():
            image = self.generate_image(name, config)

            # delay to simulte 30fps
            current_ts = datetime.now().timestamp()
            delta = current_ts - last_ts
            if delta < 1 / 30:
                time.sleep(delta)
            fps = round(1 / delta)
            last_ts = current_ts

            # stamp the framecount on the image
            h, w, _ = image.shape
            x_offset = int(w / 4)
            font = cv.FONT_HERSHEY_SIMPLEX
            cv.putText(image, f"frame {frame_count}  ({fps} fps)", (x_offset, 100), font, 1, (200, 200, 0), 2,
                       cv.LINE_AA)
            frame_count += 1

            # send the image to the encoder
            target.encode_image(image)

    def start_streaming(self, target: JpegEncoder, config: dict):
        if self._stream_thread is not None:
            raise RuntimeError("Camera is already streaming")
        self._stream_thread = Thread(target=self._stream_runner, args=(target, "main", config), daemon=True)
        self._stream_thread.start()

    def stop_streaming(self):
        self.stop_signal.set()
        self._stream_thread.join()
        self._stream_thread = None
