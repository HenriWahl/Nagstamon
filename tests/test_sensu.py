import datetime
import unittest

from Nagstamon.servers.Sensu import SensuServer


class TestAsLocaltimeStr(unittest.TestCase):

    def test_formats_correctly(self):
        dt = datetime.datetime(2023, 6, 15, 12, 30, 45)
        result = SensuServer._aslocaltimestr(dt)
        self.assertEqual(result, '2023-06-15 12:30:45')

    def test_formats_midnight(self):
        dt = datetime.datetime(2000, 1, 1, 0, 0, 0)
        result = SensuServer._aslocaltimestr(dt)
        self.assertEqual(result, '2000-01-01 00:00:00')


class TestFormatClientSubscription(unittest.TestCase):

    def test_prepends_client_prefix(self):
        self.assertEqual(SensuServer._format_client_subscription('myhost'), 'client:myhost')

    def test_preserves_hostname(self):
        self.assertEqual(SensuServer._format_client_subscription('web-01.example.com'),
                         'client:web-01.example.com')


class TestGetEventDurationString(unittest.TestCase):

    def setUp(self):
        self.server = SensuServer.__new__(SensuServer)

    def test_same_timestamps_returns_none(self):
        self.assertIsNone(self.server._get_event_duration_string(100, 100))

    def test_five_seconds(self):
        self.assertEqual(self.server._get_event_duration_string(100, 105), '0d 0h 0m 5s')

    def test_one_minute(self):
        self.assertEqual(self.server._get_event_duration_string(0, 60), '0d 0h 1m 0s')

    def test_one_hour(self):
        self.assertEqual(self.server._get_event_duration_string(0, 3600), '0d 1h 0m 0s')

    def test_complex_duration(self):
        self.assertEqual(self.server._get_event_duration_string(0, 3661), '0d 1h 1m 1s')

    def test_one_day(self):
        self.assertEqual(self.server._get_event_duration_string(0, 86400), '1d 0h 0m 0s')


if __name__ == '__main__':
    unittest.main()
