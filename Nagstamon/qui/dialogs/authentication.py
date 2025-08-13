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
from Nagstamon.qui.dialogs.dialog import Dialog
from Nagstamon.qui.qt import (Signal,
                              Slot)
from Nagstamon.Servers import servers

class DialogAuthentication(Dialog):
    """
    dialog for authentication
    """
    # store server
    server = None

    # signal for telling server_vbox label to update
    update = Signal(str)

    # signal to tell the world that the authentication dialog will show up
    show_up = Signal()

    def __init__(self):
        Dialog.__init__(self, 'dialog_authentication')

    def initialize(self):
        """
        setup dialog fitting to server
        """
        if self.server is not None:

            self.window.setWindowTitle('Authenticate {0}'.format(self.server.name))
            if self.server.type in ['Centreon', 'Thruk']:
                self.window.input_checkbox_use_autologin.show()
                self.window.input_lineedit_autologin_key.show()
                self.window.input_lineedit_autologin_key.show()
                self.window.label_autologin_key.show()
                # enable switching autologin key and password
                self.window.input_checkbox_use_autologin.clicked.connect(self.toggle_autologin)
                self.window.input_checkbox_use_autologin.setChecked(self.server.use_autologin)
                self.window.input_lineedit_autologin_key.setText(self.server.autologin_key)
                # initialize autologin
                self.toggle_autologin()
            else:
                self.window.input_checkbox_use_autologin.hide()
                self.window.input_lineedit_autologin_key.hide()
                self.window.label_autologin_key.hide()

            # set existing values
            self.window.input_lineedit_username.setText(self.server.username)
            self.window.input_lineedit_password.setText(self.server.password)
            self.window.input_checkbox_save_password.setChecked(conf.servers[self.server.name].save_password)

    @Slot(str)
    def show_auth_dialog(self, server):
        """
        initialize and show authentication dialog
        """
        self.server = servers[server]
        self.initialize()
        # # workaround instead of sent signal
        # if not statuswindow is None:
        #     statuswindow.hide_window()
        self.show_up.emit()
        self.window.adjustSize()

        # the dock icon might be needed to be shown for a potential keyboard input
        self.show_macos_dock_icon_if_necessary()

        self.window.exec()

        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.hide_macos_dock_icon_if_necessary()

    def ok(self):
        """
        take username and password
        """

        # close window fist to avoid lagging UI
        self.window.close()

        self.server.username = self.window.input_lineedit_username.text()
        self.server.password = self.window.input_lineedit_password.text()
        self.server.refresh_authentication = False

        # store password if it should be saved
        if self.window.input_checkbox_save_password.isChecked():
            conf.servers[self.server.name].username = self.server.username
            conf.servers[self.server.name].password = self.server.password
            conf.servers[self.server.name].save_password = self.window.input_checkbox_save_password.isChecked()
            # store server settings
            conf.save_multiple_config('servers', 'server')

        # Centreon
        if self.server.type in ['Centreon', 'Thruk']:
            if self.window.input_checkbox_use_autologin:
                conf.servers[self.server.name].use_autologin = self.window.input_checkbox_use_autologin.isChecked()
                conf.servers[self.server.name].autologin_key = self.window.input_lineedit_autologin_key.text()
                # store server settings
                conf.save_multiple_config('servers', 'server')

        # reset server connection
        self.server.reset_HTTP()

        # force server to recheck right now
        self.server.thread_counter = conf.update_interval_seconds

        # update server_vbox label
        self.update.emit(self.server.name)

        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot()
    def toggle_autologin(self):
        """
        toggle autologin option for Centreon
        """
        if self.window.input_checkbox_use_autologin.isChecked():
            self.window.label_username.hide()
            self.window.label_password.hide()
            self.window.input_lineedit_username.hide()
            self.window.input_lineedit_password.hide()
            self.window.input_checkbox_save_password.hide()

            self.window.label_autologin_key.show()
            self.window.input_lineedit_autologin_key.show()
        else:
            self.window.label_username.show()
            self.window.label_password.show()
            self.window.input_lineedit_username.show()
            self.window.input_lineedit_password.show()
            self.window.input_checkbox_save_password.show()

            self.window.label_autologin_key.hide()
            self.window.input_lineedit_autologin_key.hide()

        # adjust dialog window size after UI changes
        self.window.adjustSize()
