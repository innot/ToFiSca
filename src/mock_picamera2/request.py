from enum import Enum


class Request:
    class Status(Enum):
        Pending = 0
        Complete = 1
        Cancelled = 2

    def __init__(self, camera, cookie: str):
        self.camera = camera
        self._cookie = cookie
        self._status = Request.Status.Pending
        self.reuse: bool = False
        self._controls = {}

    def add_buffer(self, stream, buffer) -> None:
        pass

    @property
    def status(self) -> Status:
        return self._status

    @property
    def buffers(self):
        raise NotImplementedError()

    @property
    def cookie(self) -> str:
        return self._cookie

    @property
    def sequence(self):
        raise NotImplementedError()

    @property
    def has_pending_buffers(self) -> bool:
        raise NotImplementedError()

    @property
    def metadata(self):
        raise NotImplementedError()

    def set_control(self, id: str, value: any):
        self._controls[id] = value

    def reuse(self):
        self.reuse = True
