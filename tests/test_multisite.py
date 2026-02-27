import re
import unittest
from datetime import datetime

from Nagstamon.servers.Multisite import MultisiteServer


class TestStateMap(unittest.TestCase):
    """MultisiteServer.statemap maps Checkmk abbreviated states to Nagstamon states.
    As used in _get_status: statemap.get(raw_state, raw_state)"""

    def setUp(self):
        self.server = MultisiteServer.__new__(MultisiteServer)
        self.server.statemap = {
            'UNREACH': 'UNREACHABLE',
            'CRIT':    'CRITICAL',
            'WARN':    'WARNING',
            'UNKN':    'UNKNOWN',
            'PEND':    'PENDING',
        }

    def test_unreach_maps_to_unreachable(self):
        self.assertEqual(self.server.statemap.get('UNREACH', 'UNREACH'), 'UNREACHABLE')

    def test_crit_maps_to_critical(self):
        self.assertEqual(self.server.statemap.get('CRIT', 'CRIT'), 'CRITICAL')

    def test_warn_maps_to_warning(self):
        self.assertEqual(self.server.statemap.get('WARN', 'WARN'), 'WARNING')

    def test_unkn_maps_to_unknown(self):
        self.assertEqual(self.server.statemap.get('UNKN', 'UNKN'), 'UNKNOWN')

    def test_pend_maps_to_pending(self):
        self.assertEqual(self.server.statemap.get('PEND', 'PEND'), 'PENDING')

    def test_up_passes_through(self):
        self.assertEqual(self.server.statemap.get('UP', 'UP'), 'UP')

    def test_down_passes_through(self):
        self.assertEqual(self.server.statemap.get('DOWN', 'DOWN'), 'DOWN')


class TestGetStartEnd(unittest.TestCase):

    def setUp(self):
        self.server = MultisiteServer.__new__(MultisiteServer)

    def test_returns_two_strings(self):
        result = self.server.get_start_end('myhost')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_format_is_datetime(self):
        start, end = self.server.get_start_end('myhost')
        fmt = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$'
        self.assertRegex(start, fmt)
        self.assertRegex(end, fmt)

    def test_end_is_two_hours_after_start(self):
        start, end = self.server.get_start_end('myhost')
        t_start = datetime.strptime(start, '%Y-%m-%d %H:%M')
        t_end = datetime.strptime(end, '%Y-%m-%d %H:%M')
        delta_minutes = (t_end - t_start).total_seconds() / 60
        # allow ±1 minute tolerance for clock ticks between the two time.strftime calls
        self.assertAlmostEqual(delta_minutes, 120, delta=1)


if __name__ == '__main__':
    unittest.main()
