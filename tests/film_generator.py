# This file is part of the ToFiSca application.
#
# Foobar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ToFiSca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ToFiSca.  If not, see <http://www.gnu.org/licenses/>.


import math

import cairo
import cv2 as cv
import numpy as np
from numpy import ndarray

from film_specs import FilmSpecKey, FilmSpecs, FSKeys


def round_rect(ctx: cairo.Context, x: float, y: float, width: float, height: float, radius: float):
    ctx.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    ctx.arc(x + width - radius, y + radius, radius, 3 * math.pi / 2, 0)
    ctx.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    ctx.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    ctx.close_path()


class FilmFrameGenerator:
    """
    FilmFrameGenerator is used for generating controlled sample images to test the ToFiSca functionallity.

    It basically simulates the output of PiCamera, but can run without PiCamera and in a development
    environment other than on a Raspberry Pi.

    It has a number of properties which can be manipulated to change the output:

    * :attr:'~field_of_view'
    * :attr:'~left_offset'
    * :attr:'~top_offset'
    * :attr:'~rotation'
    * :attr:'~defocus'
    * :attr:'~noise'

    The main method is :meth:'render_image', which returns the generated image. After the image has been rendered
    the contours of the perforation holes and the camera frames are stored in the

    * :attr:'~perforation_contours' and
    * :attr:'~camera_frame_contours'

    properties.

    :param filmspec: The film specification to use. Default is Super8. See :class:'FilmSpecs' for other options.
    :param width: The width of the generated image. Default is 2048, the medium resolution of the PiCamera HQ.
    :param height: The height of the generated image. Default is 1520, the medium resolution of the PiCamera HQ.
    :type filmspec: FilmSpecs
    """

    def __init__(self, filmspec: FilmSpecKey = FilmSpecKey.SUPER8, width: int = 2048, height: int = 1520):
        self._specs = FilmSpecs.get_film_spec(filmspec)

        self._width_px: int = width
        self._height_px: int = height
        self._aspect_ratio: float = width / height

        film_width, _ = self._specs[FSKeys.FILM_FRAME_SIZE]
        self._fov_mm: float = round(film_width * 1.15)  # Field of View ~ 15% larger than film
        self._fov_v_mm: float = self._fov_mm / self._aspect_ratio

        self._horizontal_offset: float = 0.0
        self._vertical_offset: float = 0.0
        self._rotation = 0.0  # rotation in radians
        self._flip_image = False

        self._pixel_per_mm = self._width_px / self._fov_mm

        self._perf_center_px: list[tuple[int, int]] = []
        self._perf_outline_px: list[ndarray] = []
        self._camera_frame_contour: list[ndarray] = []

        self.image = None

        # image modification
        self._noise_level = 0.1
        self._defocus_level = 0.1


    @property
    def image_size(self) -> tuple:
        """The size of the generated image in pixels.

        The size can be set  a (width, height) tupel. If height is empty or 0
        it is automatically derived from the width and the aspect ration.

        Default is 2028x1520, the medium resolution of the PiCamera HQ module.

        :return: width, height in pixels
        :rtype: tuple
        """
        return self._width_px, self._height_px

    @image_size.setter
    def image_size(self, size: tuple[int,int]) -> None:
        width, height = size
        self._width_px = width
        self._height_px = height

    @property
    def aspect_ratio(self) -> float:
        """The ratio of with to height of the generated image.

        It is automatically calculated when a image width and height is set, but can
        be manually set to automatically set the image height for a given width.

        Default is (almost) 4/3 for the simulated PiCamera HQ model.

        :return: ratio of with to height
        :rtype: float
        """
        return self._aspect_ratio

    @property
    def field_of_view(self) -> float:
        """The simulated field of view of the camera in millimeters.

        This is how many mm the full image width covers. Used to scale the frame.
        Default is 9mm to cover a full Super8 frame with some space at the edges.

        :return: FoV in mm
        :rtype: float
        """
        return self._fov_mm

    @field_of_view.setter
    def field_of_view(self, value: float):
        self._fov_mm = value
        self._pixel_per_mm = self._width_px / self._fov_mm

    @property
    def pixel_per_mm(self) -> int:
        """The number of pixels representing 1 millimeter.
        Read only.
        """
        return round(self._pixel_per_mm)

    @property
    def film_specification(self) -> dict:
        """The dimensions of the film.

        This property is read only. It can be set with the constructor.
        See :class:'FSKeys' for all keys

        Default is :class:FilmSpecifications.Super8

        :returns: The current film specification
        :rtype: Dict
        """
        return self._specs

    @property
    def horizontal_offset(self) -> float:
        """The horizontal offset of the rendered film from the centerline

        By default, the film is rendered in the center of the image.

        A positive value will move the film to the right, exposing background on the left
        A negative value will move the film to the left, exposing background on the right

        :return: Offset from the center as a fraction of the film width
        """
        return self._horizontal_offset

    @horizontal_offset.setter
    def horizontal_offset(self, value: float):
        self._horizontal_offset = value

    @property
    def vertical_offset(self) -> float:
        """The vertical offset of the rendered frame from the center of the image

        By default, the frame is rendered in the center of the image.

        A positive value will move the film towards the bottom, exposing a partial frame on the top
        A positive value will move the film towards the top, exposing a partial frame on the bottom

        :return: Offset from the center as a fraction of the frame height
        """
        return self._vertical_offset

    @vertical_offset.setter
    def vertical_offset(self, value: float):
        self._vertical_offset = value

    @property
    def rotation(self) -> float:
        """Rotate the rendered image by 'angle' degrees.

        Simulate a (slightly) misaligned film feed.

        Must be greater than -90° and less than 90°
        Default 0.0

        :return: Rotation angle in degrees
        :rtype: float
        """
        return math.degrees(self._rotation)

    @rotation.setter
    def rotation(self, angle: float):
        if angle <= -90 or angle >= 90:
            raise ValueError(f"Angle must be > -90° and < 90°, was {angle}")
        self._rotation = math.radians(angle)

    @property
    def perforation_centers(self) -> list[tuple[int, int]]:
        """Returns the (pixel) coordinates of the perforation hole centers.

        The list can have multiple entries. The first entry always refers to the first perforation hole
        of the main frame (the frame whose position is set by the offset properties). For film types with
        multiple perforation holes, those centers come next, followed by centers of frames above and below the
        main frame.

        The perforation locations are calculated when the image is drawn with :meth:'render_image'.
        If no image has been rendered, the returned list is empty.

        .. note::
        The coordinates may be outside the image dimensions if the main frame has been offset.

        :return: list of (x,y) coordinates
        :rtype: list of tuples
        """
        return self._perf_center_px

    @property
    def perforation_contours(self) -> list[ndarray]:
        """Returns all perforation hole outlines as opencv contours.

        The list can have multiple entries. The first entry always refers to the first perforation hole
        of the main frame (the frame whose position is set by the offset properties). For film types with
        multiple perforation holes those come next, followed by perforations of frames above and below the
        main frame.

        The perforation locations are calculated when the image is drawn with :meth:'render_image'.
        If no image has been rendered the returned list is empty.

        .. note::
        The coordinates may be outside the image dimensions if the main frame has been offset.

        :return: list of contours.
        :rtype: list of numpy.ndarray of (x,y) coordinates
        """
        return self._perf_outline_px

    @property
    def camera_frame_contours(self) -> list[ndarray]:
        """Returns the opencv contours of the camera frame(s).

        The list can have multiple entries. The first entry always refers to the main frame
        (the frame whose position is set by the offset properties). Any following entries are for
        frames above and below the main frame.

        The frame locations are calculated when the image is drawn with :meth:'render_image'.
        If no image has been rendered, the returned list is empty.

        .. note::
        The contours may be (partialy) outside of the image dimensions if the main frame has been offset.

        :return: list with a single contour.
        :rtype: list of numpy.ndarray of (x,y) coordinates
        """
        return self._camera_frame_contour

    @property
    def flip(self) -> bool:
        """If 'True' the generated image is flipped, i.e. the perforation hole(s) are on the right side of the film.

        :return: 'True' if the image output is flipped
        :rtype: bool
        """
        return self._flip_image

    @flip.setter
    def flip(self, value: bool):
        self._flip_image = value

    @property
    def noise(self) -> float:
        """Gausian noise level.
        If the noise-level is > 0, then a gaussian noise map is created and added to the rendered image.

        :returns: noise level from 0.0 to 255
        :rtype: float
        """
        return self._noise_level

    @noise.setter
    def noise(self, level: float):
        self._noise_level = level

    @property
    def defocus(self) -> float:
        """Out-of-focus simulation level.

        :returns: out-of-focus level in percent. '0' is in focus
        :rtype: float
        """
        return self._defocus_level

    @defocus.setter
    def defocus(self, level: float):
        self._defocus_level = level

    def render_image(self) -> np.ndarray:
        """Render the simulated camera view to a opencv image.

        :return: 3-channel (BGR) numpy array with the image data
        :rtype: numpy.ndarray
        """

        # reset contour data
        self._perf_center_px = []
        self._perf_outline_px = []
        self._camera_frame_contour = []

        surface = self._draw_image()
        buf = surface.get_data()
        opencv_img = np.ndarray(shape=(self._height_px, self._width_px, 4), dtype=np.uint8, buffer=buf)
        opencv_img = cv.cvtColor(opencv_img, cv.COLOR_BGRA2BGR)  # Remove alpha channel. PiCamera has no alpha channel

        # post processing
        opencv_img = self._add_defocus(opencv_img)
        opencv_img = self._add_noise(opencv_img)

        # mark the center of the camera frame(s)
        height, width, _ = opencv_img.shape
        for cnt in self.camera_frame_contours:
            m = cv.moments(cnt)
            cx = int(m['m10'] / m['m00'])
            cy = int(m['m01'] / m['m00'])
            if 0 < cx < width and 0 < cy < height:
                opencv_img = cv.drawMarker(opencv_img, (cx, cy), (0, 0, 255), cv.MARKER_CROSS)

        return opencv_img

    def _add_defocus(self, image: np.ndarray) -> np.ndarray:
        level = abs(self._defocus_level)  # treat in and out defous as the same for now
        if level > 0.0:
            img_h, img_w, channels = image.shape
            level = round(img_w * level / 100)  # scale level from percent of total image width to actual pixels

            # The Point spread function for a simple out-of-focus simulation
            kernel = np.zeros((level * 2 + 1, level * 2 + 1), dtype=np.float32)
            cv.circle(kernel, (level, level), level, (1.0,), -1, cv.LINE_AA)
            kernel /= kernel.sum()

            image = cv.filter2D(image, -1, kernel)

        return image

    def _add_noise(self, image: np.ndarray) -> np.ndarray:
        if self._noise_level > 0.0:
            img_h, img_w, channels = image.shape
            noisemap = np.random.normal(0, self._noise_level, (img_h, img_w, channels))
            # noisemap = noisemap.reshape(img_h, img_w, channels)
            noisemap = noisemap.astype(np.int8)
            image = cv.add(image, noisemap, dtype=0)
        return image

    def _draw_image(self) -> cairo.ImageSurface:
        """Draw the vector part of the image"""

        self._set_pattern()  # set up the colors and gradiants

        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, self._width_px, self._height_px)
        ctx = cairo.Context(surface)

        # background
        ctx.set_source(self.pat_background)
        ctx.rectangle(0, 0, self._width_px, self._height_px)
        ctx.fill()

        film_width, film_height = self._specs[FSKeys.FILM_FRAME_SIZE]
        factor = self._pixel_per_mm
        left_offset = (self._fov_mm - film_width) / 2.0 + film_width * self._horizontal_offset
        top_offset = (self._fov_v_mm - film_height) / 2.0 + film_height * self._vertical_offset

        if self._flip_image:
            ctx.scale(-factor, factor)
            ctx.translate(-left_offset, top_offset)
        else:
            ctx.scale(factor, factor)
            ctx.translate(left_offset, top_offset)

        ctx.rotate(self._rotation)

        self._draw_film(ctx)

        return surface

    def _draw_film(self, ctx: cairo.Context, recursive_direction: int = 0):
        """Draw a complete film frame to the context.

        If the complete frame leaves a gap at the top or the bottom additional frames are drawn
        above and/or below to generate a contionous film strip.

        :param ctx: A cairo context which has been scaled, translated and rotated as required.
        :type ctx: cairo.Context
        :param recursive_direction: The direction of the appended frame
        :type recursive_direction: int
        """

        # first calculate the pixel coordinates of the perforation and the camera frame
        self._determine_contours(ctx)

        self._draw_film_stock(ctx)
        self._draw_perforation(ctx)
        self._draw_camera_frame(ctx)
        self._draw_projector_frame(ctx)

        # now determine if we need to draw further frames above or below
        width, height = self._specs[FSKeys.FILM_FRAME_SIZE]

        _, y1 = ctx.user_to_device(0, 0)
        _, y2 = ctx.user_to_device(width, 0)
        _, y3 = ctx.user_to_device(0, height)
        _, y4 = ctx.user_to_device(width, height)

        if max(y1, y2) > 0 and recursive_direction <= 0:
            # there is a gap at the top edge to be filled by another frame
            ctx.save()
            ctx.translate(0, -height)
            self._draw_film(ctx, -1)  # a little recursion
            ctx.restore()

        if min(y3, y4) < self._height_px and recursive_direction >= 0:
            # there is a gap at the bottom edge to be filled by another frame
            ctx.save()
            ctx.translate(0, height)
            self._draw_film(ctx, 1)  # a little recursion
            ctx.restore()
            return

        return

    def _set_pattern(self):
        """Set up all colors and patterns used for generating the image."""
        # TODO: Make them changeable iso hard-coded to simulate different exposure levels

        self.pat_background = cairo.SolidPattern(0.95, 0.95, 0.95, 1.0)  # not quite full white
        self.pat_filmstock = cairo.SolidPattern(0.1, 0.1, 0.1, 1.0)  # almost black
        self.pat_camera_frame = cairo.SolidPattern(0.5, 0.5, 0.5, 1.0)  # just some middle grey

        width, height = self._specs[FSKeys.PROJECTOR_FRAME_SIZE]
        left, top = self._specs[FSKeys.PROJECTOR_FRAME_POS]
        self.pat_projector_frame = cairo.LinearGradient(0, top, 0, top + height)
        self.pat_projector_frame.add_color_stop_rgb(0, 0.9, 0.9, 0.9)
        self.pat_projector_frame.add_color_stop_rgb(1, 0.1, 0.1, 0.1)

        self.pat_annotations = cairo.SolidPattern(0.05, 0.05, 0.05, 1.0)  # Text almost black

    def _determine_contours(self, ctx: cairo.Context) -> None:
        """Calculate the contours of all perforation holes and the camera frame area.

        These contours are stored in the :attr:'~perforation_contours' and :attr:'camera_frame_contours'
        properties. Also the perforation hole centers are calculated and stored in the
        :attr:'~perforation_centers' property.

        :param ctx: A cairo context which has been scaled, translated and rotated as required.
        """

        # first the perforation

        width, height = self._specs[FSKeys.PERFORATION_SIZE]

        for ref_pos in self._specs[FSKeys.PERFORATION_POS]:
            # position is on the inner edge between top and bottom
            # convert to top left corner
            ref_x, ref_y = ref_pos

            center_x_px, center_y_px = ctx.user_to_device(ref_x - (width / 2), ref_y)
            self._perf_center_px.append((int(center_x_px), int(center_y_px)), )

            # top left corner
            x = ref_x - width
            y = ref_y - height / 2

            x1, y1 = ctx.user_to_device(x, y)
            x2, y2 = ctx.user_to_device(x + width, y)
            x3, y3 = ctx.user_to_device(x + width, y + height)
            x4, y4 = ctx.user_to_device(x, y + height)
            contour = np.array([[int(x1), int(y1)], [int(x2), int(y2)], [int(x3), int(y3)], [int(x4), int(y4)]])
            self._perf_outline_px.append(contour)

        # and now the camera frame

        # it is referenced of the first perforation position
        ref_x = self._specs[FSKeys.PERFORATION_POS][0][0]
        ref_y = self._specs[FSKeys.PERFORATION_POS][0][1]

        dx, dy = self._specs[FSKeys.CAMERA_FRAME_POS]
        width, height = self._specs[FSKeys.CAMERA_FRAME_SIZE]

        x = ref_x + dx
        y = ref_y + dy

        x1, y1 = ctx.user_to_device(x, y)
        x2, y2 = ctx.user_to_device(x + width, y)
        x3, y3 = ctx.user_to_device(x + width, y + height)
        x4, y4 = ctx.user_to_device(x, y + height)
        contour = np.array([[int(x1), int(y1)], [int(x2), int(y2)], [int(x3), int(y3)], [int(x4), int(y4)]])
        self._camera_frame_contour.append(contour)

    def _draw_film_stock(self, ctx: cairo.Context):
        """Draw the film stock, that is the film strip background.

        The stock color is taken from :attr:'~pat_filmstock

        :param ctx: A cairo context which has been scaled, translated and rotated as required.
        :type ctx: cairo.Context
        """
        width, height = self._specs[FSKeys.FILM_FRAME_SIZE]
        ctx.rectangle(0, 0, width, height)
        ctx.set_source(self.pat_filmstock)
        ctx.fill()

    def _draw_perforation(self, ctx: cairo.Context):
        """Draw the perforation holes.

        Depending on the film specification these can be one or more holes.

        :param ctx: A cairo context which has been scaled, translated and rotated as required.
        :type ctx: cairo.Context
        """
        width, height = self._specs[FSKeys.PERFORATION_SIZE]
        radius = self._specs[FSKeys.PERFORATION_RADIUS]
        ctx.set_source(self.pat_background)

        for ref_pos in self._specs[FSKeys.PERFORATION_POS]:
            ref_x = ref_pos[0]
            ref_y = ref_pos[1]

            x = ref_x - width
            y = ref_y - height / 2
            round_rect(ctx, x, y, width, height, radius)
            ctx.fill()

    def _draw_camera_frame(self, ctx: cairo.Context) -> None:
        """
        Draw the camera aperture frame.

        By definition, this is slightly larger than the projector aperture frame.

        :param ctx: A cairo context which has been scaled, translated and rotated as required.
        """
        width, height = self._specs[FSKeys.CAMERA_FRAME_SIZE]
        dx, dy = self._specs[FSKeys.CAMERA_FRAME_POS]

        ref_x, ref_y = self._specs[FSKeys.PERFORATION_POS][0]

        x = ref_x + dx
        y = ref_y + dy

        radius = self._specs[FSKeys.FRAME_CORNER_RADIUS]
        ctx.set_source(self.pat_camera_frame)
        round_rect(ctx, x, y, width, height, radius)
        ctx.fill()

    def _draw_projector_frame(self, ctx: cairo.Context) -> None:
        """
        Draw the projector aperture frame.

        By definition this is slightly smaller than the camera aperture frame.

        :param ctx: A cairo context which has been scaled, translated and rotated as required.
        :type ctx: cairo.Context
        """
        width, height = self._specs[FSKeys.PROJECTOR_FRAME_SIZE]
        dx, dy = self._specs[FSKeys.PROJECTOR_FRAME_POS]

        ref_x, ref_y = self._specs[FSKeys.PERFORATION_POS][0]
        x = ref_x + dx
        y = ref_y + dy

        radius = self._specs[FSKeys.FRAME_CORNER_RADIUS]
        ctx.set_source(self.pat_projector_frame)
        round_rect(ctx, x, y, width, height, radius)
        ctx.fill()


if __name__ == "__main__":
    tfg = FilmFrameGenerator(FilmSpecKey.SUPER8, 1024, 760)
    # tfg.field_of_view = 12
    # tfg.rotation = 0.0
    # tfg.left_offset = 2
    # tfg.top_offset = 1

    loop = True
    while loop:
        _, frame_height = tfg.film_specification[FSKeys.FILM_FRAME_SIZE]

        for offset in np.arange(0, 1, 0.1):

            tfg.vertical_offset = offset
            tfg.horizontal_offset = offset

            # tfg.defocus += 0.1

            img = tfg.render_image()

            w, h = tfg.image_size

            pc = tfg.perforation_centers[0]  # draw only first perforation
            po = tfg.perforation_contours
            co = tfg.camera_frame_contours

            cv.drawMarker(img, pc, (0, 255, 0), markerType=cv.MARKER_CROSS)
            cv.drawContours(img, po, -1, (0, 0, 255))
            cv.drawContours(img, co, -1, (255, 0, 255))

            cv.imshow("Display window", img)
            k = cv.waitKey(0)
            if k == 120:
                loop = False
                break
