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


from Nagstamon.qui.dialogs.about import DialogAbout
from Nagstamon.qui.dialogs.acknowledge import DialogAcknowledge
from Nagstamon.qui.dialogs.action import DialogAction
from Nagstamon.qui.dialogs.authentication import DialogAuthentication
from Nagstamon.qui.dialogs.dialog import Dialog
from Nagstamon.qui.dialogs.downtime import DialogDowntime
from Nagstamon.qui.dialogs.server import DialogServer
from Nagstamon.qui.dialogs.server_missing import DialogServerMissing
from Nagstamon.qui.dialogs.settings import DialogSettings
from Nagstamon.qui.dialogs.submit import DialogSubmit


class Dialogs():
    """
    class for accessing all dialogs
    """
    windows = list()
    settings = None
    server = None
    action = None
    acknowledge = None
    downtime = None
    submit = None
    authentication = None
    server_missing = None
    about = None


    def initialize_dialog_settings(self, dialog):
        """
        initialize settings dialog
        """
        # self.settings = Dialog_Settings('settings_main')
        self.settings = dialog
        self.settings.initialize()
        self.windows.append(self.settings.window)

    def initialize_dialog_server(self, dialog):
        """
        initialize settings dialog
        """
        # self.server = Dialog_Server('settings_server')
        self.server = dialog
        self.server.initialize()
        self.windows.append(self.server.window)
        # check if special widgets have to be shown
        self.server.edited.connect(self.settings.toggle_zabbix_widgets)
        self.server.edited.connect(self.settings.toggle_op5monitor_widgets)
        self.server.edited.connect(self.settings.toggle_expire_time_widgets)

    def initialize_dialog_action(self, dialog):
        # self.action = Dialog_Action('settings_action')
        self.action = dialog
        self.action.initialize()
        self.windows.append(self.action.window)

    def initialize_dialog_acknowledge(self, dialog):
        # self.acknowledge = Dialog_Acknowledge('dialog_acknowledge')
        self.acknowledge = dialog
        self.acknowledge.initialize()
        self.windows.append(self.acknowledge.window)
        self.acknowledge.window.button_change_defaults_acknowledge.clicked.connect(self.settings.show_defaults)
        self.acknowledge.window.button_change_defaults_acknowledge.clicked.connect(self.acknowledge.window.close)

    def initialize_dialog_downtime(self, dialog):
        # self.downtime = Dialog_Downtime('dialog_downtime')
        self.downtime = dialog
        self.downtime.initialize()
        self.windows.append(self.downtime.window)
        self.downtime.window.button_change_defaults_downtime.clicked.connect(self.settings.show_defaults)
        self.downtime.window.button_change_defaults_downtime.clicked.connect(self.downtime.window.close)

    def initialize_dialog_submit(self, dialog):
        # self.submit = Dialog_Submit('dialog_submit')
        self.submit = dialog
        self.submit.initialize()
        self.windows.append(self.submit.window)

    def initialize_dialog_authentication(self, dialog):
        # self.authentication = Dialog_Authentication('dialog_authentication')
        self.authentication = dialog
        self.authentication.initialize()
        self.windows.append(self.authentication.window)

    def initialize_dialog_server_missing(self, dialog):
        # self.server_missing = Dialog_Server_missing('dialog_server_missing')
        self.server_missing = dialog
        self.server_missing.initialize()
        self.windows.append(self.server_missing.window)
        # open server creation dialog
        self.server_missing.window.button_create_server.clicked.connect(self.settings.show_new_server)
        self.server_missing.window.button_enable_server.clicked.connect(self.settings.show)

    def initialize_dialog_about(self, dialog):
        # self.about = Dialog_About('dialog_about')
        self.about = dialog
        self.windows.append(self.about.window)

    def get_shown_dialogs(self):
        """
        get a list of currently show dialog windows - needed for macOS hide dock icon stuff
        """
        return [x for x in self.windows if x.isVisible()]


dialogs = Dialogs()
dialogs.initialize_dialog_settings(DialogSettings())
dialogs.initialize_dialog_about(DialogAbout())
dialogs.initialize_dialog_acknowledge(DialogAcknowledge())
dialogs.initialize_dialog_action(DialogAction())
dialogs.initialize_dialog_downtime(DialogDowntime())
dialogs.initialize_dialog_submit(DialogSubmit())
dialogs.initialize_dialog_authentication(DialogAuthentication())
dialogs.initialize_dialog_server_missing(DialogServerMissing())
dialogs.initialize_dialog_server(DialogServer())

# signals and slots between dialogs
# settings -> server
dialogs.settings.server_created.connect(dialogs.server.new)
dialogs.settings.server_edited.connect(dialogs.server.edit)
dialogs.settings.server_copied.connect(dialogs.server.copy)
# settings -> action
dialogs.settings.action_created.connect(dialogs.action.new)
dialogs.settings.action_edited.connect(dialogs.action.edit)
dialogs.settings.action_copied.connect(dialogs.action.copy)
# action -> settings refresh_list
dialogs.action.edited_update_list.connect(dialogs.settings.refresh_list)
# server -> settings refresh_list
dialogs.server.edited_update_list.connect(dialogs.settings.refresh_list)
