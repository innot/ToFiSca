import asyncio
import io
from asyncio import Task
from pprint import pprint
from threading import Condition, Lock
from typing import Any

import numpy as np
from pydantic import Field

from app import App
from configuration.config_item import ConfigItem
from configuration.database import Scope
from models import SizePixels

try:
    from picamera2 import Picamera2
    from picamera2.outputs import FileOutput
    from picamera2.encoders import JpegEncoder
    from libcamera import controls
except ImportError:
    from mock_picamera2 import Picamera2, controls
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


class CameraControls(ConfigItem):
    # values for the imx477 sensor. Other sensors might have different defaults and limits
    ae_enable: bool = Field(default=True)
    ae_exposure_mode: int = Field(default=0, ge=0, le=3)
    exposure_time: int = Field(default=20_000, ge=1, le=66_666)
    analogue_gain: float = Field(default=1.0, ge=1.0, le=16.0)
    awb_enable: int = Field(default=True)
    awb_mode: int = Field(default=0, ge=0, le=7)
    colour_temperature: int | None = Field(default=None, ge=100, le=100_000)
    colour_gain_red: float = Field(default=1.0, ge=0.0, le=32.0)
    colour_gain_blue: float = Field(default=1.0, ge=0.0, le=32.0)
    brightness: float = Field(default=0.0, ge=-1.0, le=1.0)
    contrast: float = Field(default=1.0, ge=0.0, le=32.0)
    saturation: float = Field(default=1.0, ge=0.0, le=32.0)
    sharpness: float = Field(default=1.0, ge=0.0, le=16.0)
    noise_reduction_mode: int = Field(default=0, ge=0, le=4)

    def as_controls_dict(self) -> dict[str, int | float | tuple[float, float]]:
        result: dict[str, int | float | tuple[float, float]] = {}

        result["AeEnable"] = self.ae_enable
        if self.ae_enable:
            result["AeExposureMode"] = self.ae_exposure_mode
            if self.ae_exposure_mode == 3:
                result["ExposureTime"] = self.exposure_time
        else:
            result["AnalogueGain"] = self.analogue_gain
            result["ExposureTime"] = self.exposure_time

        result["AwbEnable"] = self.awb_enable
        if self.awb_enable:
            result["AwbMode"] = self.awb_mode
        else:
            result["ColourTemperature"] = self.colour_temperature
            result["ColourGains"] = (self.colour_gain_red, self.colour_gain_blue)

        result["Brightness"] = self.brightness
        result["Contrast"] = self.contrast
        result["Saturation"] = self.saturation
        result["Sharpness"] = self.sharpness

        result["NoiseReductionMode"] = self.noise_reduction_mode

        return result


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
        self._supported_picamera_controls = self._picamera.camera_controls
        self._current_controls = CameraControls()

        pprint(self._supported_picamera_controls)

        self._config = CameraConfig()

        self._preview_config: dict = self._picamera.create_still_configuration()
        self.preview_size = self._config.preview_resolution
        self._current_preview_image: np.ndarray | None = None
        self._current_metadata: dict[str, Any] = {}

        self._stream_config: dict = self._picamera.create_video_configuration()
        self._scan_config: dict = self._picamera.create_still_configuration()

        self._stream_output: VideoStreamOutput | None = None
        # The BufferedIO to take the output of the camera for further distribution.
        # If not None indicates that a stream is currently active

        self._stream_output_counter: int = 0
        # number of open streams

        self._stream_lock = Lock()
        # mutex to secure changing any stream configurations

        self._shutdown_task: Task | None = None

    async def init(self):
        await self._config.retrieve(self.app.config_database, self.pid)
        await self._current_controls.retrieve(self.app.config_database, self.pid)

        # listen for shutdown events to free any allocated resources
        self._shutdown_task = asyncio.create_task(self._shutdown_waiter())

    async def _shutdown_waiter(self):
        await self.app.shutdown_event.wait()
        self._picamera.close()

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

    async def set_controls(self, new_controls: CameraControls, as_default: bool = False):
        self._current_controls = new_controls

        # change the controls immediatley if a video feed is running
        if self._stream_output is not None:
            self._picamera.set_controls(new_controls)

        # store the controls in the camera configuration
        self._preview_config["controls"] = new_controls


        if as_default:
            await self._current_controls.store(self.app.config_database, Scope.GLOBAL)
        else:
            await self._current_controls.store(self.app.config_database, self.pid)


    async def get_preview_image(self, reload: bool = False):

        # return the current preview image unless reload is True
        if not reload and self._current_preview_image is not None:
            return self._current_preview_image

        loop = asyncio.get_running_loop()
        config = self._preview_config

        def _get_image_runner() -> tuple[np.ndarray, dict[str, Any]]:

            pwm_duration = int(1_000_000 / self.app.hardware_manager.backlight.frequency)

            camera_controls = {
                # "AeEnable": False,
                # "AeFlickerMode": 1,
                # "AeFlickerPeriod": pwm_duration,
                "AwbEnable": True,
                # "ColourTemperature": 6400,
                "AeExposureMode": 3,
                "ExposureTime": pwm_duration * 2,
            }

            if not self._stream_output:
                # Video stream is not running - start the camera, take picture, and stop the camera again
                self.app.hardware_manager.backlight.dutycycle = 30
                self.app.hardware_manager.backlight.enable = True
                self._picamera.configure(config)
                self._picamera.set_controls(camera_controls)
                self._picamera.start()
                array = self._picamera.capture_array()
                metadata = self._picamera.capture_metadata()
                self._picamera.stop()
                self.app.hardware_manager.backlight.enable = False
            else:
                # Video stream is already running. Need to use the switch_mode... method
                self._stream_lock.acquire_lock()
                array = self._picamera.switch_mode_and_capture_array(config, name="main")
                metadata = self._picamera.capture_metadata()
                self._stream_lock.release_lock()

            pprint(metadata)

            return array, metadata

        # Get the image in a separate thread so we do not block the event loop
        result = await loop.run_in_executor(None, _get_image_runner)
        self._current_preview_image = result[0]
        self._current_metadata = result[1]
        pprint(result[1])
        return result[0]

    def start_streaming(self, encoder: JpegEncoder, size: tuple = (1014, 760)) -> VideoStreamOutput:
        with self._stream_lock:
            self._stream_output_counter += 1
            if self._stream_output:
                return self._stream_output

            self.app.hardware_manager.backlight.frequency = 100
            self.app.hardware_manager.backlight.enable = True

            config = self._preview_config
            config["lores"] = config["main"].copy()
            config["lores"]["preserve_ar"] = True
            config["lores"]["size"] = (1014, 760)

            self._stream_output = VideoStreamOutput()
            output = FileOutput(self._stream_output)
            self._picamera.configure(config)
            # self._picamera.controls.ExposureTime = 10_000
            # self._picamera.controls.ScalerCrop = (0,0,4056,3040)
            self._picamera.start_recording(encoder, output, name="lores")
            return self._stream_output

    def stop_streaming(self):
        with self._stream_lock:
            self._stream_output_counter -= 1
            if self._stream_output_counter == 0:
                self._picamera.stop_recording()
                self._stream_output = None
                self.app.hardware_manager.backlight.enable = False
            elif self._stream_output_counter < 0:
                raise RuntimeError("stop_streaming called without any running stream")
