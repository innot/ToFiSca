import cv2 as cv
from pydantic import Field

from app import App
from config_item import ConfigItem
from database import Scope
from models import Size

try:
    from picamera2 import Picamera2
except ImportError:
    from tests.mock_picamera2 import MockPiCamera2 as Picamera2


class CameraConfig(ConfigItem):
    aspect_ration: float = Field(default=(4056 / 3040), description="The aspect ratio of the camera.")
    preview_resolution: Size = Field(default=Size(width=2028, height=1520),
                                     description="The resolution used for preview images in the frontend")
    stream_resolution: Size = Field(default=Size(width=1024, height=768),
                                    description="The resolution used for streaming images to the frontend")
    scan_resolution: Size = Field(default=Size(width=4056, height=3040),
                                  description="The resolution used for scanning images")


class CameraManager:
    def __init__(self, app: App, pid: int) -> None:

        self.app = app
        self.pid = pid

        self._picamera = Picamera2()
        self._cam_started: bool = False

        self._config = CameraConfig()

        self._preview_config: dict = self._picamera.create_still_configuration()
        self._stream_config: dict = self._picamera.create_video_configuration()
        self._scan_config: dict = self._picamera.create_still_configuration()

    async def load(self):
        await self._config.retrieve(self.app.config_database, self.pid)

    @property
    def config(self) -> CameraConfig:
        return self._config.model_copy()

    async def set_config(self, new_config: CameraConfig, as_default: bool = False):
        self._config = new_config
        if as_default:
            await self._config.store(self.app.config_database, Scope.GLOBAL)
        else:
            await self._config.store(self.app.config_database, self.pid)

        # todo: update the configurations

    def get_preview_image(self):

        # todo: should the camera be started at initialization?
        # how much processing does it take if the camera is running continously
        if not self._cam_started:
            self._picamera.start()
            self._cam_started = True

        config = self._preview_config

        array = self._picamera.switch_mode_and_capture_array(config)

        return array

    def start_streaming(self, output, size: tuple = (640, 480)):
        print("Camera_manager: start streaming")
        self._picamera.start_recording(output, format='mjpeg', resize=size)
        self._stream_output = output

    def stop_streaming(self):
        print("Camera_manager: stop streaming")
        if self._stream_output is not None:
            self._picamera.stop_recording()
            self._stream_output.finish()
            self._stream_output = None


if __name__ == '__main__':
    ch = CameraManager()
    buf = ch.get_png_image(400)
    image = cv.imdecode(buf, cv.IMREAD_UNCHANGED)
    cv.imshow('png', image)
    cv.waitKey(0)
