#  This file is part of the ToFiSca application.
#
#  ToFiSca is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ToFiSca is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ToFiSca.  If not, see <http://www.gnu.org/licenses/>.
#
#  Copyright (c) 2025 by Thomas Holland, thomas@innot.de
#

from pydantic import BaseModel, Field, ValidationError

from configuration.config_item import ConfigItem


class Point(BaseModel):
    x: float = Field(0, ge=0.0, le=1.0)
    y: float = Field(0, ge=0.0, le=1.0)


class OffsetPoint(BaseModel):
    dx: float = Field(0, ge=-1.0, le=1.0)
    dy: float = Field(0, ge=-1.0, le=1.0)


class Size(BaseModel):
    width: float = Field(0, ge=0.0, le=1.0)
    height: float = Field(0, ge=0.0, le=1.0)


class Rect(BaseModel):
    """
    A Rectangle described by its top left point (x/y) and its size (widht/height).
    All values are normalized between 0 and 1.
    """
    x: float = Field(0, ge=0.0, le=1.0)
    y: float = Field(0, ge=0.0, le=1.0)
    width: float = Field(0, ge=0.0, le=1.0)
    height: float = Field(0, ge=0.0, le=1.0)

    @property
    def center(self) -> Point:
        """Get the center point of the given rectangle"""
        return Point(x=self.x + (self.width / 2), y=self.y + (self.height / 2))


class RectEdges(BaseModel):
    """
    A Rectangle described by its top, bottom, left, and right edges.
    """
    top: float = Field(0, ge=0.0, le=1.0)
    bottom: float = Field(0, ge=0.0, le=1.0)
    left: float = Field(0, ge=0.0, le=1.0)
    right: float = Field(0, ge=0.0, le=1.0)

    @property
    def center(self) -> Point:
        """Get the center point of the given rectangle"""
        return Point(x=(self.left + self.right) / 2, y=(self.top + self.bottom) / 2)


class PerforationLocation(ConfigItem):
    top_edge: float = Field(default=0, ge=0.0, le=1.0)
    bottom_edge: float = Field(default=0, ge=0.0, le=1.0)
    inner_edge: float = Field(default=0, ge=0.0, le=1.0)
    outer_edge: float = Field(default=0, ge=0.0, le=1.0)

    @property
    def reference(self) -> Point:
        x = self.inner_edge
        y = (self.top_edge + self.bottom_edge) / 2
        return Point(x=x, y=y)

    @property
    def center(self) -> Point:
        x = (self.inner_edge + self.outer_edge) / 2
        y = (self.top_edge + self.bottom_edge) / 2
        return Point(x=x, y=y)

    @property
    def width(self) -> float:
        return self.inner_edge - self.outer_edge

    @property
    def height(self) -> float:
        return self.bottom_edge - self.top_edge

    @property
    def rect(self) -> Rect:
        x = self.top_edge
        y = self.outer_edge
        return Rect(x=x, y=y, width=self.width, height=self.height)


class ScanArea(ConfigItem):
    ref: PerforationLocation = Field(default=None, description="The reference this ScanArea is based on.")
    ref_delta: OffsetPoint = Field(default=None, description="delta from reference point to top left")
    size: Size = Field(default=None, description="width of the scan area")

    @property
    def rect(self) -> Rect:
        """
        Convert the ScanArea to a Rect relative to the complete image
        """
        x = self.ref.reference.x + self.ref_delta.dx
        y = self.ref.reference.y + self.ref_delta.dy
        width = self.size.width
        height = self.size.height
        return Rect(x=x, y=y, width=width, height=height)

    @property
    def edges(self) -> RectEdges:
        """
        Get the top/bottom/left/right edges of the scanarea relative to the complete image
        """
        top = self.ref.reference.y + self.ref_delta.dy
        bottom = top + self.size.height
        left = self.ref.reference.x + self.ref_delta.dx
        right = left + self.size.width
        return RectEdges(top=top, bottom=bottom, left=left, right=right)

    @property
    def is_valid(self) -> bool:
        # use the validation to see if any edge is outside [0,1]
        try:
            _ = self.edges
            return True
        except ValidationError:
            return False
