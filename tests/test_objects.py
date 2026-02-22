"""
Tests for the core domain objects: GenericObject, GenericHost, GenericService, Result.
"""
import unittest

from Nagstamon.objects import GenericHost, GenericObject, GenericService, Result


class TestGenericObjectFlags(unittest.TestCase):

    def setUp(self):
        self.obj = GenericObject()

    def test_default_passiveonly_false(self):
        self.assertFalse(self.obj.is_passive_only())

    def test_passiveonly_true(self):
        self.obj.passiveonly = True
        self.assertTrue(self.obj.is_passive_only())

    def test_default_flapping_false(self):
        self.assertFalse(self.obj.is_flapping())

    def test_flapping_true(self):
        self.obj.flapping = True
        self.assertTrue(self.obj.is_flapping())

    def test_default_acknowledged_false(self):
        self.assertFalse(self.obj.is_acknowledged())

    def test_acknowledged_true(self):
        self.obj.acknowledged = True
        self.assertTrue(self.obj.is_acknowledged())

    def test_default_scheduled_downtime_false(self):
        self.assertFalse(self.obj.is_in_scheduled_downtime())

    def test_scheduled_downtime_true(self):
        self.obj.scheduled_downtime = True
        self.assertTrue(self.obj.is_in_scheduled_downtime())

    def test_default_visible_true(self):
        self.assertTrue(self.obj.is_visible())

    def test_visible_false(self):
        self.obj.visible = False
        self.assertFalse(self.obj.is_visible())

    def test_get_name_returns_string(self):
        self.obj.name = 'my-item'
        self.assertEqual(self.obj.get_name(), 'my-item')

    def test_get_name_stringifies_non_string(self):
        self.obj.name = 99
        self.assertEqual(self.obj.get_name(), '99')

    def test_get_host_name_returns_empty_on_base(self):
        self.assertEqual(self.obj.get_host_name(), '')

    def test_get_service_name_returns_empty_on_base(self):
        self.assertEqual(self.obj.get_service_name(), '')

    def test_get_hash_returns_empty_on_base(self):
        self.assertEqual(self.obj.get_hash(), '')


class TestGenericObjectGetColumns(unittest.TestCase):

    def setUp(self):
        self.obj = GenericObject()
        self.obj.name = 'item'
        self.obj.status = 'WARNING'
        self.obj.duration = '3h'

    def test_single_column(self):
        result = list(self.obj.get_columns(['name']))
        self.assertEqual(result, ['item'])

    def test_multiple_columns(self):
        result = list(self.obj.get_columns(['name', 'status', 'duration']))
        self.assertEqual(result, ['item', 'WARNING', '3h'])

    def test_columns_are_strings(self):
        self.obj.passiveonly = True
        result = list(self.obj.get_columns(['passiveonly']))
        self.assertIsInstance(result[0], str)


class TestGenericHost(unittest.TestCase):

    def setUp(self):
        self.host = GenericHost()
        self.host.name = 'web01'
        self.host.status = 'DOWN'
        self.host.server = 'nagios01'
        self.host.site = 'prod'

    def test_get_host_name(self):
        self.assertEqual(self.host.get_host_name(), 'web01')

    def test_is_host_returns_true(self):
        self.assertTrue(self.host.is_host())

    def test_get_service_name_empty(self):
        self.assertEqual(self.host.get_service_name(), '')

    def test_get_hash_includes_all_fields(self):
        h = self.host.get_hash()
        self.assertIn('nagios01', h)
        self.assertIn('prod', h)
        self.assertIn('web01', h)
        self.assertIn('DOWN', h)

    def test_get_hash_format(self):
        self.assertEqual(self.host.get_hash(), 'nagios01 prod web01 DOWN')

    def test_services_dict_initially_empty(self):
        self.assertEqual(self.host.services, {})


class TestGenericService(unittest.TestCase):

    def setUp(self):
        self.svc = GenericService()
        self.svc.name = 'check_ping'
        self.svc.host = 'web01'
        self.svc.status = 'CRITICAL'
        self.svc.server = 'nagios01'
        self.svc.site = 'prod'

    def test_get_host_name(self):
        self.assertEqual(self.svc.get_host_name(), 'web01')

    def test_get_service_name(self):
        self.assertEqual(self.svc.get_service_name(), 'check_ping')

    def test_is_host_returns_false(self):
        self.assertFalse(self.svc.is_host())

    def test_get_hash_format(self):
        self.assertEqual(self.svc.get_hash(), 'nagios01 prod web01 check_ping CRITICAL')

    def test_get_hash_includes_all_fields(self):
        h = self.svc.get_hash()
        self.assertIn('nagios01', h)
        self.assertIn('prod', h)
        self.assertIn('web01', h)
        self.assertIn('check_ping', h)
        self.assertIn('CRITICAL', h)

    def test_default_unreachable_false(self):
        self.assertFalse(self.svc.unreachable)


class TestResult(unittest.TestCase):

    def test_default_result_empty_string(self):
        r = Result()
        self.assertEqual(r.result, '')

    def test_default_error_empty_string(self):
        r = Result()
        self.assertEqual(r.error, '')

    def test_default_status_code_zero(self):
        r = Result()
        self.assertEqual(r.status_code, 0)

    def test_keyword_init(self):
        r = Result(result='OK', error='', status_code=200)
        self.assertEqual(r.result, 'OK')
        self.assertEqual(r.error, '')
        self.assertEqual(r.status_code, 200)

    def test_error_keyword(self):
        r = Result(result='FAIL', error='timeout', status_code=503)
        self.assertEqual(r.error, 'timeout')
        self.assertEqual(r.status_code, 503)

    def test_extra_keywords_stored(self):
        r = Result(content='body', custom_key='value')
        self.assertEqual(r.content, 'body')
        self.assertEqual(r.custom_key, 'value')


if __name__ == '__main__':
    unittest.main()
