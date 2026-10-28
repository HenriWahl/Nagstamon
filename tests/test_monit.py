"""Monit XML v1 contract, as emitted by src/http/xml.c in Monit."""

import unittest
from unittest.mock import Mock, patch

from Nagstamon.config import Server
from Nagstamon.objects import Result
from Nagstamon.servers import create_server
from Nagstamon.servers.Monit import MonitServer


def service_xml(name='nginx', status=0, hint=0, monitor=1, mode=0):
    return (
        '<service type="3"><name>{}</name><status>{}</status>'
        '<status_hint>{}</status_hint><monitor>{}</monitor>'
        '<monitormode>{}</monitormode><collected_sec>1700000000</collected_sec>'
        '</service>'.format(name, status, hint, monitor, mode)
    )


def status_xml(services, hostname='node.example'):
    return ('<?xml version="1.0" encoding="ISO-8859-1"?>'
            '<monit><server><localhostname>{}</localhostname></server>{}</monit>'
            .format(hostname, services))


class TestMonit(unittest.TestCase):
    def setUp(self):
        self.server = MonitServer(name='test-monit')
        self.server.monitor_url = 'https://example.com/monit/'

    def poll(self, xml):
        self.server.fetch_url = Mock(return_value=Result(result=xml, status_code=200))
        return self.server._get_status()

    def test_registration_and_basic_authentication(self):
        config = Server()
        config.name = 'monit'
        config.type = 'Monit'
        config.monitor_url = 'https://example.com:2812'
        config.authentication = 'basic'
        config.username = 'reader'
        config.password = 'secret'
        server = create_server(config)
        self.assertIsInstance(server, MonitServer)
        self.assertEqual(server.create_session().auth, (b'reader', b'secret'))
        self.assertEqual(server.MENU_ACTIONS, ['Monitor'])

    def test_status_mapping(self):
        for status, hint, monitor, expected, message in [
            (0, 0, 1, 'OK', 'OK'),
            (512, 0, 1, 'CRITICAL', 'Does not exist failed'),
            (32 | 2, 0, 1, 'CRITICAL', 'Resource failed | Connection failed'),
            (16, 16, 1, 'WARNING', 'Size changed'),
            (16 | 32, 16, 1, 'CRITICAL', 'Size changed | Connection failed'),
            (512, 0, 0, 'UNKNOWN', 'Not monitored'),
            (512, 0, 2, 'UNKNOWN', 'Initializing'),
            (0, 0, 5, 'UNKNOWN', 'Waiting'),
            (1 << 31, 0, 1, 'CRITICAL', 'Unknown event bits: 0x80000000'),
        ]:
            with self.subTest(status=status, hint=hint, monitor=monitor):
                self.assertEqual(self.poll(status_xml(service_xml(
                    status=status, hint=hint, monitor=monitor))).error, '')
                host = self.server.new_hosts['node.example']
                service = host.services['nginx']
                self.assertEqual(host.status, 'UP')
                self.assertEqual(service.status, expected)
                self.assertEqual(service.status_information, message)
                self.assertEqual(service.host, 'node.example')
                self.assertEqual(service.server, 'test-monit')
                self.assertEqual(service.passiveonly, monitor == 0)
                self.assertTrue(service.last_check)
                self.assertEqual(service.duration, '')

    def test_endpoint_and_refresh_remove_old_services(self):
        self.poll(status_xml(service_xml('old') + service_xml('new')))
        self.server.fetch_url.assert_called_once_with(
            'https://example.com/monit/_status?format=xml', giveback='raw')
        self.poll(status_xml(service_xml('new', mode=1)))
        host = self.server.new_hosts['node.example']
        self.assertEqual(set(host.services), {'new'})
        self.assertFalse(host.services['new'].passiveonly)

    def test_hostname_fallback_and_unicode(self):
        self.poll(status_xml(service_xml('café &amp; worker'), hostname=''))
        self.assertIn('café & worker', self.server.new_hosts['example.com'].services)

    def test_full_poll_updates_problem_counts_and_recovers(self):
        self.server.enabled = True
        self.server.init_http = Mock()
        self.server.fetch_url = Mock(return_value=Result(
            result=status_xml(service_xml(status=512)), status_code=200))
        self.server.get_status()
        self.assertEqual(self.server.critical, 1)
        self.assertEqual(self.server.hosts['node.example'].services['nginx'].status,
                         'CRITICAL')
        self.server.fetch_url.return_value = Result(
            result=status_xml(service_xml()), status_code=200)
        self.server.get_status()
        self.assertEqual(self.server.critical, 0)
        self.assertEqual(self.server.hosts['node.example'].services['nginx'].status, 'OK')

    def test_http_and_transport_errors_are_preserved(self):
        for code, error in [(400, ''), (401, ''), (403, ''), (503, ''), (0, 'timeout')]:
            with self.subTest(code=code):
                response = Result(result='failure', error=error, status_code=code)
                self.server.fetch_url = Mock(return_value=response)
                self.assertIs(self.server._get_status(), response)
                self.assertEqual(self.server.new_hosts, {})

    def test_invalid_response_does_not_publish_partial_results(self):
        for xml in ['<html>login</html>', '<monit>', '<monit/>',
                    status_xml(service_xml() + service_xml(status='invalid')),
                    status_xml('<service><name>broken</name></service>')]:
            with self.subTest(xml=xml):
                result = self.poll(xml)
                self.assertEqual(result.result, 'ERROR')
                self.assertTrue(result.error)
                self.assertEqual(self.server.new_hosts, {})

    @patch('Nagstamon.servers.Monit.webbrowser_open')
    def test_monitor_links_encode_service_names(self, browser):
        self.server.open_monitor('node.example', 'worker/a & b')
        browser.assert_called_with('https://example.com/monit/worker%2Fa%20%26%20b')
        self.server.open_monitor('node.example')
        browser.assert_called_with('https://example.com/monit/')
