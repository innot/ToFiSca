import unittest

from picamera2 import Picamera2


class MyTestCase(unittest.TestCase):
    def test_something(self):
        picam2 = Picamera2()
        camera_config = picam2.create_still_configuration()
        picam2.configure(camera_config)
        picam2.start()


        self.assertEqual(False, False)  # add assertion here


if __name__ == '__main__':
    unittest.main()
