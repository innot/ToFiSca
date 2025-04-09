from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from queue import Queue
from threading import Lock, Thread

import libcamera
from mock_picamera2.request import Request
from mock_picamera2.stream import StreamConfiguration, StreamRole


# from film_generator import TestFrameGenerator


class SensorConfiguration:
    @dataclass
    class Binning:
        bin_x: int = 1
        bin_y: int = 1

    @dataclass
    class Skipping:
        x_odd_inc: int = 1
        x_even_inc: int = 1
        y_odd_inc: int = 1
        y_even_inc: int = 1

    def __init__(self):  # real signature unknown; restored from __doc__
        self.analog_crop: libcamera.Rectangle | None = None
        self.binning: SensorConfiguration.Binning = SensorConfiguration.Binning()
        self.bit_depth: int = 0
        self.output_size: libcamera.Size | None = None
        self.skipping: SensorConfiguration.Skipping = SensorConfiguration.Skipping()

    def is_valid(self):
        return self.bit_depth and self.binning.bin_x and self.binning.bin_y and \
            self.skipping.x_odd_inc and self.skipping.y_odd_inc and \
            self.skipping.x_even_inc and self.skipping.y_even_inc and \
            not self.output_size


class CameraConfiguration:
    class Status(Enum):
        Valid = 0
        Adjusted = 1
        Invalid = 2

    def __init__(self):
        self._config: list[StreamConfiguration] = []
        self.orientation = libcamera.Orientation.Rotate0
        self.sensor_config = SensorConfiguration()

    def __iter__(self):
        for config in self._config:
            yield config

    def __len__(self):
        return len(self._config)

    def __getitem__(self, item):
        return self._config[item]

    @property
    def status(self) -> Status:
        return self.validate()

    def add_configuration(self, stream_config: StreamConfiguration):
        self._config.append(stream_config)

    def at(self, index: int) -> StreamConfiguration:
        return self._config[index]

    def validate(self) -> Status:
        raise NotImplementedError()

    @property
    def size(self) -> int:
        return len(self._config)

    @property
    def empty(self) -> bool:
        return len(self) == 0


class CameraManager:
    pass


class Camera(ABC):

    def __init__(self):
        self._lock = Lock()

        self._is_running = False

        self._thread: Thread | None = None

        self._request_queue: Queue[Request | None] = Queue()

    @property
    def id(self) -> str:
        return f"/mock/camera/none"

    @property
    @abstractmethod
    def controls(self) -> dict[libcamera.ControlId, libcamera.ControlInfo]:
        return {}

    @abstractmethod
    def generate_configuration(self, roles: list[StreamRole]) -> CameraConfiguration:
        return CameraConfiguration()

    def acquire(self):
        with self._lock:
            if self._acquired:
                raise SystemError("Failed to acquire camera")
            self._acquired = True

    def release(self):
        self._acquired = False

    def start(self, controls: dict[libcamera.ControlId, libcamera.ControlInfo]) -> None:
        if not self._is_running:
            self._thread = Thread(target=self._camera_runner, name="Camera_runner", args=(controls,))
            self._thread.start()
            self._is_running = True

    def stop(self) -> None:
        if not self._is_running:
            return

        # clear the request queue
        with self._lock:
            while self._request_queue.qsize() > 0:
                self._request_queue.get()

        self._request_queue.put(None)  # signals the thread to stop
        self._thread.join()

    def queue_request(self, request: Request):
        self._request_queue.put(request)

    def create_request(self, cookie: str | None = None) -> Request:
        return Request(self, cookie)

    def _camera_runner(self, controls: dict[libcamera.ControlId, libcamera.ControlInfo]) -> None:
        queue = self._request_queue
        while True:
            request = queue.get()
            if request is None:
                break

            request.
