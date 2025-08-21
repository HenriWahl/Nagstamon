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

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)
from Nagstamon.qui.qt import (QAction,
                              QMenu, \
                              QCursor,
                              QPoint,
                              Signal,
                              Slot)
from Nagstamon.Servers import servers


class MenuAtCursor(QMenu):
    """
    Displays the menu at the current mouse pointer position.

    Signals:
        is_shown (bool): Emitted with True when the menu is shown, and with False when it is closed.

    Args:
        parent (QWidget, optional): The parent widget of the menu.

    Methods:
        show_at_cursor(): Shows the menu at the current mouse pointer position and emits is_shown signals.
    """
    # flag to avoid too fast popping up menus
    # available = True

    is_shown = Signal(bool)

    def __init__(self, parent=None):
        QMenu.__init__(self, parent=parent)

    @Slot()
    def show_at_cursor(self):
        """
        Pop up at mouse pointer position, lock itself to avoid constantly popping menus on Windows
        """
        # get cursor coordinates and decrease them to show menu under mouse pointer
        x = QCursor.pos().x() - 10
        y = QCursor.pos().y() - 10
        # tell the world that the menu will be shown
        self.is_shown.emit(True)
        # show menu
        self.exec(QPoint(x, y))
        # tell world that menu will be closed
        self.is_shown.emit(False)
        del x, y

class MenuContext(MenuAtCursor):
    """
    class for universal context menu, used at systray icon and hamburger menu
    """

    menu_ready = Signal(QMenu)

    def __init__(self, parent=None):
        MenuAtCursor.__init__(self, parent=parent)

        self.parent_statuswindow = self.parentWidget()

        # connect all relevant widgets which should show the context menu
        for widget in [self.parent_statuswindow.toparea.button_hamburger_menu,
                       self.parent_statuswindow.toparea.label_version,
                       self.parent_statuswindow.toparea.label_empty_space,
                       self.parent_statuswindow.toparea.logo,
                       self.parent_statuswindow.statusbar.logo,
                       self.parent_statuswindow.statusbar.label_message]:
            self.menu_ready.connect(widget.set_menu)

        for color_label in self.parent_statuswindow.statusbar.color_labels.values():
            self.menu_ready.connect(color_label.set_menu)

        self.initialize()

    @Slot()
    def initialize(self):
        """
        add actions and servers to menu
        """

        # first clear to get rid of old servers
        self.clear()

        self.action_refresh = QAction('Refresh', self)
        self.action_refresh.triggered.connect(self.parent_statuswindow.refresh)
        self.addAction(self.action_refresh)

        self.action_recheck = QAction('Recheck all', self)
        self.action_recheck.triggered.connect(self.parent_statuswindow.recheck_all)
        self.addAction(self.action_recheck)

        self.addSeparator()

        # dict to hold all servers - more flexible this way
        self.action_servers = dict()

        # connect every server to its monitoring webpage
        for server in sorted([x.name for x in conf.servers.values() if x.enabled], key=str.lower):
            self.action_servers[server] = QAction(server, self)
            self.action_servers[server].triggered.connect(servers[server].open_monitor_webpage)
            self.addAction(self.action_servers[server])

        self.addSeparator()

        self.action_settings = QAction('Settings...', self)
        self.action_settings.triggered.connect(self.parent_statuswindow.hide_window)
        self.action_settings.triggered.connect(self.parent_statuswindow.injected_dialogs.settings.show)
        self.addAction(self.action_settings)

        self.action_save_position = QAction('Save position', self)
        # TODO: remove action from menu if not needed aka not floating
        if conf.statusbar_floating:
            self.addAction(self.action_save_position)
        self.action_save_position.triggered.connect(self.parent_statuswindow.save_position_to_conf)

        self.addSeparator()

        self.action_about = QAction('About...', self)
        self.action_about.triggered.connect(self.parent_statuswindow.hide_window)
        self.action_about.triggered.connect(self.parent_statuswindow.injected_dialogs.about.show)
        self.addAction(self.action_about)

        self.action_exit = QAction('Exit', self)
        self.action_exit.triggered.connect(self.parent_statuswindow.exit)
        self.addAction(self.action_exit)

        # tell all widgets to use the new menu
        self.menu_ready.emit(self)


class MenuContextSystrayicon(MenuContext):
    """
    Necessary for Ubuntu 16.04 new Qt5-Systray-AppIndicator meltdown
    Maybe in general a good idea to offer status window popup here
    """

    action_status = None

    def __init__(self, parent=None):
        """
        clone of normal MenuContext which serves well in all other places
        but no need of signal/slots initialization
        """
        QMenu.__init__(self, parent=parent)

        self.parent_statuswindow = self.parentWidget()

        # initialize as default + extra
        self.initialize()


    def initialize(self):
        """
        initialize as inherited + a popup menu entry mostly useful in Ubuntu Unity
        """
        MenuContext.initialize(self)
        # makes even less sense on OSX
        if OS != OS_MACOS:
            self.action_status = QAction('Show status window', self)
            self.action_status.triggered.connect(self.parent_statuswindow.show_window_systrayicon)
            self.insertAction(self.action_refresh, self.action_status)
            self.insertSeparator(self.action_refresh)