# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
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

from Nagstamon.config import conf
from Nagstamon.helpers import USER_AGENT
from Nagstamon.qui.qt import (QUrl,
                              Signal,
                              Slot,
                              WebEngineCertificateError,
                              WebEnginePage,
                              WebEngineView,
                              WebEngineProfile)
from Nagstamon.qui.dialogs.dialog import Dialog
from Nagstamon.servers import servers


class WebEnginePage(WebEnginePage):
    def __init__(self, ignore_tls_errors=False, parent=None):
        super().__init__(parent)
        self.ignore_tls_errors = ignore_tls_errors
        self.certificateError.connect(self.handle_certificateError)

    @Slot(WebEngineCertificateError)
    def handle_certificateError(self, error):

        print("TLS error:", error.description())

        if self.ignore_tls_errors:
            error.acceptCertificate()
            return True
        return False

class DialogWebLogin(Dialog):
    """
    small dialog for web login
    """

    page_loaded = Signal()

    def __init__(self):
        Dialog.__init__(self, 'dialog_weblogin', )
        self.cookie_store = None
        self.profile = None
        self.page = None
        #self.webengine_view = WebEngineView()
        self.webengine_view = None

        self.cookies = dict()

    # @Slot(str)
    # def initialize(self):
    # #     """
    # #     ...
    # #     """
    # #     self.profile = WebEngineProfile.defaultProfile()
    # #     self.profile.setHttpUserAgent(USER_AGENT)
    # #     self.cookie_store = self.profile.cookieStore()
    #      self.cookies = dict()
    # #     self.webengine_view.loadStarted.connect(self.on_load_started)
    # #     self.webengine_view.loadFinished.connect(self.on_load_finished)
    # #
    # #     self.cookie_store.cookieAdded.connect(self.handle_cookie_added)
    # #
    # #     self.window.vbox.addWidget(self.webengine_view)

    @Slot(str, str)
    def set_url(self, server_name, url):
        """
        set url to load
        """

        if not self.webengine_view:
            self.webengine_view = WebEngineView()
            self.profile = WebEngineProfile.defaultProfile()
            self.profile.setHttpUserAgent(USER_AGENT)
            self.cookie_store = self.profile.cookieStore()
            self.webengine_view.loadStarted.connect(self.on_load_started)
            self.webengine_view.loadFinished.connect(self.on_load_finished)
            self.cookie_store.cookieAdded.connect(self.handle_cookie_added)
            self.window.vbox.addWidget(self.webengine_view)

        server = servers.get(server_name)
        if server:
            self.window.setWindowTitle('Nagstamon Web Login - ' + server_name)
            self.page = WebEnginePage(ignore_tls_errors=server.ignore_cert)
            self.webengine_view.setPage(self.page)
            self.page.setUrl(QUrl(url))

    def on_load_started(self):
        print('weblogin load started', self.webengine_view.url())

    def on_load_finished(self):
        print('weblogin load finished')
        self.page_loaded.emit()

    def handle_cookie_added(self, cookie):
        # Extrahiert relevante Cookie-Daten als Dictionary
        cookie_data = {
            'name': cookie.name().data().decode(),
            'value': cookie.value().data().decode(),
            'domain': cookie.domain(),
            'path': cookie.path(),
            'expiration': cookie.expirationDate().toSecsSinceEpoch() if cookie.expirationDate().isValid() else None,
            'secure': cookie.isSecure(),
            'httponly': cookie.isHttpOnly(),
        }
        # Fügt das Cookie nur hinzu, wenn es noch nicht gespeichert wurde
        cookey = f'{cookie.domain()}+{cookie.name().data().decode()}'
        if cookie_data not in self.cookies.values():
            self.cookies[cookey] = cookie_data
            # save_cookies(cookies)
            print("Cookie gespeichert:", cookie_data['name'], cookie_data['value'])
            self.server.session.cookies.set(
                name=cookie_data['name'],
                value=cookie_data['value'],
                domain=cookie_data['domain'],
                expires=cookie_data['expiration'],
                path=cookie_data['path'],
                secure=cookie_data['secure'],
                rest={'HttpOnly': cookie_data['httponly']}
            )


    @Slot(str)
    def show_browser(self, server):
        """
        initialize and show authentication browser window
        """

        self.server = servers[server]
        self.set_url(self.server.name, self.server.monitor_url)
        self.show()
        self.window.adjustSize()

        # the dock icon might be needed to be shown for a potential keyboard input
        self.check_macos_dock_icon_fix_show.emit()

        self.window.exec()

        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.check_macos_dock_icon_fix_hide.emit()

    @Slot()
    def close_browser(self):
        """
        close browser window
        """
        # according to https://bugreports.qt.io/browse/QTBUG-128345 the QWebEngine can't be closed, so it will
        # run further in the background
        # this might be mitigated by only needing it once for initial login and cookie retrieval
        self.window.close()
        self.webengine_view.close()
