import unittest

import vrctracker

import os
import sys

class VRCTrackerTests(unittest.TestCase):

    def test_get_user_data_dir(self):
        self.assertTrue(os.path.isdir(vrctracker.VRCTrackerApp.get_user_data_dir()))

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_get_vrchat_data_dir_windows(self):
        result = vrctracker.VRCTrackerApp.get_user_data_dir()
        self.assertEqual(result, os.path.abspath(os.path.expandvars("%LOCALAPPDATA%\\..\\LocalLow\\VRChat\\VRChat")))

    def test_init(self):
        app = vrctracker.VRCTrackerApp()

if __name__ == '__main__':
    unittest.main()
