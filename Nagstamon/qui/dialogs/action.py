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
from urllib.parse import quote

from Nagstamon.Servers import SERVER_TYPES
from Nagstamon.config import (Action,
                              conf)
from Nagstamon.qui.dialogs.dialog import Dialog
from Nagstamon.qui.qt import (QMessageBox,
                              Signal,
                              Slot)


class DialogAction(Dialog):
    """
    Dialog used to set up one single action
    """

    # signal to emit when ok button is pressed - used to update the list of actions
    edited_update_list = Signal(str, str, str)

    # mapping between action types and combobox content
    ACTION_TYPES = {'browser': 'Browser',
                    'command': 'Command',
                    'url': 'URL'}

    def __init__(self):
        Dialog.__init__(self, 'settings_action')
        # initial values
        self.action_conf = None
        self.mode = None
        self.previous_action_conf = None
        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in a list
        self.TOGGLE_DEPS = {
            self.window.input_checkbox_re_host_enabled: [self.window.input_lineedit_re_host_pattern,
                                                         self.window.input_checkbox_re_host_reverse],
            self.window.input_checkbox_re_service_enabled: [self.window.input_lineedit_re_service_pattern,
                                                            self.window.input_checkbox_re_service_reverse],
            self.window.input_checkbox_re_status_information_enabled: [
                self.window.input_lineedit_re_status_information_pattern,
                self.window.input_checkbox_re_status_information_reverse],
            self.window.input_checkbox_re_duration_enabled: [self.window.input_lineedit_re_duration_pattern,
                                                             self.window.input_checkbox_re_duration_reverse],
            self.window.input_checkbox_re_attempt_enabled: [self.window.input_lineedit_re_attempt_pattern,
                                                            self.window.input_checkbox_re_attempt_reverse],
            self.window.input_checkbox_re_groups_enabled: [self.window.input_lineedit_re_groups_pattern,
                                                           self.window.input_checkbox_re_groups_reverse]}

        # fill action types into combobox
        self.window.input_combobox_type.addItems(sorted(self.ACTION_TYPES.values()))

        # fill default order fields combobox with monitor server types
        self.window.input_combobox_monitor_type.addItem("All monitor servers")
        self.window.input_combobox_monitor_type.addItems(sorted(SERVER_TYPES.keys(), key=str.lower))
        # default to Nagios as it is the mostly used monitor server
        self.window.input_combobox_monitor_type.setCurrentIndex(0)

    def dialog_decoration(method, *args):
        """
        try with a decorator instead of repeated calls
        """

        # the function which decorates method
        # wraps is used to keep the original method's name and docstring
        @wraps(method)
        def decoration_function(self, *decorated_args):
            """
            self.server_conf has to be set by decorated method
            """

            # previous action conf only useful when editing - defaults to None
            self.previous_action_conf = None

            # call decorated method
            method(self, *decorated_args)

            # run through all input widgets and apply defaults from config
            for widget in self.window.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.window.__dict__[widget].setChecked(self.action_conf.__dict__[setting])
                    elif widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.window.__dict__[widget].setChecked(self.action_conf.__dict__[setting])
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.window.__dict__[widget].setText(self.action_conf.__dict__[setting])
                    elif widget.startswith('input_textedit_'):
                        setting = widget.split('input_textedit_')[1]
                        self.window.__dict__[widget].setText(self.action_conf.__dict__[setting])

            # set comboboxes
            self.window.input_combobox_type.setCurrentText(self.ACTION_TYPES[self.action_conf.type.lower()])
            self.window.input_combobox_monitor_type.setCurrentText(self.action_conf.monitor_type)

            # apply toggle-dependencies between checkboxes and certain widgets
            self.toggle_toggles()

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
        create new server
        """
        self.mode = 'new'

        # create a new server config object
        self.action_conf = Action()
        # window title might be pretty simple
        self.window.setWindowTitle('New action')

    @Slot(str)
    @dialog_decoration
    def edit(self, name):
        """
        edit existing action
        """
        self.mode = 'edit'
        # shorter action conf
        self.action_conf = conf.actions[name]
        # store action name in case it will be changed
        self.previous_action_conf = deepcopy(self.action_conf)
        # set window title
        self.window.setWindowTitle(f'Edit {self.action_conf.name}')

    @Slot(str)
    @dialog_decoration
    def copy(self, name):
        """
        copy existing action
        """
        self.mode = 'copy'
        # shorter action conf
        self.action_conf = deepcopy(conf.actions[name])
        # set window title before name change to reflect copy
        self.window.setWindowTitle(f'Copy {self.action_conf.name}')
        # indicate copy of other action
        self.action_conf.name = f'Copy of {self.action_conf.name}'

    def ok(self):
        """
        evaluate the state of widgets to get new configuration
        """
        # check that no duplicate name exists
        if self.window.input_lineedit_name.text() in conf.actions and \
                (self.mode in ['new', 'copy'] or
                 self.mode == 'edit' and self.action_conf != conf.actions[self.window.input_lineedit_name.text()]):
            # cry if duplicate name exists
            QMessageBox.critical(self.window, 'Nagstamon',
                                 f'The action name <b>{self.window.input_lineedit_name.text()}</b> is already used.',
                                 QMessageBox.StandardButton.Ok)
        else:
            # get configuration from UI
            for widget in self.window.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.action_conf.__dict__[setting] = self.window.__dict__[widget].isChecked()
                    if widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.action_conf.__dict__[setting] = self.window.__dict__[widget].isChecked()
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.action_conf.__dict__[setting] = self.window.__dict__[widget].currentText()
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.action_conf.__dict__[setting] = self.window.__dict__[widget].text()
                    elif widget.startswith('input_textedit_'):
                        setting = widget.split('input_textedit_')[1]
                        self.action_conf.__dict__[setting] = self.window.__dict__[widget].toPlainText()

            # edited action will be deleted and recreated with new configuration
            if self.mode == 'edit':
                # delete previous name
                conf.actions.pop(self.previous_action_conf.name)

            # Avoid the wrong monitor type which blocks display of action
            if self.action_conf.monitor_type not in SERVER_TYPES:
                self.action_conf.monitor_type = ''

            # lower type to recognize action type on monitor
            self.action_conf.type = self.action_conf.type.lower()

            # add edited or new/copied action
            conf.actions[self.action_conf.name] = self.action_conf

            # refresh list of actions, give call the current action name to highlight it
            self.edited_update_list.emit('list_actions', 'actions', self.action_conf.name)

            # delete the old action .conf file to reflect name changes
            # new one will be written soon
            if self.previous_action_conf is not None:
                conf.delete_file('actions', 'action_{0}.conf'.format(quote(self.previous_action_conf.name, safe='')))

            # store server settings
            conf.save_multiple_config('actions', 'action')

        # call close and macOS dock icon treatment from ancestor
        super().ok()
