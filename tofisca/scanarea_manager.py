# This file is part of the ToFiSca application.
#
# ToFiSca is free software: you can redistribute it and/or modify
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

import cv2 as cv
import numpy as np
from pydantic import Field

from configuration.database import ConfigDatabase, Scope
from configuration.config_item import ConfigItem
from film_specs import FilmSpecs, FSKeys, FilmSpecKey
from models import ScanArea, PerforationLocation, Rect, Point, OffsetPoint, Size, RectEdges


class NoImageSetError(RuntimeError):

    def __init__(self):
        msg = "No Image has been set for the ScanAreaManager. Call scan_are_manager_instace.image=... first."
        super().__init__(msg)


class ScanAreaManagerNotSetUpError(RuntimeError):

    def __init__(self):
        msg = "The ScanAreaManager has not been set up. Call 'autodetect' or 'manualdetect' first."
        super().__init__(msg)


class ScanAreaManagerException(Exception):
    pass


class BlankFrameException(ScanAreaManagerException):
    def __init__(self):
        super().__init__("The current image is blank, i.e. it has no detectable content.")


class ScanAreaOutOfImageException(ScanAreaManagerException):
    """
    The ScanArea is not 100% within the given image.
    Probably the reference perforation hole has shifted too far.
    """

    def __init__(self, starting_point: Point, scanarea: ScanArea, *args):
        self.starting_point = starting_point
        self.scanarea = scanarea
        super().__init__(*args)

    def __str__(self):
        msg = f"ScanArea {self.scanarea} outside of image. Starting point was {self.starting_point}"
        return msg


class MalformedPerforationException(ScanAreaManagerException):
    """A perforation hole was found, but its size does not match the reference perforation hole."""

    def __init__(self, msg: str, perfloc: PerforationLocation, expected_size: float, actual_size: float):
        self.msg = msg
        self.perfloc = perfloc
        self.expected_size = expected_size
        self.actual_size = actual_size

        if self.actual_size > self.expected_size:
            type_str = "oversized"
        elif self.actual_size < self.expected_size:
            type_str = "undersized"
        else:
            type_str = "offset"

        msg = f"{self.msg}: found {type_str} perforation at location ({self.perfloc})."

        super().__init__(msg)


class PerforationNotFoundException(ScanAreaManagerException):
    """Could not find a perforation hole anywhere in the relevant part of the image."""

    def __init__(self, perf_edges: PerforationLocation = None, starting_point: Point = None, perf_line: int = None,
                 *args):

        self.edges = perf_edges
        self.starting_point = starting_point
        self.perf_line = perf_line

        super().__init__(*args)

    def __str__(self):
        if self.starting_point is not None:
            from_msg = f" from start point {self.starting_point}."
        elif self.perf_line is not None:
            from_msg = f" on perforation line at {self.perf_line}."
        else:
            from_msg = "."

        if self.edges is not None:
            nf_str = ["Not Found" if edge == -1 else f"{edge}" for edge in self.edges]
            edge_str = f"Top={nf_str[0]}, Bottom={nf_str[1]}, Inner={nf_str[2]}"
        else:
            edge_str = ""

        return f"Perforation edge(s) not found{from_msg} {edge_str}"


class ImageThresholdLevels(ConfigItem):
    perforation_level: float = Field(default=255, ge=0, le=255)
    filmstock_level: float = Field(default=0, ge=0, le=255)

    @property
    def average(self) -> float:
        """The middle between the perforation level and the filmstock level."""
        return (self.perforation_level + self.filmstock_level) / 2


class ScanAreaManager:
    """The ScanAreaManager keeps track of where within the image taken by the camera the
    actual content (ScanArea) is.

    It does so by detecting the perforation hole in the image and uses it to determine the scanarea.
    The perforation hole must be on the left-hand side of the image.

    The manager must be set up by calling either :meth:'autodetect' or :meth:'manualdetect' method.
    The autodetect method only works if the camera image contains a complete perforation hole.
    If only a partial perforation hole is visible (cropped at the left edge), manual detection is required
    with a (user selectable) point within the perforation.
    Also, a complete film frame must be visible as otherwise the detected scanarea will be outside the image.

    After the inital setup the scan area can be adjusted with the :attr:'region_of_interest' property, e.g. to increase the roi
    from the default area (the camera area as per the film specification)

    After it has been set up, calls to :meth:`update` with a new image will return
    the location of the scanarea for the image.

    :param pid: The id of the project this scanarea is associated with.
                Used for saving and loading the state from the config database.
                If `None` (the default), the scanarea is not associated with any project.
                Instead it will save and load from the GLOBAL context (used for unit tests)
    :param filmspecs: The film dimension specifications. Defaults to 'Filmspecs.Super8'
    """

    def __init__(self, pid: int = None, filmspecs: FilmSpecKey = None):

        if pid:
            self._pid: int | Scope = pid
        else:
            self._pid: int | Scope = Scope.GLOBAL

        self._specs_key: FilmSpecKey | None = None
        self._specs: dict[FSKeys, any] | None = None
        self.film_spec = filmspecs

        self._scanarea: ScanArea | None = None
        """The current scan area and its reference perforation location. This is updated for each new image
        set with the :meth:`update` method."""

        self._reference_perfloc: PerforationLocation | None = None
        """
        The reference perforation location that defines the size and approximate position of a well
        formed perforation hole. Only set by the :meth:`autodetect` and :meth:`manualdetect` methods.
        """

        self._image: np.ndarray | None = None
        """The current image which is to be analyzed."""

        self._blank_image_threshold: int = 10  # todo: adjust as necessar or make user configurable

        self._threshold_levels: ImageThresholdLevels | None = None

    async def load_current_state(self, database: ConfigDatabase, pid: int) -> None:
        """
        Load the last saved state from the config database for the given Project id.
        If there is no previous state in the database, the reference PerforationLocation and the
        ScanArea remain at `None`.
        The pid is stored and will be used for storing the state with the :meth:`save_current_state` method.
        :param pid: The Project id under which the state is to be stored.
        """
        self._reference_perfloc = await PerforationLocation().retrieve(database, pid)
        self._scanarea = await ScanArea().retrieve(database, pid)
        self._threshold_levels = await ImageThresholdLevels().retrieve(database, pid)

    async def save_current_state(self, database: ConfigDatabase, pid: int) -> None:
        """
        Save the current state to the config database for the given Project id.
        This should be called after each successful :meth:`update` call to ensure
        a consistent state in case the scanning is interrupted and started again with a new
        ScanAreaManager instance.
        """
        await self._reference_perfloc.store(database, pid)
        await self._scanarea.store(database, pid)
        await self._threshold_levels.store(database, pid)

    @property
    def film_spec(self) -> FilmSpecKey:
        return self._specs_key

    @film_spec.setter
    def film_spec(self, film_spec: FilmSpecKey) -> None:
        if film_spec != self._specs_key:
            self._specs = FilmSpecs.get_film_spec(film_spec)
            self._specs_key = film_spec

    @property
    def image(self) -> np.ndarray:
        """The image upon which the current ScanArea is derived from.
        This property is read-only. Use :meth:`update` to analyze a new image."""
        return self._image

    @property
    def reference_perfloc(self) -> PerforationLocation:
        """
        The reference perforation location that defines the size and approximate position of
        the perforation location set during the :meth:`autodetect` or :meth:`manualdetect` methods.

        Can be `None` if it is not yet set by a call to :meth:`autodetect` or :meth:`manualdetect`.

        This property is read-only
        """
        return self._reference_perfloc

    @property
    def scanarea(self) -> ScanArea:
        """
        The current scanarea.

        The scanarea can be modified if required. However, if modified manually the :meth:'autodetect' method
        should not be called afterward as it will overwrite the scanarea.
        Setting a new ScanArea will also set the :attr:`reference_perfloc` property.
        """
        return self._scanarea

    @scanarea.setter
    def scanarea(self, scanarea: ScanArea) -> None:
        self._scanarea = scanarea

    @property
    def recommended_shift(self) -> float:
        """The recommended shift of the film to move the center of the Scanarea towards the center
        of the image.

        This is a utility to inform the caller by what fraction of one full frame the film should
        be transported further or less to keep the Scanarea centered as much as possible.

        This property is read-only.

        :returns: A value around 0.0. Negative for shorter, positive for longer frame advances.
        """
        if not self._scanarea:
            raise ScanAreaManagerNotSetUpError

        # How much of the image the frame occupies
        frame_to_perf = self._specs[FSKeys.FILM_FRAME_SIZE][1] / self._specs[FSKeys.PERFORATION_SIZE][1]
        frame_height = self._reference_perfloc.height * frame_to_perf
        centerline = self._scanarea.perf_ref.center.y  # center of perforation relative to image

        # delta is negative if centerline is above mid-image (shorter frame advance required)
        # delta is positive if centerline is below mid-image (longer frame advance required)
        delta_centerline = centerline - 0.5

        # scale result by the frame height
        offset = delta_centerline / frame_height

        return offset

    #
    # Detection methods
    #

    async def autodetect(self, image: np.ndarray) -> None:
        """
        Try to automatically detect a frame in the image.

        This is done by making contour detection of the image and looking for contours that
        have the shape of a perforation hole.
        If found, the ScanArea is set up relative to the perforation hole with the size determined
        from the film specification.

        .. note::
            This only works if the perforation hole is completely visible and the camera frame derived
            from its position is completely within the image.

        If successful, the scanarea and perforationlocation of the Manager are set.

        :raises PerforationNotFoundException: If no contour with the shape of a perforation hole can be found.
        :raises ScanAreaOutOfImageException: If a perforation contour was found, but a ScanArea derived from it is at
            least partially outside the image
        """
        self._image = image

        # mark the current areas as invalid
        self._reference_perfloc = None
        self._scanarea = None

        # start with getting a list of all perforation hole candidates
        perf_list = await self._find_perforations()

        if not perf_list:
            # did not find any perforation holes
            raise PerforationNotFoundException()

        frame_list: list[ScanArea | None] = []
        start_point: Point | None = None
        scanarea: ScanArea | None = None

        # Check if a frame referenced from this perforation is 100% within the image
        # i.e. filter out perforations at the top / bottom edge
        for perf_rect in perf_list:
            # Set starting point to the middle of the perforation
            start_point = perf_rect.center

            # Set the background color and film stock color intensities
            # This is done here to improve the edge detector in the next step
            await self._get_intensities_from_perforation(perf_rect)

            # Locate the top, bottom and inner edge of the perforation
            # Due to noise and blurring these edges may not be the same as the contour
            # find_perf_from_point is better at locating these edges.
            perf_loc = await self._find_perforation_from_point(start_point)

            if not perf_loc:
                # no valid edges found - go with the detected contour
                perf_loc = PerforationLocation(top_edge=perf_rect.y,
                                               bottom_edge=perf_rect.y + perf_rect.height,
                                               inner_edge=perf_rect.x + perf_rect.width)

            scanarea = await self._get_scanarea_from_perforation(perf_loc)

            if scanarea.is_valid:
                # Valid frame found. Store for finding the most centered frame later
                frame_list.append(scanarea)

        if not frame_list:
            # Empty list - did not find a valid frame. For the error message, we use the last detected perforation hole.
            raise ScanAreaOutOfImageException(start_point, scanarea)

        result = frame_list.pop(0)  # use the first found frame unless we find a better one
        result_center = result.rect.center.y
        result_delta = abs(0.5 - result_center)  # distance to the middle of the image

        if len(frame_list) > 1:
            # Check if another frame is closer to the center of the image
            for scanarea in frame_list:
                center = scanarea.edges.top + scanarea.size.height / 2
                delta = abs(0.5 - center)
                if delta < result_delta:
                    result = scanarea
                    result_delta = delta

        self._reference_perfloc = result.perf_ref
        self._scanarea = result

    async def manualdetect(self, image: np.ndarray, start_point: Point) -> None:
        """With a given starting point located within a perforation hole, find the size
        of the perforation hole and set the PerforationLocation.

        If no ScanArea has been set, a ScanArea suitable for the FilmSpec is also created.
        """
        self._image = image

        # mark the current areas as invalid
        self._reference_perfloc = None
        self._scanarea = None

        perf_loc = await self._find_perforation_from_point(start_point)
        if not perf_loc:
            raise PerforationNotFoundException(perf_loc, start_point)

        # now we can set the threshold levels correctly
        await self._get_intensities_from_perforation(perf_loc.rect)

        if not self._scanarea:
            # ScanArea has not yet been set up. Do so now, using the specified film dimensions and the perforation size
            scanarea = await self._get_scanarea_from_perforation(perf_loc)
            if not scanarea.is_valid:
                # scanarea is not within the image
                raise ScanAreaOutOfImageException(start_point, scanarea)
        else:
            # Scanarea has already been set up: set the new reference point
            scanarea = self._scanarea
            scanarea.perf_ref = perf_loc

        self._reference_perfloc = perf_loc
        self._scanarea = scanarea

    #
    # Update method
    #

    async def update(self, image: np.ndarray) -> Rect:
        """
        Update the Manager with a new image.
        Based on the previously set PerforationLocation and ScanArea, this method will locate
        the topmost valid perforation location of the current image and set
        the ScanArea accordingly.

        This is the main method to call for a new image.

        :returns: A rectangle with normalized values covering the scanarea,
                  i.e. the area to be cut from the image for further processing
        """
        if not self._scanarea:
            raise

        self._image = image

        img_h, img_w, _ = image.shape

        # first, try finding the perforation starting at the center of the previous perforation hole
        perf_loc = await self._find_perforation_from_point(self._scanarea.perf_ref.center)
        if perf_loc is None:
            # not found: try looking somewhere up or down the image (but on the same vertical axis)
            try:
                perf_loc = await self._find_perforation_from_line(self._scanarea.perf_ref.center.x)
            except PerforationNotFoundException as exc:
                # No perforation edges found. Maybe we ran out of film
                if self._is_blank():
                    raise BlankFrameException()
                else:
                    raise exc  # pass the PerforationNotFoundException to the caller

        # We now have a well-behaved perforation hole.
        # Store it as a reference for the next image
        self._scanarea.perf_ref = perf_loc

        return self._scanarea.rect

    #
    # private methods
    #

    async def _find_perforation_from_line(self, line_pos: float) -> PerforationLocation:
        """
        Find the first perforation hole located on the vertical line at the center of the
        current PerforationLocation.

        If the vertical size of the hole is different from the reference size, it is assumed
        that the perforation is damaged. But if either top or bottom edge is similar to that of the
        previous detection the other edge is calculated from the good edge.

        :param line_pos: The normalized x coordinate at which to look for the perforation.
        :return: A new PerforationLocation object
         """

        # The threshold is right between the background level (bright) and the film stock level (darkish)
        threshold = self._threshold_levels.average

        img_h, img_w, _ = self._image.shape

        # number of pixels around the ref point axis to average out noise
        delta = round(img_w * 0.01 + 1)  # 1% of the image width should be a good value

        perf_line = round(line_pos * img_w)  # scale the line_pos to the actual image size

        # First get vertical slice of the image around the perf_line and average the pixel values.
        img_slice = self._image[0:img_h, perf_line - delta:perf_line + delta]
        grey_slice = cv.cvtColor(img_slice, cv.COLOR_BGR2GRAY)
        line = np.average(grey_slice, axis=1)

        # get the boundaries of a valid perforation hole
        edges = self._max_perf_edges(self._scanarea)
        min_top = edges.top * img_h
        max_bottom = edges.bottom * img_h
        max_inner = edges.right * img_w

        start = 0
        found = False
        top_edge = bottom_edge = inner_edge = outer_edge = -1

        while start < max_bottom:
            # search the first dark spot, starting from the top (in case there is a partial perforation hole at the top)
            part_line = line[start:]
            first_dark = int(np.argmax(part_line < threshold))  # argmax returns int64

            # find the first occurence of a dark to light transition (top edge of perf)
            part_line = line[first_dark:]
            top = int(np.argmax(part_line > threshold))

            # and now, starting from top, the first transition from light to dark (bottom edge)
            part_line = part_line[top:]
            bot = int(np.argmax(part_line < threshold))

            if top == 0 or bot == 0:
                raise PerforationNotFoundException()

            # adjust top and bottom to actual pixel positions
            top_edge = start + first_dark + top
            bottom_edge = start + first_dark + top + bot

            # we now have the top and bottom edge of the perforation hole
            # get the inner edge
            mid = round((top_edge + bottom_edge) / 2)

            img_slice = self._image[mid - delta:mid + delta, perf_line:img_w]
            grey_slice = cv.cvtColor(img_slice, cv.COLOR_BGR2GRAY)
            line = np.mean(grey_slice, axis=0)

            idx = int(np.argmax(line < threshold))
            if idx == 0:
                inner_edge = img_w  # this will cause an MalformedPerforationException later
            else:
                inner_edge = perf_line + idx

            # Set the outer edge to inner_edge minus perforation width
            reference_width = self._reference_perfloc.width * img_w
            outer_edge = inner_edge - reference_width

            found = True
            break

        if not found:
            raise PerforationNotFoundException(perf_line=perf_line)
        if top_edge < min_top or bottom_edge > max_bottom or inner_edge > max_inner:
            # found a perforation, but the resulting ScanArea is at least partially outside the image
            raise PerforationNotFoundException(perf_line=perf_line)

        # Normalize result and pack into a PerforationLocation
        perfloc = PerforationLocation(top_edge=top_edge / img_h,
                                      bottom_edge=bottom_edge / img_h,
                                      inner_edge=inner_edge / img_w,
                                      outer_edge=outer_edge / img_w)

        # check that all edges are valid and fix if possible
        await self._fix_perforation(perfloc)

        return perfloc

    async def _find_perforation_from_point(self, start_point: Point) -> PerforationLocation | None:
        """
        Starting the given point, locate the edges of the perforation hole.

        If the top, bottom or inner edge could not be found, `None` is returned.
        If the outer Edge is not found (hole partially outside image), then it is set to 0.

        :param start_point: The starting point. Must be within a perforation hole.
        """

        img_h, img_w, _ = self._image.shape
        p_x = round(start_point.x * img_w)
        p_y = round(start_point.y * img_h)

        # number of pixels around the ref point axis to average out noise
        delta = 10  # pixels. TODO: change this to something relative to the image size

        # clamp to ensure we stay in the image
        y_start = max(p_y - delta, 0)
        y_end = min(p_y + delta, img_h)
        x_start = max(p_x - delta, 0)
        x_end = min(p_x + delta, img_w)

        # Check that the area around the starting point is all above the threshold. If not
        # the image might have shifted so much that the starting point is not within a perforation
        # hole anymore
        img_slice = self._image[y_start:y_end, x_start:x_end]
        grey_slice = cv.cvtColor(img_slice, cv.COLOR_BGR2GRAY)
        avg = np.average(grey_slice)

        if self._threshold_levels:
            # The threshold is right between the background level (bright) and the film stock level (darkish)
            threshold = self._threshold_levels.average
            if avg < threshold:
                return None
        else:
            # Need to make a guess - use the level at the startpoint as perforation and subtract a bit for the stock.
            # This assumes that the startpoint was actually over a perforation hole. If not, this will
            # fail further down when not being able to detect an edge.
            threshold = avg - 20

        # First find the top and bottom edge of the perforation
        img_slice = self._image[0:img_h, max(p_x - delta, 0):min(p_x + delta, img_w)]
        grey_slice = cv.cvtColor(img_slice, cv.COLOR_BGR2GRAY)
        line = np.average(grey_slice, axis=1)

        # top edge, starting from the ref position and checking upward for
        # a value below the threshold
        val_slice = np.flip(line[:p_y])
        idx = int(np.argmax(val_slice < threshold))  # np.argmax returns int64
        if 0 < idx < img_h:  # check if valid
            top_edge = p_y - idx
        else:
            return None

        # ...now the same for the bottom edge...
        val_slice = line[p_y:]
        idx = int(np.argmax(val_slice < threshold))
        if 0 < idx < img_h:  # check if valid
            bot_edge = p_y + idx
        else:
            return None

        # ...then the inner edge of the perforation...
        img_slice = self._image[p_y - delta:p_y + delta, 0:img_w]
        grey_slice = cv.cvtColor(img_slice, cv.COLOR_BGR2GRAY)
        line = np.mean(grey_slice, axis=0)
        val_slice = line[p_x:]
        idx = int(np.argmax(val_slice < threshold))
        if 0 <= idx < img_w:
            inner_edge = p_x + idx  # found inner edge
        else:
            return None

        # The outer edge is special as it may be outside the image
        val_slice = np.flip(line[:max(p_x, 1)])
        idx = int(np.argmax(val_slice < threshold))
        if 0 <= idx < img_w:
            outer_edge = p_x - idx  # found outer edge
        else:
            outer_edge = 0

        # Normalize result and pack into a PerforationLocation
        perfloc = PerforationLocation(top_edge=top_edge / img_h,
                                      bottom_edge=bot_edge / img_h,
                                      inner_edge=inner_edge / img_w,
                                      outer_edge=outer_edge / img_w, )

        # check that all edges are valid and fix if possible
        await self._fix_perforation(perfloc)

        return perfloc

    async def _fix_perforation(self, perfloc: PerforationLocation) -> None:
        """
        Check if the given perforation location has the same size as the reference perforation location.
        If the size is wrong, try to fix the offending edge. This assumes, that the given perforation location
        is approximately at the same position as the reference perforation location.
        If the perforation cannot be fixed a MalformedPerforationException will be raised.
        """
        if self._reference_perfloc is None:
            # If the reference has not yet been set, there is nothing we can 'fix'
            # This happens when this gets called from one of the detection methods.
            # Leave perfloc as is.
            return

        ref_loc = self._reference_perfloc
        ref_height = ref_loc.height
        ref_width = ref_loc.width
        last_inner = self._scanarea.perf_ref.inner_edge

        # now check that the hole height is in limits (2% of reference size)
        height = perfloc.bottom_edge - perfloc.top_edge
        epsilon = ref_height * 0.02
        if abs(height - ref_height) > epsilon:
            # It is not. Check if either top or bottom edge is within 2% of the last value
            top_offset = perfloc.top_edge - self._scanarea.perf_ref.top_edge
            bot_offset = perfloc.bottom_edge - self._scanarea.perf_ref.bottom_edge
            if abs(top_offset) < epsilon:
                # top is good, use it to define bottom
                perfloc.bottom_edge = perfloc.top_edge + ref_height
            elif abs(bot_offset) < epsilon:
                # bottom is good, use it to define top
                perfloc.top_edge = perfloc.bottom_edge - ref_height
            else:
                # Neither edge is good. Fail
                raise MalformedPerforationException("Perforation Vertical", perfloc, ref_height, perfloc.height)

        # Handle the case where the inner edge is more than 5% off of the last location inner edge
        # (Damaged edge or dirt). In this case, use the previous inner edge and adjust outer accordingly
        delta_inner = perfloc.inner_edge - last_inner
        if abs(delta_inner) > 0.05:
            perfloc.inner_edge = last_inner
            perfloc.outer_edge = max(0.0, last_inner - ref_width)

    async def _find_perforations(self) -> list[Rect]:
        """
        Find all shapes in the current image that look like a perforation hole.
        To look like means all bright shapes, that have the same aspect ratio as a perforation hole,
        and that are at least 0.2% of the image.

        :returns: A list of Rect objects with normalized values for x,y, width and height.
        """
        if self._image is None:
            raise NoImageSetError()

        ff = self._specs

        img_h, img_w, _ = self._image.shape

        p_w, p_h = ff[FSKeys.PERFORATION_SIZE]

        specs_aspect_ratio = p_w / p_h

        tolerance = 0.1  # Acceptable variation: 10% TODO: Check if appropriate

        # Perforation should cover min 0.2% of image. Used to filter out small random noise contours
        min_pref_area = (img_w * img_h) / 500  # TODO: check if appropriate

        # Convert to grayscale and then to a binary image
        gray_image = cv.cvtColor(self._image, cv.COLOR_BGR2GRAY)
        gray_image = cv.medianBlur(gray_image, 5)  # reduce noise to improve detection

        # Threshold for better contour detection
        threshold = np.amax(gray_image)
        threshold -= int(threshold / 10)  # top 10% - TODO: check if useful

        _, thresh_img = cv.threshold(gray_image, threshold, 255, cv.THRESH_BINARY)

        # contour detection
        contours, _ = cv.findContours(thresh_img, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE)

        # debug
        # cv.drawContours(image, contours, -1, (255, 0, 0), 1)

        # filter matching contours - contours with the right aspect ratio
        perf_list = []
        for cnt in contours:
            x, y, w, h = cv.boundingRect(cnt)
            cnt_aspect_ratio = w / h
            cnt_area = cv.contourArea(cnt)
            if cnt_area > min_pref_area:  # filter small random noise contours
                if abs(cnt_aspect_ratio - specs_aspect_ratio) < tolerance:
                    # normalize
                    rect = Rect(x=x / img_w, y=y / img_h, width=w / img_w, height=h / img_h)
                    perf_list.append(rect)

        return perf_list

    async def _get_intensities_from_perforation(self, perf_rect: Rect):
        """
        Determine the background and film stock intensities.

        Looks at the center of the perf_rect for the background gray level (background light) and at a point
        just below the perf_rect for the film stock gray level.
        Both values are stored in this ScanAreaManager instance.

        The intensities are used to improve the perforation-edge detection.

        :param perf_rect: The perforation to look at
        """
        if self._image is None:
            raise NoImageSetError()

        img_h, img_w, _ = self._image.shape

        px = perf_rect.x * img_w
        py = perf_rect.y * img_h
        pw = perf_rect.width * img_w
        ph = perf_rect.height * img_h

        center_x = int(px + (pw / 2))
        center_y = int(py + (ph / 2))
        outside_x = int(center_x)
        outside_y = int(center_y + ph + (ph / 10))  # 10% of perforation below the bottom edge

        # Background color is the average gray level 10 pixel around the mid-point of the perforation hole
        clip = self._image[center_y - 10:center_y + 10, center_x - 10:center_x + 10]
        grey_clip = cv.cvtColor(clip, cv.COLOR_BGR2GRAY)
        perforation_level = float(np.average(grey_clip))

        # Film stock level is taken from a point just below the perforation hole below,
        # because for some film types with perforation holes between frames, there
        # may not be any image above the perforation hole.
        clip = self._image[outside_y - 10:outside_y + 10, outside_x - 10:outside_x + 10]
        grey_clip = cv.cvtColor(clip, cv.COLOR_BGR2GRAY)
        filmstock_level = float(np.average(grey_clip))

        self._threshold_levels = ImageThresholdLevels(perforation_level=perforation_level,
                                                      filmstock_level=filmstock_level)

    async def _get_scanarea_from_perforation(self, perfloc: PerforationLocation) -> ScanArea:
        """
        Determine the camera frame position relative to the perforation hole.

        For film types that have multiple perforation holes per frame, this method assumes that the
        given perforation is the first one in the list of the FilmSpec.

        :param perfloc: The location of the perforation
        """
        top_edge = perfloc.top_edge
        bot_edge = perfloc.bottom_edge

        # Determine the scale, i.e. unit per mm.
        perf_w_mm, perf_h_mm = self._specs[FSKeys.PERFORATION_SIZE]
        scale_v = (bot_edge - top_edge) / perf_h_mm

        if self._image is not None:
            scale_h = scale_v / self._image_aspect_ration()
        else:
            # Without image we assume an aspect_ratio of 1. This is only relevant during testing
            scale_h = scale_v

        # start with the reference point. go from mm to unit
        cam_dx, cam_dy = self._specs[FSKeys.CAMERA_FRAME_POS]
        delta_ref = OffsetPoint(dx=cam_dx * scale_h, dy=cam_dy * scale_v)

        # and now the frame itself
        cam_w, cam_h = self._specs[FSKeys.CAMERA_FRAME_SIZE]
        size = Size(width=cam_w * scale_h, height=cam_h * scale_v)

        return ScanArea(perf_ref=perfloc, ref_delta=delta_ref, size=size)

    async def _is_blank(self) -> bool:
        """Checks if the given image is blank, i.e. if it has a uniform color"""

        # The maximum grey level variation. A small value indicates a uniform image.
        threshold = self._blank_image_threshold

        _, stddev = cv.meanStdDev(self._image)
        return bool(np.amax(stddev) < threshold)

    def _image_aspect_ration(self) -> float:
        """
        Gets the aspect ration of the current image.
        It is defined as width / height
        """
        img_h, img_w, _ = self._image.shape
        return img_w / img_h

    @staticmethod
    def _max_perf_edges(scanarea: ScanArea) -> RectEdges:
        """
        Get the area where a perforation hole must be in so that the associated scanarea is still 100% within
        the image, i.e. no edge of the scanarea is outside the image.

        This can be used to limit the search for a perforation hole to the area where it ensures a full frame.

        None of the returned edges are less than zero or more than 1 (outside of image)
        """
        perf_height = scanarea.perf_ref.bottom_edge - scanarea.perf_ref.top_edge

        upmost_ref_point_y = -scanarea.ref_delta.dy
        top = clamp(upmost_ref_point_y - perf_height / 2, 0.0, 1.0)

        downmost_ref_point_y = 1.0 - scanarea.size.height - scanarea.ref_delta.dy
        bottom = clamp(downmost_ref_point_y + perf_height / 2, 0.0, 1.0)

        left = 0.0  # perforation can always be at the left edge
        right = clamp(1.0 - scanarea.size.width - scanarea.ref_delta.dx, 0.0, 1.0)

        return RectEdges(top=top, bottom=bottom, left=left, right=right)


def clamp(n: float, min_value: float, max_value: float) -> float:
    """Clamp value n to the min and max values"""
    return max(min_value, min(n, max_value))
