
import configparser
import unittest

from tofisca import HardwareManager, CamType


class MyTestCase(unittest.TestCase):
    def test_cameratype(self):
        hm = HardwareManager()
        self.assertIsNotNone(hm.camera_type)  # there is a default
        for entry in CamType:
            hm.camera_type = entry.name
            self.assertEqual(entry.name, hm.camera_type)

        # test invalid cam type
        with self.assertRaises(ValueError):
            hm.camera_type = 'foobar'

    def test_load_save(self):
        hm = HardwareManager()
        cp = configparser.ConfigParser()
        cp['test'] = {}
        config = cp['test']
        hm.save(config)
        self.assertEqual(hm.camera_type, config['cameratype'])

        # change parameter and check if load restores the old value
        hm.camera_type = 'V1'
        hm.retrieve(config)
        self.assertEqual('HQ', hm.camera_type)


if __name__ == '__main__':
    unittest.main()
