"""
Saving the configuration must not write unchanged passwords into the system keyring again.

On macOS writing a password replaces the keychain entry, which may ask the user for
permission and blocks the main thread meanwhile - at every start and at every quit.
A fake keyring is used, so the real one of the machine running the tests stays untouched.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Ensure repository root is on sys.path first so imports use local source tree
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from Nagstamon import config as config_module

MONITOR_URL = 'https://monitor.example.com/nagios'
ACCOUNT = f'user@{MONITOR_URL}'


class FakeKeyring:
    def __init__(self, passwords):
        self.passwords = dict(passwords)
        self.writes = list()

    def get_password(self, service, account):
        return self.passwords.get(account)

    def set_password(self, service, account, password):
        self.writes.append(account)
        self.passwords[account] = password

    def delete_password(self, service, account):
        self.passwords.pop(account, None)

    def get_keyring(self):
        return self


class TestKeyringSave(unittest.TestCase):

    def setUp(self):
        self.configdir = Path(tempfile.mkdtemp())
        (self.configdir / 'servers').mkdir()
        # the flag left by the Nagstamon 3.4 migration makes loading the config save it
        (self.configdir / 'nagstamon.conf').write_text('[Nagstamon]\n'
                                                       'use_system_keyring = True\n'
                                                       'save_config_after_urlencode = True\n')
        obfuscated_user = config_module.conf.obfuscate('user')
        obfuscated_empty = config_module.conf.obfuscate('')
        (self.configdir / 'servers' / 'server_Test.conf').write_text('[server_Test]\n'
                                                                     'enabled = True\n'
                                                                     'type = Nagios\n'
                                                                     'name = Test\n'
                                                                     f'monitor_url = {MONITOR_URL}\n'
                                                                     f'username = {obfuscated_user}\n'
                                                                     'password = \n'
                                                                     'save_password = True\n'
                                                                     f'proxy_username = {obfuscated_empty}\n'
                                                                     f'proxy_password = {obfuscated_empty}\n')
        self.keyring = FakeKeyring({ACCOUNT: 'secret'})
        for patcher in (mock.patch.object(sys, 'argv', ['nagstamon', str(self.configdir)]),
                        mock.patch.object(config_module, 'keyring', self.keyring, create=True),
                        mock.patch.object(config_module.Config, 'is_keyring_available', return_value=True),
                        mock.patch.dict(config_module.keyring_passwords, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_unchanged_password_is_not_written_again(self):
        conf = config_module.Config()
        self.assertEqual(conf.servers['Test'].password, 'secret')
        conf.save_config()
        conf.save_config()
        self.assertEqual(self.keyring.writes, [])

    def test_changed_password_is_written_once(self):
        conf = config_module.Config()
        conf.servers['Test'].password = 'new secret'
        conf.save_config()
        conf.save_config()
        self.assertEqual(self.keyring.writes, [ACCOUNT])
        self.assertEqual(self.keyring.passwords[ACCOUNT], 'new secret')

    def test_migration_flag_does_not_survive_saving(self):
        config_module.Config()
        self.assertNotIn('save_config_after_urlencode', (self.configdir / 'nagstamon.conf').read_text())


if __name__ == '__main__':
    unittest.main()
