"""
Prometheus shares its label and duration handling with the Alertmanager server, so these
tests guard the parsing after both were moved into Nagstamon.helpers
"""

import json
import unittest

from Nagstamon.helpers import detect_from_labels, get_duration
from Nagstamon.servers.Prometheus import PrometheusServer


class test_prometheus(unittest.TestCase):

    def setUp(self):
        self.server = PrometheusServer()
        self.server.name = 'test'
        self.server.map_to_hostname = 'pod_name,namespace,instance'
        self.server.map_to_servicename = 'alertname'
        self.server.map_to_status_information = 'message,summary,description'

        self.payload = {'data': {'alerts': [
            {'labels': {'alertname': 'DiskFull', 'severity': 'critical',
                        'instance': 'host1:9100'},
             'annotations': {'summary': 'disk is full'},
             'state': 'firing',
             'activeAt': '2026-09-01T10:00:00Z'},
            {'labels': {'alertname': 'Watchdog', 'severity': 'none'},
             'annotations': {},
             'state': 'firing',
             'activeAt': '2026-09-01T10:00:00Z'},
        ]}}

    def fetch(self, payload):
        class FakeResult:
            result = json.dumps(payload)
            error = ''
            status_code = 200
        self.server.fetch_url = lambda *args, **kwargs: FakeResult()
        self.server.new_hosts = {}
        self.server._get_status()
        return self.server.new_hosts

    def test_alerts_are_parsed(self):
        hosts = self.fetch(self.payload)
        self.assertEqual(list(hosts), ['host1:9100'])
        service = hosts['host1:9100'].services['DiskFull']
        self.assertEqual(service.status, 'CRITICAL')
        self.assertEqual(service.status_information, 'disk is full')
        self.assertEqual(service.attempt, 'firing')
        self.assertNotEqual(service.duration, '')

    def test_severity_none_is_skipped(self):
        hosts = self.fetch(self.payload)
        names = [name for host in hosts.values() for name in host.services]
        self.assertNotIn('Watchdog', names)

    def test_missing_active_at_does_not_raise(self):
        del self.payload['data']['alerts'][0]['activeAt']
        hosts = self.fetch(self.payload)
        self.assertEqual(hosts['host1:9100'].services['DiskFull'].duration, '')

    def test_unmatched_labels_fall_back(self):
        self.server.map_to_hostname = 'does_not_exist'
        hosts = self.fetch(self.payload)
        self.assertEqual(list(hosts), ['unknown'])


class test_shared_helpers(unittest.TestCase):

    def test_detect_from_labels(self):
        labels = {'instance': 'host1', 'namespace': 'monitoring'}
        self.assertEqual(detect_from_labels(labels, 'pod,instance'), 'host1')
        self.assertEqual(detect_from_labels(labels, 'pod,namespace'), 'monitoring')
        self.assertEqual(detect_from_labels(labels, 'pod', 'fallback'), 'fallback')

    def test_get_duration(self):
        self.assertEqual(get_duration(None), '')
        self.assertEqual(get_duration(''), '')
        self.assertEqual(get_duration('no time at all'), '')
        self.assertTrue(get_duration('2020-01-01T00:00:00Z').endswith('s'))


if __name__ == '__main__':
    unittest.main()
