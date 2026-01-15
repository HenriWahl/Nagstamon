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

from Nagstamon.config import conf
from Nagstamon.helpers import webbrowser_open
from Nagstamon.qui.qt import (QComboBox,
                              Signal,
                              Slot)
from Nagstamon.servers import servers


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


