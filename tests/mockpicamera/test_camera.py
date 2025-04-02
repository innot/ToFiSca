import unittest

import mockpicamera


class TestMockCamera(unittest.TestCase):

    def test_defaults(self):
        picamera = mockpicamera.PiCamera()
        self.assertEqual('imx477', picamera.revision)
        self.assertTupleEqual((4056, 3040), picamera.resolution)
        modes = picamera.sensor_modes
        self.assertEqual(4, len(modes))

    def test_revision(self):
        picamera = mockpicamera.PiCamera()
        picamera.revision = 'imx219'
        self.assertEqual('imx219', picamera.revision)
        self.assertEqual((3280, 2464), picamera.resolution)
        modes = picamera.sensor_modes
        self.assertEqual(7, len(modes))

        picamera.revision = 'ov5647'
        self.assertEqual('ov5647', picamera.revision)
        self.assertEqual((2592, 1944), picamera.resolution)
        modes = picamera.sensor_modes
        self.assertEqual(7, len(modes))


if __name__ == '__main__':
    unittest.main()
