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
from Nagstamon.qui.dialogs.dialog import Dialog
from Nagstamon.qui.qt import (Signal,
                              Slot)


class DialogDowntime(Dialog):
    """
    dialog for putting hosts/services into downtime
    """

    # send signal to get start and end of downtime asynchronously
    get_start_end = Signal(str, str)

    # signal to tell worker to commit downtime
    downtime = Signal(dict)

    # store host and service to be used for OK button evaluation
    server = None
    host_list = service_list = []

    def __init__(self):
        Dialog.__init__(self, 'dialog_downtime')

    def initialize(self, server=None, host=[], service=[]):
        # store server, host and service to be used for OK button evaluation
        self.server = server
        self.host_list = host
        self.service_list = service

        self.window.setWindowTitle('Downtime for host and service')
        text = ''

        for i in range(len(self.host_list)):
            if self.service_list[i] == "":
                text += f'Host <b>{self.host_list[i]}</b><br>'
            else:
                text += f'Service <b>{self.service_list[i]}</b> on host <b>{self.host_list[i]}</b><br>'

        self.window.input_label_description.setText(text)

        # default flags of monitor acknowledgement
        self.window.input_spinbox_duration_hours.setValue(int(conf.defaults_downtime_duration_hours))
        self.window.input_spinbox_duration_minutes.setValue(int(conf.defaults_downtime_duration_minutes))
        self.window.input_radiobutton_type_fixed.setChecked(conf.defaults_downtime_type_fixed)
        self.window.input_radiobutton_type_flexible.setChecked(conf.defaults_downtime_type_flexible)

        # hide/show downtime settings according to type
        self.window.input_radiobutton_type_fixed.clicked.connect(self.set_type_fixed)
        self.window.input_radiobutton_type_flexible.clicked.connect(self.set_type_flexible)

        # show or hide widgets for time settings
        if self.window.input_radiobutton_type_fixed.isChecked():
            self.set_type_fixed()
        else:
            self.set_type_flexible()

        # empty times at start, will be filled by set_start_end
        self.window.input_lineedit_start_time.setText('n/a')
        self.window.input_lineedit_end_time.setText('n/a')

        # default author + comment
        self.window.input_lineedit_comment.setText(conf.defaults_downtime_comment)
        self.window.input_lineedit_comment.setFocus()

        if self.server is not None:
            # at first initialization server is still None
            self.get_start_end.emit(self.server.name, self.host_list[0])

    def ok(self):
        """
        schedule downtime for miserable host/service
        """
        # type of downtime - fixed or flexible
        if self.window.input_radiobutton_type_fixed.isChecked() is True:
            fixed = 1
        else:
            fixed = 0

        for line_number in range(len(self.host_list)):
            service = self.service_list[line_number]
            host = self.host_list[line_number]

            self.downtime.emit({'server': self.server,
                                'host': host,
                                'service': service,
                                'author': self.server.username,
                                'comment': self.window.input_lineedit_comment.text(),
                                'fixed': fixed,
                                'start_time': self.window.input_lineedit_start_time.text(),
                                'end_time': self.window.input_lineedit_end_time.text(),
                                'hours': int(self.window.input_spinbox_duration_hours.value()),
                                'minutes': int(self.window.input_spinbox_duration_minutes.value())})
        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot(str, str)
    def set_start_end(self, start, end):
        """
        put values sent by worker into start and end fields
        """
        self.window.input_lineedit_start_time.setText(start)
        self.window.input_lineedit_end_time.setText(end)

    @Slot()
    def set_type_fixed(self):
        """
        enable/disable appropriate widgets if type is "Fixed"
        """
        self.window.label_duration.hide()
        self.window.label_duration_hours.hide()
        self.window.label_duration_minutes.hide()
        self.window.input_spinbox_duration_hours.hide()
        self.window.input_spinbox_duration_minutes.hide()

    @Slot()
    def set_type_flexible(self):
        """
        enable/disable appropriate widgets if type is "Flexible"
        """
        self.window.label_duration.show()
        self.window.label_duration_hours.show()
        self.window.label_duration_minutes.show()
        self.window.input_spinbox_duration_hours.show()
        self.window.input_spinbox_duration_minutes.show()
