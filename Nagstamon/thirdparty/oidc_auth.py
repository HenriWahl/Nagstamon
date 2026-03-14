# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

"""
OIDC authentication helper for Nagstamon.

Implements Authorization Code flow with PKCE via the system browser.
Auto-discovers the OIDC issuer from the server's login redirect.
Uses only stdlib + requests (no additional dependencies).
"""

import base64
import hashlib
import html
import json as _json
import secrets
import socket
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from Nagstamon.config import AppInfo, conf, debug_queue
import datetime

# User-Agent sent during OIDC discovery and token requests, identifying Nagstamon as an OIDC client
OIDC_USER_AGENT = f'NagstamonOIDC/{AppInfo.VERSION}'


def _debug(msg):
    """Log an OIDC debug message if debug_mode is enabled."""
    if conf.debug_mode:
        debug_queue.append(f'DEBUG: {datetime.datetime.now()} [OIDC] {msg}')


class OIDCError(Exception):
    """Base exception for OIDC authentication errors."""
    pass


class OIDCTimeoutError(OIDCError):
    """Raised when the browser authentication times out."""
    pass


class OIDCDiscoveryError(OIDCError):
    """Raised when OIDC provider discovery fails."""
    pass


class OIDCTokenError(OIDCError):
    """Raised when token exchange or refresh fails."""
    pass


class TokenResult:
    """Holds the result of an OIDC token exchange or refresh."""

    def __init__(self, access_token, refresh_token=None, id_token=None, expires_at=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.id_token = id_token
        self.expires_at = expires_at


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler that captures the OIDC authorization code callback."""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        _debug(f'CallbackHandler: received {self.command} {parsed.path} (params: {list(params.keys())})')

        if parsed.path == '/callback':
            if 'error' in params:
                error = html.escape(params['error'][0])
                desc = html.escape(params.get('error_description', [''])[0])
                self.server.oidc_error = f'{error}: {desc}'
                self.server.oidc_code = None
                self._send_response('Authentication failed. You can close this tab.')
            elif 'code' in params:
                self.server.oidc_code = params['code'][0]
                self.server.oidc_state = params.get('state', [None])[0]
                self.server.oidc_error = None
                _debug(f'CallbackHandler: got code=<redacted>, state=<redacted>')
                self._send_response('Authentication successful! You can close this tab.')
            else:
                self.server.oidc_error = 'No authorization code received'
                self.server.oidc_code = None
                self._send_response('Authentication failed. You can close this tab.')
        else:
            self.send_error(404)
            return

        # signal the waiting thread that we received a response
        _debug(f'CallbackHandler: setting event (code={bool(self.server.oidc_code)}, error={self.server.oidc_error})')
        self.server.oidc_event.set()

    def _send_response(self, message):
        is_success = 'successful' in message.lower()
        icon = '&#10004;' if is_success else '&#10008;'
        color = '#2e7d32' if is_success else '#c62828'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        body = (
            '<!DOCTYPE html><html><head>'
            '<title>Nagstamon OIDC</title>'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<style>'
            'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;'
            '  display: flex; justify-content: center; align-items: center; min-height: 100vh;'
            '  margin: 0; background: #f5f5f5; color: #333; }'
            '.card { background: #fff; border-radius: 12px; padding: 48px; text-align: center;'
            '  box-shadow: 0 2px 12px rgba(0,0,0,0.1); max-width: 420px; }'
            f'.icon {{ font-size: 64px; color: {color}; margin-bottom: 16px; }}'
            f'h2 {{ color: {color}; margin: 0 0 12px; font-size: 22px; }}'
            'p { color: #666; margin: 0; font-size: 14px; }'
            '</style></head><body>'
            f'<div class="card"><div class="icon">{icon}</div>'
            f'<h2>{html.escape(message)}</h2>'
            '<p>This tab will close automatically...</p>'
            '</div>'
            '<script>setTimeout(function(){window.close();},3000);</script>'
            '</body></html>'
        )
        self.wfile.write(body.encode('utf-8'))

    def log_message(self, format, *args):
        # suppress default stderr logging
        pass


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge (S256) per RFC 7636."""
    # 64 bytes -> 86 chars base64url (well within the 43-128 range required by spec)
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return code_verifier, code_challenge


class _ReusableHTTPServer(HTTPServer):
    """HTTPServer with SO_REUSEADDR so the port is freed immediately after close."""
    allow_reuse_address = True
    allow_reuse_port = True


def discover_oidc_from_icingaweb2(monitor_url, session=None, timeout=15):
    """
    Auto-discover the OIDC issuer and endpoints from IcingaWeb2's login redirect.

    IcingaWeb2 configured with OIDC (e.g., mod_auth_openidc or its own OIDC module)
    will redirect the login page to Keycloak. We follow that redirect to extract
    the issuer URL, then fetch the .well-known/openid-configuration.

    Args:
        monitor_url: The IcingaWeb2 base URL (e.g., https://icinga.example.com/icingaweb2)
        session: Optional requests.Session for proxy/TLS settings
        timeout: Request timeout in seconds

    Returns:
        dict with keys: issuer, authorization_endpoint, token_endpoint, end_session_endpoint

    Raises:
        OIDCDiscoveryError if discovery fails
    """
    if session is None:
        session = requests.Session()

    session.headers['User-Agent'] = OIDC_USER_AGENT

    login_url = f'{monitor_url.rstrip("/")}/authentication/login'
    _debug(f'Discovery: fetching login page {login_url}')

    try:
        # Don't follow redirects, we need to capture the Location header
        response = session.get(login_url, allow_redirects=False, timeout=timeout)
        _debug(f'Discovery: login page returned status {response.status_code}')
    except requests.RequestException as e:
        raise OIDCDiscoveryError(f'Failed to connect to {login_url}: {e}')

    # Follow redirects manually to find the OIDC authorization endpoint
    redirect_url = None
    server_client_id = None
    max_redirects = 10
    current_response = response
    current_url = login_url
    for i in range(max_redirects):
        if current_response.status_code in (301, 302, 303, 307, 308):
            location = current_response.headers.get('Location', '')
            if not location:
                break
            # Resolve relative redirects against current URL
            if not location.startswith(('http://', 'https://')):
                from urllib.parse import urljoin
                location = urljoin(current_url, location)
            redirect_url = location
            _debug(f'Discovery: redirect #{i+1} -> {redirect_url}')

            # Stop at the first redirect that looks like an OIDC authorization endpoint
            # (detected by the presence of client_id in the query params, which is required by RFC 6749)
            redirect_parsed_check = urlparse(redirect_url)
            redirect_params_check = parse_qs(redirect_parsed_check.query)
            if 'client_id' in redirect_params_check:
                _debug(f'Discovery: found OIDC endpoint in redirect #{i+1}, stopping redirect chase')
                # Extract the server-side client_id from the redirect query params
                if 'client_id' in redirect_params_check:
                    server_client_id = redirect_params_check['client_id'][0]
                    _debug(f'Discovery: server-side client_id={server_client_id}')
                break

            try:
                current_url = redirect_url
                current_response = session.get(redirect_url, allow_redirects=False, timeout=timeout)
            except requests.RequestException:
                break
        else:
            break

    if not redirect_url:
        raise OIDCDiscoveryError(
            f'No OIDC redirect found at {login_url}. '
            'Make sure IcingaWeb2 is configured to redirect to your OIDC provider.'
        )

    # Extract the issuer URL from the redirect URL by stripping well-known OIDC path segments.
    # e.g. https://idp.example.com/realms/myrealm/protocol/openid-connect/auth -> https://idp.example.com/realms/myrealm
    #      https://idp.example.com/oauth2/v1/authorize                         -> https://idp.example.com/oauth2
    parsed = urlparse(redirect_url)
    path = parsed.path

    # Find the issuer base path, look for /protocol/openid-connect or /auth in the path
    issuer_path = path
    for marker in ('/protocol/openid-connect', '/.well-known'):
        idx = path.find(marker)
        if idx != -1:
            issuer_path = path[:idx]
            break

    issuer_url = f'{parsed.scheme}://{parsed.netloc}{issuer_path}'
    _debug(f'Discovery: extracted issuer URL: {issuer_url}')

    # Fetch the OIDC well-known configuration
    well_known_url = f'{issuer_url}/.well-known/openid-configuration'
    _debug(f'Discovery: fetching well-known config from {well_known_url}')
    try:
        wk_response = session.get(well_known_url, timeout=timeout)
        wk_response.raise_for_status()
        oidc_config = wk_response.json()
        _debug(f'Discovery: got OIDC config with endpoints: auth={oidc_config.get("authorization_endpoint")}, token={oidc_config.get("token_endpoint")}')
    except (requests.RequestException, ValueError) as e:
        raise OIDCDiscoveryError(f'Failed to fetch OIDC configuration from {well_known_url}: {e}')

    required_keys = ['authorization_endpoint', 'token_endpoint']
    for key in required_keys:
        if key not in oidc_config:
            raise OIDCDiscoveryError(f'OIDC configuration missing required key: {key}')

    return {
        'issuer': oidc_config.get('issuer', issuer_url),
        'authorization_endpoint': oidc_config['authorization_endpoint'],
        'token_endpoint': oidc_config['token_endpoint'],
        'end_session_endpoint': oidc_config.get('end_session_endpoint', ''),
        'server_client_id': server_client_id,
    }


class OIDCAuthenticator:
    """
    Handles OIDC Authorization Code flow with PKCE via the system browser.

    Usage:
        authenticator = OIDCAuthenticator(
            authorization_endpoint='https://idp.example.com/oauth2/authorize',
            token_endpoint='https://idp.example.com/oauth2/token',
            client_id='nagstamon',
            redirect_port=12345,
        )
        result = authenticator.authenticate()
        # result.access_token, result.refresh_token, result.expires_at
    """

    def __init__(self, authorization_endpoint, token_endpoint, client_id='nagstamon',
                 redirect_port=12345, scope='openid', session=None):
        self.authorization_endpoint = authorization_endpoint
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.redirect_port = redirect_port
        self.scope = scope
        self.session = session or requests.Session()
        self.session.headers['User-Agent'] = OIDC_USER_AGENT

    def authenticate(self, timeout=120):
        """
        Run the full OIDC Authorization Code + PKCE flow.

        1. Start a local HTTP server for the callback
        2. Open the system browser to the authorization URL
        3. Wait for the callback with the authorization code
        4. Exchange the code for tokens

        Args:
            timeout: Seconds to wait for the user to complete authentication

        Returns:
            TokenResult with access_token, refresh_token, id_token, expires_at

        Raises:
            OIDCTimeoutError if the user doesn't complete auth within timeout
            OIDCTokenError if token exchange fails
        """
        code_verifier, code_challenge = _generate_pkce()
        state = secrets.token_urlsafe(32)

        port = self.redirect_port
        redirect_uri = f'http://localhost:{port}/callback'

        # Build authorization URL
        auth_params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': self.scope,
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }
        auth_url = f'{self.authorization_endpoint}?{urlencode(auth_params)}'
        _debug(f'Authenticate: starting callback server on port {port}')
        _debug(f'Authenticate: authorization URL: {self.authorization_endpoint} (client_id={self.client_id})')

        # Start local callback server (SO_REUSEADDR ensures port is freed immediately)
        try:
            server = _ReusableHTTPServer(('127.0.0.1', port), _CallbackHandler)
        except OSError as e:
            raise OIDCError(
                f'Port {port} is already in use — another OIDC login may be in progress. '
                f'Please wait for it to finish or close the previous browser tab.'
            ) from e
        server.oidc_code = None
        server.oidc_state = None
        server.oidc_error = None
        server.oidc_event = threading.Event()
        server.timeout = 1  # handle_request timeout for clean shutdown

        # Run server in a background thread
        server_thread = threading.Thread(target=self._run_server, args=(server, timeout), daemon=True)
        server_thread.start()

        # Open the system browser
        _debug('Authenticate: opening system browser for login')
        webbrowser.open(auth_url)

        # Wait for the callback
        _debug(f'Authenticate: waiting up to {timeout}s for callback...')
        if not server.oidc_event.wait(timeout=timeout):
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)
            raise OIDCTimeoutError(f'Authentication timed out after {timeout} seconds')

        _debug(f'Authenticate: event fired, code={bool(server.oidc_code)}, error={server.oidc_error}')
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        _debug('Authenticate: server thread joined')

        if server.oidc_error:
            _debug(f'Authenticate: error from callback: {server.oidc_error}')
            raise OIDCError(f'Authentication error: {server.oidc_error}')

        if not server.oidc_code:
            raise OIDCError('No authorization code received')

        # Validate state
        if server.oidc_state != state:
            _debug('Authenticate: state mismatch!')
            raise OIDCError('State mismatch — possible CSRF attack')

        _debug('Authenticate: received authorization code, exchanging for tokens...')
        # Exchange authorization code for tokens
        return self._exchange_code(server.oidc_code, redirect_uri, code_verifier)

    def _run_server(self, server, timeout):
        """Run the HTTP server until shutdown() is called."""
        server.serve_forever(poll_interval=0.5)

    def _exchange_code(self, code, redirect_uri, code_verifier):
        """Exchange authorization code for tokens at the token endpoint."""
        _debug(f'TokenExchange: posting to {self.token_endpoint}')
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier,
        }
        try:
            response = self.session.post(self.token_endpoint, data=token_data, timeout=15)
            _debug(f'TokenExchange: response status {response.status_code}')
            response.raise_for_status()
            token_json = response.json()
        except (requests.RequestException, ValueError) as e:
            _debug(f'TokenExchange: failed: {e}')
            raise OIDCTokenError(f'Token exchange failed: {e}')

        access_token = token_json.get('access_token')
        if not access_token:
            _debug(f'TokenExchange: no access_token in response keys: {list(token_json.keys())}')
            raise OIDCTokenError('No access_token in token response')

        expires_in = token_json.get('expires_in', 300)
        expires_at = time.time() + int(expires_in)
        _debug(f'TokenExchange: success, expires_in={expires_in}s, has_refresh={bool(token_json.get("refresh_token"))}')

        return TokenResult(
            access_token=access_token,
            refresh_token=token_json.get('refresh_token'),
            id_token=token_json.get('id_token'),
            expires_at=expires_at,
        )

    def refresh(self, refresh_token):
        """
        Use a refresh_token to obtain a new access_token.

        Args:
            refresh_token: The refresh token from a previous authentication

        Returns:
            TokenResult with new access_token, refresh_token, expires_at

        Raises:
            OIDCTokenError if refresh fails
        """
        _debug(f'TokenRefresh: refreshing token at {self.token_endpoint}')
        token_data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'refresh_token': refresh_token,
        }
        try:
            response = self.session.post(self.token_endpoint, data=token_data, timeout=15)
            _debug(f'TokenRefresh: response status {response.status_code}')
            response.raise_for_status()
            token_json = response.json()
        except (requests.RequestException, ValueError) as e:
            _debug(f'TokenRefresh: failed: {e}')
            raise OIDCTokenError(f'Token refresh failed: {e}')

        access_token = token_json.get('access_token')
        if not access_token:
            raise OIDCTokenError('No access_token in refresh response')

        expires_in = token_json.get('expires_in', 300)
        expires_at = time.time() + int(expires_in)
        _debug(f'TokenRefresh: success, expires_in={expires_in}s')

        return TokenResult(
            access_token=access_token,
            refresh_token=token_json.get('refresh_token', refresh_token),
            id_token=token_json.get('id_token'),
            expires_at=expires_at,
        )


class OIDCBearerAuth(requests.auth.AuthBase):
    """
    requests-compatible auth handler that uses OIDC Bearer tokens
    with automatic refresh before expiry.

    Can be constructed either with an OIDCAuthenticator instance or with
    explicit token_endpoint/client_id for restoring from persisted tokens.
    """

    def __init__(self, access_token, refresh_token, expires_at,
                 authenticator=None, token_endpoint=None, client_id=None,
                 on_token_refreshed=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.on_token_refreshed = on_token_refreshed
        self._lock = threading.Lock()

        if authenticator is not None:
            self.authenticator = authenticator
        elif token_endpoint:
            # Create a minimal authenticator from persisted data
            self.authenticator = OIDCAuthenticator(
                authorization_endpoint='',
                token_endpoint=token_endpoint,
                client_id=client_id or 'nagstamon',
            )
        else:
            self.authenticator = None

    def __call__(self, r):
        with self._lock:
            # Auto-refresh if token expires within 60 seconds
            if (self.refresh_token and self.authenticator and
                    self.expires_at and (time.time() > self.expires_at - 60)):
                remaining = self.expires_at - time.time()
                _debug(f'BearerAuth: token expires in {remaining:.0f}s, refreshing...')
                try:
                    result = self.authenticator.refresh(self.refresh_token)
                    self.access_token = result.access_token
                    self.refresh_token = result.refresh_token or self.refresh_token
                    self.expires_at = result.expires_at
                    _debug(f'BearerAuth: token refreshed, new expiry in {result.expires_at - time.time():.0f}s')
                    # Notify persistence layer about refreshed tokens
                    if self.on_token_refreshed:
                        self.on_token_refreshed({
                            'access_token': self.access_token,
                            'refresh_token': self.refresh_token,
                            'id_token': '',
                            'expires_at': self.expires_at,
                            'token_endpoint': self.authenticator.token_endpoint,
                            'authorization_endpoint': self.authenticator.authorization_endpoint,
                            'client_id': self.authenticator.client_id,
                        })
                except OIDCTokenError as e:
                    _debug(f'BearerAuth: refresh failed: {e}')
                    # refresh failed, continue with current token, server will get 401
                    pass

        # Debug: decode JWT payload to show claims (no crypto verification)
        if conf.debug_mode:
            try:
                parts = self.access_token.split('.')
                if len(parts) >= 2:
                    # Fix base64 padding
                    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
                    payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
                    _debug(f'BearerAuth: JWT claims: iss={payload.get("iss")}, '
                           f'aud={payload.get("aud")}, azp={payload.get("azp")}, '
                           f'exp={payload.get("exp")}')
            except Exception as e:
                _debug(f'BearerAuth: could not decode JWT: {e}')

        r.headers['Authorization'] = f'Bearer {self.access_token}'
        r.headers['X-OAuth2'] = '1'
        return r
