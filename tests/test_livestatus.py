import re
import time
import unittest

from Nagstamon.servers.Livestatus import duration, format_timestamp, service_to_host


class TestFormatTimestamp(unittest.TestCase):

    def test_epoch_zero(self):
        # Unix epoch 0 must format as a date/time string
        result = format_timestamp(0)
        self.assertRegex(result, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')

    def test_known_timestamp(self):
        # 2023-03-15 00:00:00 UTC = 1678838400
        result = format_timestamp(1678838400)
        self.assertRegex(result, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')

    def test_current_time(self):
        result = format_timestamp(time.time())
        self.assertRegex(result, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')


class TestDuration(unittest.TestCase):

    def test_output_format(self):
        past = time.time() - 3661
        result = duration(past)
        self.assertRegex(result, r'^\d{2}d \d{2}h \d{2}m \d{2}s$')

    def test_about_one_hour(self):
        past = time.time() - 3661  # ~1h 1m 1s
        result = duration(past)
        # days should be 00, hours should be 01
        parts = re.match(r'^(\d{2})d (\d{2})h (\d{2})m (\d{2})s$', result)
        self.assertIsNotNone(parts)
        self.assertEqual(parts.group(1), '00')
        self.assertEqual(parts.group(2), '01')

    def test_about_one_day(self):
        past = time.time() - 86400  # ~24h
        result = duration(past)
        parts = re.match(r'^(\d{2})d (\d{2})h (\d{2})m (\d{2})s$', result)
        self.assertIsNotNone(parts)
        self.assertEqual(parts.group(1), '01')


class TestServiceToHost(unittest.TestCase):

    def test_strips_host_prefix(self):
        data = {
            'host_name': 'myhost',
            'host_state': 'UP',
            'host_address': '1.2.3.4',
        }
        result = service_to_host(data)
        self.assertEqual(result, {'name': 'myhost', 'state': 'UP', 'address': '1.2.3.4'})

    def test_ignores_non_host_keys(self):
        data = {
            'host_name': 'myhost',
            'service_description': 'ping',
            'other': 'value',
        }
        result = service_to_host(data)
        self.assertIn('name', result)
        self.assertNotIn('service_description', result)
        self.assertNotIn('other', result)

    def test_empty_input(self):
        self.assertEqual(service_to_host({}), {})

    def test_no_host_keys(self):
        data = {'service_description': 'ping', 'check_command': 'check_ping'}
        self.assertEqual(service_to_host(data), {})


if __name__ == '__main__':
    unittest.main()
