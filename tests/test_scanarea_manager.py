import cv2 as cv
import numpy as np
import pytest

import film_generator as film_generator
from configuration.database import ConfigDatabase, Scope
from film_specs import FilmSpecKey
from models import PerforationLocation, OffsetPoint, Size, ScanArea, Point
from scanarea_manager import ScanAreaManager, ScanAreaOutOfImageException, PerforationNotFoundException


@pytest.fixture(scope='session', autouse=True)
def database():
    return ConfigDatabase("memory")


@pytest.fixture()
def sam():
    """ScanAreaManager"""
    sam = ScanAreaManager(filmspecs=FilmSpecKey.SUPER8)
    return sam


@pytest.fixture(scope="function")
def tfg():
    """TestFrameGenerator"""
    tfg = film_generator.TestFrameGenerator(width=1024, height=768)
    return tfg


def test_initial_properties(sam):
    assert sam.film_spec == FilmSpecKey.SUPER8
    assert sam.reference_perfloc is None
    assert sam.scanarea is None
    assert sam.image is None


@pytest.mark.asyncio
async def test_store_and_retrieve(sam, tfg, database):
    img = tfg.render_image()
    await sam.autodetect(img)
    ref_perfloc = sam.reference_perfloc
    scanarea = sam.scanarea

    # noinspection PyTypeChecker
    await sam.save_current_state(database, Scope.GLOBAL)
    # GLOBAL because we do not have a project. Not official API but works.

    sam2 = ScanAreaManager(filmspecs=FilmSpecKey.SUPER8)
    # noinspection PyTypeChecker
    await sam2.load_current_state(database, Scope.GLOBAL)
    assert ref_perfloc == sam2.reference_perfloc
    assert scanarea == sam2.scanarea


@pytest.mark.asyncio
async def test_autodetect(sam, tfg):
    # start with the default settings
    img = tfg.render_image()
    await sam.autodetect(img)
    assert sam.scanarea is not None
    rect1 = sam.scanarea.rect
    assert rect1 is not None
    sam._scanarea = None  # reset for next test

    # test that autodetect() is deterministic, i.e. multiple invocations should always
    # return the same results.
    await sam.autodetect(img)
    rect2 = sam.scanarea.rect
    assert rect1 == rect2
    sam._scanarea = None  # reset for next test

    # add noise
    tfg.noise = 15
    img = tfg.render_image()
    await sam.autodetect(img)
    assert sam.scanarea is not None
    sam._scanarea = None  # reset for next test

    # add bluring
    tfg.defocus = 1.0
    img = tfg.render_image()
    await sam.autodetect(img)
    assert sam.scanarea is not None
    sam._scanarea = None  # reset for next test

    # move frame outside - should not find any valid ScanArea
    with pytest.raises(ScanAreaOutOfImageException):
        tfg.horizontal_offset = 0.3
        img = tfg.render_image()
        await sam.autodetect(img)

    # blank image - should not find any perforation
    with pytest.raises(PerforationNotFoundException):
        await sam.autodetect(blank_image())


@pytest.mark.asyncio
async def test_manualdetect(sam, tfg):
    img = tfg.render_image()
    img_h, img_w, _ = img.shape

    ref_perf_x = tfg.perforation_centers[0][0] / img_w
    ref_perf_y = tfg.perforation_centers[0][1] / img_h
    await sam.manualdetect(img, Point(x=ref_perf_x, y=ref_perf_y))
    assert sam.scanarea is not None

    assert ref_perf_x == pytest.approx(sam.reference_perfloc.center.x), 2
    assert ref_perf_y == pytest.approx(sam.reference_perfloc.center.y), 2

    # move the frame outside so that we have only a partial perforation
    tfg.horizontal_offset = -ref_perf_x
    img = tfg.render_image()
    await sam.manualdetect(img, Point(x=0, y=ref_perf_y))
    assert sam.scanarea is not None

    # blank image - should not find any perforation
    with pytest.raises(PerforationNotFoundException):
        await sam.manualdetect(blank_image(), Point(x=0.5, y=0.5))


@pytest.mark.asyncio
async def test_recommended_shift(sam, tfg):
    image = tfg.render_image()
    await sam.autodetect(image)
    img_h, img_w, _ = image.shape

    # By default, the rendered frame is in the center
    assert 0.0 == pytest.approx(sam.recommended_shift)

    # now shift the image down by 1/4 of a frame
    tfg.vertical_offset = 0.25
    await sam.update(tfg.render_image())
    assert 0.25 == pytest.approx(sam.recommended_shift, rel=1e-2)

    # und up
    tfg.vertical_offset = -0.25
    await sam.update(tfg.render_image())
    assert -0.25 == pytest.approx(sam.recommended_shift, rel=1e-2)


@pytest.mark.asyncio
async def test_get_intensities_from_perforation(sam, tfg):
    assert sam._threshold_levels is None

    image = tfg.render_image()
    await sam.autodetect(image)

    assert sam._threshold_levels is not None

    assert sam._threshold_levels.perforation_level > (0.9 * 255)  # TestFrameGenerator uses 0.95 as the background level
    assert sam._threshold_levels.filmstock_level < (0.2 * 255)  # TestFramewGenerator uses 0.1 for the stock level
    assert ((0.95 + 0.1) / 2) * 255 == pytest.approx(sam._threshold_levels.average, rel=1e-2)


@pytest.mark.asyncio
async def test_get_scanarea_from_perforation(sam):
    # create an artifical perforation location that maps 1 mm to 10% of the image
    perfloc = PerforationLocation(top_edge=0.0, bottom_edge=0.1143, inner_edge=0.0914, outer_edge=0.0)
    scanarea = await sam._get_scanarea_from_perforation(perfloc)

    assert 0.569 == pytest.approx(scanarea.size.width, rel=1e-3)  # scanarea width
    assert 0.422 == pytest.approx(scanarea.size.height, rel=1e-3)  # scanarea height
    assert 0.0914 == pytest.approx(scanarea.ref.width, rel=1e-3)  # perforation width
    assert 0.1143 == pytest.approx(scanarea.ref.height, rel=1e-3)  # perforation height
    assert 0.0046 == pytest.approx(scanarea.ref_delta.dx, rel=1e-3)  # offset dx
    assert -0.211 == pytest.approx(scanarea.ref_delta.dy, rel=1e-3)  # offset dy


@pytest.mark.asyncio
async def test_is_blank(sam, tfg):
    image = tfg.render_image()
    sam._image = image
    assert not await sam._is_blank()

    image = blank_image(640, 480, sam._blank_image_threshold - 1)
    sam._image = image
    assert await sam._is_blank()

    image = blank_image(640, 480, sam._blank_image_threshold + 2)
    sam._image = image
    assert not await sam._is_blank()


def test_max_perf_edges(sam):
    perfloc = PerforationLocation(top_edge=0.4, bottom_edge=0.6, inner_edge=0.2, outer_edge=0.1)
    refdelta = OffsetPoint(dx=0.1, dy=-0.2)
    size = Size(width=0.6, height=0.4)
    scanarea = ScanArea(ref=perfloc, ref_delta=refdelta, size=size)

    edges = ScanAreaManager._max_perf_edges(scanarea)

    assert 0.1 == pytest.approx(edges.top), 2
    assert 0.9 == pytest.approx(edges.bottom), 2
    assert 0.0 == pytest.approx(edges.left), 2
    assert 0.3 == pytest.approx(edges.right), 2


def blank_image(width: int = 640, height: int = 480, variation: int = 10) -> np.ndarray:
    img = np.zeros([height, width, 3], dtype=np.uint8)
    img.fill(240)  # or img[:] = 255
    img_h, img_w, channels = img.shape
    noisemap = np.random.normal(0, variation, (img_h, img_w, channels))
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
