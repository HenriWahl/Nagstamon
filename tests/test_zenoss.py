import unittest

from Nagstamon.servers.Zenoss import ZenossServer


class TestCalcDuration(unittest.TestCase):

    def setUp(self):
        self.server = ZenossServer.__new__(ZenossServer)

    def test_same_timestamps_returns_none(self):
        self.assertIsNone(self.server._calc_duration('2023-01-15 12:00:00',
                                                     '2023-01-15 12:00:00'))

    def test_five_seconds(self):
        self.assertEqual(self.server._calc_duration('2023-01-15 12:00:00',
                                                    '2023-01-15 12:00:05'),
                         '0d 0h 0m 5s')

    def test_one_minute_thirty_seconds(self):
        self.assertEqual(self.server._calc_duration('2023-01-15 12:00:00',
                                                    '2023-01-15 12:01:30'),
                         '0d 0h 1m 30s')

    def test_one_hour(self):
        self.assertEqual(self.server._calc_duration('2023-01-15 12:00:00',
                                                    '2023-01-15 13:00:00'),
                         '0d 1h 0m 0s')

    def test_one_day_one_hour_thirty_minutes(self):
        self.assertEqual(self.server._calc_duration('2023-01-15 00:00:00',
                                                    '2023-01-16 01:30:00'),
                         '1d 1h 30m 0s')


if __name__ == '__main__':
    unittest.main()
