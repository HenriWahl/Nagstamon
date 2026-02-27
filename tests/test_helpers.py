import unittest

from Nagstamon.helpers import (
    human_readable_duration_from_seconds,
    is_found_by_re,
    machine_sortable_date,
)


class TestIsFoundByRe(unittest.TestCase):
    # The function uses str(reverse) == "True" internally, so it accepts both
    # string values (the typical case coming from config files) and booleans.

    def test_found_not_reversed_string(self):
        self.assertTrue(is_found_by_re('hello world', 'hello', 'False'))

    def test_found_reversed_string(self):
        self.assertFalse(is_found_by_re('hello world', 'hello', 'True'))

    def test_not_found_not_reversed_string(self):
        self.assertFalse(is_found_by_re('hello world', 'xyz', 'False'))

    def test_not_found_reversed_string(self):
        self.assertTrue(is_found_by_re('hello world', 'xyz', 'True'))

    def test_found_not_reversed_bool(self):
        self.assertTrue(is_found_by_re('hello world', 'hello', False))

    def test_found_reversed_bool(self):
        self.assertFalse(is_found_by_re('hello world', 'hello', True))

    def test_not_found_not_reversed_bool(self):
        self.assertFalse(is_found_by_re('hello world', 'xyz', False))

    def test_not_found_reversed_bool(self):
        self.assertTrue(is_found_by_re('hello world', 'xyz', True))

    def test_regex_pattern_matches(self):
        self.assertTrue(is_found_by_re('host-prod-01', r'host-\w+-\d+', False))

    def test_regex_pattern_no_match(self):
        self.assertFalse(is_found_by_re('host-prod-01', r'host-\d+', False))


class TestHumanReadableDurationFromSeconds(unittest.TestCase):

    def test_seconds_only(self):
        self.assertEqual(human_readable_duration_from_seconds(30), '0h 00m 30s')

    def test_minutes_and_seconds(self):
        self.assertEqual(human_readable_duration_from_seconds(90), '0h 01m 30s')

    def test_hours_minutes_seconds(self):
        self.assertEqual(human_readable_duration_from_seconds(3661), '1h 01m 01s')

    def test_days(self):
        self.assertEqual(human_readable_duration_from_seconds(90061), '1d 1h 01m 01s')

    def test_exactly_one_hour(self):
        self.assertEqual(human_readable_duration_from_seconds(3600), '1h 00m 00s')

    def test_string_input(self):
        # function accepts string input via int() conversion
        self.assertEqual(human_readable_duration_from_seconds('30'), '0h 00m 30s')


class TestMachineSortableDate(unittest.TestCase):

    def test_seconds_only(self):
        self.assertEqual(machine_sortable_date('30s'), 30)

    def test_minutes_and_seconds(self):
        self.assertEqual(machine_sortable_date('5m 30s'), 330)

    def test_hours_minutes_seconds(self):
        self.assertEqual(machine_sortable_date('1h 30m 15s'), 3600 + 1800 + 15)

    def test_days_hours_minutes_seconds(self):
        self.assertEqual(machine_sortable_date('2d 3h 15m 30s'),
                         2 * 86400 + 3 * 3600 + 15 * 60 + 30)

    def test_weeks(self):
        self.assertEqual(machine_sortable_date('1w'), 604800)

    def test_none_input_treated_as_zero(self):
        self.assertEqual(machine_sortable_date(None), 0)

    def test_zero_seconds(self):
        self.assertEqual(machine_sortable_date('0s'), 0)


if __name__ == '__main__':
    unittest.main()
