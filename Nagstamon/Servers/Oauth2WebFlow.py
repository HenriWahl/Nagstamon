"""Oauth2 Authorization Code Grant/Web Application Flow/Standard Flow with local webserver."""
import requests
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from requests_oauthlib import OAuth2Session
import logging

from Nagstamon.Helpers import webbrowser_open

log = logging.getLogger(__name__)


class LocalOauthServer(http.server.BaseHTTPRequestHandler):

    """Local Oauth server to receive authorization code."""

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)
        if not hasattr(server, "code"):
            server.code = None

    def do_GET(self):
        url_parse = urlparse(self.path)
        params = parse_qs(url_parse.query)
        if "code" in params:
            self.server.code = params["code"][0]
            print(params["code"][0])
        self.protocol_version = 'HTTP/1.1'
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(
            "<html><head><title>Nagstamon Oauth Login</title>"
            "<script>window.close()</script></head>"
            "<body>You have logged in Nagstamon. You can close this window.</body></html>",
            'UTF-8'))


class OauthTcpServer(socketserver.TCPServer):

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        self.allow_reuse_address = True     # we will restart this server frequently
        self.code = None                    # used to store Oauth code from handler
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)


def get_oauth2_session(client_id, client_secret, openid_config_url, port: int, timeout: int = 180) -> OAuth2Session:
    """Login via Oauth2 and return an authenticated session."""
    redirect_uri = "http://localhost:{}/".format(port)

    openid_configuration = requests.get(openid_config_url).json()
    oauth = OAuth2Session(client_id=client_id,
                          redirect_uri=redirect_uri,
                          auto_refresh_kwargs={
                              "client_id": client_id,
                              "client_secret": client_secret
                          },
                          auto_refresh_url=openid_configuration["token_endpoint"],
                          token_updater=lambda x: None
                          )
    authorization_url, state = oauth.authorization_url(openid_configuration["authorization_endpoint"])

    server = OauthTcpServer(("localhost", port), LocalOauthServer)
    server.timeout = 10
    max_tries = 10
    tries = max_tries

    log.debug("Starting local webserver and opening OAuth provider in browser")
    with server as httpd:
        while server.code is None and tries > 0:
            webbrowser_open(authorization_url, new=2)
            httpd.handle_request()
            tries -= 1

    if server.code is None:
        log.warning("Login timed out (%ss) after %s tries.", timeout, max_tries)
        raise TimeoutError("Login timed out (%ss).")
    else:
        log.debug("Received auth code.")

    oauth.fetch_token(token_url=openid_configuration["token_endpoint"],
                      code=server.code,
                      client_secret=client_secret)
    log.debug("Fetched token. Authenticated successfully.")

    return oauth
