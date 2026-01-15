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

from io import StringIO
from pathlib import Path

from Nagstamon.config import (conf,
                              RESOURCES,
                              OS,
                              OS_MACOS)

from Nagstamon.qui.constants import ICON
from Nagstamon.qui.globals import statuswindow_properties
from Nagstamon.qui.helpers import hide_macos_dock_icon
from Nagstamon.qui.qt import (QBrush,
                              QListWidgetItem,
                              QObject,
                              QSignalMapper,
                              QSizePolicy,
                              Qt,
                              Signal,
                              Slot,
                              uic,
                              UI_FILE_QT6_QT5_DOWNGRADES)

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import NSApp


class Dialog(QObject):
    """
    one single dialog
    """
    # send a signal, e.g., to the status window if a dialog pops up
    show_dialog = Signal()

    # signals for macOS dock icon fix
    check_macos_dock_icon_fix_show = Signal()
    check_macos_dock_icon_fix_hide = Signal()

    # dummy toggle dependencies
    TOGGLE_DEPS = {}
    # auxiliary list of checkboxes which HIDE some other widgets if triggered - for example proxy OS settings
    TOGGLE_DEPS_INVERTED = []
    # widgets that might be enabled/disabled depending on a monitor server type
    VOLATILE_WIDGETS = {}
    # names of widgets and their defaults
    WIDGET_NAMES = {}
    # style stuff used by settings dialog for servers/actions listwidget
    GRAY = QBrush(Qt.GlobalColor.gray)

    def __init__(self, dialog):
        QObject.__init__(self)

        # load UI file for manipulation
        ui_file_path = Path(f'{RESOURCES}/qui/{dialog}.ui')
        ui_file_content = ui_file_path.read_text(encoding='utf-8')
        # replace all problematic Qt6 names by Qt5 names to be able to use one single UI file for both Qt5 and Qt6
        for qt6_name, qt5_name in UI_FILE_QT6_QT5_DOWNGRADES.items():
            ui_file_content = ui_file_content.replace(qt6_name, qt5_name)
        # convert string to file-like object for loadUi()
        ui_file_content_io = StringIO(ui_file_content)
        # load UI file from resource
        self.window = uic.loadUi(ui_file_content_io)

        # explicitly set window flags to avoid '?' button on Windows
        self.window.setWindowFlags(Qt.WindowType.WindowCloseButtonHint)

        # hoping to avoid overly large dialogs
        self.window.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        # set small titlebar icon
        self.window.setWindowIcon(ICON)

        # treat dialog content after pressing OK button
        if 'button_box' in dir(self.window):
            self.window.button_box.accepted.connect(self.ok)
            self.window.button_box.rejected.connect(self.cancel)

        # QSignalMapper needed to connect all toggle-needing-checkboxes/radiobuttons to one .toggle()-method which
        # decides which sender to use as key in self.TOGGLE_DEPS
        self.signalmapper_toggles = QSignalMapper()

        # try to get and keep focus
        self.window.setWindowModality(Qt.WindowModality.ApplicationModal)

    def initialize(self):
        """
        dummy initialize method
        """
        pass

    @Slot()
    def show(self, tab=0):
        """
        simple show method, to be enriched
        """
        # if running on macOS with disabled dock icon the dock icon might have to be made visible
        # to make Nagstamon accept keyboard input
        self.check_macos_dock_icon_fix_show.emit()

        # in case dock icon is configured invisible in macOS it has to be shown while dialog is shown
        # to be able to get keyboard focus
        if OS == OS_MACOS and \
                conf.icon_in_systray and \
                conf.hide_macos_dock_icon:
            hide_macos_dock_icon(False)

        # tell the world that dialog pops up
        self.show_dialog.emit()

        # reset the window if it only needs smaller screen estate
        self.window.adjustSize()
        self.window.show()
        # make sure the dialog window will be the topmost
        self.window.raise_()
        # hidden dock icon on macOS needs extra activation
        if OS == OS_MACOS and \
                conf.icon_in_systray and \
                conf.hide_macos_dock_icon:
            NSApp.activateIgnoringOtherApps_(True)

    def toggle_visibility(self, checkbox, widgets=None):
        """
        state of checkbox toggles visibility of widgets
        some checkboxes might trigger an inverted behaviour - thus the 'inverted' value
        """
        if widgets is None:
            widgets = []
        if checkbox in self.TOGGLE_DEPS_INVERTED:
            if checkbox.isChecked():
                for widget in widgets:
                    widget.hide()
            else:
                for widget in widgets:
                    widget.show()
        # normal case - click on checkbox activates more options
        else:
            if checkbox.isChecked():
                for widget in widgets:
                    widget.show()
            else:
                for widget in widgets:
                    widget.hide()

    @Slot(str)
    def toggle(self, checkbox):
        """
        change state of the dependant widgets, slot for signals from checkboxes in UI
        """
        # Due to older Qt5 in Ubuntu 14.04 signal mapper has to use strings
        self.toggle_visibility(self.window.__dict__[checkbox],
                               self.TOGGLE_DEPS[self.window.__dict__[checkbox]])

        # adjust dialog window size after UI changes
        self.window.adjustSize()

    def toggle_toggles(self):
        # apply toggle-dependencies between checkboxes as certain widgets
        for checkbox, widgets in self.TOGGLE_DEPS.items():
            # toggle visibility
            self.toggle_visibility(checkbox, widgets)
            # multiplex slot .toggle() by signal-mapping
            # Due to older Qt5 in Ubuntu 14.04 signal mapper has to use strings
            self.signalmapper_toggles.setMapping(checkbox, checkbox.objectName())
            checkbox.toggled.connect(self.signalmapper_toggles.map)
            checkbox.toggled.connect(self.window.adjustSize)

        # finally, map signals with .sender() - [QWidget] is important!
        self.signalmapper_toggles.mappedString[str].connect(self.toggle)

    def fill_list(self, list_widget, config):
        """
        fill list widget with items from config
        """
        for config_item in sorted(config, key=str.lower):
            list_item = QListWidgetItem(config_item)
            if config[config_item].enabled is False:
                list_item.setForeground(self.GRAY)
            list_widget.addItem(list_item)

    @Slot()
    def ok(self):
        """
        as default closes dialog - might be refined, for example, by settings dialog
        """
        self.window.close()
        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.check_macos_dock_icon_fix_show.emit()

    @Slot()
    def cancel(self):
        """
        as default closes dialog - might be refined, for example by settings dialog
        """
        self.window.close()
        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.check_macos_dock_icon_fix_hide.emit()

