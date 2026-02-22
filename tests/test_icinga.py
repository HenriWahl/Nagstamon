import unittest

from Nagstamon.servers.Icinga import IcingaServer


class TestLooseVersion(unittest.TestCase):

    def test_simple_version(self):
        server = IcingaServer()
        self.assertEqual(server.looseversion('1.2.3'), [1, 2, 3])

    def test_two_part_version(self):
        server = IcingaServer()
        self.assertEqual(server.looseversion('2.0'), [2, 0])

    def test_comparison_greater(self):
        server = IcingaServer()
        self.assertGreater(server.looseversion('2.10.1'), server.looseversion('2.9.5'))

    def test_comparison_less(self):
        server = IcingaServer()
        self.assertLess(server.looseversion('1.2.3'), server.looseversion('2.0.0'))

    def test_comparison_equal(self):
        server = IcingaServer()
        self.assertEqual(server.looseversion('1.4.0'), server.looseversion('1.4.0'))

    def test_major_version_dominates(self):
        server = IcingaServer()
        self.assertGreater(server.looseversion('2.0.0'), server.looseversion('1.99.99'))


if __name__ == '__main__':
    unittest.main()
