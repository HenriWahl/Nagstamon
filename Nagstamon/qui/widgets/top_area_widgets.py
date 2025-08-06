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
from Nagstamon.helpers import webbrowser_open
from Nagstamon.qui.qt import (QComboBox,
                              Signal,
                              Slot)
from Nagstamon.qui.widgets.button import Button
from Nagstamon.Servers import servers


class PushButtonBrowserURL(Button):
    """
    QPushButton for ServerVBox which opens certain URL if clicked
    """

    def __init__(self, text='', parent=None, server=None, url_type=''):
        Button.__init__(self, text, parent=parent)
        self.server = server
        self.url_type = url_type
        self.status_window = self.parentWidget().parentWidget()

    @Slot()
    def open_url(self):
        """
            open URL from BROWSER_URLS in webbrowser
        """
        # BROWSER_URLS come with $MONITOR$ instead of real monitor url - heritage from actions
        url = self.server.BROWSER_URLS[self.url_type]
        url = url.replace('$MONITOR$', self.server.monitor_url)
        url = url.replace('$MONITOR-CGI$', self.server.monitor_cgi_url)

        if conf.debug_mode:
            self.server.debug(server=self.server.get_name(), debug='Open {0} web page {1}'.format(self.url_type, url))

        # use Python method to open browser
        webbrowser_open(url)

        # hide status window to get screen space for browser
        if not conf.fullscreen and not conf.windowed:
            # TODO: shall become a signal
            self.status_window.hide_window()


class ComboBoxServers(QComboBox):
    """
    combobox which does lock status window so it does not close when opening combobox
    """
    monitor_opened = Signal()

    # flag to avoid silly focusOutEvent
    freshly_opened = False

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent=parent)
        # react to clicked monitor
        self.activated.connect(self.response)

    def mousePressEvent(self, event):
        # first click opens combobox popup
        self.freshly_opened = True
        # tell status window that there is no combobox anymore
        self.showPopup()

    def fill(self):
        """
        fill default order fields combobox with server names
        """
        self.clear()
        self.addItem('Go to monitor...')
        self.addItems(sorted([x.name for x in conf.servers.values() if x.enabled], key=str.lower))

    @Slot()
    def response(self):
        """
        response to activated item in servers combobox
        """
        if self.currentText() in servers:
            # open webbrowser with server URL
            webbrowser_open(servers[self.currentText()].monitor_url)

            # hide window to make room for webbrowser
            self.monitor_opened.emit()

        self.setCurrentIndex(0)


