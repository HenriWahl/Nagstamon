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

from Nagstamon.qui.qt import (QUrl,
                              Slot,
                              WebEngineView)
from Nagstamon.qui.dialogs.dialog import Dialog


class DialogWebLogin(Dialog):
    """
    small dialog for web login
    """

    def __init__(self):
        Dialog.__init__(self, 'dialog_weblogin',)
        self.webengine_view = WebEngineView()


    @Slot(str)
    def initialize(self):
        """

        """
        self.webengine_view.loadStarted.connect(self.on_load_started)
        self.webengine_view.loadFinished.connect(self.on_load_finished)
        self.window.vbox.addWidget(self.webengine_view)

    @Slot()
    def slot_test(self):
        """
        ...
        """
        print('slot_test weblogin')

    @Slot(str, str)
    def set_url(self, server_name, url):
        """
        set url to load
        """
        self.window.setWindowTitle('Nagstamon Web Login - ' + server_name)
        self.webengine_view.setUrl(QUrl(url))

    def on_load_started(self):
        print('weblogin load started', self.webengine_view.url())

    def on_load_finished(self):
        print('weblogin load finished')