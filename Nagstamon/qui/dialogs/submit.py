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


class DialogSubmit(Dialog):
    """
    dialog for submitting arbitrarily chosen results
    """
    # store host and service to be used for OK button evaluation
    server = None
    host = service = ''

    submit = Signal(dict)

    def __init__(self):
        Dialog.__init__(self, 'dialog_submit')

    @Slot(object, str, str)
    def initialize(self, server=None, host='', service=''):
        # store server, host and service to be used for OK button evaluation
        self.server = server
        self.host = host
        self.service = service

        # if service is "" it must be a host
        if service == "":
            # set label for acknowledging a host
            self.window.setWindowTitle('Submit check result for host')
            self.window.input_label_description.setText('Host <b>%s</b>' % (host))
            # services do not need all states
            self.window.input_radiobutton_result_up.show()
            self.window.input_radiobutton_result_ok.hide()
            self.window.input_radiobutton_result_warning.hide()
            self.window.input_radiobutton_result_critical.hide()
            self.window.input_radiobutton_result_unknown.show()
            self.window.input_radiobutton_result_unreachable.show()
            self.window.input_radiobutton_result_down.show()
            # activate first radiobutton
            self.window.input_radiobutton_result_up.setChecked(True)
        else:
            # set label for acknowledging a service on host
            self.window.setWindowTitle('Submit check result for service')
            self.window.input_label_description.setText('Service <b>%s</b> on host <b>%s</b>' % (service, host))
            # hosts do not need all states
            self.window.input_radiobutton_result_up.hide()
            self.window.input_radiobutton_result_ok.show()
            self.window.input_radiobutton_result_warning.show()
            self.window.input_radiobutton_result_critical.show()
            self.window.input_radiobutton_result_unknown.show()
            self.window.input_radiobutton_result_unreachable.hide()
            self.window.input_radiobutton_result_down.hide()
            # activate first radiobutton
            self.window.input_radiobutton_result_ok.setChecked(True)

        # clear text fields
        self.window.input_lineedit_check_output.setText('')
        self.window.input_lineedit_performance_data.setText('')
        self.window.input_lineedit_comment.setText(conf.defaults_submit_check_result_comment)
        self.window.input_lineedit_check_output.setFocus()

    def ok(self):
        """
        submit an arbitrary check result
        """
        # default state
        state = "ok"

        for button in ["ok", "up", "warning", "critical", "unreachable", "unknown", "down"]:
            if self.window.__dict__['input_radiobutton_result_' + button].isChecked():
                state = button
                break

        # tell worker to submit
        self.submit.emit({'server': self.server,
                          'host': self.host,
                          'service': self.service,
                          'state': state,
                          'comment': self.window.input_lineedit_comment.text(),
                          'check_output': self.window.input_lineedit_check_output.text(),
                          'performance_data': self.window.input_lineedit_performance_data.text()})
        # call close and macOS dock icon treatment from ancestor
        super().ok()