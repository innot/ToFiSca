from enum import Enum

from libcamera import PixelFormat, Size
from libcamera.libcamera import SizeRange, ColorSpace


class StreamFormats:

    def __init__(self, formats: dict[PixelFormat, list[SizeRange]]):
        self._formats = formats

    def sizes(self, pixel_format: PixelFormat) -> list[Size]:
        raise NotImplementedError()

    def pixel_formats(self) -> list[PixelFormat]:
        values = [pf[0] for pf in self._formats.items()]
        return values

    def range(self, pixel_format: PixelFormat) -> SizeRange:
        pass


class StreamRole(Enum):
    Raw = 0
    StillCapture = 1
    VideoRecording = 2
    Viewfinder = 3


class StreamConfiguration:

    def __init__(self, formats: StreamFormats = None):
        self._stream: Stream | None = None
        self._formats: StreamFormats | None = None
        self.pixel_format: PixelFormat | None = None
        self.size: Size | None = None
        self.frame_size: int = 0
        self.stride: int = 0
        self.buffer_count: int = 0
        self.color_space: ColorSpace | None = None

    def __repr__(self):
        return f"{self.size}-{self.pixel_format}"


class Stream:

    def __init__(self):
        self._configuration: StreamConfiguration | None = None

    @property
    def configuration(self) -> StreamConfiguration:
        return self._configuration
