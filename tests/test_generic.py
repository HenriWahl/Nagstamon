"""
Tests for GenericServer and its NagiosServer subclass.

NagiosServer adds no logic of its own – all behaviour comes from GenericServer.
The tests here cover every pure, network-free method that is practical to test
without a running monitor:
  - get_name / get_username / get_password
  - check_for_error  (static method)
  - get_worst_status_current
  - get_events_history_count
"""
import unittest

from Nagstamon.servers.Generic import GenericServer
from Nagstamon.servers.Nagios import NagiosServer


def _make_server(**counters):
    """Return a bare NagiosServer instance with all status counters initialised."""
    s = NagiosServer.__new__(NagiosServer)
    s.worst_status_current = 'UP'
    for attr in ('down', 'unreachable', 'disaster', 'critical',
                 'high', 'average', 'warning', 'information', 'unknown'):
        setattr(s, attr, counters.get(attr, 0))
    return s


class TestGetAccessors(unittest.TestCase):

    def setUp(self):
        self.server = NagiosServer.__new__(NagiosServer)
        self.server.name = 'my-server'
        self.server.username = 'admin'
        self.server.password = 'secret'

    def test_get_name_returns_string(self):
        self.assertEqual(self.server.get_name(), 'my-server')

    def test_get_name_stringifies_non_string(self):
        self.server.name = 42
        self.assertEqual(self.server.get_name(), '42')

    def test_get_username_returns_string(self):
        self.assertEqual(self.server.get_username(), 'admin')

    def test_get_password_returns_string(self):
        self.assertEqual(self.server.get_password(), 'secret')


class TestCheckForError(unittest.TestCase):
    """check_for_error is a static method on GenericServer."""

    def test_no_error_returns_none(self):
        self.assertIsNone(GenericServer.check_for_error('OK', '', 200))

    def test_status_400_returns_none(self):
        # boundary: >400 triggers error, 400 itself does not
        self.assertIsNone(GenericServer.check_for_error('result', '', 400))

    def test_status_401_returns_result(self):
        r = GenericServer.check_for_error('body', '', 401)
        self.assertIsNotNone(r)
        self.assertEqual(r.status_code, 401)

    def test_status_500_returns_result(self):
        r = GenericServer.check_for_error('body', '', 500)
        self.assertIsNotNone(r)

    def test_non_empty_error_string_returns_result(self):
        r = GenericServer.check_for_error('body', 'timeout', 200)
        self.assertIsNotNone(r)
        self.assertEqual(r.error, 'timeout')

    def test_result_attributes_are_preserved(self):
        r = GenericServer.check_for_error('err_body', 'some error', 503)
        self.assertEqual(r.result, 'err_body')
        self.assertEqual(r.error, 'some error')
        self.assertEqual(r.status_code, 503)


class TestGetWorstStatusCurrent(unittest.TestCase):

    def test_all_zero_returns_up(self):
        self.assertEqual(_make_server().get_worst_status_current(), 'UP')

    def test_information_only(self):
        self.assertEqual(_make_server(information=1).get_worst_status_current(), 'INFORMATION')

    def test_unknown_only(self):
        self.assertEqual(_make_server(unknown=1).get_worst_status_current(), 'UNKNOWN')

    def test_information_beats_unknown(self):
        # information is checked before unknown in the elif chain
        self.assertEqual(_make_server(information=1, unknown=1).get_worst_status_current(), 'INFORMATION')

    def test_warning_beats_information(self):
        self.assertEqual(_make_server(information=1, warning=1).get_worst_status_current(), 'WARNING')

    def test_average_beats_warning(self):
        self.assertEqual(_make_server(warning=1, average=1).get_worst_status_current(), 'AVERAGE')

    def test_high_beats_average(self):
        self.assertEqual(_make_server(average=1, high=1).get_worst_status_current(), 'HIGH')

    def test_critical_beats_high(self):
        self.assertEqual(_make_server(high=1, critical=1).get_worst_status_current(), 'CRITICAL')

    def test_disaster_beats_critical(self):
        self.assertEqual(_make_server(critical=1, disaster=1).get_worst_status_current(), 'DISASTER')

    def test_unreachable_beats_disaster(self):
        self.assertEqual(_make_server(disaster=1, unreachable=1).get_worst_status_current(), 'UNREACHABLE')

    def test_down_beats_everything(self):
        s = _make_server(down=1, unreachable=1, disaster=1, critical=1,
                         high=1, average=1, warning=1, information=1, unknown=1)
        self.assertEqual(s.get_worst_status_current(), 'DOWN')


class TestGetEventsHistoryCount(unittest.TestCase):

    def setUp(self):
        self.server = NagiosServer.__new__(NagiosServer)

    def test_empty_history_returns_zero(self):
        self.server.events_history = {}
        self.assertEqual(self.server.get_events_history_count(), 0)

    def test_counts_only_true_entries(self):
        self.server.events_history = {'evt1': True, 'evt2': False, 'evt3': True}
        self.assertEqual(self.server.get_events_history_count(), 2)

    def test_all_seen_returns_zero(self):
        self.server.events_history = {'a': False, 'b': False}
        self.assertEqual(self.server.get_events_history_count(), 0)

    def test_all_unseen_returns_count(self):
        self.server.events_history = {'x': True, 'y': True, 'z': True}
        self.assertEqual(self.server.get_events_history_count(), 3)


if __name__ == '__main__':
    unittest.main()
