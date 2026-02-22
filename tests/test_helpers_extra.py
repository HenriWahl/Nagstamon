"""
Additional tests for Nagstamon/helpers.py covering functions not exercised
by the existing test_helpers.py:
  - not_empty
  - human_readable_duration_from_timestamp (all four output-format branches)
  - compare_host / compare_service / compare_status / compare_status_information
  - md5ify
  - STATES and STATES_SOUND constants
  - machine_sortable_date with Checkmk-style space-separated strings
"""
import re
import time
import unittest
from hashlib import md5

from Nagstamon.helpers import (
    STATES,
    STATES_SOUND,
    compare_host,
    compare_service,
    compare_status,
    compare_status_information,
    human_readable_duration_from_timestamp,
    machine_sortable_date,
    md5ify,
    not_empty,
)


class TestNotEmpty(unittest.TestCase):

    def test_spaces_only_is_empty(self):
        self.assertFalse(not_empty('   '))

    def test_nbsp_only_is_empty(self):
        self.assertFalse(not_empty('&nbsp;'))

    def test_mixed_nbsp_and_spaces_is_empty(self):
        self.assertFalse(not_empty('  &nbsp;  '))

    def test_real_text_is_not_empty(self):
        self.assertTrue(not_empty('hello'))

    def test_text_with_surrounding_spaces_is_not_empty(self):
        self.assertTrue(not_empty('  ok  '))


class TestHumanReadableDurationFromTimestamp(unittest.TestCase):

    def test_seconds_format(self):
        ts = time.time() - 10
        result = human_readable_duration_from_timestamp(ts)
        self.assertRegex(result, r'^\d{2}s$')

    def test_minutes_format(self):
        ts = time.time() - 120  # 2 minutes ago
        result = human_readable_duration_from_timestamp(ts)
        self.assertRegex(result, r'^\d{2}m \d{2}s$')

    def test_hours_format(self):
        ts = time.time() - 7322  # ~2h 2m 2s ago
        result = human_readable_duration_from_timestamp(ts)
        self.assertRegex(result, r'^\d+h \d{2}m \d{2}s$')

    def test_days_format(self):
        ts = time.time() - (86400 + 3661)  # 1d 1h 1m 1s ago
        result = human_readable_duration_from_timestamp(ts)
        self.assertRegex(result, r'^\d+d \d+h \d{2}m \d{2}s$')


class TestCompareHelpers(unittest.TestCase):

    def test_compare_host_lowercases(self):
        self.assertEqual(compare_host('MYHOST'), 'myhost')

    def test_compare_host_preserves_case_insensitive_sort(self):
        self.assertLess(compare_host('Alpha'), compare_host('beta'))

    def test_compare_service_lowercases(self):
        self.assertEqual(compare_service('CheckPing'), 'checkping')

    def test_compare_status_up_is_lowest(self):
        self.assertEqual(compare_status('UP'), 0)

    def test_compare_status_down_is_highest(self):
        self.assertEqual(compare_status('DOWN'), STATES.index('DOWN'))

    def test_compare_status_down_greater_than_warning(self):
        self.assertGreater(compare_status('DOWN'), compare_status('WARNING'))

    def test_compare_status_critical_greater_than_warning(self):
        self.assertGreater(compare_status('CRITICAL'), compare_status('WARNING'))

    def test_compare_status_information_lowercases(self):
        self.assertEqual(compare_status_information('DISK USAGE HIGH'), 'disk usage high')


class TestMd5ify(unittest.TestCase):

    def test_returns_32_char_hex(self):
        result = md5ify(b'admin')
        self.assertEqual(len(result), 32)
        self.assertRegex(result, r'^[0-9a-f]{32}$')

    def test_matches_hashlib_md5(self):
        payload = b'nagstamon'
        self.assertEqual(md5ify(payload), md5(payload).hexdigest())

    def test_different_inputs_produce_different_hashes(self):
        self.assertNotEqual(md5ify(b'admin'), md5ify(b'password'))


class TestStatesConstants(unittest.TestCase):

    def test_up_is_in_states(self):
        self.assertIn('UP', STATES)

    def test_down_is_in_states(self):
        self.assertIn('DOWN', STATES)

    def test_states_starts_with_up(self):
        self.assertEqual(STATES[0], 'UP')

    def test_states_ends_with_down(self):
        self.assertEqual(STATES[-1], 'DOWN')

    def test_warning_in_states(self):
        self.assertIn('WARNING', STATES)

    def test_critical_in_states(self):
        self.assertIn('CRITICAL', STATES)

    def test_states_sound_subset_of_states(self):
        for state in STATES_SOUND:
            self.assertIn(state, STATES)

    def test_states_sound_contains_warning(self):
        self.assertIn('WARNING', STATES_SOUND)

    def test_states_sound_contains_critical(self):
        self.assertIn('CRITICAL', STATES_SOUND)

    def test_states_sound_contains_down(self):
        self.assertIn('DOWN', STATES_SOUND)


class TestMachineSortableDateCheckmkStyle(unittest.TestCase):
    """
    Checkmk-style strings use a space between number and unit (e.g. '5 s', '3 m').
    The function returns negated epoch-based values so that more-recent durations
    produce SMALLER numbers — i.e. the sort order is: 5s < 3m < 1h < 1d.
    """

    def test_space_seconds_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('5 s'), int)

    def test_space_minutes_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('3 m'), int)

    def test_space_hours_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('2 h'), int)

    def test_space_days_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('1 d'), int)

    def test_more_recent_sorts_before_less_recent(self):
        # 5 seconds ago < 3 minutes ago < 2 hours ago < 1 day ago
        r_5s = machine_sortable_date('5 s')
        r_3m = machine_sortable_date('3 m')
        r_2h = machine_sortable_date('2 h')
        r_1d = machine_sortable_date('1 d')
        self.assertLess(r_5s, r_3m)
        self.assertLess(r_3m, r_2h)
        self.assertLess(r_2h, r_1d)

    def test_sec_suffix_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('10 sec'), int)

    def test_min_suffix_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('5 min'), int)

    def test_hrs_suffix_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('1 hrs'), int)

    def test_days_suffix_returns_integer(self):
        self.assertIsInstance(machine_sortable_date('2 days'), int)

    def test_nagios_style_ordering_consistent(self):
        # Nagios-style (no spaces): larger number = older
        n_5s = machine_sortable_date('5s')
        n_3m = machine_sortable_date('3m')
        n_1d = machine_sortable_date('1d')
        self.assertLess(n_5s, n_3m)
        self.assertLess(n_3m, n_1d)


if __name__ == '__main__':
    unittest.main()
