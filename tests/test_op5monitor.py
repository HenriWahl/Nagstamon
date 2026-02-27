import time
import unittest

from Nagstamon.servers.op5Monitor import human_duration


class TestHumanDuration(unittest.TestCase):

    def test_future_timestamp_returns_na(self):
        self.assertEqual(human_duration(time.time() + 100), 'n/a')

    def test_seconds(self):
        result = human_duration(time.time() - 5)
        self.assertRegex(result, r'^\d+s$')

    def test_minutes(self):
        result = human_duration(time.time() - 60)
        self.assertRegex(result, r'^\d+m$')

    def test_hours(self):
        result = human_duration(time.time() - 3600)
        self.assertRegex(result, r'^\d+h$')

    def test_days(self):
        result = human_duration(time.time() - 86400)
        self.assertRegex(result, r'^\d+d$')

    def test_weeks(self):
        result = human_duration(time.time() - 86400 * 7)
        self.assertRegex(result, r'^\d+w$')

    def test_mixed_units(self):
        # 1 day + 2 hours + 30 minutes + 15 seconds ago
        start = time.time() - (86400 + 7200 + 1800 + 15)
        result = human_duration(start)
        self.assertRegex(result, r'^\d+d \d+h \d+m \d+s$')


if __name__ == '__main__':
    unittest.main()
