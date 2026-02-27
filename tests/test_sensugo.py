import time
import unittest

from Nagstamon.servers.SensuGo import NAMESPACE_SEPARATOR, SensuGoServer


class TestExtractNamespace(unittest.TestCase):

    def setUp(self):
        self.server = SensuGoServer.__new__(SensuGoServer)

    def test_extracts_default_namespace(self):
        host_column = 'default' + NAMESPACE_SEPARATOR + 'myhost'
        self.assertEqual(self.server._extract_namespace(host_column), 'default')

    def test_extracts_custom_namespace(self):
        host_column = 'production' + NAMESPACE_SEPARATOR + 'web-01'
        self.assertEqual(self.server._extract_namespace(host_column), 'production')


class TestDurationSince(unittest.TestCase):

    def setUp(self):
        self.server = SensuGoServer.__new__(SensuGoServer)

    def test_zero_timestamp_returns_na(self):
        self.assertEqual(self.server._duration_since(0), 'n/a')

    def test_future_timestamp_returns_na(self):
        future = int(time.time()) + 1000
        self.assertEqual(self.server._duration_since(future), 'n/a')

    def test_past_timestamp_returns_duration_string(self):
        past = int(time.time()) - 3600
        result = self.server._duration_since(past)
        self.assertNotEqual(result, 'n/a')
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


if __name__ == '__main__':
    unittest.main()
