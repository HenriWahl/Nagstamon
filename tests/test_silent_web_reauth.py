"""
Tests for silent renewal of web authentication sessions via SSO auto-submit forms.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from Nagstamon.servers.Generic import GenericServer

IDP_URL = 'https://login.microsoftonline.com/tenant/saml2'
ACS_URL = 'https://monitor.example.com/main/check_mk/saml_acs.py?acs'

SSO_FORM = f'''<html><body>
<form method="POST" name="hiddenform" action="{ACS_URL}">
<input type="hidden" name="SAMLResponse" value="PHNhbWw+" />
<input type="hidden" name="RelayState" value="entra,index.py" />
</form></body></html>'''

LOGIN_PAGE = '<html><body><form action="/common/login"><input name="loginfmt" /></form></body></html>'

BSSO_INTERRUPT_PAGE = '''<html><head><meta name="PageID" content="BssoInterrupt" />
<script>$Config={"pgid":"BssoInterrupt","urlPost":"/tenant/saml2?sso_nonce=NONCE","oPostParams":{"SAMLRequest":"PD94"}};
</script></head><body></body></html>'''


def fake_response(url, text='', status_code=200):
    response = mock.Mock()
    response.url = url
    response.text = text
    response.status_code = status_code
    response.is_redirect = False
    return response


@mock.patch('Nagstamon.servers.Generic.get_sso_cookies', return_value={'x-ms-RefreshTokenCredential': 'prt'})
class TestSilentWebReauthentication(unittest.TestCase):

    def setUp(self):
        self.server = GenericServer()
        self.server.name = 'test'
        self.server.authentication = 'web'
        self.server.session = mock.Mock()
        self.server.session.cookies = []

    @mock.patch('Nagstamon.servers.Generic.save_jar_cookies')
    def test_posts_sso_result_and_saves_cookies(self, save_jar_cookies, get_sso_cookies):
        self.server.session.request.return_value = fake_response('https://monitor.example.com/main/check_mk/index.py')
        self.assertTrue(self.server.silent_web_reauthentication(fake_response(IDP_URL, SSO_FORM)))
        self.server.session.request.assert_called_once_with(
            'POST', ACS_URL, data={'SAMLResponse': 'PHNhbWw+', 'RelayState': 'entra,index.py'}, cookies={},
            allow_redirects=False, timeout=self.server.timeout)
        save_jar_cookies.assert_called_once()

    @mock.patch('Nagstamon.servers.Generic.save_jar_cookies')
    def test_interactive_login_page_fails(self, save_jar_cookies, get_sso_cookies):
        self.server.session.request.return_value = fake_response(IDP_URL, LOGIN_PAGE)
        self.assertFalse(self.server.silent_web_reauthentication(fake_response(IDP_URL, LOGIN_PAGE)))
        # one retry with Windows SSO cookies, then give up
        self.server.session.request.assert_called_once_with(
            'GET', IDP_URL, data=None, cookies={'x-ms-RefreshTokenCredential': 'prt'},
            allow_redirects=False, timeout=self.server.timeout)
        save_jar_cookies.assert_not_called()

    @mock.patch('Nagstamon.servers.Generic.save_jar_cookies')
    def test_rejected_sso_result_fails(self, save_jar_cookies, get_sso_cookies):
        self.server.session.request.return_value = fake_response(ACS_URL, status_code=403)
        self.assertFalse(self.server.silent_web_reauthentication(fake_response(IDP_URL, SSO_FORM)))
        save_jar_cookies.assert_not_called()

    @mock.patch('Nagstamon.servers.Generic.save_jar_cookies')
    def test_bsso_interrupt_is_answered_with_nonce(self, save_jar_cookies, get_sso_cookies):
        self.server.session.request.side_effect = [fake_response(IDP_URL, SSO_FORM),
                                                   fake_response('https://monitor.example.com/main/check_mk/index.py')]
        self.assertTrue(self.server.silent_web_reauthentication(fake_response(IDP_URL, BSSO_INTERRUPT_PAGE)))
        first_call = self.server.session.request.call_args_list[0]
        self.assertEqual(first_call.args, ('POST', 'https://login.microsoftonline.com/tenant/saml2?sso_nonce=NONCE'))
        self.assertEqual(first_call.kwargs['data'], {'SAMLRequest': 'PD94'})
        get_sso_cookies.assert_called_with('https://login.microsoftonline.com/tenant/saml2?sso_nonce=NONCE')

    def test_fetch_url_retries_after_silent_reauthentication(self, get_sso_cookies):
        data_url = 'https://monitor.example.com/main/check_mk/view.py'
        self.server.session.get.side_effect = [fake_response(IDP_URL, SSO_FORM),
                                               fake_response(data_url, 'data')]
        with mock.patch.object(self.server, 'silent_web_reauthentication', return_value=True) as reauth:
            result = self.server.fetch_url(data_url, giveback='raw')
        reauth.assert_called_once()
        self.assertEqual(result.result, 'data')
        self.assertEqual(result.status_code, 200)

    def test_fetch_url_reports_401_when_silent_reauthentication_fails(self, get_sso_cookies):
        self.server.session.get.return_value = fake_response(IDP_URL, LOGIN_PAGE)
        with mock.patch.object(self.server, 'silent_web_reauthentication', return_value=False):
            result = self.server.fetch_url('https://monitor.example.com/main/check_mk/view.py', giveback='raw')
        self.assertEqual(result.status_code, 401)


if __name__ == '__main__':
    unittest.main()
