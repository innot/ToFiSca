from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from formats import name_to_fourcc

class Orientation(Enum):
    # EXIF tag 274 starts from '1'
    Rotate0 = 1,
    Rotate0Mirror = 2,
    Rotate180 = 3,
    Rotate180Mirror = 4,
    Rotate90Mirror = 5,
    Rotate270 = 6,
    Rotate270Mirror = 7,
    Rotate90 = 8,


class Point:

    def __init__(self, x: int = 0, y: int = 0):
        self.x = x
        self.y = y

    def __neg__(self):
        return Point(-self.x, -self.y)

    def __repr__(self):
        return f"libcamera.Point({self.x}, {self.y})"


class Size:

    def __init__(self, width: int = 0, height: int = 0):
        self.width = width
        self.height = height

    def __eq__(self, other):
        return self.width == other.width and self.height == other.height

    def __repr__(self):
        return f"libcamera.Size({self.width}, {self.height})"

    def __mult__(self, factor: int | float) -> Size:
        return Size(self.width * factor, self.height * factor)

    def __div__(self, factor: int | float) -> Size:
        return Size(int(self.width / factor), int(self.height / factor))

    @property
    def is_null(self):
        return self.width == 0 and self.height == 0

    def align_down_to(self, h_alignment: int = 0,
                      v_alignment: int = 0) -> Size:
        raise NotImplementedError()
        # return self

    def align_up_to(self, h_alignment: int = 0,
                    v_alignment: int = 0) -> Size:
        raise NotImplementedError()
        # return self

    def bound_to(self, bound: Size) -> Size:
        raise NotImplementedError()
        # return self

    def expand_to(self, expand: Size) -> Size:
        raise NotImplementedError()
        # return self

    def grow_by(self, margins: Size) -> Size:
        raise NotImplementedError()
        # return self

    def shrink_by(self, margins: Size) -> Size:
        raise NotImplementedError()
        # return self

    def aligned_down_to(self, h_alignment: int = 0,
                        v_alignment: int = 0) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def aligned_up_to(self, h_alignment: int = 0,
                      v_alignment: int = 0) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def bounded_to(self, bound: Size) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def expanded_to(self, expand: Size) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def grown_by(self, margins: Size) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def shrunk_by(self, margins: Size) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def bounded_to_aspect_ratio(self, ratio: Size) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def expanded_to_aspect_ratio(self, ratio: Size) -> Size:
        raise NotImplementedError()
        # return Size(self.width, self.height)

    def centered_to(self, center: Point) -> Rectangle:
        raise NotImplementedError()
        # return Size(self.width, self.height)


class SizeRange:

    def __init__(self, size: Size = None, min_size: Size = None, max_size: Size = None, hstep: int = 0, vstep: int = 0):
        if size:
            self.min = size
            self.max = size
            self.hStep = 1
            self.vStep = 1
        elif min_size and max_size:
            self.min = min_size
            self.max = max_size
        self.hStep = hstep
        self.vStep = vstep

    def __repr__(self):
        return f"libcamera.SizeRange(({self.min.width}, {self.min.height}), ({self.max.width}, {self.max.height}), {self.hStep}, {self.vStep})"

    def contains(self, size: Size) -> bool:
        return size.width < self.min.width or size.width > self.max.width or \
            size.height < self.min.height or size.height > self.max.height or \
            (self.hStep and (size.width - self.min.width) % self.hStep) or \
            (self.vStep and (size.height - self.min.height) % self.vStep)


class Rectangle:
    # no doc

    def __init__(self, x: int = 0, y: int = 0, width: int = 0, height: int = 0,
                 size: Size = None, ):  # real signature unknown; restored from __doc__
        self.x, self.y, self.width, self.height = x, y, width, height
        if size:
            self.width, self.height = size.width, size.height

    def __repr__(self):
        return f"libcamera.Rectangle({self.x}, {self.y}, {self.width}, {self.height})"

    @property
    @property
    def is_null(self):
        return self.width == 0 and self.height == 0

    @property
    def size(self):
        return Size(self.width, self.height)

    @property
    def topLeft(self):
        return Point(self.x, self.y)

    @property
    def center(self) -> Point:
        raise NotImplementedError()

    def scale_by(self, numerator: Size, denominator: Size) -> Rectangle:
        raise NotImplementedError()
        # return self

    def translate_by(self, point: Point) -> Rectangle:
        raise NotImplementedError()
        # return self

    def bounded_to(self, bound: Rectangle) -> Rectangle:
        raise NotImplementedError()
        # return Rectangle()

    def enclosed_in(self, boundary: Rectangle):
        raise NotImplementedError()
        # return Rectangle()

    def scaled_by(self, numerator: Size, denominator: Size):
        raise NotImplementedError()
        # return Rectangle()

    def translated_by(self, point: Point):
        raise NotImplementedError()


class ControlType(Enum):
    Null = 0
    Bool = 1
    Byte = 2
    Integer32 = 5
    Float = 7
    String = 8
    Rectangle = 9
    Size = 10
    Point = 11


@dataclass(frozen=True)
class ControlId:
    id: int
    name: str
    vendor: str
    type: ControlType
    isarray: bool = None
    size: int = 0

    def enumerators(self) -> dict[int, str]:
        raise NotImplementedError()


@dataclass
class ControlInfo:
    max: int | float | Point | Size | Rectangle = None
    min: int | float | Point | Size | Rectangle = None
    default: any = None
    values: Iterable = None

class ColorSpace:
    class Primaries(Enum):
        Raw = 0
        Smpte170m = 1
        Rec709 = 2
        Rec2020 = 3

    class TransferFunction(Enum):
        Linear = 0
        Srgb = 1
        Rec709 = 2

    class YcbcrEncoding(Enum):
        Null = 0
        Rec601 = 1
        Rec709 = 2
        Rec2020 = 3

    class Range(Enum):
        Full = 0
        Limited = 1

    def __init__(self, p: Primaries, t: TransferFunction, e: YcbcrEncoding, r: Range):
        self.primaries = p
        self.transfer_function = t
        self.ycbcr_encoding = e
        self.range = r

    @staticmethod
    def Raw() -> ColorSpace:
        return ColorSpace(ColorSpace.Primaries.Raw,
                          ColorSpace.TransferFunction.Linear,
                          ColorSpace.YcbcrEncoding.Null,
                          ColorSpace.Range.Full)

    @staticmethod
    def Srgb() -> ColorSpace:
        return ColorSpace(ColorSpace.Primaries.Rec709,
                          ColorSpace.TransferFunction.Srgb,
                          ColorSpace.YcbcrEncoding.Null,
                          ColorSpace.Range.Full)

    @staticmethod
    def Sycc() -> ColorSpace:
        return ColorSpace(ColorSpace.Primaries.Rec709,
                          ColorSpace.TransferFunction.Srgb,
                          ColorSpace.YcbcrEncoding.Rec601,
                          ColorSpace.Range.Full)

    @staticmethod
    def Smpte170m() -> ColorSpace:
        return ColorSpace(ColorSpace.Primaries.Smpte170m,
                          ColorSpace.TransferFunction.Rec709,
                          ColorSpace.YcbcrEncoding.Rec601,
                          ColorSpace.Range.Limited)

    @staticmethod
    def Rec709() -> ColorSpace:
        return ColorSpace(ColorSpace.Primaries.Rec709,
                          ColorSpace.TransferFunction.Rec709,
                          ColorSpace.YcbcrEncoding.Rec709,
                          ColorSpace.Range.Limited)

    @staticmethod
    def Rec2020() -> ColorSpace:
        return ColorSpace(ColorSpace.Primaries.Rec2020,
                          ColorSpace.TransferFunction.Rec709,
                          ColorSpace.YcbcrEncoding.Rec2020,
                          ColorSpace.Range.Limited)


class Transform:

    def __init__(self, rotation: int = 0, hflip: bool = False, vflip: bool = False,
                 transpose: bool = False):  # real signature unknown; restored from __doc__
        self.rotation = rotation
        self.hflip = hflip
        self.vflip = vflip
        self.transpose = transpose

    def compose(self, arg0):  # real signature unknown; restored from __doc__
        raise NotImplementedError()

    def inverse(self):  # real signature unknown; restored from __doc__
        raise NotImplementedError()

    def invert(self):  # real signature unknown; restored from __doc__
        raise NotImplementedError()


class PixelFormat:

    def __init__(self, fourcc: int = 0, modifier: int = 0, name: str = None):
        if name:
            fourcc, modifier = name_to_fourcc(name)

        self.fourcc = fourcc
        self.modifier = modifier

        self.info_name: str = name


