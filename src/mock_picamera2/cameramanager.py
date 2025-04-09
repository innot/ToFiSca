from __future__ import annotations

from libcamera import Camera
from libcamera.camera_imx477 import CameraImx477

_cm = None


class CameraManager(object):
    instance = None

    @classmethod
    def singleton(cls) -> CameraManager:
        if not cls.instance:
            cls.instance = CameraManager()
        return cls.instance

    def __init__(self):
        self._cameras = [CameraImx477()]

    @property
    def version(self):
        return "0.4.0 mock"  # v0.4.0 is the version number returnes by the real CameraManager

    @property
    def cameras(self) -> list[Camera]:
        return self._cameras

    @property
    def event_fd(self):
        raise NotImplementedError()

    def get(self, cam_id: str) -> Camera | None:
        for cam in self._cameras:
            if cam.id == cam_id:
                return cam
            return None

    def get_ready_requests(self) -> list[libcamera.Request]:
        pass
