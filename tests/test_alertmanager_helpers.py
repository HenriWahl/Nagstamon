import re
import unittest

from Nagstamon.servers.Alertmanager import AlertmanagerServer
from Nagstamon.servers.Alertmanager.helpers import (
    convert_timestring_to_utc,
    detect_from_labels,
    get_duration,
)


class TestDetectFromLabels(unittest.TestCase):

    def test_single_label_match(self):
        labels = {'alertname': 'Error', 'severity': 'critical'}
        self.assertEqual(detect_from_labels(labels, 'alertname'), 'Error')

    def test_first_label_in_list_wins(self):
        labels = {'instance': '127.0.0.1', 'alertname': 'Error'}
        self.assertEqual(detect_from_labels(labels, 'instance,alertname'), '127.0.0.1')

    def test_second_label_in_list_matches_when_first_absent(self):
        labels = {'alertname': 'Error'}
        self.assertEqual(detect_from_labels(labels, 'instance,alertname'), 'Error')

    def test_no_match_returns_empty_default(self):
        labels = {'alertname': 'Error'}
        self.assertEqual(detect_from_labels(labels, 'missing'), '')

    def test_no_match_returns_custom_default(self):
        labels = {'alertname': 'Error'}
        self.assertEqual(detect_from_labels(labels, 'missing', 'unknown'), 'unknown')

    def test_custom_delimiter(self):
        labels = {'foo': 'bar', 'baz': 'qux'}
        self.assertEqual(detect_from_labels(labels, 'foo|baz', list_delimiter='|'), 'bar')

    def test_empty_config_returns_default(self):
        labels = {'alertname': 'Error'}
        self.assertEqual(detect_from_labels(labels, '', 'unknown'), 'unknown')


class TestGetDuration(unittest.TestCase):

    def test_old_timestamp_returns_days_format(self):
        result = get_duration('1970-01-01T00:00:00.000Z')
        self.assertRegex(result, r'^\d+d \d+h \d{2}m \d{2}s$')

    def test_recent_timestamp_returns_seconds_format(self):
        from datetime import datetime, timezone
        recent = datetime.now(timezone.utc).isoformat()
        result = get_duration(recent)
        self.assertRegex(result, r'^\d{2}s$')


class TestConvertTimestringToUtc(unittest.TestCase):

    def test_returns_iso_format_with_utc_offset(self):
        result = convert_timestring_to_utc('2023-01-15 12:00:00')
        self.assertRegex(result, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$')

    def test_output_ends_with_utc_offset(self):
        result = convert_timestring_to_utc('2023-06-01 08:30:00')
        # result must be timezone-aware (contains offset)
        self.assertTrue('+' in result or result.endswith('Z'))


class TestMapSeverity(unittest.TestCase):

    def setUp(self):
        self.server = AlertmanagerServer()
        self.server.map_to_unknown = 'unknown'
        self.server.map_to_critical = 'critical,crit'
        self.server.map_to_warning = 'warning,warn'
        self.server.map_to_down = 'down'
        self.server.map_to_ok = 'ok,info'

    def test_maps_to_unknown(self):
        self.assertEqual(self.server.map_severity('unknown'), 'UNKNOWN')

    def test_maps_to_critical(self):
        self.assertEqual(self.server.map_severity('critical'), 'CRITICAL')

    def test_maps_to_critical_alias(self):
        self.assertEqual(self.server.map_severity('crit'), 'CRITICAL')

    def test_maps_to_warning(self):
        self.assertEqual(self.server.map_severity('warning'), 'WARNING')

    def test_maps_to_warning_alias(self):
        self.assertEqual(self.server.map_severity('warn'), 'WARNING')

    def test_maps_to_down(self):
        self.assertEqual(self.server.map_severity('down'), 'DOWN')

    def test_maps_to_ok(self):
        self.assertEqual(self.server.map_severity('ok'), 'OK')

    def test_maps_to_ok_alias(self):
        self.assertEqual(self.server.map_severity('info'), 'OK')

    def test_unmapped_severity_uppercased(self):
        # A severity not in any map is returned uppercased (e.g. "error" -> "ERROR")
        self.assertEqual(self.server.map_severity('error'), 'ERROR')

    def test_none_severity_causes_skip(self):
        # "none" uppercases to "NONE" which triggers alert skipping in _process_alert
        self.assertEqual(self.server.map_severity('none'), 'NONE')

    def test_empty_maps_fall_through_to_uppercase(self):
        server = AlertmanagerServer()
        server.map_to_unknown = ''
        server.map_to_critical = ''
        server.map_to_warning = ''
        server.map_to_down = ''
        server.map_to_ok = ''
        self.assertEqual(server.map_severity('warning'), 'WARNING')
        self.assertEqual(server.map_severity('critical'), 'CRITICAL')
        self.assertEqual(server.map_severity('error'), 'ERROR')


if __name__ == '__main__':
    unittest.main()
