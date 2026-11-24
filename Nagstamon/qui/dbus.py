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

# DBus connection for Qt

from os import sep
from random import random
from sys import (modules,
                 stdout)
from time import monotonic
from traceback import print_exc

from Nagstamon.config import (AppInfo,
                              OS,
                              OS_NON_LINUX,
                              RESOURCES)
from Nagstamon.qui.qt import (QObject,
                              Signal)

# DBus only interesting for Linux too
if OS not in OS_NON_LINUX:
    # get DBUS availability - still possible it does not work due to missing
    # .service file on certain distributions
    try:
        from dbus import (Interface,
                          SessionBus)
        # no DBusQtMainLoop available for Qt6
        from dbus.mainloop.glib import DBusGMainLoop as DBusMainLoop

        # flag to check later if DBus is available
        DBUS_AVAILABLE = True

    except ImportError as error:
        print(error)
        print('No DBus for desktop notification available.')
        DBUS_AVAILABLE = False


class DBus(QObject):
    """
    Create connection to DBus for desktop notification for Linux/Unix
    """

    open_statuswindow = Signal()

    # random ID needed because otherwise all instances of Nagstamon
    # will get commands by clicking on notification bubble via DBUS
    random_id = str(int(random() * 100000))

    def __init__(self):
        QObject.__init__(self)

        self.id = 0
        self.actions = [('open' + self.random_id), 'Open status window']
        self.timeout = 0
        # use icon from resources in hints, not the package icon - doesn't work either
        self.icon = ''
        # use Nagstamon image if icon is not available from the system
        # see https://developer.gnome.org/notification-spec/#icons-and-images
        self.hints = {'image-path': f'{RESOURCES}{sep}nagstamon.svg'}

        if not OS in OS_NON_LINUX and DBUS_AVAILABLE:
            if 'dbus' in modules:
                # try/except needed because of partly occuring problems with DBUS
                # see https://github.com/HenriWahl/Nagstamon/issues/320
                try:
                    # import dbus  # never used
                    dbus_mainloop = DBusMainLoop(set_as_default=True)
                    dbus_sessionbus = SessionBus(dbus_mainloop)
                    dbus_object = dbus_sessionbus.get_object('org.freedesktop.Notifications',
                                                             '/org/freedesktop/Notifications')
                    self.dbus_interface = Interface(dbus_object,
                                                    dbus_interface='org.freedesktop.Notifications')
                    # connect button to action
                    self.dbus_interface.connect_to_signal('ActionInvoked', self.action_callback)
                    self.connected = True

                except Exception:
                    print_exc(file=stdout)
                    self.connected = False
        else:
            self.connected = False

    def show(self, summary, message):
        """
        simply show a message
        """
        if self.connected:
            notification_id = self.dbus_interface.Notify(AppInfo.NAME,
                                                         self.id,
                                                         self.icon,
                                                         summary,
                                                         message,
                                                         self.actions,
                                                         self.hints,
                                                         self.timeout)
            # reuse ID
            self.id = int(notification_id)

    def action_callback(self, dummy, action):
        """
        react to clicked action button in notification bubble
        """
        if action == 'open' + self.random_id:
            self.open_statuswindow.emit()


# Wayland fix: position of the last click onto a systray icon, (0, 0) means unknown
class SystrayClickPosition:
    """
    Wayland fix: keep the click position the systray host reported via DBus
    together with the time it arrived, so that an old position left over from
    a previous click can be told apart from a fresh one
    """

    # a click position older than this does not belong to the current click
    max_age = 2.0

    def __init__(self):
        self.x = 0
        self.y = 0
        self.timestamp = 0.0

    def store(self, x, y):
        """
        store a position reported by a systray host
        """
        try:
            x, y = int(x), int(y)
        except (TypeError, ValueError):
            return
        # 0, 0 means unknown - hosts without a real click position send it
        if x == 0 and y == 0:
            return
        self.x = x
        self.y = y
        self.timestamp = monotonic()

    def fresh(self):
        """
        return the click position if it arrived recently, otherwise None
        """
        if self.timestamp > 0.0 and monotonic() - self.timestamp <= self.max_age:
            return self.x, self.y
        return None


systray_click_position = SystrayClickPosition()


def monitor_systray_clicks():
    """
    Wayland fix: XWayland knows neither the systray icon geometry nor the cursor position, but the systray
    host sends the click position as DBus call Activate(x, y) - so get it from a DBus monitoring connection
    """
    # Position is also delivered as SecondaryActivate(x, y) on middle click and
    # as ContextMenu(x, y) before a host shows its own menu. GNOME Shell for
    # example only sends Activate(x, y) on double clicks and uses
    # SecondaryActivate(x, y) for middle clicks, so all of them are useful.
    click_members = ('Activate', 'SecondaryActivate', 'ContextMenu')

    def store_position(connection, message):
        # a monitor must not reply, which would happen at an exception here, so ignore unexpected messages
        try:
            if message.get_member() in click_members:
                x, y = message.get_args_list()
                systray_click_position.store(x, y)
        except Exception:
            pass

    bus = SessionBus(private=True, mainloop=DBusMainLoop())
    # otherwise the whole process would exit if this connection gets closed
    bus.set_exit_on_disconnect(False)
    bus.add_message_filter(store_position)
    bus.call_blocking('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus.Monitoring',
                      'BecomeMonitor', 'asu', (["interface='org.kde.StatusNotifierItem'",
                                                "interface='org.freedesktop.StatusNotifierItem'"], 0),
                      timeout=1)
    return bus
