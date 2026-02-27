"""
Tests for Nagstamon/config.py AppInfo constants.
"""
import unittest

from Nagstamon.config import AppInfo


class TestAppInfo(unittest.TestCase):

    def test_name_is_string(self):
        self.assertIsInstance(AppInfo.NAME, str)

    def test_name_is_not_empty(self):
        self.assertTrue(AppInfo.NAME)

    def test_name_is_nagstamon(self):
        self.assertEqual(AppInfo.NAME, 'Nagstamon')

    def test_version_is_string(self):
        self.assertIsInstance(AppInfo.VERSION, str)

    def test_version_is_not_empty(self):
        self.assertTrue(AppInfo.VERSION)

    def test_version_starts_with_digit(self):
        self.assertTrue(AppInfo.VERSION[0].isdigit(),
                        f'Expected version to start with digit, got: {AppInfo.VERSION!r}')


if __name__ == '__main__':
    unittest.main()
