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

from Nagstamon.Config import (conf,
                              RESOURCES,
                              OS,
                              OS_MACOS)

from Nagstamon.qui.constants import ICON
from Nagstamon.qui.helpers import hide_macos_dock_icon
from Nagstamon.qui.qt import (QBrush,
                              QListWidgetItem,
                              QObject,
                              QSignalMapper,
                              QSizePolicy,
                              Qt,
                              Signal,
                              Slot,
                              uic)

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import NSApp


class Dialog(QObject):
    """
    one single dialog
    """
    # send signal e.g. to statuswindow if dialog pops up
    show_dialog = Signal()

    # dummy toggle dependencies
    TOGGLE_DEPS = {}
    # auxiliary list of checkboxes which HIDE some other widgets if triggered - for example proxy OS settings
    TOGGLE_DEPS_INVERTED = []
    # widgets that might be enabled/disebled depending on monitor server type
    VOLATILE_WIDGETS = {}
    # names of widgets and their defaults
    WIDGET_NAMES = {}
    # style stuff used by settings dialog for servers/actions listwidget
    GRAY = QBrush(Qt.GlobalColor.gray)

    def __init__(self, dialog):
        QObject.__init__(self)

        # load UI file from resources
        self.window = uic.loadUi(f'{RESOURCES}/qui/{dialog}.ui')

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

    def show(self, tab=0):
        """
        simple how method, to be enriched
        """
        # if running on macOS with disabled dock icon the dock icon might have to be made visible
        # to make Nagstamon accept keyboard input
        self.show_macos_dock_icon_if_necessary()

        # in case dock icon is configured invisible in macOS it has to be shown while dialog is shown
        # to be able to get keyboard focus
        if OS == OS_MACOS and \
                conf.icon_in_systray and \
                conf.hide_macos_dock_icon:
            hide_macos_dock_icon(False)

        # tell the world that dialog pops up
        self.show_dialog.emit()

        # reset window if only needs smaller screen estate
        self.window.adjustSize()
        self.window.show()
        # make sure dialog window will be the topmost
        self.window.raise_()
        # hidden dock icon on macOS needs extra activation
        if OS == OS_MACOS and \
                conf.icon_in_systray and \
                conf.hide_macos_dock_icon:
            NSApp.activateIgnoringOtherApps_(True)

    def toggle_visibility(self, checkbox, widgets=[]):
        """
        state of checkbox toggles visibility of widgets
        some checkboxes might trigger an inverted behaviour - thus the 'inverted' value
        """
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
        change state of depending widgets, slot for signals from checkboxes in UI
        """
        # Due to older Qt5 in Ubuntu 14.04 signalmapper has to use strings
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
            # Due to older Qt5 in Ubuntu 14.04 signalmapper has to use strings
            self.signalmapper_toggles.setMapping(checkbox, checkbox.objectName())
            checkbox.toggled.connect(self.signalmapper_toggles.map)
            checkbox.toggled.connect(self.window.adjustSize)

        # finally map signals with .sender() - [QWidget] is important!
        self.signalmapper_toggles.mappedString[str].connect(self.toggle)

    def fill_list(self, listwidget, config):
        """
        fill listwidget with items from config
        """
        for configitem in sorted(config, key=str.lower):
            listitem = QListWidgetItem(configitem)
            if config[configitem].enabled is False:
                listitem.setForeground(self.GRAY)
            listwidget.addItem(listitem)

    @Slot()
    def ok(self):
        """
        as default closes dialog - might be refined, for example by settings dialog
        """
        self.window.close()
        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.hide_macos_dock_icon_if_necessary()

    @Slot()
    def cancel(self):
        """
        as default closes dialog - might be refined, for example by settings dialog
        """
        self.window.close()
        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.hide_macos_dock_icon_if_necessary()

    def show_macos_dock_icon_if_necessary(self):
        """
        show macOS dock icon again if it is configured to be hidden
        was only necessary to show up to let dialog get keyboard focus
        """
        if OS == OS_MACOS and \
                conf.icon_in_systray and \
                conf.hide_macos_dock_icon:
            # if no window is shown already show dock icon
            if not len(dialogs.get_shown_dialogs()):
                hide_macos_dock_icon(False)

    def hide_macos_dock_icon_if_necessary(self):
        """
            hide macOS dock icon again if it is configured to be hidden
            was only necessary to show up to let dialog get keyboard focus
        """
        if OS == OS_MACOS and \
                conf.icon_in_systray and \
                conf.hide_macos_dock_icon:
            # if no window is shown anymore hide dock icon
            if not len(dialogs.get_shown_dialogs()):
                hide_macos_dock_icon(True)
