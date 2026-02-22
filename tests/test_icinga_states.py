"""
Tests for the Icinga server family:
  - IcingaServer.looseversion  (edge cases not in test_icinga.py)
  - Icinga2APIServer._insert_service_to_hosts
  - STATES_MAPPING / STATES_MAPPING_REV for Icinga2API, IcingaDBWeb, IcingaWeb2
    (all three share the same mapping, so we test them as a group)
"""
import unittest

from Nagstamon.objects import GenericService
from Nagstamon.servers.Icinga import IcingaServer
from Nagstamon.servers.Icinga2API import Icinga2APIServer
from Nagstamon.servers.IcingaDBWeb import IcingaDBWebServer
from Nagstamon.servers.IcingaWeb2 import IcingaWeb2Server

# All three subclasses share the same STATES_MAPPING values.
_ICINGA_SERVER_CLASSES = [Icinga2APIServer, IcingaDBWebServer, IcingaWeb2Server]


class TestLooseversionEdgeCases(unittest.TestCase):

    def setUp(self):
        self.server = IcingaServer.__new__(IcingaServer)

    def test_equal_versions(self):
        self.assertEqual(self.server.looseversion('1.7'), self.server.looseversion('1.7'))

    def test_patch_version_greater(self):
        self.assertGreater(self.server.looseversion('1.7.1'), self.server.looseversion('1.7'))

    def test_major_version_beats_minor(self):
        self.assertGreater(self.server.looseversion('2.0'), self.server.looseversion('1.99'))

    def test_minor_10_beats_minor_9(self):
        # Numeric comparison: 1.10 > 1.9 (unlike lexicographic "1.10" < "1.9")
        self.assertGreater(self.server.looseversion('1.10'), self.server.looseversion('1.9'))

    def test_returns_list_of_ints(self):
        result = self.server.looseversion('2.3.4')
        self.assertEqual(result, [2, 3, 4])

    def test_single_digit_version(self):
        self.assertEqual(self.server.looseversion('2'), [2])


class TestIcinga2APIInsertServiceToHosts(unittest.TestCase):

    def setUp(self):
        self.server = Icinga2APIServer.__new__(Icinga2APIServer)
        self.server.new_hosts = {}

    def _make_service(self, name, host, site='default'):
        svc = GenericService()
        svc.name = name
        svc.host = host
        svc.site = site
        return svc

    def test_creates_host_for_new_service(self):
        svc = self._make_service('check_ping', 'web01')
        self.server._insert_service_to_hosts(svc)
        self.assertIn('web01', self.server.new_hosts)

    def test_sets_host_name(self):
        svc = self._make_service('check_ping', 'web01')
        self.server._insert_service_to_hosts(svc)
        self.assertEqual(self.server.new_hosts['web01'].name, 'web01')

    def test_sets_host_site(self):
        svc = self._make_service('check_ping', 'web01', site='production')
        self.server._insert_service_to_hosts(svc)
        self.assertEqual(self.server.new_hosts['web01'].site, 'production')

    def test_registers_service_under_host(self):
        svc = self._make_service('check_ping', 'web01')
        self.server._insert_service_to_hosts(svc)
        self.assertIn('check_ping', self.server.new_hosts['web01'].services)

    def test_service_object_is_the_same_instance(self):
        svc = self._make_service('check_ping', 'web01')
        self.server._insert_service_to_hosts(svc)
        self.assertIs(self.server.new_hosts['web01'].services['check_ping'], svc)

    def test_second_service_reuses_existing_host(self):
        svc1 = self._make_service('check_ping', 'web01')
        svc2 = self._make_service('check_disk', 'web01')
        self.server._insert_service_to_hosts(svc1)
        self.server._insert_service_to_hosts(svc2)
        self.assertEqual(len(self.server.new_hosts), 1)
        self.assertIn('check_disk', self.server.new_hosts['web01'].services)

    def test_different_hosts_are_separate(self):
        svc1 = self._make_service('check_ping', 'web01')
        svc2 = self._make_service('check_ping', 'db01')
        self.server._insert_service_to_hosts(svc1)
        self.server._insert_service_to_hosts(svc2)
        self.assertEqual(len(self.server.new_hosts), 2)


class TestIcingaStatesMappingForward(unittest.TestCase):
    """STATES_MAPPING forward: numeric code → status string."""

    def _check_class(self, cls):
        m = cls.STATES_MAPPING
        # hosts
        self.assertEqual(m['hosts'][0], 'UP')
        self.assertEqual(m['hosts'][1], 'DOWN')
        self.assertEqual(m['hosts'][2], 'UNREACHABLE')
        # services
        self.assertEqual(m['services'][0], 'OK')
        self.assertEqual(m['services'][1], 'WARNING')
        self.assertEqual(m['services'][2], 'CRITICAL')
        self.assertEqual(m['services'][3], 'UNKNOWN')

    def test_icinga2api(self):
        self._check_class(Icinga2APIServer)

    def test_icingadbweb(self):
        self._check_class(IcingaDBWebServer)

    def test_icingaweb2(self):
        self._check_class(IcingaWeb2Server)


class TestIcingaStatesMappingReverse(unittest.TestCase):
    """STATES_MAPPING_REV reverse: status string → numeric code."""

    def _check_class(self, cls):
        r = cls.STATES_MAPPING_REV
        # hosts
        self.assertEqual(r['hosts']['UP'], 0)
        self.assertEqual(r['hosts']['DOWN'], 1)
        self.assertEqual(r['hosts']['UNREACHABLE'], 2)
        # services
        self.assertEqual(r['services']['OK'], 0)
        self.assertEqual(r['services']['WARNING'], 1)
        self.assertEqual(r['services']['CRITICAL'], 2)
        self.assertEqual(r['services']['UNKNOWN'], 3)

    def test_icinga2api(self):
        self._check_class(Icinga2APIServer)

    def test_icingadbweb(self):
        self._check_class(IcingaDBWebServer)

    def test_icingaweb2(self):
        self._check_class(IcingaWeb2Server)

    def test_forward_and_reverse_are_consistent(self):
        """For every class, forward[k] == v iff reverse[v] == k."""
        for cls in _ICINGA_SERVER_CLASSES:
            for category in ('hosts', 'services'):
                for code, status in cls.STATES_MAPPING[category].items():
                    self.assertEqual(
                        cls.STATES_MAPPING_REV[category][status], code,
                        f'{cls.__name__}: STATES_MAPPING_REV[{category!r}][{status!r}] '
                        f'should be {code}, not {cls.STATES_MAPPING_REV[category][status]}'
                    )


if __name__ == '__main__':
    unittest.main()
