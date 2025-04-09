import asyncio
import io
from threading import Condition

import numpy as np
from pydantic import Field

from app import App
from config_item import ConfigItem
from database import Scope
from models import SizePixels

try:
    from picamera2 import Picamera2
    from picamera2.outputs import FileOutput
    from picamera2.encoders import JpegEncoder
except ImportError:
    from mock_picamera2 import Picamera2
    from mock_picamera2.outputs import FileOutput
    from mock_picamera2.encoders import JpegEncoder


class CameraConfig(ConfigItem):
    aspect_ration: float = Field(default=(4056 / 3040), description="The aspect ratio of the camera.")

    preview_resolution: SizePixels = Field(default=SizePixels(width=2028, height=1520),
                                           description="The resolution used for preview images in the frontend")
    stream_resolution: SizePixels = Field(default=SizePixels(width=1024, height=768),
                                          description="The resolution used for streaming images to the frontend")
    scan_resolution: SizePixels = Field(default=SizePixels(width=4056, height=3040),
                                        description="The resolution used for scanning images")


class VideoStreamOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class CameraManager:
    def __init__(self, app: App, pid: int | Scope = Scope.GLOBAL) -> None:

        self.app = app
        self.pid = pid

        self._picamera = Picamera2()

        self._config = CameraConfig()

        self._preview_config: dict = self._picamera.create_still_configuration()
        self.preview_size = self._config.preview_resolution

        self._stream_config: dict = self._picamera.create_video_configuration()
        self._scan_config: dict = self._picamera.create_still_configuration()

        self._stream_output: VideoStreamOutput | None = None
        # The io to take the output of the camera for further distribution.
        # If not None indicates that a stream is currently active

        self._stream_output_counter: int = 0
        # number of open streams

    async def load(self):
        await self._config.retrieve(self.app.config_database, self.pid)

    @property
    def config(self) -> CameraConfig:
        return self._config.model_copy()

    @property
    def preview_size(self) -> SizePixels:
        return self._config.preview_resolution

    @preview_size.setter
    def preview_size(self, size: SizePixels) -> None:
        self._config.preview_resolution = size
        self._preview_config["main"]["size"] = size.as_tupel()

    async def set_config(self, new_config: CameraConfig, as_default: bool = False):
        self._config = new_config
        if as_default:
            await self._config.store(self.app.config_database, Scope.GLOBAL)
        else:
            await self._config.store(self.app.config_database, self.pid)

        # todo: update the configurations

    async def get_preview_image(self):

        loop = asyncio.get_running_loop()
        config = self._preview_config

        def _get_image_runner() -> np.ndarray:
            if not self._stream_output:
                # Video stream is not running - start the camera, take picture, and stop the camera again
                self._picamera.start(config)
                array = self._picamera.capture_array()
                self._picamera.stop()
            else:
                # video stream is already running. Need to use the switch_mode... method
                array = self._picamera.switch_mode_and_capture_array(config)
            return array

        # Get the image in a seperate thread so we do not block the event loop
        result = await loop.run_in_executor(None, _get_image_runner)
        return result

    def start_streaming(self, encoder: JpegEncoder, size: tuple = (640, 480)) -> VideoStreamOutput:
        self._stream_output_counter += 1
        if self._stream_output:
            return self._stream_output

        config = self._stream_config
        config["main"]["size"] = size

        self._stream_output = VideoStreamOutput()
        output = FileOutput(self._stream_output)
        self._picamera.configure(config)
        self._picamera.start_recording(encoder, output)
        return self._stream_output

    def stop_streaming(self):
        self._stream_output_counter -= 1
        if self._stream_output_counter == 0:
            self._picamera.stop_recording()
            self._stream_output = None
        elif self._stream_output_counter < 0:
            raise RuntimeError("stop_streaming called without any running stream")
