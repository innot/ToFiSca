from enum import Enum


class Parameter(Enum):

    # Camera image size
    CAMERA_IMAGE_SIZE = "camera.image.size"

    # ROI Manager
    ROI_RECT = "roi.rect"
    ROI_REFERENCEPOINT = "roi.referencepoint"
    ROI_PERFORATION_LINE = "roi.perforation.line"
    ROI_PERFORATION_TOP = "roi.perforation.top"
    ROI_PERFORATION_BOTTOM = "roi.perforation.bottom"
    ROI_PERFORATIONSIZE = "roi.perforationsize"

