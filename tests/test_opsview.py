import re
import unittest
from datetime import datetime

from Nagstamon.servers.Opsview import OpsviewServer, OpsviewService


class TestOpsviewService(unittest.TestCase):

    def setUp(self):
        self.svc = OpsviewService()

    def test_service_object_id_default_empty(self):
        self.assertEqual(self.svc.service_object_id, '')

    def test_is_host_returns_false(self):
        self.assertFalse(self.svc.is_host())

    def test_inherits_generic_service_defaults(self):
        self.assertFalse(self.svc.acknowledged)
        self.assertFalse(self.svc.flapping)
        self.assertFalse(self.svc.passiveonly)


class TestOpsviewServerGetStartEnd(unittest.TestCase):

    def setUp(self):
        self.server = OpsviewServer.__new__(OpsviewServer)

    def test_returns_two_strings(self):
        result = self.server.get_start_end('myhost')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_format_is_datetime_with_seconds(self):
        start, end = self.server.get_start_end('myhost')
        fmt = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
        self.assertRegex(start, fmt)
        self.assertRegex(end, fmt)

    def test_end_is_24_hours_after_start(self):
        start, end = self.server.get_start_end('myhost')
        t_start = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
        t_end = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
        delta_hours = (t_end - t_start).total_seconds() / 3600
        # allow ±1 minute tolerance for clock ticks
        self.assertAlmostEqual(delta_hours, 24, delta=1/60)


if __name__ == '__main__':
    unittest.main()
