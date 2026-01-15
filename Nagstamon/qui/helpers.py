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

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)
from Nagstamon.qui.qt import (QObject,
                              QPoint,
                              Signal,
                              Slot)
from Nagstamon.qui.widgets.app import app
from Nagstamon.servers import servers

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)


class CheckServers(QObject):
    """
    check if there are any servers configured and enabled
    """
    # signal to emit if no server is configured or enabled
    checked = Signal(str)

    @Slot()
    def check(self):
        """
        check if there are any servers configured and enabled
        """
        # no server is configured
        if len(servers) == 0:
            # emit signal that no server is configured
            self.checked.emit('no_server')
        # no server is enabled
        elif len([x for x in conf.servers.values() if x.enabled is True]) == 0:
            # emit signal that no server is enabled
            self.checked.emit('no_server_enabled')


def hide_macos_dock_icon(hide=False):
    """
    small helper to make dock icon visible or not in macOS
    inspired by https://stackoverflow.com/questions/6796028/start-a-gui-process-in-mac-os-x-without-dock-icon
    """
    if hide:
        NSApp.setActivationPolicy_(NSApplicationPresentationHideDock)
    else:
        NSApp.setActivationPolicy_(NSApplicationPresentationDefault)


def get_screen_name(x, y):
    """
    find out which screen the given coordinates belong to
    gives back 'None' if coordinates are out of any known screen
    """
    # integerify these values as they *might* be strings
    x = int(x)
    y = int(y)

    # QApplication (using Qt5 and/or its Python binding on RHEL/CentOS 7) has no attribute 'screenAt'
    try:
        screen = app.screenAt(QPoint(x, y))
        del x, y
        if screen:
            return screen.name
        else:
            return None
    except:
        return None


def get_screen_geometry(screen_name):
    """
    set screen for fullscreen
    """
    for screen in app.screens():
        if screen.name() == screen_name:
            return screen.geometry()

    # if screen_name didn't match available use primary screen
    return app.primaryScreen().geometry()


# to be used in nagstamon.py and qui/widgets/dialogs/settings.py
check_servers = CheckServers()
