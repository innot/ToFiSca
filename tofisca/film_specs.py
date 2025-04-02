from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class FilmFormat(BaseModel):
    key: FilmSpecKey = ""
    name: str = ""
    framerates: list[float] = []


class FSKeys(Enum):
    NAME = "name"
    """Name to be shown on the UI. Can include spaces and other characters not useable for the enum key."""

    FRAMERATES = "framerates"
    """Typical frame rates used for this kind of film"""

    FILM_FRAME_SIZE = "film_frame_size"
    """width / height of a single frame (in mm)"""

    PERFORATION_SIZE = "performation_size"
    """width / height of a perforation hole (in mm)"""

    PERFORATION_POS = "performation_pos"
    """list of perforation hole positions (top/left corner relative to the film frame)"""

    PERFORATIONS_PER_FRAME = "performations_ps_per_frame"
    """Number of perforation holes per frame (single side only)"""

    CAMERA_FRAME_SIZE = "camera_frame_size"
    """width / height of the camera aperture frame (in mm)"""

    CAMERA_FRAME_POS = "camera_frame_pos"
    """top / left corner of the camera aperture frame (in mm relative to the Perforation position)"""

    PROJECTOR_FRAME_SIZE = "project_frame_size"
    """width / height of the projector aperture frame (in mm)"""

    PROJECTOR_FRAME_POS = "project_frame_pos"
    """top / left corner of the projector aperture frame (in mm relative to the Perforation position)"""

    # only used for the test/mock image generator

    FRAME_CORNER_RADIUS = "frame_corner_radius"
    """corner radius of the camera and projector frames (in mm)"""

    PERFORATION_RADIUS = "performation_radius"
    """corner radius of the perforation hole (in mm)"""


class FilmSpecKey(str, Enum):
    SUPER8 = "super8"
    NORMAL8 = "normal8"
    STD16MM = "std16mm"
    SUPER16 = "super16"


"""
Specifications of film dimensions.
All values are in millimeters and positions are referenced to to middle of the inner edge of the perforation hole.
"""
film_specs: dict[FilmSpecKey, dict[FSKeys, any]] = {

    # Super8 frame specification
    # Taken from https://www.filmkorn.org/super8data/database/articles_list/super8_fotmat_standards.htm
    # and http://www.gcmstudio.com/filmspecs/filmspecs.html
    # and https://www.nfsa.gov.au/preservation/preservation-glossary/Film_format
    # All values in millimeters.
    FilmSpecKey.SUPER8: {
        FSKeys.NAME: "Super8",
        FSKeys.FRAMERATES: (18, 24),

        FSKeys.FILM_FRAME_SIZE: (7.976, 4.234),  # long frame. Small frame has a height of 4.227mm

        FSKeys.PERFORATION_SIZE: (0.914, 1.143),  # width/height of perforation
        FSKeys.PERFORATION_POS: [((0.51 + 0.914), (4.234 / 2)), ],  # inner edge, center to top of frame
        FSKeys.PERFORATIONS_PER_FRAME: 1,

        FSKeys.CAMERA_FRAME_SIZE: (5.69, 4.22),  # Camera aperture size. Found multiple values for the width.
        FSKeys.CAMERA_FRAME_POS: (1.47 - (0.51 + 0.914), - (4.22 / 2)),  # camera aperture position from Perforation Pos

        FSKeys.PROJECTOR_FRAME_SIZE: (5.46, 4.01),  # Projector aperture size
        FSKeys.PROJECTOR_FRAME_POS: (1.65 - (0.51 + 0.914), -(4.01 / 2)),

        FSKeys.PERFORATION_RADIUS: 0.13,  # corner radius
        FSKeys.FRAME_CORNER_RADIUS: 0.13,  # radius of aperture frame corners
    },

    # Regular 8mm
    # https://github.com/PM490/framebyframe/
    FilmSpecKey.NORMAL8: {
        FSKeys.NAME: "8mm Regular",
        FSKeys.FRAMERATES: (18, 24),

        FSKeys.FILM_FRAME_SIZE: (7.976, (7.62 / 2)),  # height half of 16mm film

        FSKeys.PERFORATION_SIZE: (1.829, 1.27),  # same as 16mm
        FSKeys.PERFORATION_POS: [(2.13, 0), ],  # 0.084"
        FSKeys.PERFORATIONS_PER_FRAME: 1,

        FSKeys.CAMERA_FRAME_SIZE: (4.88, 3.68),  # Camera aperture size. Found multiple values for the width.
        FSKeys.CAMERA_FRAME_POS: (1.47, (0.06 / 2)),  # camera aperture position from Perforation hole

        FSKeys.PROJECTOR_FRAME_SIZE: (4.88, 3.68),  # Projector aperture size unknown - use Camera aperture
        FSKeys.PROJECTOR_FRAME_POS: (1.47, (0.06 / 2)),

        FSKeys.PERFORATION_RADIUS: 0.13,  # corner radius
        FSKeys.FRAME_CORNER_RADIUS: 0.13,  # radius of aperture frame corners
    },

    # 16mm with single perforation
    # taken from https://en.wikipedia.org/wiki/16_mm_film
    # http://www.brianpritchard.com/16mm_windings.htm => http://www.brianpritchard.com/16mm%20Sound%201.jpg

    FilmSpecKey.STD16MM: {
        FSKeys.NAME: "16mm Standard",
        FSKeys.FRAMERATES: (24,),

        FSKeys.FILM_FRAME_SIZE: (15.95, 7.62),  # long frame. short frame would be 0.7605mm

        FSKeys.PERFORATION_SIZE: (1.829, 1.27),  # width/height of perforation
        FSKeys.PERFORATION_POS: [(2.13, 0), ],  # 0.084"
        FSKeys.PERFORATIONS_PER_FRAME: 1,

        FSKeys.CAMERA_FRAME_SIZE: (10.414, 7.47),  # Camera aperture size. Found multiple values for the width.
        FSKeys.CAMERA_FRAME_POS: (0.066, (7.62 / 2) - (7.49 / 2)),  # camera aperture position from left/top

        FSKeys.PROJECTOR_FRAME_SIZE: (9.65, 7.21),  # Projector aperture size
        FSKeys.PROJECTOR_FRAME_POS: (0.066 + ((10.414 - 9.65) / 2), (7.62 / 2) - (7.26 / 2)),

        FSKeys.FRAME_CORNER_RADIUS: 0.508,  # radius of aperture frame corners
        FSKeys.PERFORATION_RADIUS: 0.25,  # corner radius
    },

    # Super 16mm (single perforation/ wider aperature)
    # taken from https://en.wikipedia.org/wiki/16_mm_film

    FilmSpecKey.SUPER16: {
        FSKeys.NAME: "Super 16",
        FSKeys.FRAMERATES: (24,),

        FSKeys.FILM_FRAME_SIZE: (15.95, 7.62),  # long frame. short frame would be 0.7605mm

        FSKeys.PERFORATION_SIZE: (1.829, 1.270),  # width/height of perforation
        FSKeys.PERFORATION_POS: [(2.13, 0), ],  # 0.084"
        FSKeys.PERFORATIONS_PER_FRAME: 1,

        FSKeys.CAMERA_FRAME_SIZE: (12.52, 7.41),  # Camera aperture size.
        FSKeys.CAMERA_FRAME_POS: (0.066, (7.62 / 2) - (7.41 / 2)),  # camera aperture position from left/top

        FSKeys.PROJECTOR_FRAME_SIZE: (11.76, 7.08),  # Projector aperture size
        FSKeys.PROJECTOR_FRAME_POS: (0.066 + ((12.52 - 11.76) / 2), (7.62 / 2) - (7.08 / 2)),

        FSKeys.FRAME_CORNER_RADIUS: 0.508,  # radius of aperture frame corners
        FSKeys.PERFORATION_RADIUS: 0.25,  # corner radius
    }
}


class FilmSpecs:

    @classmethod
    def get_all_keys(cls) -> set[FilmSpecKey]:
        return set(film_specs.keys())

    @classmethod
    def get_api_film_formats(cls) -> list[FilmFormat]:
        result: list[FilmFormat] = []
        items = cls.get_all_keys()
        for key in items:
            specs = film_specs[key]
            ff = FilmFormat(key=key, name=specs[FSKeys.NAME], framerates=list(specs[FSKeys.FRAMERATES]))
            result.append(ff)
        return result

    @classmethod
    def get_film_format(cls, spec: FilmSpecKey) -> FilmFormat:
        specs = film_specs.get(spec)
        return FilmFormat(key=spec, name=specs[FSKeys.NAME], framerates=list(specs[FSKeys.FRAMERATES]))

    @classmethod
    def get_film_spec(cls, spec: FilmSpecKey) -> dict[FSKeys, any]:
        specs = film_specs[spec]
        return specs
