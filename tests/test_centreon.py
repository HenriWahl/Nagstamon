import re
import unittest
from datetime import datetime
from unittest.mock import patch

import Nagstamon.config as config
from Nagstamon.servers.Centreon.CentreonAPI import CentreonServer as CentreonAPIServer
from Nagstamon.servers.Centreon.CentreonLegacy import CentreonServer as CentreonLegacyServer

_BASE_URL = 'http://centreon.example.com/centreon'


# ---------------------------------------------------------------------------
# CentreonLegacy
# ---------------------------------------------------------------------------

class TestCentreonLegacyHardSoft(unittest.TestCase):

    def setUp(self):
        self.server = CentreonLegacyServer.__new__(CentreonLegacyServer)
        self.server.HARD_SOFT = {'(H)': 'hard', '(S)': 'soft'}

    def test_hard_state(self):
        self.assertEqual(self.server.HARD_SOFT['(H)'], 'hard')

    def test_soft_state(self):
        self.assertEqual(self.server.HARD_SOFT['(S)'], 'soft')


class TestCentreonLegacyTranslations(unittest.TestCase):

    def setUp(self):
        self.server = CentreonLegacyServer.__new__(CentreonLegacyServer)
        self.server.TRANSLATIONS = {
            'INDISPONIBLE': 'DOWN',
            'INJOIGNABLE':  'UNREACHABLE',
            'CRITIQUE':     'CRITICAL',
            'INCONNU':      'UNKNOWN',
            'ALERTE':       'WARNING',
        }

    def test_indisponible_translates_to_down(self):
        self.assertEqual(self.server.TRANSLATIONS['INDISPONIBLE'], 'DOWN')

    def test_injoignable_translates_to_unreachable(self):
        self.assertEqual(self.server.TRANSLATIONS['INJOIGNABLE'], 'UNREACHABLE')

    def test_critique_translates_to_critical(self):
        self.assertEqual(self.server.TRANSLATIONS['CRITIQUE'], 'CRITICAL')

    def test_inconnu_translates_to_unknown(self):
        self.assertEqual(self.server.TRANSLATIONS['INCONNU'], 'UNKNOWN')

    def test_alerte_translates_to_warning(self):
        self.assertEqual(self.server.TRANSLATIONS['ALERTE'], 'WARNING')


class TestCentreonLegacyDefineUrl(unittest.TestCase):
    """_define_url() selects a URL set based on centreon_version."""

    def _make_server(self, version):
        s = CentreonLegacyServer.__new__(CentreonLegacyServer)
        s.monitor_cgi_url = _BASE_URL
        s.XML_PATH = 'xml'
        s.centreon_version = version
        with patch.object(config.conf, 'debug_mode', False):
            s._define_url()
        return s

    def test_version_2_6_uses_base_urls(self):
        s = self._make_server(2.6)
        self.assertEqual(s.urls_centreon['main'], _BASE_URL + '/main.php')
        # version < 2.7 should NOT have broker in xml_hosts path
        self.assertNotIn('broker', s.urls_centreon['xml_hosts'])

    def test_version_2_7_has_broker_in_xml_hosts(self):
        s = self._make_server(2.7)
        self.assertIn('broker', s.urls_centreon['xml_hosts'])

    def test_version_2_8_uses_main_php(self):
        s = self._make_server(2.8)
        self.assertEqual(s.urls_centreon['main'], _BASE_URL + '/main.php')
        # 2.8 should NOT have broker in xml_hosts path
        self.assertNotIn('broker', s.urls_centreon['xml_hosts'])

    def test_version_18_10_uses_main_get_php(self):
        s = self._make_server(18.10)
        self.assertTrue(s.urls_centreon['main'].endswith('main.get.php'))

    def test_version_18_10_has_keepalive_url(self):
        s = self._make_server(18.10)
        self.assertIn('keepAlive', s.urls_centreon)

    def test_all_url_sets_include_base_url(self):
        for version in [2.6, 2.7, 2.8, 18.10]:
            s = self._make_server(version)
            for url in s.urls_centreon.values():
                self.assertTrue(url.startswith(_BASE_URL),
                                f'version {version}: URL {url!r} does not start with base URL')


# ---------------------------------------------------------------------------
# CentreonAPI
# ---------------------------------------------------------------------------

class TestCentreonAPIHardSoft(unittest.TestCase):

    def setUp(self):
        self.server = CentreonAPIServer.__new__(CentreonAPIServer)
        self.server.HARD_SOFT = {'(H)': 'hard', '(S)': 'soft'}

    def test_hard_state(self):
        self.assertEqual(self.server.HARD_SOFT['(H)'], 'hard')

    def test_soft_state(self):
        self.assertEqual(self.server.HARD_SOFT['(S)'], 'soft')


class TestCentreonAPIDefineUrl(unittest.TestCase):
    """define_url() builds the urls_centreon dict from restapi_version."""

    def _make_server(self, restapi_version):
        s = CentreonAPIServer.__new__(CentreonAPIServer)
        s.monitor_cgi_url = _BASE_URL
        s.restapi_version = restapi_version
        s.define_url()
        return s

    def test_latest_builds_correct_resources_url(self):
        s = self._make_server('latest')
        self.assertEqual(s.urls_centreon['resources'],
                         _BASE_URL + '/api/latest/monitoring/resources')

    def test_v22_04_uses_version_in_url(self):
        s = self._make_server('v22.04')
        self.assertIn('v22.04', s.urls_centreon['resources'])

    def test_v23_04_uses_version_in_url(self):
        s = self._make_server('v23.04')
        self.assertIn('v23.04', s.urls_centreon['login'])

    def test_v24_04_urls_include_base(self):
        s = self._make_server('v24.04')
        for url in s.urls_centreon.values():
            self.assertTrue(url.startswith(_BASE_URL))

    def test_all_expected_keys_present(self):
        s = self._make_server('latest')
        for key in ('resources', 'login', 'services', 'hosts'):
            self.assertIn(key, s.urls_centreon)


class TestCentreonAPIGetStartEnd(unittest.TestCase):

    def setUp(self):
        self.server = CentreonAPIServer.__new__(CentreonAPIServer)

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
        self.assertAlmostEqual(delta_minutes, 120, delta=1)


if __name__ == '__main__':
    unittest.main()
