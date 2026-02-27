"""
Additional tests for helpers.py functions not covered by test_helpers.py
or test_helpers_extra.py:
  - human_readable_duration_from_seconds: edge cases (zero, boundary values)
  - machine_sortable_date: weeks, multi-component Nagios-style strings, None
"""
import unittest

from Nagstamon.helpers import (
    human_readable_duration_from_seconds,
    machine_sortable_date,
)


class TestHumanReadableDurationFromSecondsEdgeCases(unittest.TestCase):

    def test_zero_seconds(self):
        self.assertEqual(human_readable_duration_from_seconds(0), '0h 00m 00s')

    def test_exactly_one_minute(self):
        self.assertEqual(human_readable_duration_from_seconds(60), '0h 01m 00s')

    def test_exactly_one_hour(self):
        self.assertEqual(human_readable_duration_from_seconds(3600), '1h 00m 00s')

    def test_exactly_one_day(self):
        self.assertEqual(human_readable_duration_from_seconds(86400), '1d 0h 00m 00s')

    def test_mixed_days_hours_minutes_seconds(self):
        # 1d 1h 1m 1s = 86400 + 3600 + 60 + 1 = 90061
        self.assertEqual(human_readable_duration_from_seconds(90061), '1d 1h 01m 01s')

    def test_string_input_is_accepted(self):
        # The function calls int(seconds) so string digits should work too
        self.assertEqual(human_readable_duration_from_seconds('3661'), '1h 01m 01s')


class TestMachineSortableDateWeeks(unittest.TestCase):

    def test_one_week_equals_seven_days_in_seconds(self):
        self.assertEqual(machine_sortable_date('1w'), 604800)

    def test_two_weeks(self):
        self.assertEqual(machine_sortable_date('2w'), 1209600)

    def test_one_week_greater_than_six_days(self):
        self.assertGreater(machine_sortable_date('1w'), machine_sortable_date('6d'))

    def test_two_weeks_greater_than_one_week(self):
        self.assertGreater(machine_sortable_date('2w'), machine_sortable_date('1w'))


class TestMachineSortableDateMultiComponent(unittest.TestCase):

    def test_days_plus_hours_plus_minutes_plus_seconds(self):
        # 1d 2h 30m 15s = 86400 + 7200 + 1800 + 15 = 95415
        self.assertEqual(machine_sortable_date('1d 2h 30m 15s'), 95415)

    def test_hours_plus_minutes(self):
        # 2h 5m = 7200 + 300 = 7500
        self.assertEqual(machine_sortable_date('2h 5m'), 7500)

    def test_none_input_returns_zero(self):
        self.assertEqual(machine_sortable_date(None), 0)

    def test_weeks_plus_days(self):
        # 1w 1d = 604800 + 86400 = 691200
        self.assertEqual(machine_sortable_date('1w 1d'), 691200)

    def test_larger_total_sorts_later(self):
        # Nagios style: larger value = older duration, so sorts after smaller
        self.assertGreater(machine_sortable_date('1d'), machine_sortable_date('1h'))
        self.assertGreater(machine_sortable_date('1h'), machine_sortable_date('1m'))
        self.assertGreater(machine_sortable_date('1m'), machine_sortable_date('1s'))


if __name__ == '__main__':
    unittest.main()
