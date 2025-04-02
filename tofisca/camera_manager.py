from enum import Enum
from typing import Tuple

import cv2 as cv

from film_generator import TestFrameGenerator

try:
    from mock_picamera2 import Picamera2
except ImportError:
    from mockpicamera import Picamera2

class CameraConfig:

    camera_resolution = (640, 480)


class CameraManager:
    def __init__(self, revision: str = 'imx477'):

        self._picamera = Picamera2()

        self._sensor_mode = 0
        self._still_image_size = DEFAULT_RESOLUTION
        self._video_image_size = DEFAULT_RESOLUTION
        self._stream_output = None

        # if !raspi:
        self._picamera.revision = revision

        # defaults, can be changed by :attr:'still_image_size' and :attr:'still_video_size'
        self._still_image_size = self._picamera.MAX_RESOLUTION
        self._video_image_size = (x / 4 for x in self._picamera.MAX_RESOLUTION)

        self._camera_type = self._picamera.revision
        self._camera_modes = self._picamera.sensor_modes

        # for debugging: current frame namuber
        self._frame_count: int = 0
        self.tfg = TestFrameGenerator()



    @property
    def camera_type(self) -> str:
        return self._camera_type

    @camera_type.setter
    def camera_type(self, camtype: CamType) -> None:
        self._camera_type = camtype.value

    @property
    def resolutions(self):
        """
        List of width/height-tuples nativly supported by the camera.
        Read only property.
        """
        modes = self._picamera.sensor_modes
        values = []
        for mode in modes.values():
            # only use modes that are usable for still images.
            if mode.still:
                res = mode.resolution
                values.append(res)
        return values

    @property
    def still_imagesize(self):
        """
        The size of the still image captures.
        Setting the size to a value not returned by :attr:resolutions is possible. In this case the camera
        hardware will select an appropriate mode and scale the picture.
        :
        """
        return self._still_image_size

    @still_imagesize.setter
    def still_imagesize(self, new_size: Tuple):
        self._sensor_mode = 0
        modes = self._picamera.sensor_modes
        for idx, mode in modes:
            if new_size == mode.resolution:
                self._sensor_mode = idx
                self._still_image_size = new_size
                return
        raise ValueError(f"Invalid still image ")

    @staticmethod
    def get_cam_types(self) -> list:
        return list(CamType)

    def get_png_image(self, width: int = None):
        img = self.get_image(width)
        retval, buffer = cv.imencode('.png', img)
        return buffer

    def get_image(self, param: dict = None, debug: bool = False):
        if not param:
            param = {'width': 2028, 'height': 1520}

        self.tfg.image_size = (param['width'], param['height'])
        img = self.tfg.render_image()
        if debug:
            h, w, _ = img.shape
            x_offset = int(w / 2)
            font = cv.FONT_HERSHEY_SIMPLEX
            cv.putText(img, f"{self._frame_count}", (x_offset, 50), font, 2, (0, 255, 0), 2, cv.LINE_AA)
            cv.putText(img, f"{w}x{h}", (x_offset, 100), font, 2, (0, 255, 0), 2, cv.LINE_AA)
            self._frame_count += 1
        return img

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
