import json
import unittest

from Nagstamon.servers.Zabbix import ZabbixServer


import unittest
from Nagstamon.servers.Zabbix import ZabbixServer

class TestNagiosifyService(unittest.TestCase):
    def setUp(self):
        self.server = ZabbixServer.__new__(ZabbixServer)

    def test_splits_on_on(self):
        self.assertEqual(self.server.nagiosify_service('CPU load on myhost'), 'CPU load')

    def test_splits_on_is(self):
        # When only the " is " separator is present, split on it and keep the left part
        self.assertEqual(self.server.nagiosify_service('Service is running'), 'Service')

    def test_no_separator_unchanged(self):
        self.assertEqual(self.server.nagiosify_service('Disk usage'), 'Disk usage')

    def test_empty_string(self):
        self.assertEqual(self.server.nagiosify_service(''), '')


class TestGenerateCgiData(unittest.TestCase):

    def setUp(self):
        self.server = ZabbixServer.__new__(ZabbixServer)
        self.server.auth_token = 'mytoken123'
        self.server.api_version = '5.4.0'

    def test_structure(self):
        data = json.loads(self.server.generate_cgi_data('host.get'))
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertEqual(data['method'], 'host.get')
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['params'], {})

    def test_includes_auth_for_pre_640(self):
        self.server.api_version = '5.4.0'
        data = json.loads(self.server.generate_cgi_data('host.get'))
        self.assertIn('auth', data)
        self.assertEqual(data['auth'], 'mytoken123')

    def test_excludes_auth_for_640_and_later(self):
        self.server.api_version = '6.4.0'
        data = json.loads(self.server.generate_cgi_data('host.get'))
        self.assertNotIn('auth', data)

    def test_no_auth_flag_omits_auth(self):
        self.server.api_version = '5.4.0'
        data = json.loads(self.server.generate_cgi_data('apiinfo.version', no_auth=True))
        self.assertNotIn('auth', data)

    def test_params_are_included(self):
        params = {'limit': 10, 'output': 'extend'}
        data = json.loads(self.server.generate_cgi_data('host.get', params=params))
        self.assertEqual(data['params'], params)


if __name__ == '__main__':
    unittest.main()
