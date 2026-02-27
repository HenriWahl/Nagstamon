import re
import unittest
from datetime import datetime, timezone

from Nagstamon.servers.Prometheus import PrometheusServer


class TestGetDuration(unittest.TestCase):

    def setUp(self):
        self.server = PrometheusServer.__new__(PrometheusServer)

    def test_old_timestamp_returns_days_format(self):
        result = self.server._get_duration('1970-01-01T00:00:00.000Z')
        self.assertRegex(result, r'^\d+d \d+h \d{2}m \d{2}s$')

    def test_recent_timestamp_returns_seconds_format(self):
        recent = datetime.now(timezone.utc).isoformat()
        result = self.server._get_duration(recent)
        self.assertRegex(result, r'^\d{2}s$')

    def test_one_hour_ago_returns_hour_format(self):
        from datetime import timedelta
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        result = self.server._get_duration(one_hour_ago)
        self.assertRegex(result, r'^\d+h \d{2}m \d{2}s$')

    def test_one_minute_ago_returns_minute_format(self):
        from datetime import timedelta
        one_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        result = self.server._get_duration(one_min_ago)
        self.assertRegex(result, r'^\d{2}m \d{2}s$')


if __name__ == '__main__':
    unittest.main()
