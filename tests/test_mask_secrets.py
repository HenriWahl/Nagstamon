"""
Tests for hiding secrets in the debug log
"""

import json
import unittest

from Nagstamon.servers.Generic import mask_secrets


class test_mask_secrets(unittest.TestCase):

    def test_login_password_is_masked(self):
        payload = json.dumps({'method': 'user.login', 'params': {'username': 'someuser', 'password': 'hunter2'}})
        masked = mask_secrets(payload)
        self.assertNotIn('hunter2', masked)
        self.assertIn('someuser', masked)
        self.assertIn('user.login', masked)

    def test_session_id_and_token_are_masked(self):
        for key, secret in (('sessionid', 'abc123'), ('token', 'tok456'), ('secret', 'sec789')):
            with self.subTest(key=key):
                masked = mask_secrets(json.dumps({'method': 'x', 'params': {key: secret, 'extend': False}}))
                self.assertNotIn(secret, masked)
                self.assertIn('extend', masked)

    def test_payload_without_secrets_is_unchanged(self):
        payload = '{"method": "problem.get", "params": {"recent": false}}'
        self.assertEqual(mask_secrets(payload), payload)


if __name__ == '__main__':
    unittest.main()
