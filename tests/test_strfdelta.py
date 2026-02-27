"""
strfdelta() is a module-level utility function defined identically in five server
modules: IcingaDBWeb, IcingaDBWebNotifications, IcingaWeb2, Monitos4x, SnagView3.
This test suite imports from each module and verifies correctness once.
"""
import datetime
import unittest

import Nagstamon.servers.IcingaDBWeb as IcingaDBWeb
import Nagstamon.servers.IcingaDBWebNotifications as IcingaDBWebNotifications
import Nagstamon.servers.IcingaWeb2 as IcingaWeb2
import Nagstamon.servers.Monitos4x as Monitos4x
import Nagstamon.servers.SnagView3 as SnagView3

_MODULES = [IcingaDBWeb, IcingaDBWebNotifications, IcingaWeb2, Monitos4x, SnagView3]
_FMT = '{days}d {hours}h {minutes}m {seconds}s'


def _all_strfdelta_results(tdelta):
    return [mod.strfdelta(tdelta, _FMT) for mod in _MODULES]


class TestStrfdelta(unittest.TestCase):

    def test_zero_timedelta(self):
        td = datetime.timedelta(0)
        for result in _all_strfdelta_results(td):
            self.assertEqual(result, '0d 0h 0m 0s')

    def test_seconds_only(self):
        td = datetime.timedelta(seconds=30)
        for result in _all_strfdelta_results(td):
            self.assertEqual(result, '0d 0h 0m 30s')

    def test_minutes_and_seconds(self):
        td = datetime.timedelta(seconds=90)
        for result in _all_strfdelta_results(td):
            self.assertEqual(result, '0d 0h 1m 30s')

    def test_hours_minutes_seconds(self):
        td = datetime.timedelta(hours=1, minutes=5, seconds=10)
        for result in _all_strfdelta_results(td):
            self.assertEqual(result, '0d 1h 5m 10s')

    def test_days(self):
        td = datetime.timedelta(days=2, hours=3, minutes=15, seconds=45)
        for result in _all_strfdelta_results(td):
            self.assertEqual(result, '2d 3h 15m 45s')

    def test_format_string_with_padding(self):
        td = datetime.timedelta(hours=2, minutes=5, seconds=9)
        fmt = '{days}d {hours}h {minutes:02d}m {seconds:02d}s'
        for mod in _MODULES:
            result = mod.strfdelta(td, fmt)
            self.assertEqual(result, '0d 2h 05m 09s')


if __name__ == '__main__':
    unittest.main()
