import unittest

from Nagstamon.servers.Thruk import ThrukServer


class TestThrukStatesMapping(unittest.TestCase):

    def test_host_state_0_is_ok(self):
        self.assertEqual(ThrukServer.STATES_MAPPING['hosts'][0], 'OK')

    def test_host_state_1_is_down(self):
        self.assertEqual(ThrukServer.STATES_MAPPING['hosts'][1], 'DOWN')

    def test_host_state_2_is_unreachable(self):
        self.assertEqual(ThrukServer.STATES_MAPPING['hosts'][2], 'UNREACHABLE')

    def test_service_state_0_is_ok(self):
        self.assertEqual(ThrukServer.STATES_MAPPING['services'][0], 'OK')

    def test_service_state_1_is_warning(self):
        self.assertEqual(ThrukServer.STATES_MAPPING['services'][1], 'WARNING')

    def test_service_state_2_is_critical(self):
        self.assertEqual(ThrukServer.STATES_MAPPING['services'][2], 'CRITICAL')

    def test_service_state_3_is_unknown(self):
        self.assertEqual(ThrukServer.STATES_MAPPING['services'][3], 'UNKNOWN')


class TestThrukStatusMapping(unittest.TestCase):

    def test_ack_gif_maps_to_acknowledged(self):
        self.assertEqual(ThrukServer.STATUS_MAPPING['ack.gif'], 'acknowledged')

    def test_passiveonly_gif_maps_to_passiveonly(self):
        self.assertEqual(ThrukServer.STATUS_MAPPING['passiveonly.gif'], 'passiveonly')

    def test_disabled_gif_maps_to_passiveonly(self):
        self.assertEqual(ThrukServer.STATUS_MAPPING['disabled.gif'], 'passiveonly')

    def test_ndisabled_gif_maps_to_notifications_disabled(self):
        self.assertEqual(ThrukServer.STATUS_MAPPING['ndisabled.gif'], 'notifications_disabled')

    def test_downtime_gif_maps_to_scheduled_downtime(self):
        self.assertEqual(ThrukServer.STATUS_MAPPING['downtime.gif'], 'scheduled_downtime')

    def test_flapping_gif_maps_to_flapping(self):
        self.assertEqual(ThrukServer.STATUS_MAPPING['flapping.gif'], 'flapping')

    def test_all_mapped_values_are_valid_flag_names(self):
        valid_flags = {'acknowledged', 'passiveonly', 'notifications_disabled',
                       'scheduled_downtime', 'flapping'}
        for gif, flag in ThrukServer.STATUS_MAPPING.items():
            self.assertIn(flag, valid_flags, f'{gif!r} maps to unknown flag {flag!r}')


if __name__ == '__main__':
    unittest.main()
