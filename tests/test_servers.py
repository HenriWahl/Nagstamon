"""
Tests for the generic server creation in Nagstamon.servers
"""

import unittest

from Nagstamon.config import Server, conf
from Nagstamon.servers import create_server


class test_create_server(unittest.TestCase):

    def make_config(self, **kwargs):
        server_conf = Server()
        server_conf.name = 'test'
        server_conf.type = 'Alertmanager'
        server_conf.enabled = True
        server_conf.monitor_url = 'http://localhost:9093'
        server_conf.authentication = 'basic'
        server_conf.username = 'someuser'
        server_conf.password = 'somepassword'
        server_conf.use_autologin = False
        for key, value in kwargs.items():
            setattr(server_conf, key, value)
        return server_conf

    def test_credentials_are_not_suppressed_without_saved_password(self):
        """
        issue #1212 - a server which does not save its password was created with
        refresh_authentication set, which makes fetch_url() send every request through a
        session without any credentials
        """
        server = create_server(self.make_config(save_password=False))
        self.assertFalse(server.refresh_authentication)

    def test_credentials_are_not_suppressed_with_saved_password(self):
        server = create_server(self.make_config(save_password=True))
        self.assertFalse(server.refresh_authentication)

    def test_session_carries_the_configured_credentials(self):
        server = create_server(self.make_config(save_password=False))
        session = server.create_session()
        self.assertEqual(session.auth, (b'someuser', b'somepassword'))

    def test_session_carries_a_bearer_token(self):
        server = create_server(self.make_config(save_password=False,
                                                authentication='bearer',
                                                password='sometoken'))
        session = server.create_session()
        self.assertEqual(session.auth.token, 'sometoken')


class test_create_zabbix_server(unittest.TestCase):
    """
    ZabbixServer.__init__() reads its configuration from conf.servers, so the
    configuration has to be registered there before the server is created
    """

    def setUp(self):
        server_conf = Server()
        server_conf.name = 'test-zabbix'
        server_conf.type = 'Zabbix'
        server_conf.enabled = True
        server_conf.monitor_url = 'http://localhost/zabbix'
        server_conf.authentication = 'basic'
        server_conf.username = 'someuser'
        server_conf.password = 'somepassword'
        server_conf.save_password = True
        server_conf.use_autologin = False
        self.server_conf = server_conf
        conf.servers[server_conf.name] = server_conf

    def tearDown(self):
        conf.servers.pop(self.server_conf.name, None)

    def test_credentials_are_not_suppressed(self):
        """
        a fresh Zabbix server used to set refresh_authentication in its constructor, which
        made fetch_url() drop the session and the GUI report an authentication problem
        before the first poll had even happened - init_http() calls check_authentication()
        on every poll and assigns the flag itself, so the constructor must not preset it
        """
        server = create_server(self.server_conf)
        self.assertFalse(server.refresh_authentication)


if __name__ == '__main__':
    unittest.main()
