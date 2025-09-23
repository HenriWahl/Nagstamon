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
import os

from PyQt6.QtGui import QWindow

from Nagstamon.cookies import (cookie_data_to_jar,
                               load_cookies,
                               save_cookies)
from Nagstamon.helpers import USER_AGENT
from Nagstamon.qui.qt import (QNetworkProxy,
                              QNetworkProxyFactory,
                              Qt,
                              QUrl,
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

    show_up = Signal()

    page_loaded = Signal()

    def __init__(self):
        Dialog.__init__(self, 'dialog_weblogin', )
        self.cookie_store = None
        self.page = None
        self.profile = None
        self.proxy = None
        # self.webengine_view = WebEngineView()
        self.webengine_view = None

        self.cookies = dict()


    @Slot(str, str)
    def set_url(self, server_name, url):
        """
        set url to load
        """

        server = servers.get(server_name)

    def on_load_finished(self):
        """
        send message when page is loaded so the statuswindow can refresh
        """
        print('load finished')
        if self.server:
            print('emit signal page_loaded')
            self.page_loaded.emit()

    @Slot(str)
    def show_browser(self, server_name):
        """
        initialize and show authentication browser window
        """
        self.show_up.emit()

        self.server = servers[server_name]

        self.proxy = QNetworkProxy()

        if self.server.use_proxy:
            QNetworkProxyFactory.setUseSystemConfiguration(False)
            self.proxy.setType(QNetworkProxy.ProxyType.HttpProxy)
            if self.server.use_proxy_from_os:
                QNetworkProxyFactory.setUseSystemConfiguration(True)
            else:
                self.proxy.setType(QNetworkProxy.ProxyType.HttpProxy)
                # kick out any protocol prefix
                host, port = self.server.proxy_address.split('https://')[-1].split('http://')[-1].split(':')
                # ...and any trailing path
                port = port.split('/')[0]
                self.proxy.setHostName(host)
                self.proxy.setPort(int(port))
                if self.server.proxy_username:
                    self.proxy.setUser(self.server.proxy_username)
                    self.proxy.setPassword(self.server.proxy_password)
                QNetworkProxy.setApplicationProxy(self.proxy)
        else:
            self.proxy.setType(QNetworkProxy.ProxyType.NoProxy)
            QNetworkProxy.setApplicationProxy(self.proxy)

        #reset webengine view if already existing - especially for proxy changes
        if self.page:
            self.page.deleteLater()
            self.page = None
        if self.webengine_view:
            self.webengine_view.close()
            self.window.vbox.removeWidget(self.webengine_view)
            self.webengine_view.destroy()
            self.webengine_view = None
        if self.profile:
            self.profile = None
        if self.cookie_store:
            self.cookie_store = None

        self.webengine_view = WebEngineView()
        self.window.button_reload.clicked.connect(self.webengine_view.reload)

        self.profile = WebEngineProfile.defaultProfile()
        self.profile.setHttpUserAgent(USER_AGENT)

        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self.handle_cookie_added)

        self.webengine_view.loadFinished.connect(self.on_load_finished)

        self.window.vbox.addWidget(self.webengine_view)

        self.window.setWindowTitle('Nagstamon Web Login - ' + server_name)
        self.page = WebEnginePage(ignore_tls_errors=self.server.ignore_cert)
        self.webengine_view.setPage(self.page)
        self.page.setUrl(QUrl(self.server.monitor_url))

        self.show()
        self.window.adjustSize()

        # the dock icon might be needed to be shown for a potential keyboard input
        self.check_macos_dock_icon_fix_show.emit()

        self.window.open()

        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.check_macos_dock_icon_fix_hide.emit()

        self.webengine_view.show()
        #self.page.triggerAction(WebEnginePage.WebAction.ReloadAndBypassCache)
        #self.webengine_view.reload()
        self.window.update()

    @Slot(str)
    def close_browser(self, server_name):
        """
        close browser window
        """
        # according to https://bugreports.qt.io/browse/QTBUG-128345 the QWebEngine can't be closed, so it will
        # run further in the background
        # this might be mitigated by only needing it once for initial login and cookie retrieval
        if hasattr(self, 'server') and \
                self.server.name == server_name:
            self.window.close()
            if self.page:
                self.page.deleteLater()
                self.page = None
            if self.webengine_view:
                self.window.vbox.removeWidget(self.webengine_view)
                self.webengine_view.destroy()
                self.webengine_view = None
            if self.profile:
                self.profile = None
            if self.cookie_store:
                self.cookie_store = None

            print('closed weblogin for', server_name)


    def handle_cookie_added(self, cookie):
        # load existing cookies from SQLite databases
        cookies = load_cookies()
        # extract relevant cookie data as dictionary
        cookie_data = {
            'name': cookie.name().data().decode(),
            'value': cookie.value().data().decode(),
            'domain': cookie.domain(),
            'path': cookie.path(),
            'expiration': cookie.expirationDate().toSecsSinceEpoch() if cookie.expirationDate().isValid() else None,
            'secure': cookie.isSecure(),
            'httponly': cookie.isHttpOnly(),
            'server': self.server.name
        }
        # Save cookie only if not already saved
        cookey = f"{self.server.name}+{cookie_data['domain']}+{cookie_data['path']}+{cookie_data['name']}"
        if cookie_data not in cookies.values():
            cookies[cookey] = cookie_data
            save_cookies(cookies)

        # update server cookies to jar format
        self.server.session.cookies = cookie_data_to_jar(self.server.name, cookies)