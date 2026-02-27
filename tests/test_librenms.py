import datetime
import unittest

from Nagstamon.servers.LibreNMS import LibreNMSServer


class TestCalculateDuration(unittest.TestCase):

    def setUp(self):
        self.server = LibreNMSServer.__new__(LibreNMSServer)

    def test_empty_string_returns_na(self):
        self.assertEqual(self.server._calculate_duration(''), 'n/a')

    def test_none_returns_na(self):
        self.assertEqual(self.server._calculate_duration(None), 'n/a')

    def test_invalid_format_returns_na(self):
        self.assertEqual(self.server._calculate_duration('not-a-date'), 'n/a')

    def test_old_timestamp_returns_days_format(self):
        result = self.server._calculate_duration('2020-01-01 00:00:00')
        self.assertRegex(result, r'^\d+d \d+h \d{2}m$')

    def test_hours_format(self):
        one_hr_ago = (datetime.datetime.now() - datetime.timedelta(hours=1, minutes=5)
                      ).strftime('%Y-%m-%d %H:%M:%S')
        result = self.server._calculate_duration(one_hr_ago)
        self.assertRegex(result, r'^\d+h \d{2}m \d{2}s$')

    def test_minutes_format(self):
        two_min_ago = (datetime.datetime.now() - datetime.timedelta(minutes=2, seconds=10)
                       ).strftime('%Y-%m-%d %H:%M:%S')
        result = self.server._calculate_duration(two_min_ago)
        self.assertRegex(result, r'^\d+m \d{2}s$')

    def test_seconds_format(self):
        thirty_sec_ago = (datetime.datetime.now() - datetime.timedelta(seconds=30)
                          ).strftime('%Y-%m-%d %H:%M:%S')
        result = self.server._calculate_duration(thirty_sec_ago)
        self.assertRegex(result, r'^\d+s$')


if __name__ == '__main__':
    unittest.main()
