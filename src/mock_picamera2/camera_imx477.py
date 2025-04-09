from libcamera import ColorSpace, PixelFormat, Size, SizeRange
from mock_picamera2.camera import Camera, CameraConfiguration
from mock_picamera2.stream import StreamRole, StreamFormats, StreamConfiguration

class CameraImx477(Camera):
    from libcamera import ControlId, ControlType, ControlInfo, Rectangle

    Controls = {
        ControlId(1, "libcamera", "AeEnable", ControlType.Bool): ControlInfo(values=[True, False]),
        ControlId(3, "libcamera", "AeMeteringMode", ControlType.Integer32): ControlInfo(min=0, max=3),
        ControlId(4, "libcamera", "AeConstraintMode", ControlType.Integer32): ControlInfo(min=0, max=3),
        ControlId(5, "libcamera", "AeExposureMode", ControlType.Integer32): ControlInfo(min=0, max=3),
        ControlId(6, "libcamera", "ExposureValue", ControlType.Float): ControlInfo(min=-8.0, max=8.0),
        ControlId(7, "libcamera", "ExposureTime", ControlType.Integer32): ControlInfo(min=1, max=66666),
        ControlId(8, "libcamera", "AnalogueGain", ControlType.Float): ControlInfo(min=1.0, max=16.0),
        ControlId(9, "libcamera", "AeFlickerMode", ControlType.Integer32): ControlInfo(min=0, max=1),
        ControlId(10, "libcamera", "AeFlickerPeriod", ControlType.Integer32): ControlInfo(min=100, max=1000000),
        ControlId(12, "libcamera", "Brightness", ControlType.Float): ControlInfo(min=-1.0, max=1.0),
        ControlId(13, "libcamera", "Contrast", ControlType.Float): ControlInfo(min=0.0, max=32.0),
        ControlId(15, "libcamera", "AwbEnable", ControlType.Bool): ControlInfo(values=[True, False]),
        ControlId(16, "libcamera", "AwbMode", ControlType.Integer32): ControlInfo(min=0, max=7),
        ControlId(18, "libcamera", "ColourGains", ControlType.Float, True, 2): ControlInfo(min=0.0, max=32.0),
        ControlId(19, "libcamera", "ColourTemperature", ControlType.Integer32): ControlInfo(min=100, max=100000),
        ControlId(20, "libcamera", "Saturation", ControlType.Float): ControlInfo(min=0.0, max=32.0),
        ControlId(22, "libcamera", "Sharpness", ControlType.Float): ControlInfo(min=0.0, max=16.0),
        ControlId(25, "libcamera", "ScalerCrop", ControlType.Rectangle): ControlInfo(
            min=Rectangle(0, 0, 0, 0), max=Rectangle(65535, 65535, 65535, 65535)),
        ControlId(28, "libcamera", "FrameDurationLimits", ControlType.Integer32, True, 2): ControlInfo(min=33333,
                                                                                                       max=120000),
        ControlId(41, "libcamera", "HdrMode", ControlType.Integer32): ControlInfo(values=[0, 1, 2, 3, 4]),
        ControlId(10002, "draft", "NoiseReductionMode", ControlType.Integer32): ControlInfo(min=0, max=4),
        ControlId(20001, "rpi", "StatsOutputEnable", ControlType.Bool): ControlInfo(values=[True, False]),
        ControlId(20003, "rpi", "ScalerCrops", ControlType.Rectangle, True): ControlInfo(
            min=Rectangle(0, 0, 0, 0), max=Rectangle(65535, 65535, 65535, 65535)),
        ControlId(20007, "rpi", "CnnEnableInputTensor", ControlType.Bool): ControlInfo(values=[True, False]),
        ControlId(20011, "rpi", "SyncMode", ControlType.Integer32): ControlInfo(min=0, max=2),
        ControlId(20014, "rpi", "SyncFrames", ControlType.Integer32): ControlInfo(min=1, max=1000000)
    }

    pixel_format_names = {
        'R8', 'R16', 'MONO_PISP_COMP1', 'SGRBG10', 'SGBRG10', 'SBGGR10', 'SRGGB10',
        'NV21', 'SBGGR8', 'SGRBG12', 'SGBRG12', 'SBGGR12', 'SRGGB12', 'YUV420', 'NV12', 'YVU420', 'SBGGR16',
        'BGGR_PISP_COMP1', 'SGRBG14', 'SGBRG14', 'SBGGR14', 'SRGGB14', 'XBGR8888', 'BGR888', 'RGB888', 'XRGB8888',
        'YUV444', 'YVU444', 'SGBRG16', 'GBRG_PISP_COMP1', 'SGRBG16', 'GRBG_PISP_COMP1', 'YUV422', 'YVU422', 'SRGGB16',
        'RGGB_PISP_COMP1', 'BGR161616', 'RGB161616', 'SRGGB8', 'SGRBG8', 'SGBRG8', 'YVYU', 'YUYV', 'VYUY', 'UYVY',
    }

    def _get_formats(self, role: StreamRole) -> StreamFormats:

        if role == StreamRole.Raw:
            return StreamFormats({
                PixelFormat(name="SRGGB10_CSI2P"): [
                    SizeRange(size=Size(1332, 990))
                ],
                PixelFormat(name="SRGGB12_CSI2P"): [
                    SizeRange(size=Size(2028, 1080)),
                    SizeRange(size=Size(1332, 1520)),
                    SizeRange(size=Size(4056, 3040)),
                ],
            })

        entries: dict[PixelFormat, list[SizeRange]] = {}
        for format_name in self.pixel_format_names:
            pf = PixelFormat(name=format_name)
            sr = SizeRange(min_size=Size(32, 32), max_size=Size(4056, 3040), hstep=2, vstep=2)
            entries[pf] = [sr]
        return StreamFormats(entries)

    @property
    def id(self) -> str:
        return "/mock/camera/imx477"

    @property
    def controls(self) -> dict[ControlId, ControlInfo]:
        return self.controls

    def generate_configuration(self, roles: list[StreamRole]) -> CameraConfiguration:
        config = CameraConfiguration()
        for role in roles:
            sc = StreamConfiguration()
            if role == StreamRole.Raw:
                sc.buffer_count = 2
                sc.color_space = ColorSpace.Raw()
                sc.formats = None  # todo
                sc.pixel_format = PixelFormat(name='SRGGB12_CSI2P')
                sc.size = Size(4056, 3040)
            if role == StreamRole.StillCapture:
                sc.buffer_count = 1
                sc.color_space = ColorSpace.Sycc()
                sc.formats = None  # todo
                sc.pixel_format = PixelFormat(name='YUV420')
                sc.size = Size(4056, 3040)
            if role == StreamRole.VideoRecording:
                sc.buffer_count = 4
                sc.color_space = ColorSpace.Rec709()
                sc.formats = None  # todo
                sc.pixel_format = PixelFormat(name='YUV420')
                sc.size = Size(1920, 1080)
            if role == StreamRole.VideoRecording:
                sc.buffer_count = 4
                sc.color_space = ColorSpace.Sycc()
                sc.formats = None  # todo
                sc.pixel_format = PixelFormat(name='XRGB8888')
                sc.size = Size(800, 600)

            sc.formats = self._get_formats(role)
            config.add_configuration(sc)

        return config
