import unittest

import cv2 as cv
import numpy as np

import mockpicamera.film_generator as fg
from tofisca.configuration.database import ConfigDatabase, Scope
from tofisca.film_specs import FilmSpecKey
from tofisca.models import PerforationLocation, OffsetPoint, Size, ScanArea, Point
from tofisca.scanarea_manager import ScanAreaManager, ScanAreaOutOfImageException, PerforationNotFoundException


class ScanAreaManagerTestCase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.tfg = fg.TestFrameGenerator(FilmSpecKey.SUPER8, 1024, 760)
        ConfigDatabase("memory")

    async def asyncTearDown(self) -> None:
        ConfigDatabase.delete_singleton()

    async def test_initial_properties(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)
        self.assertIsNotNone(sam)

        self.assertEqual(sam.film_spec, FilmSpecKey.SUPER8)
        self.assertIsNone(sam.reference_perfloc)
        self.assertIsNone(sam.scanarea)
        self.assertIsNone(sam.image)

    async def test_store_and_retrieve(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)
        img = self.tfg.render_image()
        await sam.autodetect(img)
        ref_perfloc = sam.reference_perfloc
        scanarea = sam.scanarea

        # noinspection PyTypeChecker
        await sam.save_current_state(
            Scope.GLOBAL)  # GLOBAL because we do not have a project. Not official API but works.

        sam2 = ScanAreaManager(FilmSpecKey.SUPER8)
        # noinspection PyTypeChecker
        await sam2.load_current_state(Scope.GLOBAL)
        self.assertEqual(ref_perfloc, sam2.reference_perfloc)
        self.assertEqual(scanarea, sam2.scanarea)

    async def test_autodetect(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)

        # start with the default settings
        img = self.tfg.render_image()
        await sam.autodetect(img)
        self.assertIsNotNone(sam.scanarea)
        rect1 = sam.scanarea.rect
        self.assertIsNotNone(rect1)
        sam._scanarea = None  # reset for next test

        # test that autodetect() is deterministic, i.e. multiple invocations should always
        # return the same results.
        await sam.autodetect(img)
        rect2 = sam.scanarea.rect
        self.assertEqual(rect1, rect2)
        sam._scanarea = None  # reset for next test

        # add noise
        self.tfg.noise = 15
        img = self.tfg.render_image()
        await sam.autodetect(img)
        self.assertIsNotNone(sam.scanarea)
        sam._scanarea = None  # reset for next test

        # add bluring
        self.tfg.defocus = 1.0
        img = self.tfg.render_image()
        await sam.autodetect(img)
        self.assertIsNotNone(sam.scanarea)
        sam._scanarea = None  # reset for next test

        # move frame outside - should not find any valid ScanArea
        with self.assertRaises(ScanAreaOutOfImageException):
            self.tfg.horizontal_offset = 0.3
            img = self.tfg.render_image()
            await sam.autodetect(img)

        # blank image - should not find any perforation
        with self.assertRaises(PerforationNotFoundException):
            img = blank_image(500, 400)
            await sam.autodetect(img)

    async def test_manualdetect(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)
        img = self.tfg.render_image()
        img_h, img_w, _ = img.shape

        ref_perf_x = self.tfg.perforation_centers[0][0] / img_w
        ref_perf_y = self.tfg.perforation_centers[0][1] / img_h
        await sam.manualdetect(img, Point(x=ref_perf_x, y=ref_perf_y))
        self.assertIsNotNone(sam.scanarea)

        self.assertAlmostEqual(ref_perf_x, sam.reference_perfloc.center.x, 2)
        self.assertAlmostEqual(ref_perf_y, sam.reference_perfloc.center.y, 2)

        # move the frame outside so that we have only a partial perforation
        self.tfg.horizontal_offset = -ref_perf_x
        img = self.tfg.render_image()
        await sam.manualdetect(img, Point(x=0, y=ref_perf_y))
        self.assertIsNotNone(sam.scanarea)

        # blank image - should not find any perforation
        img = blank_image(1024, 760)
        with self.assertRaises(PerforationNotFoundException):
            await sam.manualdetect(img, Point(x=0.5, y=0.5))

    async def test_recommended_shift(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)

        image = self.tfg.render_image()
        await sam.autodetect(image)
        img_h, img_w, _ = image.shape

        # By default, the rendered frame is in the center
        self.assertAlmostEqual(0.0, sam.recommended_shift, 2)

        # now shift the image down by 1/4 of a frame
        self.tfg.vertical_offset = 0.25
        await sam.update(self.tfg.render_image())
        self.assertAlmostEqual(0.25, sam.recommended_shift, 2)

        # und up
        self.tfg.vertical_offset = -0.25
        await sam.update(self.tfg.render_image())
        self.assertAlmostEqual(-0.25, sam.recommended_shift, 2)

    async def test_get_intensities_from_perforation(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)

        self.assertIsNone(sam._threshold_levels)

        image = self.tfg.render_image()

        # cv.imshow("image", image)
        # cv.waitKey(0)

        await sam.autodetect(image)

        self.assertTrue(
            sam._threshold_levels.perforation_level > (0.9 * 255))  # TestFrameGenerator uses 0.95 as the background level
        self.assertTrue(
            sam._threshold_levels.filmstock_level < (0.2 * 255))  # TestFramewGenerator uses 0.1 for the stock level
        self.assertAlmostEqual(((0.95 + 0.1) / 2) * 255, sam._threshold_levels.average, 0)

    async def test_get_scanarea_from_perforation(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)

        # create an artifical perforation location that maps 1 mm to 10% of the image
        perfloc = PerforationLocation(top_edge=0.0, bottom_edge=0.1143, inner_edge=0.0914, outer_edge=0.0)
        scanarea = await sam._get_scanarea_from_perforation(perfloc)

        self.assertAlmostEqual(0.569, scanarea.size.width, 3)  # scanarea width
        self.assertAlmostEqual(0.422, scanarea.size.height, 3)  # scanarea height
        self.assertAlmostEqual(0.0914, scanarea.ref.width, 3)  # perforation width
        self.assertAlmostEqual(0.1143, scanarea.ref.height, 3)  # perforation height
        self.assertAlmostEqual(0.0046, scanarea.ref_delta.dx, 3)  # offset dx
        self.assertAlmostEqual(-0.211, scanarea.ref_delta.dy, 3)  # offset dy

    async def test_is_blank(self):
        sam = ScanAreaManager(FilmSpecKey.SUPER8)

        image = self.tfg.render_image()
        sam._image = image
        self.assertFalse(await sam._is_blank())

        image = blank_image(640, 480, sam._blank_image_threshold - 1)
        sam._image = image
        self.assertTrue(await sam._is_blank())

        image = blank_image(640, 480, sam._blank_image_threshold + 2)
        sam._image = image
        self.assertFalse(await sam._is_blank())

    def test_max_perf_edges(self):
        perfloc = PerforationLocation(top_edge=0.4, bottom_edge=0.6, inner_edge=0.2, outer_edge=0.1)
        refdelta = OffsetPoint(dx=0.1, dy=-0.2)
        size = Size(width=0.6, height=0.4)
        scanarea = ScanArea(ref=perfloc, ref_delta=refdelta, size=size)

        edges = ScanAreaManager._max_perf_edges(scanarea)

        self.assertAlmostEqual(0.1, edges.top, 2)
        self.assertAlmostEqual(0.9, edges.bottom, 2)
        self.assertAlmostEqual(0.0, edges.left, 2)
        self.assertAlmostEqual(0.3, edges.right, 2)


def blank_image(width: int, height: int, random_variation: int = 10) -> np.ndarray:
    img = np.zeros([height, width, 3], dtype=np.uint8)
    img.fill(240)  # or img[:] = 255
    img_h, img_w, channels = img.shape
    noisemap = np.random.normal(0, random_variation, (img_h, img_w, channels))
    # noisemap = noisemap.reshape(img_h, img_w, channels)
    noisemap = noisemap.astype(np.int8)
    img = cv.add(img, noisemap, dtype=0)
    return img


def _find_red_marker(image: np.ndarray) -> tuple:
    """Find the red marker that TestFilmGenerator places in the middle of each camera frame."""

    # split image and only use red channel
    red_channel = image[..., 2]
    _, red_channel = cv.threshold(red_channel, 254, 255, cv.THRESH_BINARY)

    lines = cv.HoughLinesP(red_channel, 1, np.pi / 180, 20)

    cx = cy = None
    # Draw the lines
    if lines is not None:
        for i in range(0, len(lines)):
            x1, y1, x2, y2 = lines[i][0]
            if x1 == x2:
                cx = x1
            if y1 == y2:
                cy = y1

    return cx, cy


def debug_show_image(sam: ScanAreaManager) -> None:
    image = sam.image
    img: np.ndarray = image.copy()
    img_h, img_w, _ = img.shape

    scanarea = sam.scanarea

    perf_line = round(scanarea.ref.inner_edge * img_w)
    perf_top = round(scanarea.ref.top_edge * img_h)
    perf_bot = round(scanarea.ref.bottom_edge * img_h)
    ref_point_x = round(scanarea.ref.reference.x * img_w)
    ref_point_y = round(scanarea.ref.reference.y * img_h)
    x = round(scanarea.rect.x * img_w)
    y = round(scanarea.rect.y * img_h)
    w = round(scanarea.rect.width * img_w)
    h = round(scanarea.rect.height * img_h)

    cv.line(img, (perf_line, 0), (perf_line, img_h), (255, 0, 0))
    cv.line(img, (perf_line - 20, perf_top), (perf_line + 20, perf_top), (255, 0, 0))
    cv.line(img, (perf_line - 20, perf_bot), (perf_line + 20, perf_bot), (255, 0, 0))
    cv.drawMarker(img, (ref_point_x, ref_point_y), (255, 255, 0), cv.MARKER_CROSS)
    cv.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0))

    cv.imshow("Test", img)
    cv.waitKey(0)


if __name__ == '__main__':
    unittest.main()
