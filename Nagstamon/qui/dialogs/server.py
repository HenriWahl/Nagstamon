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

from copy import deepcopy
from functools import wraps
import os
from urllib.parse import quote

from Nagstamon.config import conf, CONFIG_STRINGS, BOOLPOOL, Server
from Nagstamon.qui.globals import (ecp_available,
                                   kerberos_available)
from Nagstamon.qui.qt import (QFileDialog,
                              QMessageBox,
                              QStyle,
                              Signal,
                              Slot)
from Nagstamon.qui.dialogs.dialog import Dialog
from Nagstamon.servers import (create_server,
                               servers,
                               SERVER_TYPES)


class DialogServer(Dialog):
    """
    dialog used to set up one single server
    """

    # tell server has been edited
    edited = Signal()

    # signal to emit when ok button is pressed - used to remove previous server
    edited_remove_previous = Signal(str)

    # signal to emit when ok button is pressed - used to update the list of servers
    edited_update_list = Signal(str, str, str)

    # signal to emit when a new server vbox has to be created
    create_server_vbox = Signal(str)


    def __init__(self):
        Dialog.__init__(self, 'settings_server')
        # file chooser Dialog
        self.file_chooser = QFileDialog()
        # configuration for server
        self.server_conf = None
        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in a list
        self.TOGGLE_DEPS = {
            self.window.input_checkbox_use_autologin: [self.window.label_autologin_key,
                                                       self.window.input_lineedit_autologin_key],
            self.window.input_checkbox_use_proxy: [self.window.groupbox_proxy],

            self.window.input_checkbox_use_proxy_from_os: [self.window.label_proxy_address,
                                                           self.window.input_lineedit_proxy_address,
                                                           self.window.label_proxy_username,
                                                           self.window.input_lineedit_proxy_username,
                                                           self.window.label_proxy_password,
                                                           self.window.input_lineedit_proxy_password],
            self.window.input_checkbox_show_options: [self.window.groupbox_options],
            self.window.input_checkbox_custom_cert_use: [self.window.label_custom_ca_file,
                                                         self.window.input_lineedit_custom_cert_ca_file,
                                                         self.window.button_choose_custom_cert_ca_file]}

        self.TOGGLE_DEPS_INVERTED = [self.window.input_checkbox_use_proxy_from_os]

        # these widgets are shown or hidden depending on server type properties
        # the servers listed at each widget do need them
        self.VOLATILE_WIDGETS = {
            self.window.label_monitor_cgi_url: ['Nagios', 'Icinga', 'Thruk', 'Sensu', 'SensuGo'],
            self.window.input_lineedit_monitor_cgi_url: ['Nagios', 'Icinga', 'Thruk', 'Sensu', 'SensuGo'],
            self.window.input_checkbox_use_autologin: ['Centreon', 'monitos4x', 'Thruk'],
            self.window.input_lineedit_autologin_key: ['Centreon', 'monitos4x', 'Thruk'],
            self.window.label_autologin_key: ['Centreon', 'monitos4x', 'Thruk'],
            self.window.input_checkbox_no_cookie_auth: ['IcingaWeb2', 'Sensu'],
            self.window.input_checkbox_use_display_name_host: ['Icinga', 'IcingaWeb2'],
            self.window.input_checkbox_use_display_name_service: ['Icinga', 'IcingaWeb2', 'Thruk'],
            self.window.input_checkbox_use_description_name_service: ['Zabbix'],
            self.window.input_checkbox_force_authuser: ['Checkmk Multisite'],
            self.window.groupbox_checkmk_views: ['Checkmk Multisite'],
            self.window.input_lineedit_host_filter: ['op5Monitor'],
            self.window.input_lineedit_service_filter: ['op5Monitor'],
            self.window.label_service_filter: ['op5Monitor'],
            self.window.label_host_filter: ['op5Monitor'],
            self.window.input_lineedit_hashtag_filter: ['Opsview'],
            self.window.label_hashtag_filter: ['Opsview'],
            self.window.input_checkbox_can_change_only: ['Opsview'],
            self.window.label_monitor_site: ['Sensu'],
            self.window.input_lineedit_monitor_site: ['Sensu'],
            self.window.label_map_to_hostname: ['Prometheus', 'Alertmanager'],
            self.window.input_lineedit_map_to_hostname: ['Prometheus', 'Alertmanager'],
            self.window.label_map_to_servicename: ['Prometheus', 'Alertmanager'],
            self.window.input_lineedit_map_to_servicename: ['Prometheus', 'Alertmanager'],
            self.window.label_map_to_status_information: ['Prometheus', 'Alertmanager'],
            self.window.input_lineedit_map_to_status_information: ['Prometheus', 'Alertmanager'],
            self.window.label_alertmanager_filter: ['Alertmanager'],
            self.window.input_lineedit_alertmanager_filter: ['Alertmanager'],
            self.window.label_map_to_ok: ['Alertmanager'],
            self.window.input_lineedit_map_to_ok: ['Alertmanager'],
            self.window.label_map_to_unknown: ['Alertmanager'],
            self.window.input_lineedit_map_to_unknown: ['Alertmanager'],
            self.window.label_map_to_warning: ['Alertmanager'],
            self.window.input_lineedit_map_to_warning: ['Alertmanager'],
            self.window.label_map_to_critical: ['Alertmanager'],
            self.window.input_lineedit_map_to_critical: ['Alertmanager'],
            self.window.label_map_to_down: ['Alertmanager'],
            self.window.input_lineedit_map_to_down: ['Alertmanager'],
            self.window.input_lineedit_notification_filter: ['IcingaDBWebNotifications'],
            self.window.label_notification_filter: ['IcingaDBWebNotifications'],
            self.window.input_lineedit_notification_lookback: ['IcingaDBWebNotifications'],
            self.window.label_notification_lookback: ['IcingaDBWebNotifications'],
            self.window.label_disabled_backends: ['Thruk'],
            self.window.input_lineedit_disabled_backends: ['Thruk'],
        }

        # to be used when selecting authentication method Kerberos
        self.AUTHENTICATION_WIDGETS = [
            self.window.label_username,
            self.window.input_lineedit_username,
            self.window.label_password,
            self.window.input_lineedit_password,
            self.window.input_checkbox_save_password]

        self.AUTHENTICATION_BEARER_WIDGETS = [
            self.window.label_username,
            self.window.input_lineedit_username]

        self.AUTHENTICATION_ECP_WIDGETS = [
            self.window.label_idp_ecp_endpoint,
            self.window.input_lineedit_idp_ecp_endpoint]

        # fill default order fields combobox with monitor server types
        self.window.input_combobox_type.addItems(sorted(SERVER_TYPES.keys(), key=str.lower))
        # default to Nagios as it is the mostly used monitor server
        self.window.input_combobox_type.setCurrentText('Nagios')

        # set folder and play symbols to choose and play buttons
        self.window.button_choose_custom_cert_ca_file.setText('')
        self.window.button_choose_custom_cert_ca_file.setIcon(
            self.window.button_choose_custom_cert_ca_file.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        # connect choose custom cert CA file button with file dialog
        self.window.button_choose_custom_cert_ca_file.clicked.connect(self.choose_custom_cert_ca_file)

        # fill authentication combobox
        self.window.input_combobox_authentication.addItems(['Basic', 'Bearer', 'Digest', 'Web'])
        if ecp_available:
            self.window.input_combobox_authentication.addItems(['ECP'])
        if kerberos_available:
            self.window.input_combobox_authentication.addItems(['Kerberos'])

        # detect change of a server type which leads to certain options shown or hidden
        self.window.input_combobox_type.activated.connect(self.toggle_type)

        # when authentication is changed to Kerberos then disable username/password as they are now useless
        self.window.input_combobox_authentication.activated.connect(self.toggle_authentication)

        # reset Checkmk views
        self.window.button_checkmk_view_hosts_reset.clicked.connect(self.checkmk_view_hosts_reset)
        self.window.button_checkmk_view_services_reset.clicked.connect(self.checkmk_view_services_reset)

        # mode needed for evaluate dialog after ok button pressed - defaults to 'new'
        self.mode = 'new'

    @Slot(int)
    def toggle_type(self, server_type_index=0):
        # server_type_index is not needed - we get the server type from .currentText()
        # check if server type is listed in volatile widgets to decide if it has to be shown or hidden
        for widget, server_types in self.VOLATILE_WIDGETS.items():
            if self.window.input_combobox_type.currentText() in server_types:
                widget.show()
            else:
                widget.hide()

    @Slot()
    def toggle_authentication(self):
        """
        when authentication is changed to Kerberos then disable username/password as they are now useless
        """
        if self.window.input_combobox_authentication.currentText() == 'Kerberos':
            for widget in self.AUTHENTICATION_WIDGETS:
                widget.hide()
        else:
            for widget in self.AUTHENTICATION_WIDGETS:
                widget.show()

        if self.window.input_combobox_authentication.currentText() == 'ECP':
            for widget in self.AUTHENTICATION_ECP_WIDGETS:
                widget.show()
        else:
            for widget in self.AUTHENTICATION_ECP_WIDGETS:
                widget.hide()

        # change credential input for bearer auth
        if self.window.input_combobox_authentication.currentText() == 'Bearer':
            for widget in self.AUTHENTICATION_BEARER_WIDGETS:
                widget.hide()
                self.window.label_password.setText('Token')
        else:
            for widget in self.AUTHENTICATION_BEARER_WIDGETS:
                widget.show()
                self.window.label_password.setText('Password')

        # after hiding authentication widgets dialog might shrink
        self.window.adjustSize()

    def dialog_decoration(method, *args, **kwargs):
        """
        try with a decorator instead of repeated calls
        """

        # the function which decorates method
         # wraps is used to keep the original method's name and docstring
        @wraps(method)
        def decoration_function(self, *args, **kwargs):
            """
                self.server_conf has to be set by decorated method
            """
            # previous server conf only useful when editing - defaults to None
            self.previous_server_conf = None

            # call decorated method
            method(self, *args, **kwargs)

            # run through all input widgets and apply defaults from config
            for widget in self.window.__dict__:

                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.window.__dict__[widget].setChecked(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.window.__dict__[widget].setChecked(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.window.__dict__[widget].setCurrentText(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.window.__dict__[widget].setText(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_spinbox_'):
                        setting = widget.split('input_spinbox_')[1]
                        self.window.__dict__[widget].setValue(self.server_conf.__dict__[setting])

            # set the current authentication type by using capitalized first letter via .title()
            self.window.input_combobox_authentication.setCurrentText(self.server_conf.authentication.title())

            # initially hide unnecessary widgets
            self.toggle_type()

            # disable unneeded authentication widgets if Kerberos is used
            self.toggle_authentication()

            # apply toggle-dependencies between checkboxes and certain widgets
            self.toggle_toggles()

            # open extra options if wanted, for example, by button_fix_tls_error
            if 'show_options' in self.__dict__:
                if self.show_options:
                    self.window.input_checkbox_show_options.setChecked(True)

            # important final size adjustment
            self.window.adjustSize()

            # if running on macOS with disabled dock icon, the dock icon might have to be made visible
            # to make Nagstamon accept keyboard input
            self.check_macos_dock_icon_fix_show.emit()

            self.window.exec()

            # en reverse the dock icon might be hidden again after a potential keyboard input
            self.check_macos_dock_icon_fix_hide.emit()

        # give back decorated function
        return decoration_function

    @Slot()
    @dialog_decoration
    def new(self):
        """
        create new server, set default values
        """
        self.mode = 'new'

        # create a new server config object
        self.server_conf = Server()
        # window title might be pretty simple
        self.window.setWindowTitle('New server')

    @Slot(str)
    @dialog_decoration
    def edit(self, name=None, show_options=False):
        """
        edit existing server
        when called by Edit button in ServerVBox use given server name to get server config
        """

        self.mode = 'edit'
        # shorter server conf
        # if name is None:
        #     self.server_conf = conf.servers[dialogs.settings.window.list_servers.currentItem().text()]
        # else:
        #     self.server_conf = conf.servers[name]
        self.server_conf = conf.servers[name]
        # store monitor name in case it will be changed
        self.previous_server_conf = deepcopy(self.server_conf)
        # set window title
        self.window.setWindowTitle('Edit %s' % (self.server_conf.name))
        # set self.show_options to give value to decorator
        self.show_options = show_options

    @Slot(str)
    @dialog_decoration
    def copy(self, name=None):
        """
        copy existing server
        """
        self.mode = 'copy'
        # shorter server conf
        self.server_conf = deepcopy(conf.servers[name])
        # set window title before name change to reflect copy
        self.window.setWindowTitle(f'Copy {self.server_conf.name}')
        # indicate copy of another server
        self.server_conf.name = f'Copy of {self.server_conf.name}'

    def ok(self):
        """
        evaluate the state of widgets to get new configuration
        """
        # strip name to avoid whitespace
        server_name = self.window.input_lineedit_name.text().strip()

        # check that no duplicate name exists
        if server_name in conf.servers and \
                (self.mode in ['new', 'copy'] or
                 self.mode == 'edit' and self.server_conf != conf.servers[server_name]):
            # cry if duplicate name exists
            QMessageBox.critical(self.window,
                                 'Nagstamon',
                                 f'The monitor server name <b>{server_name}</b> is already used.',
                                 QMessageBox.StandardButton.Ok)
        else:
            # get configuration from UI
            for widget in self.window.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].isChecked()
                    elif widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].isChecked()
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].currentText()
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].text()
                    elif widget.startswith('input_spinbox_'):
                        setting = widget.split('input_spinbox_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].value()

            # URLs should not end with / - clean it
            self.server_conf.monitor_url = self.server_conf.monitor_url.rstrip('/')
            self.server_conf.monitor_cgi_url = self.server_conf.monitor_cgi_url.rstrip('/')

            # convert some strings to integers and bools
            for item in self.server_conf.__dict__:
                if type(self.server_conf.__dict__[item]) == str:
                    # when an item is not one of those which always have to be strings, then it might be OK to convert it
                    if not item in CONFIG_STRINGS:
                        if self.server_conf.__dict__[item] in BOOLPOOL:
                            self.server_conf.__dict__[item] = BOOLPOOL[self.server_conf.__dict__[item]]
                        elif self.server_conf.__dict__[item].isdecimal():
                            self.server_conf.__dict__[item] = int(self.server_conf.__dict__[item])

            # store lowered authentication type
            self.server_conf.authentication = self.server_conf.authentication.lower()

            # edited servers will be deleted and recreated with new configuration
            if self.mode == 'edit':
                # remove old server vbox from the status window if still running
                self.edited_remove_previous.emit(self.previous_server_conf.name)

                # delete previous name
                conf.servers.pop(self.previous_server_conf.name)

                # delete edited and now not needed server instance - if it exists
                if self.previous_server_conf.name in servers.keys():
                    servers.pop(self.previous_server_conf.name)

            # some monitor servers do not need cgi-url - reuse self.VOLATILE_WIDGETS to find out which one
            if self.server_conf.type not in self.VOLATILE_WIDGETS[self.window.input_lineedit_monitor_cgi_url]:
                self.server_conf.monitor_cgi_url = self.server_conf.monitor_url

            # add new server configuration in every case and use stripped name to avoid spaces
            self.server_conf.name = server_name
            conf.servers[server_name] = self.server_conf

            # add new server instance to global servers dict
            servers[server_name] = create_server(self.server_conf)
            if self.server_conf.enabled:
                servers[server_name].enabled = True
                # create vbox
                self.create_server_vbox.emit(server_name)

            # reorder servers in dict to reflect changes
            servers_freshly_sorted = sorted(servers.items())
            servers.clear()
            servers.update(servers_freshly_sorted)
            del servers_freshly_sorted

            # refresh the list of servers, give call the current server name to highlight it
            self.edited_update_list.emit('list_servers', 'servers', self.server_conf.name)

            # tell the main window about changes (Zabbix, Opsview, for example)
            self.edited.emit()

            # delete the old server .conf file to reflect name changes
            # new one will be written soon
            if self.previous_server_conf is not None:
                conf.delete_file('servers', f"server_{quote(self.previous_server_conf.name, safe='')}.conf")

            # store server settings
            conf.save_multiple_config('servers', 'server')

        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot()
    def choose_custom_cert_ca_file(self):
        """
        show dialog for selection of non-default browser
        """
        file_filter = 'All files (*)'
        file = self.file_chooser.getOpenFileName(self.window,
                                                    directory=os.path.expanduser('~'),
                                                    filter=file_filter)[0]

        # only take filename if QFileDialog gave something useful back
        if file != '':
            self.window.input_lineedit_custom_cert_ca_file.setText(file)

    @Slot()
    def checkmk_view_hosts_reset(self):
        self.window.input_lineedit_checkmk_view_hosts.setText('nagstamon_hosts')

    @Slot()
    def checkmk_view_services_reset(self):
        self.window.input_lineedit_checkmk_view_services.setText('nagstamon_svc')
