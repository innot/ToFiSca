from enum import Enum


class controls:
    class libcamera:
        pass

    class draft:
        class NoiseReductionModeEnum(Enum):
            Off = 0
            Fast = 1
            HighQuality = 2
            Minimal = 3
            ZSL = 4

    class debug:
        pass

    class rpi:
        pass

    def __init__(self, *args, **kwargs):  # real signature unknown
        pass
