"""
Tests for GenericServer class-level constants and BearerAuth that were not
covered by the earlier test_generic.py (which focused on instance methods).
"""
import unittest
from unittest.mock import MagicMock

from Nagstamon.servers.Generic import BearerAuth, GenericServer


class TestBearerAuth(unittest.TestCase):

    def setUp(self):
        self.auth = BearerAuth('mytoken123')

    def test_stores_token(self):
        self.assertEqual(self.auth.token, 'mytoken123')

    def test_adds_authorization_header(self):
        request = MagicMock()
        request.headers = {}
        self.auth(request)
        self.assertEqual(request.headers['Authorization'], 'Bearer mytoken123')

    def test_returns_the_request_object(self):
        request = MagicMock()
        request.headers = {}
        result = self.auth(request)
        self.assertIs(result, request)

    def test_bearer_prefix_is_correct(self):
        request = MagicMock()
        request.headers = {}
        self.auth(request)
        self.assertTrue(request.headers['Authorization'].startswith('Bearer '))

    def test_empty_token(self):
        auth = BearerAuth('')
        request = MagicMock()
        request.headers = {}
        auth(request)
        self.assertEqual(request.headers['Authorization'], 'Bearer ')


class TestGenericServerStatusMapping(unittest.TestCase):

    def test_ack_gif_maps_to_acknowledged(self):
        self.assertEqual(GenericServer.STATUS_MAPPING['ack.gif'], 'acknowledged')

    def test_passiveonly_gif_maps_to_passiveonly(self):
        self.assertEqual(GenericServer.STATUS_MAPPING['passiveonly.gif'], 'passiveonly')

    def test_disabled_gif_maps_to_passiveonly(self):
        self.assertEqual(GenericServer.STATUS_MAPPING['disabled.gif'], 'passiveonly')

    def test_ndisabled_gif_maps_to_notifications_disabled(self):
        self.assertEqual(GenericServer.STATUS_MAPPING['ndisabled.gif'], 'notifications_disabled')

    def test_downtime_gif_maps_to_scheduled_downtime(self):
        self.assertEqual(GenericServer.STATUS_MAPPING['downtime.gif'], 'scheduled_downtime')

    def test_flapping_gif_maps_to_flapping(self):
        self.assertEqual(GenericServer.STATUS_MAPPING['flapping.gif'], 'flapping')

    def test_all_values_are_known_flags(self):
        valid_flags = {
            'acknowledged', 'passiveonly', 'notifications_disabled',
            'scheduled_downtime', 'flapping'
        }
        for gif, flag in GenericServer.STATUS_MAPPING.items():
            self.assertIn(flag, valid_flags,
                          f'{gif!r} maps to unknown flag {flag!r}')


class TestGenericServerConstants(unittest.TestCase):

    def test_type_is_generic(self):
        self.assertEqual(GenericServer.TYPE, 'Generic')

    def test_status_codes_no_auth_contains_401(self):
        self.assertIn(401, GenericServer.STATUS_CODES_NO_AUTH)

    def test_status_codes_no_auth_contains_403(self):
        self.assertIn(403, GenericServer.STATUS_CODES_NO_AUTH)

    def test_browser_urls_has_required_keys(self):
        for key in ('monitor', 'hosts', 'services', 'history'):
            self.assertIn(key, GenericServer.BROWSER_URLS)

    def test_menu_actions_contains_recheck(self):
        self.assertIn('Recheck', GenericServer.MENU_ACTIONS)

    def test_menu_actions_contains_acknowledge(self):
        self.assertIn('Acknowledge', GenericServer.MENU_ACTIONS)

    def test_menu_actions_contains_downtime(self):
        self.assertIn('Downtime', GenericServer.MENU_ACTIONS)

    def test_submit_check_result_args_contains_check_output(self):
        self.assertIn('check_output', GenericServer.SUBMIT_CHECK_RESULT_ARGS)


if __name__ == '__main__':
    unittest.main()
