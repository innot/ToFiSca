#
import threading
import time
from enum import Enum

import cv2 as cv
import numpy as np

from mock_camera import Camera
from mock_configuration import CameraConfiguration
from mock_controls import Controls


class CameraType(Enum):
    imx477 = 0
    imx219 = 1
    ov5647 = 2


AllCameraModes = {
    CameraType.imx477:
        [{'bit_depth': 10,
          'crop_limits': (696, 528, 2664, 1980),
          'exposure_limits': (31, 66512892),
          'format': "SRGGB10_CSI2P",
          'fps': 120.05,
          'size': (1332, 990),
          'unpacked': 'SRGGB10'},
         {'bit_depth': 12,
          'crop_limits': (0, 440, 4056, 2160),
          'exposure_limits': (60, 127156999),
          'format': "SRGGB12_CSI2P",
          'fps': 50.03,
          'size': (2028, 1080),
          'unpacked': 'SRGGB12'},
         {'bit_depth': 12,
          'crop_limits': (0, 0, 4056, 3040),
          'exposure_limits': (60, 127156999),
          'format': "SRGGB12_CSI2P",
          'fps': 40.01,
          'size': (2028, 1520),
          'unpacked': 'SRGGB12'},
         {'bit_depth': 12,
          'crop_limits': (0, 0, 4056, 3040),
          'exposure_limits': (114, 239542228),
          'format': "SRGGB12_CSI2P",
          'fps': 10.0,
          'size': (4056, 3040),
          'unpacked': 'SRGGB12'}]
}

CameraNativeModes = {
    CameraType.imx477:
        {'bit_depth': 12,
         'format': "SRGGB12_CSI2P",
         'size': (4056, 3040)
         }
}


class PreviewNotSupportedError(NotImplementedError):
    def __init__(self):
        super(NotImplementedError).__init__("Preview is currently not implemented.")


class Picamera2(object):
    """
    A simulated PiCamera that generates test images for testing the ToFiSca application.
    """

    def __init__(self, camera_num=0, verbose_console=None, tuning=None, allocator=None):

        self._camera_type = CameraType(camera_num)

        if not self._camera_type in AllCameraModes:
            raise ValueError(f"camera_num {camera_num}={self._camera_type.name} is not implemented")

        self.camera: Camera | None = None
        self.camera_config: dict | None = None
        self.controls: Controls | None= None

        self.started = False

        self.completed_requests = []

    @property
    def sensor_modes(self) -> list:
        return AllCameraModes[self._camera_type]

    @property
    def sensor_resolution(self):
        return CameraNativeModes[self._camera_type]['size']

    @property
    def sensor_format(self):
        return CameraNativeModes[self._camera_type]['format']

    @property
    def preview_configuration(self) -> CameraConfiguration:
        raise PreviewNotSupportedError()

    @property
    def still_configuration(self) -> CameraConfiguration:
        config = CameraConfiguration(self.create_still_configuration())
        config.enable_raw()
        return config

    @property
    def video_configuration(self) -> CameraConfiguration:
        config = CameraConfiguration(self.create_video_configuration())
        config.enable_raw()
        return config

    @property
    def camera_controls(self) -> dict[str, any]:
        # List of all supported camera controls
        controls = {
            "Brightness": (-1.0, 1.0, 0.0),
        }
        return controls

    def start(self, config=None, show_preview=False) -> None:
        if show_preview:
            raise PreviewNotSupportedError()
        if config is not None:
            self.configure(config)
        if self.started:
            return

        self.camera.start(self.controls)

        request = self.camera.create_request(self.camera_idx)

        self.started = True

    def capture_array(self, name="main", wait=None, signal_function=None):
        pass


    def configure(self, camera_config=None) -> None:
        if self.started:
            raise RuntimeError("Camera must be stopped before configuring")

        if camera_config == "preview":
            raise PreviewNotSupportedError
        if camera_config == "still":
            camera_config = self.create_still_configuration()
        if camera_config == "video":
            camera_config = self.create_video_configuration()
        if isinstance(camera_config, CameraConfiguration):
            if camera_config.raw is not None:
                # For raw streams, patch up the format/size now if they haven't been set.
                if camera_config.raw.format is None:
                    camera_config.raw.format = self.sensor_format
                if camera_config.raw.size is None:
                    camera_config.raw.size = camera_config.main.size
            # We expect values to have been set for any lores/raw streams.
            camera_config = camera_config.make_dict()
        if camera_config is None:
            camera_config = self.create_preview_configuration()

        self.camera_config = camera_config
        self.controls = camera_config["controls"]



    def create_preview_configuration(self, **kwargs) -> dict:
        raise PreviewNotSupportedError

    def create_still_configuration(self,
                                   main=None,
                                   lores=None,
                                   use_case="still",
                                   controls=None,
                                   sensor=None,
                                   **kwargs) -> dict:
        if not main:
            main = {}
        if not sensor:
            sensor = {}
        if not controls:
            controls = {}

        main = self._make_initial_stream_config(
            {"format": "BGR888", "size": self.sensor_resolution, "preserve_ar": True}, main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"], "preserve_ar": False},
                                                 lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)

        config = {
            "use_case": use_case,
            "main": main,
            "lores": lores,
            "controls": controls,
            "sensor": sensor,
        }
        return config

    def create_video_configuration(self,
                                   main=None,
                                   lores=None,
                                   use_case="video",
                                   controls=None,
                                   sensor=None,
                                   **kwargs) -> dict:
        if not main:
            main = {}
        if not sensor:
            sensor = {}
        if not controls:
            controls = {}

        main = self._make_initial_stream_config({"format": "XBGR8888", "size": (1280, 720), "preserve_ar": True},
                                                main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"], "preserve_ar": False},
                                                 lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)

        config = {
            "use_case": use_case,
            "main": main,
            "lores": lores,
            "conrols": controls,
            "sensor": sensor,
        }
        return config

    @staticmethod
    def _make_initial_stream_config(stream_config: dict, updates: dict | None, ignore_list=None) -> dict | None:
        if not ignore_list:
            ignore_list = []

        if updates is None:
            return None

        valid = ("format", "size", "stride", "preserve_ar")
        for key, value in updates.items():
            # if isinstance(value, SensorFormat):
            #     value = str(value)
            if key in valid:
                stream_config[key] = value
            elif key in ignore_list:
                pass  # allows us to pass items from the sensor_modes as a raw stream
            else:
                raise ValueError(f"Bad key {key!r}: valid stream configuration keys are {valid}")
        return stream_config

    @staticmethod
    def align_stream(stream_config: dict, optimal=True) -> None:
        if optimal:
            # Adjust the image size so that all planes are a mutliple of 32/64 bytes wide.
            # This matches the hardware behaviour and means we can be more efficient.
            align = 32  # if Picamera2.platform == Platform.Platform.VC4 else 64
            if stream_config["format"] in ("YUV420", "YVU420"):
                align *= 2  # because the UV planes will have half this alignment
            elif stream_config["format"] in ("XBGR8888", "XRGB8888", "RGB161616", "BGR161616"):
                align //= 2  # we have an automatic extra factor of 2 here
        else:
            align = 2
        size = stream_config["size"]
        stream_config["size"] = (size[0] - size[0] % align, size[1] - size[1] % 2)

    ########################################################################################
    ########################################################################################
    ########################################################################################

    def capture(
            self, output, format=None, use_video_port=False, resize=None,
            splitter_port=0, bayer=False, **options):
        """
        Capture an image from the camera, storing it in *output*.

        Refer to the PiCamera documentation for details.
        """
        pass

    def start_recording(
            self, output, format=None, resize=None, splitter_port=1, **options):

        if format != 'mjpeg':
            raise TypeError("start_recording: only 'mjpeg' output is supported")

        if self.streaming_thread is None:
            self.streaming_thread = threading.Thread(target=self.image_generator,
                                                     args=(output, resize, self.streaming_event))
            self.streaming_thread.start()

    def stop_recording(self, splitter_port=1):
        if self.streaming_thread is not None:
            self.streaming_event.set()
            self.streaming_thread.join(1)
            self.streaming_thread = None

    def image_generator(self, output, size: tuple, event: threading.Event):
        counter = 0
        while True:
            width, height = size
            img = np.zeros((height, width, 3), np.uint8)
            cv.putText(img, str(counter), (20, height >> 1), cv.FONT_HERSHEY_SIMPLEX, 1, (128, 255, 128), 2,
                       cv.LINE_AA)
            retval, buffer = cv.imencode('.jpg', img)
            buffer = buffer.tobytes()
            output.write(buffer)
            print(
                f"Image_generator() wrote image {counter} with {len(buffer)} bytes to output. Content {buffer[10:]}...")
            counter += 1
            time.sleep(1 / 2)
            if event.is_set():
                event.clear()
                print("Image_generator() received end signal")
                return


class formats:

    YUV_FORMATS = {"NV21", "NV12", "YUV420", "YVU420",
                   "YVYU", "YUYV", "UYVY", "VYUY"}

    RGB_FORMATS = {"BGR888", "RGB888", "XBGR8888", "XRGB8888", "RGB161616", "BGR161616"}

    BAYER_FORMATS = {"SBGGR8", "SGBRG8", "SGRBG8", "SRGGB8",
                     "SBGGR10", "SGBRG10", "SGRBG10", "SRGGB10",
                     "SBGGR10_CSI2P", "SGBRG10_CSI2P", "SGRBG10_CSI2P", "SRGGB10_CSI2P",
                     "SBGGR12", "SGBRG12", "SGRBG12", "SRGGB12",
                     "SBGGR12_CSI2P", "SGBRG12_CSI2P", "SGRBG12_CSI2P", "SRGGB12_CSI2P",
                     "BGGR_PISP_COMP1", "GBRG_PISP_COMP1", "GRBG_PISP_COMP1", "RGGB_PISP_COMP1",
                     "SBGGR16", "SGBRG16", "SGRBG16", "SRGGB16", }

    MONO_FORMATS = {"R8", "R10", "R12", "R16", "R8_CSI2P", "R10_CSI2P", "R12_CSI2P"}

    ALL_FORMATS = YUV_FORMATS | RGB_FORMATS | BAYER_FORMATS | MONO_FORMATS

    @classmethod
    def is_YUV(cls, fmt: str) -> bool:
        return fmt in cls.YUV_FORMATS

    @classmethod
    def is_RGB(cls, fmt: str) -> bool:
        return fmt in cls.RGB_FORMATS

    @classmethod
    def is_Bayer(cls, fmt: str) -> bool:
        return fmt in cls.BAYER_FORMATS

    @classmethod
    def is_mono(cls, fmt: str) -> bool:
        return fmt in cls.MONO_FORMATS

    @classmethod
    def is_raw(cls, fmt: str) -> bool:
        return cls.is_Bayer(fmt) or cls.is_mono(fmt)

    @classmethod
    def assert_format_valid(cls, fmt: str) -> None:
        if fmt not in cls.ALL_FORMATS:
            raise ValueError(f"Invalid format: {fmt}. Valid formats are: {cls.ALL_FORMATS}")
