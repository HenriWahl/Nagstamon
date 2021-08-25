import json

from pylint import lint

import unittest
from Nagstamon.Servers.Alertmanager import AlertmanagerServer

conf = {}
conf['debug_mode'] = True

class test_alertmanager(unittest.TestCase):

    def test_lint_with_pylint(self):
        with self.assertRaises(SystemExit) as cm:
            lint.Run(['Nagstamon/Servers/Alertmanager'])
        self.assertEqual(cm.exception.code, 0)

    def test_unit_alert_suppressed(self):
        with open('tests/test_alertmanager_suppressed.json') as json_file:
            data = json.load(json_file)
        
        test_class = AlertmanagerServer()
        test_class.map_to_hostname = 'instance,pod_name,namespace'
        test_class.map_to_servicename = 'alertname'
        test_class.map_to_status_information = 'message,summary,description'
        test_class.map_to_unknwon = ''
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
        test_class.map_to_unknwon = ''
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
        test_class.map_to_unknwon = ''
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
        self.assertEqual(test_result['status'], 'ERROR')
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
        test_class.map_to_unknwon = ''
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
        self.assertEqual(test_result['status'], 'ERROR')
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
        test_class.map_to_unknwon = 'unknown'
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


if __name__ == '__main__':
    unittest.main()
