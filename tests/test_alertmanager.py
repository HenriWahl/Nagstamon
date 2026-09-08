import json
import logging
from datetime import datetime, timedelta

import dateutil.parser
from pylint import lint

import unittest
from Nagstamon import config
from Nagstamon.objects import GenericHost, Result
from Nagstamon.servers.Alertmanager.helpers import DebugQueueHandler
from Nagstamon.servers.Alertmanager import (AlertmanagerServer,
                                            AlertmanagerService)

conf = {}
conf['debug_mode'] = True

class test_alertmanager(unittest.TestCase):

    def test_lint_with_pylint(self):
        with self.assertRaises(SystemExit) as cm:
            lint.Run(['Nagstamon/servers/Alertmanager'])
        self.assertEqual(cm.exception.code, 0)

    def test_unit_alert_suppressed(self):
        with open('tests/test_alertmanager_suppressed.json') as json_file:
            data = json.load(json_file)
        
        test_class = AlertmanagerServer()
        test_class.map_to_hostname = 'instance,pod_name,namespace'
        test_class.map_to_servicename = 'alertname'
        test_class.map_to_status_information = 'message,summary,description'
        test_class.map_to_unknown = ''
        test_class.map_to_critical = ''
        test_class.map_to_warning = ''
        test_class.map_to_ok = ''

        test_result = test_class._process_alert(data)

        self.assertEqual(test_result['attempt'], 'suppressed')
        self.assertEqual(test_result['acknowledged'], True)
        self.assertEqual(test_result['scheduled_downtime'], True)
        self.assertEqual(test_result['host'], '127.0.0.1')
        self.assertEqual(test_result['name'], 'Error')
        self.assertEqual(test_result['server'], '')
        self.assertEqual(test_result['status'], 'WARNING')
        self.assertEqual(test_result['labels'], {"alertname":"Error","device":"murpel","endpoint":"metrics","instance":"127.0.0.1:9100","job":"node-exporter","namespace":"monitoring","pod":"monitoring-prometheus-node-exporter-4711","prometheus":"monitoring/monitoring-prometheus-oper-prometheus","service":"monitoring-prometheus-node-exporter","severity":"warning"})
        self.assertEqual(test_result['generatorURL'], 'http://localhost')
        self.assertEqual(test_result['fingerprint'], '0ef7c4bd7a504b8d')
        self.assertEqual(test_result['silenced_by'], ['bb043288-42a0-4315-8bae-15cde1d7e239'])
        self.assertEqual(test_result['status_information'], 'Network interface "murpel" showing errors on node-exporter monitoring/monitoring-prometheus-node-exporter-4711')


    def test_unit_alert_skipped(self):
        with open('tests/test_alertmanager_skipped.json') as json_file:
            data = json.load(json_file)

        test_class = AlertmanagerServer()
        test_class.map_to_hostname = 'instance,pod_name,namespace'
        test_class.map_to_servicename = 'alertname'
        test_class.map_to_status_information = 'message,summary,description'

        test_result = test_class._process_alert(data)

        self.assertEqual(test_result, False)


    def test_unit_alert_warning(self):
        with open('tests/test_alertmanager_warning.json') as json_file:
            data = json.load(json_file)

        test_class = AlertmanagerServer()
        test_class.map_to_hostname = 'instance,pod_name,namespace'
        test_class.map_to_servicename = 'alertname'
        test_class.map_to_status_information = 'message,summary,description'
        test_class.map_to_unknown = ''
        test_class.map_to_critical = ''
        test_class.map_to_warning = ''
        test_class.map_to_ok = ''

        test_result = test_class._process_alert(data)

        self.assertEqual(test_result['attempt'], 'active')
        self.assertEqual(test_result['acknowledged'], False)
        self.assertEqual(test_result['scheduled_downtime'], False)
        self.assertEqual(test_result['host'], 'unknown')
        self.assertEqual(test_result['name'], 'TargetDown')
        self.assertEqual(test_result['server'], '')
        self.assertEqual(test_result['status'], 'WARNING')
        self.assertEqual(test_result['labels'], {"alertname": "TargetDown","job": "kubelet","prometheus": "monitoring/monitoring-prometheus-oper-prometheus","severity": "warning"})
        self.assertEqual(test_result['generatorURL'], 'http://localhost')
        self.assertEqual(test_result['fingerprint'], '7be970c6e97b95c9')
        self.assertEqual(test_result['status_information'], '66.6% of the kubelet targets are down.')


    def test_unit_alert_critical(self):
        with open('tests/test_alertmanager_critical.json') as json_file:
            data = json.load(json_file)
        
        test_class = AlertmanagerServer()
        test_class.map_to_hostname = 'instance,pod_name,namespace'
        test_class.map_to_servicename = 'alertname'
        test_class.map_to_status_information = 'message,summary,description'
        test_class.map_to_unknown = ''
        test_class.map_to_critical = ''
        test_class.map_to_warning = ''
        test_class.map_to_ok = ''

        test_result = test_class._process_alert(data)

        self.assertEqual(test_result['attempt'], 'active')
        self.assertEqual(test_result['acknowledged'], False)
        self.assertEqual(test_result['scheduled_downtime'], False)
        self.assertEqual(test_result['host'], '127.0.0.1')
        self.assertEqual(test_result['name'], 'Error')
        self.assertEqual(test_result['server'], '')
        # 'error' is mapped nowhere here, so it falls back to UNKNOWN instead of being
        # handed through as 'ERROR' and never counted - see issue #797
        self.assertEqual(test_result['status'], 'UNKNOWN')
        self.assertEqual(test_result['labels'], {"alertname":"Error","device":"murpel","endpoint":"metrics","instance":"127.0.0.1:9100","job":"node-exporter","namespace":"monitoring","pod":"monitoring-prometheus-node-exporter-4711","prometheus":"monitoring/monitoring-prometheus-oper-prometheus","service":"monitoring-prometheus-node-exporter","severity":"error"})
        self.assertEqual(test_result['generatorURL'], 'http://localhost')
        self.assertEqual(test_result['fingerprint'], '0ef7c4bd7a504b8d')
        self.assertEqual(test_result['status_information'], 'Network interface "murpel" showing errors on node-exporter monitoring/monitoring-prometheus-node-exporter-4711')


    def test_unit_alert_critical_with_empty_maps(self):
        with open('tests/test_alertmanager_critical.json') as json_file:
            data = json.load(json_file)
        
        test_class = AlertmanagerServer()
        test_class.map_to_hostname = ''
        test_class.map_to_servicename = ''
        test_class.map_to_status_information = ''
        test_class.map_to_unknown = ''
        test_class.map_to_critical = ''
        test_class.map_to_warning = ''
        test_class.map_to_ok = ''

        test_result = test_class._process_alert(data)

        self.assertEqual(test_result['attempt'], 'active')
        self.assertEqual(test_result['acknowledged'], False)
        self.assertEqual(test_result['scheduled_downtime'], False)
        self.assertEqual(test_result['host'], 'unknown')
        self.assertEqual(test_result['name'], 'unknown')
        self.assertEqual(test_result['server'], '')
        self.assertEqual(test_result['status'], 'UNKNOWN')
        self.assertEqual(test_result['labels'], {"alertname":"Error","device":"murpel","endpoint":"metrics","instance":"127.0.0.1:9100","job":"node-exporter","namespace":"monitoring","pod":"monitoring-prometheus-node-exporter-4711","prometheus":"monitoring/monitoring-prometheus-oper-prometheus","service":"monitoring-prometheus-node-exporter","severity":"error"})
        self.assertEqual(test_result['generatorURL'], 'http://localhost')
        self.assertEqual(test_result['fingerprint'], '0ef7c4bd7a504b8d')
        self.assertEqual(test_result['status_information'], '')


    def test_unit_alert_custom_severity_critical(self):
        with open('tests/test_alertmanager_custom_severity.json') as json_file:
            data = json.load(json_file)
        
        test_class = AlertmanagerServer()
        test_class.map_to_hostname = 'instance,pod_name,namespace'
        test_class.map_to_servicename = 'alertname'
        test_class.map_to_status_information = 'message,summary,description'
        test_class.map_to_unknown = 'unknown'
        test_class.map_to_critical = 'error,rocketchat'
        test_class.map_to_warning = 'warning'
        test_class.map_to_ok = 'ok'

        test_result = test_class._process_alert(data)

        self.assertEqual(test_result['attempt'], 'active')
        self.assertEqual(test_result['acknowledged'], False)
        self.assertEqual(test_result['scheduled_downtime'], False)
        self.assertEqual(test_result['host'], '127.0.0.1')
        self.assertEqual(test_result['name'], 'Error')
        self.assertEqual(test_result['server'], '')
        self.assertEqual(test_result['status'], 'CRITICAL')
        self.assertEqual(test_result['labels'], {"alertname":"Error","device":"murpel","endpoint":"metrics","instance":"127.0.0.1:9100","job":"node-exporter","namespace":"monitoring","pod":"monitoring-prometheus-node-exporter-4711","prometheus":"monitoring/monitoring-prometheus-oper-prometheus","service":"monitoring-prometheus-node-exporter","severity":"rocketchat"})
        self.assertEqual(test_result['generatorURL'], 'http://localhost')
        self.assertEqual(test_result['fingerprint'], '0ef7c4bd7a504b8d')
        self.assertEqual(test_result['status_information'], 'Network interface "murpel" showing errors on node-exporter monitoring/monitoring-prometheus-node-exporter-4711')




    def test_unit_alert_without_timestamps(self):
        """not every Alertmanager implementation delivers all timestamps"""
        with open('tests/test_alertmanager_warning.json') as json_file:
            data = json.load(json_file)
        del data['startsAt']
        del data['updatedAt']

        test_class = AlertmanagerServer()
        test_class.map_to_hostname = 'instance,pod_name,namespace'
        test_class.map_to_servicename = 'alertname'
        test_class.map_to_status_information = 'message,summary,description'
        test_class.map_to_unknown = ''
        test_class.map_to_critical = ''
        test_class.map_to_warning = ''
        test_class.map_to_ok = ''

        test_result = test_class._process_alert(data)

        self.assertEqual(test_result['duration'], '')
        self.assertEqual(test_result['last_check'], '')
        self.assertEqual(test_result['status'], 'WARNING')


    def test_unit_get_alerts_url(self):
        test_class = AlertmanagerServer()
        test_class.monitor_url = 'http://localhost:9093'

        test_class.alertmanager_filter = ''
        self.assertEqual(test_class.get_alerts_url(),
                         'http://localhost:9093/api/v2/alerts?silenced=true&inhibited=false')

        # a single filter has to be encoded, it contains " and =
        test_class.alertmanager_filter = 'severity="critical"'
        self.assertEqual(test_class.get_alerts_url(),
                         'http://localhost:9093/api/v2/alerts?silenced=true&'
                         'inhibited=false&filter=severity%3D%22critical%22')

        # several matchers become several filter parameters
        test_class.alertmanager_filter = 'severity="critical", job="node"'
        self.assertEqual(test_class.get_alerts_url(),
                         'http://localhost:9093/api/v2/alerts?silenced=true&inhibited=false'
                         '&filter=severity%3D%22critical%22&filter=job%3D%22node%22')

        # a comma inside a quoted value does not split the matcher
        test_class.alertmanager_filter = 'severity=~"warning,critical"'
        self.assertEqual(test_class.get_alerts_url(),
                         'http://localhost:9093/api/v2/alerts?silenced=true&inhibited=false'
                         '&filter=severity%3D~%22warning%2Ccritical%22')

        # silenced and inhibited alerts can be switched on and off
        test_class.alertmanager_filter = ''
        test_class.alertmanager_show_silenced = False
        test_class.alertmanager_show_inhibited = True
        self.assertEqual(test_class.get_alerts_url(),
                         'http://localhost:9093/api/v2/alerts?silenced=false&inhibited=true')


    def test_unit_silence_matchers(self):
        test_class = AlertmanagerServer()
        alert = AlertmanagerService()
        alert.labels = {'alertname': 'Error', 'instance': '127.0.0.1:9100', 'pod': 'volatile-4711'}

        # only the configured labels are used
        test_class.silence_matcher_labels = 'alertname,instance'
        matchers = test_class.get_silence_matchers(alert)
        self.assertEqual([x['name'] for x in matchers], ['alertname', 'instance'])
        self.assertTrue(all(x['isEqual'] and not x['isRegex'] for x in matchers))

        # without configured labels all of them are used
        test_class.silence_matcher_labels = ''
        self.assertEqual(len(test_class.get_silence_matchers(alert)), 3)

        # a silence without matchers would silence everything, so unknown labels fall back
        test_class.silence_matcher_labels = 'does_not_exist'
        self.assertEqual(len(test_class.get_silence_matchers(alert)), 3)


class test_alertmanager_silences(unittest.TestCase):
    """tests for the silences Nagstamon creates - fetch_url is replaced by a recorder"""

    def setUp(self):
        self.requests = []

        self.server = AlertmanagerServer()
        self.server.monitor_url = 'http://localhost:9093'
        self.server.silence_matcher_labels = 'alertname'

        self.alert = AlertmanagerService()
        self.alert.display_name = 'Error'
        self.alert.labels = {'alertname': 'Error', 'instance': '127.0.0.1:9100'}

        host = GenericHost()
        host.name = '127.0.0.1'
        host.services = {'0ef7c4bd7a504b8d': self.alert}
        self.server.hosts = {'127.0.0.1': host}

        def fetch_url(url, giveback=None, cgi_data=None, **kwargs):
            self.requests.append({'url': url, 'cgi_data': json.loads(cgi_data)})
            return None

        self.server.fetch_url = fetch_url

    def test_acknowledge_without_expire_time_lasts(self):
        """without an end time the silence used to end at the very moment it started"""
        self.server._set_acknowledge('127.0.0.1', 'Error', 'someone', 'because',
                                     False, False, False)

        self.assertEqual(len(self.requests), 1)
        silence = self.requests[0]['cgi_data']
        self.assertEqual(self.requests[0]['url'], 'http://localhost:9093/api/v2/silences')
        self.assertEqual(silence['createdBy'], 'someone')
        # the marker tells an acknowledgement from a downtime when reading it back
        self.assertEqual(silence['comment'], 'Nagstamon acknowledgement: because')

        duration = (dateutil.parser.parse(silence['endsAt'])
                    - dateutil.parser.parse(silence['startsAt']))
        self.assertEqual(duration, timedelta(hours=AlertmanagerServer.DEFAULT_SILENCE_HOURS))

    def test_acknowledge_with_expire_time(self):
        # the acknowledge dialog hands over a local time in this format
        expire_time = (datetime.now() + timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M:%S')
        self.server._set_acknowledge('127.0.0.1', 'Error', 'someone', 'because',
                                     False, False, False,
                                     expire_time=expire_time)

        silence = self.requests[0]['cgi_data']
        duration = (dateutil.parser.parse(silence['endsAt'])
                    - dateutil.parser.parse(silence['startsAt']))
        # the exact seconds depend on when the test runs
        self.assertAlmostEqual(duration.total_seconds(),
                               timedelta(hours=4).total_seconds(),
                               delta=5)

    def test_acknowledge_all_services(self):
        other = AlertmanagerService()
        other.display_name = 'Warning'
        other.labels = {'alertname': 'Warning'}
        self.server.hosts['127.0.0.1'].services['abcdef'] = other

        self.server._set_acknowledge('127.0.0.1', 'Error', 'someone', 'because',
                                     False, False, False, all_services=['Warning'])

        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[1]['cgi_data']['matchers'][0]['value'], 'Warning')

    def test_downtime_fixed_uses_end_time(self):
        self.server._set_downtime('127.0.0.1', 'Error', 'someone', 'maintenance', True,
                                  '2026-09-01 10:00:00', '2026-09-01 12:00:00', 0, 0)

        silence = self.requests[0]['cgi_data']
        duration = (dateutil.parser.parse(silence['endsAt'])
                    - dateutil.parser.parse(silence['startsAt']))
        self.assertEqual(duration, timedelta(hours=2))

    def test_downtime_flexible_uses_duration(self):
        """hours and minutes used to be accepted and then ignored"""
        self.server._set_downtime('127.0.0.1', 'Error', 'someone', 'maintenance', False,
                                  '2026-09-01 10:00:00', '2026-09-01 12:00:00', 3, 30)

        silence = self.requests[0]['cgi_data']
        duration = (dateutil.parser.parse(silence['endsAt'])
                    - dateutil.parser.parse(silence['startsAt']))
        self.assertEqual(duration, timedelta(hours=3, minutes=30))

    def test_unknown_service_does_not_raise(self):
        self.server._set_acknowledge('127.0.0.1', 'Does Not Exist', 'someone', 'because',
                                     False, False, False)
        self.server._set_downtime('nosuchhost', 'Error', 'someone', 'maintenance', True,
                                  '2026-09-01 10:00:00', '2026-09-01 12:00:00', 0, 0)
        self.assertEqual(self.requests, [])


class test_alertmanager_silence_removal(unittest.TestCase):
    """acknowledgement, downtime and their removal all end up as silences"""

    def setUp(self):
        self.expired = []

        self.server = AlertmanagerServer()
        self.server.monitor_url = 'http://localhost:9093'

        self.alert = AlertmanagerService()
        self.alert.display_name = 'Error'
        self.alert.labels = {'alertname': 'Error'}
        self.alert.silenced_by = ['silence-1', 'silence-2']

        host = GenericHost()
        host.name = '127.0.0.1'
        host.services = {'0ef7c4bd7a504b8d': self.alert}
        self.server.hosts = {'127.0.0.1': host}

        def expire_silence(silence_id):
            self.expired.append(silence_id)
            return Result(result='', status_code=self.status_codes.get(silence_id, 200))

        # status code the faked API answers with, per silence
        self.status_codes = {}
        self.server.expire_silence = expire_silence

    def test_alert_webpage_url(self):
        """the Monitor action used to open the plain Alertmanager start page"""
        self.server.silence_matcher_labels = 'alertname,instance'
        self.assertEqual(
            self.server.get_alert_webpage_url('127.0.0.1', 'Error'),
            'http://localhost:9093/#/alerts?filter=%7Balertname%3D%22Error%22%7D')

    def test_alert_webpage_url_of_unknown_alert(self):
        self.assertEqual(self.server.get_alert_webpage_url('127.0.0.1', 'Nope'),
                         'http://localhost:9093/#/alerts')

    def test_build_silence_comment(self):
        self.assertEqual(
            AlertmanagerServer.build_silence_comment('Nagstamon downtime', 'because'),
            'Nagstamon downtime: because')
        self.assertEqual(
            AlertmanagerServer.build_silence_comment('Nagstamon downtime', ''),
            'Nagstamon downtime')

    def test_remove_silences_expires_all_of_them(self):
        self.assertEqual(self.server.remove_silences('127.0.0.1', 'Error'), 2)
        self.assertEqual(self.expired, ['silence-1', 'silence-2'])

    def test_remove_silences_without_silence(self):
        self.alert.silenced_by = []
        self.assertEqual(self.server.remove_silences('127.0.0.1', 'Error'), 0)
        self.assertEqual(self.expired, [])

    def test_remove_silences_of_unknown_alert(self):
        self.assertEqual(self.server.remove_silences('127.0.0.1', 'Nope'), 0)
        self.assertEqual(self.expired, [])

    def test_remove_silences_does_not_count_a_failed_one(self):
        self.status_codes['silence-1'] = 404
        self.assertEqual(self.server.remove_silences('127.0.0.1', 'Error'), 1)
        # the failing one must not stop the others from being expired
        self.assertEqual(self.expired, ['silence-1', 'silence-2'])

    def test_acknowledgement_and_downtime_are_told_apart(self):
        """a suppressed alert used to be acknowledged and in downtime at the same time"""
        self.server.get_silences = lambda: [
            {'id': 'silence-1', 'comment': 'Nagstamon downtime: maintenance'}]
        self.alert.silenced_by = ['silence-1']
        self.alert.acknowledged = True
        self.alert.scheduled_downtime = True

        self.server.apply_silence_kind([self.alert])

        self.assertFalse(self.alert.acknowledged)
        self.assertTrue(self.alert.scheduled_downtime)

    def test_acknowledgement_marker(self):
        self.server.get_silences = lambda: [
            {'id': 'silence-1', 'comment': 'Nagstamon acknowledgement: because'}]
        self.alert.silenced_by = ['silence-1']
        self.alert.acknowledged = True
        self.alert.scheduled_downtime = True

        self.server.apply_silence_kind([self.alert])

        self.assertTrue(self.alert.acknowledged)
        self.assertFalse(self.alert.scheduled_downtime)

    def test_foreign_silence_stays_both(self):
        """silences created outside of Nagstamon cannot be told apart"""
        self.server.get_silences = lambda: [
            {'id': 'silence-1', 'comment': 'silenced via the web interface'}]
        self.alert.silenced_by = ['silence-1']
        self.alert.acknowledged = True
        self.alert.scheduled_downtime = True

        self.server.apply_silence_kind([self.alert])

        self.assertTrue(self.alert.acknowledged)
        self.assertTrue(self.alert.scheduled_downtime)


class test_alertmanager_severity_mapping(unittest.TestCase):
    """an alert whose severity is not mapped used to disappear - see issue #797"""

    def setUp(self):
        self.server = AlertmanagerServer()
        self.server.map_to_critical = 'critical,error'
        self.server.map_to_warning = 'warning,warn'
        self.server.map_to_unknown = 'unknown'
        self.server.map_to_ok = 'ok'
        self.server.map_to_down = 'down'
        self.server.map_to_disaster = 'disaster'
        self.server.map_to_high = 'high'
        self.server.map_to_average = 'average'
        self.server.map_to_information = 'info'

    def test_configured_mappings(self):
        self.assertEqual(self.server.map_severity('critical'), 'CRITICAL')
        self.assertEqual(self.server.map_severity('error'), 'CRITICAL')
        self.assertEqual(self.server.map_severity('warn'), 'WARNING')
        self.assertEqual(self.server.map_severity('unknown'), 'UNKNOWN')
        self.assertEqual(self.server.map_severity('ok'), 'OK')
        self.assertEqual(self.server.map_severity('disaster'), 'DISASTER')
        self.assertEqual(self.server.map_severity('high'), 'HIGH')
        self.assertEqual(self.server.map_severity('average'), 'AVERAGE')
        self.assertEqual(self.server.map_severity('info'), 'INFORMATION')

    def test_map_to_down_becomes_critical(self):
        """only hosts can be DOWN, an alert always becomes a service"""
        self.assertEqual(self.server.map_severity('down'), 'CRITICAL')

    def test_unmapped_severity_falls_back_to_unknown(self):
        """'unreachable' is exactly the severity from issue #797"""
        self.assertEqual(self.server.map_severity('unreachable'), 'UNKNOWN')
        self.assertEqual(self.server.map_severity('rocketchat'), 'UNKNOWN')

    def test_severity_named_like_a_state_still_works(self):
        self.server.map_to_critical = ''
        self.assertEqual(self.server.map_severity('critical'), 'CRITICAL')
        self.assertEqual(self.server.map_severity('WARNING'), 'WARNING')

    def test_none_is_kept_for_skipping(self):
        self.assertEqual(self.server.map_severity('none'), 'NONE')

    def test_worse_state_wins(self):
        self.server.map_to_warning = 'ambiguous'
        self.server.map_to_critical = 'ambiguous'
        self.assertEqual(self.server.map_severity('ambiguous'), 'CRITICAL')

    def test_empty_severity_does_not_match_an_empty_option(self):
        """an alert can carry an empty severity label, and map_to_disaster is unset by
        default - which used to make such an alert a DISASTER"""
        self.server.map_to_disaster = ''
        self.server.map_to_critical = ''
        self.assertEqual(self.server.map_severity(''), 'UNKNOWN')


class test_alertmanager_alert_groups(unittest.TestCase):
    """honouring the grouping of the Alertmanager - see issue #746"""

    def setUp(self):
        self.server = AlertmanagerServer()
        self.server.monitor_url = 'http://localhost:9093'
        self.server.map_to_hostname = 'instance'
        self.server.alertmanager_use_alert_groups = True

    def test_groups_endpoint_is_used(self):
        self.assertEqual(self.server.get_alerts_url(),
                         'http://localhost:9093/api/v2/alerts/groups?'
                         'silenced=true&inhibited=false')
        self.server.alertmanager_use_alert_groups = False
        self.assertEqual(self.server.get_alerts_url(),
                         'http://localhost:9093/api/v2/alerts?'
                         'silenced=true&inhibited=false')

    def test_hostname_from_mapped_label(self):
        group = {'labels': {'instance': 'host1:9100'}}
        self.assertEqual(self.server.get_group_hostname(group), 'host1')

    def test_hostname_falls_back_to_the_group_key(self):
        """group_by may well use a label which is not the host"""
        group = {'labels': {'job': 'node', 'severity': 'critical'}}
        self.assertEqual(self.server.get_group_hostname(group),
                         'job=node, severity=critical')

    def test_hostname_of_a_nameless_group(self):
        group = {'labels': {}, 'receiver': {'name': 'devnull'}}
        self.assertEqual(self.server.get_group_hostname(group), 'devnull')

    def test_alerts_of_a_group_land_under_the_group(self):
        group_alert = {'labels': {'alertname': 'DiskFull', 'severity': 'critical',
                                  'instance': 'host2:9100'},
                       'annotations': {'summary': 'full'},
                       'status': {'state': 'active'},
                       'fingerprint': 'abc',
                       'startsAt': '2026-09-01T10:00:00Z'}
        self.server.map_to_servicename = 'alertname'
        self.server.map_to_status_information = 'summary'
        self.server.map_to_critical = 'critical'
        self.server.new_hosts = {}

        self.server.add_alert(group_alert, [], hostname='the-group')

        self.assertEqual(list(self.server.new_hosts), ['the-group'])
        service = self.server.new_hosts['the-group'].services['abc']
        self.assertEqual(service.display_name, 'DiskFull')
        self.assertEqual(service.status, 'CRITICAL')


class test_alertmanager_debug_queue(unittest.TestCase):
    """the log of the Alertmanager ends up in the debug queue of Nagstamon"""

    def setUp(self):
        self.debug_mode = config.conf.debug_mode
        config.debug_queue.clear()

    def tearDown(self):
        config.conf.debug_mode = self.debug_mode
        config.debug_queue.clear()

    @staticmethod
    def make_record():
        return logging.LogRecord('alertmanager', logging.ERROR, __file__, 1,
                                 'something went wrong', None, None)

    def test_records_are_queued_in_debug_mode(self):
        config.conf.debug_mode = True
        DebugQueueHandler().emit(self.make_record())
        self.assertEqual(len(config.debug_queue), 1)

    def test_nothing_is_queued_without_debug_mode(self):
        """nobody drains the queue then, so the records would only pile up"""
        config.conf.debug_mode = False
        DebugQueueHandler().emit(self.make_record())
        self.assertEqual(config.debug_queue, [])


if __name__ == '__main__':
    unittest.main()
