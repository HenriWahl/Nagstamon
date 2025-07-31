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

from Nagstamon.qui.widgets.dialogs.dialog import Dialog


class DialogServerMissing(Dialog):
    """
    small dialog to ask about disabled ot not configured servers
    """

    def __init__(self):
        Dialog.__init__(self, 'dialog_server_missing')

        # hide dialog when server is to be created or enabled
        self.window.button_create_server.clicked.connect(self.window.hide)
        self.window.button_enable_server.clicked.connect(self.window.hide)
        self.window.button_ignore.clicked.connect(self.ok)
        # simply hide the window if ignore button chosen
        self.window.button_ignore.clicked.connect(self.window.hide)
        self.window.button_ignore.clicked.connect(self.cancel)
        # bye bye if exit button was pressed
        self.window.button_exit.clicked.connect(self.window.hide)
        self.window.button_exit.clicked.connect(exit)

    def initialize(self, mode='no_server'):
        """
        use dialog for missing and not enabled servers, depending on mode
        """
        if mode == 'no_server':
            self.window.label_no_server_configured.show()
            self.window.label_no_server_enabled.hide()
            self.window.button_enable_server.hide()
            self.window.button_create_server.show()
        else:
            self.window.label_no_server_configured.hide()
            self.window.label_no_server_enabled.show()
            self.window.button_enable_server.show()
            self.window.button_create_server.hide()