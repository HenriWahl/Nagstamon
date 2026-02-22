import unittest
from unittest.mock import MagicMock, patch

from Nagstamon.servers.ZabbixProblemBased import ZabbixLightApi, ZabbixLightApiException


class TestZabbixLightApiInit(unittest.TestCase):

    def _make_api(self, base_url='http://zabbix.example.com'):
        with patch('Nagstamon.config.conf') as mock_conf:
            mock_conf.debug_mode = False
            import requests
            with patch.object(requests, 'Session', return_value=MagicMock()):
                return ZabbixLightApi('TestServer', base_url, False)

    def test_url_gets_api_suffix_appended(self):
        api = self._make_api('http://zabbix.example.com')
        self.assertEqual(api.monitor_url, 'http://zabbix.example.com/api_jsonrpc.php')

    def test_server_name_stored(self):
        api = self._make_api()
        self.assertEqual(api.server_name, 'TestServer')

    def test_validate_certs_stored(self):
        api = self._make_api()
        self.assertFalse(api.validate_certs)

    def test_zbx_auth_initially_none(self):
        api = self._make_api()
        self.assertIsNone(api.zbx_auth)

    def test_request_id_starts_at_zero(self):
        api = self._make_api()
        self.assertEqual(api.zbx_req_id, 0)


class TestZabbixLightApiLoggedIn(unittest.TestCase):

    def test_returns_false_when_auth_is_none(self):
        api = ZabbixLightApi.__new__(ZabbixLightApi)
        api.zbx_auth = None
        self.assertFalse(api.logged_in())


class TestZabbixLightApiException(unittest.TestCase):

    def test_is_exception(self):
        exc = ZabbixLightApiException('something went wrong')
        self.assertIsInstance(exc, Exception)

    def test_message_preserved(self):
        exc = ZabbixLightApiException('bad response')
        self.assertEqual(str(exc), 'bad response')


if __name__ == '__main__':
    unittest.main()
