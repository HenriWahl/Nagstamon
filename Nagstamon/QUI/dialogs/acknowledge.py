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
from Nagstamon.QUI.dialogs.dialog import Dialog
from Nagstamon.QUI.qt import (QDateTime,
                              Signal,
                              Slot)
from Nagstamon.Servers import SERVER_TYPES

class DialogAcknowledge(Dialog):
    """
    dialog for acknowledging host/service problems
    """

    # store host and service to be used for OK button evaluation
    server = None
    host_list = service_list = []

    # tell worker to acknowledge some troublesome item
    acknowledge = Signal(dict)

    def __init__(self,):
        Dialog.__init__(self, 'dialog_acknowledge')

        self.TOGGLE_DEPS = {
            self.window.input_checkbox_use_expire_time: [self.window.input_datetime_expire_time]
        }

        # still clumsy but better than negating the other server types
        PROMETHEUS_OR_ALERTMANAGER = ['Alertmanager',
                                      'Prometheus']
        NOT_PROMETHEUS_OR_ALERTMANAGER = [x.TYPE for x in SERVER_TYPES.values() if
                                          x.TYPE not in PROMETHEUS_OR_ALERTMANAGER]

        self.VOLATILE_WIDGETS = {
            self.window.input_checkbox_use_expire_time: ['IcingaWeb2', 'Icinga2API'],
            self.window.input_datetime_expire_time: ['IcingaWeb2', 'Icinga2API', 'Alertmanager'],
            self.window.input_checkbox_sticky_acknowledgement: NOT_PROMETHEUS_OR_ALERTMANAGER,
            self.window.input_checkbox_send_notification: NOT_PROMETHEUS_OR_ALERTMANAGER,
            self.window.input_checkbox_persistent_comment: NOT_PROMETHEUS_OR_ALERTMANAGER,
            self.window.input_checkbox_acknowledge_all_services: NOT_PROMETHEUS_OR_ALERTMANAGER
        }

        self.FORCE_DATETIME_EXPIRE_TIME = ['Alertmanager']

    @Slot(object, list, list)
    def initialize(self, server=None, host=[], service=[]):
        # store server, host and service to be used for OK button evaluation
        self.server = server
        self.host_list = host
        self.service_list = service

        self.window.setWindowTitle('Acknowledge hosts and services')
        text = ''

        for i in range(len(self.host_list)):
            if self.service_list[i] == "":
                text += f'Host <b>{self.host_list[i]}</b><br>'
            else:
                text += f'Service <b>{self.service_list[i]}</b> on host <b>{self.host_list[i]}</b><br>'

        self.window.input_label_description.setText(text)

        # default flags of monitor acknowledgement
        self.window.input_checkbox_sticky_acknowledgement.setChecked(conf.defaults_acknowledge_sticky)
        self.window.input_checkbox_send_notification.setChecked(conf.defaults_acknowledge_send_notification)
        self.window.input_checkbox_persistent_comment.setChecked(conf.defaults_acknowledge_persistent_comment)
        self.window.input_checkbox_use_expire_time.setChecked(conf.defaults_acknowledge_expire)
        if len(self.host_list) == 1:
            self.window.input_checkbox_acknowledge_all_services.setChecked(conf.defaults_acknowledge_all_services)
            self.window.input_checkbox_acknowledge_all_services.show()
        else:
            self.window.input_checkbox_acknowledge_all_services.setChecked(False)
            self.window.input_checkbox_acknowledge_all_services.hide()

        # default author + comment
        self.window.input_lineedit_comment.setText(conf.defaults_acknowledge_comment)
        self.window.input_lineedit_comment.setFocus()

        # set default and minimum value for expiry time
        qdatetime = QDateTime.currentDateTime()
        self.window.input_datetime_expire_time.setMinimumDateTime(qdatetime)
        # set default expiry time from configuration
        self.window.input_datetime_expire_time.setDateTime(qdatetime.addSecs(
            conf.defaults_acknowledge_expire_duration_hours * 60 * 60 + conf.defaults_acknowledge_expire_duration_minutes * 60
        ))

        # Show or hide widgets based on server
        if self.server is not None:
            for widget, server_types in self.VOLATILE_WIDGETS.items():
                if self.server.TYPE in server_types:
                    widget.show()
                    self.toggle_toggles()
                else:
                    widget.hide()
            if self.server.TYPE in self.FORCE_DATETIME_EXPIRE_TIME:
                self.window.input_datetime_expire_time.show()

        # Adjust to current size if items are hidden in the menu
        # Otherwise it will get confused and chop off text
        self.window.options_groupbox.adjustSize()
        self.window.adjustSize()

    def ok(self):
        """
        acknowledge miserable host/service
        """
        # create a list of all service of selected host to acknowledge them all
        all_services = list()
        acknowledge_all_services = self.window.input_checkbox_acknowledge_all_services.isChecked()

        if acknowledge_all_services is True:
            for i in self.server.nagitems_filtered["services"].values():
                for s in i:
                    if s.host in self.host_list:
                        all_services.append(s.name)

        if self.window.input_checkbox_use_expire_time.isChecked() or self.server.TYPE in self.FORCE_DATETIME_EXPIRE_TIME:
            # Format used in UI
            # 2019-11-01T18:17:39
            expire_datetime = self.window.input_datetime_expire_time.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        else:
            expire_datetime = None

        for line_number in range(len(self.host_list)):
            service = self.service_list[line_number]
            host = self.host_list[line_number]

            # send signal to tablewidget worker to care about acknowledging with supplied information
            self.acknowledge.emit({'server': self.server,
                                   'host': host,
                                   'service': service,
                                   'author': self.server.username,
                                   'comment': self.window.input_lineedit_comment.text(),
                                   'sticky': self.window.input_checkbox_sticky_acknowledgement.isChecked(),
                                   'notify': self.window.input_checkbox_send_notification.isChecked(),
                                   'persistent': self.window.input_checkbox_persistent_comment.isChecked(),
                                   'acknowledge_all_services': acknowledge_all_services,
                                   'all_services': all_services,
                                   'expire_time': expire_datetime})
        # call close and macOS dock icon treatment from ancestor
        super().ok()
