from libcamera import ControlId, ControlType, ControlInfo, HdrModeEnum, Rectangle


class Imx477:

    name = "imx477"



    CameraModes = [
        {'bit_depth': 10,
         'crop_limits': (696, 528, 2664, 1980),
         'exposure_limits': (31, 66512892),
         'format': "SRGGB10_CSI2P",
         'fps': 120.05,
         'size': (1332, 990),
         'unpacked': 'SRGGB10'},
        {'bit_depth': 12,
         'crop_limits': (0, 440, 4056, 2160),
         'exposure_limits': (60, 127156999),
         'format': "SRGGB12_CSI2P",
         'fps': 50.03,
         'size': (2028, 1080),
         'unpacked': 'SRGGB12'},
        {'bit_depth': 12,
         'crop_limits': (0, 0, 4056, 3040),
         'exposure_limits': (60, 127156999),
         'format': "SRGGB12_CSI2P",
         'fps': 40.01,
         'size': (2028, 1520),
         'unpacked': 'SRGGB12'},
        {'bit_depth': 12,
         'crop_limits': (0, 0, 4056, 3040),
         'exposure_limits': (114, 239542228),
         'format': "SRGGB12_CSI2P",
         'fps': 10.0,
         'size': (4056, 3040),
         'unpacked': 'SRGGB12'}
    ]

    NativeModes = {
        'bit_depth': 12,
        'format': "SRGGB12_CSI2P",
        'size': (4056, 3040)
    }

