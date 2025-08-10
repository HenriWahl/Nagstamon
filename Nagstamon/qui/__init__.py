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

from os import sep
import os.path
import sys

# it is important that this import is done before importing any other qui module, because
# they may need a QApplication instance to be created
from Nagstamon.qui.widgets.app import app

from Nagstamon.qui.constants import (COLORS,
                                     COLOR_STATE_NAMES,
                                     COLOR_STATUS_LABEL,
                                     HEADERS,
                                     HEADERS_HEADERS,
                                     HEADERS_HEADERS_COLUMNS,
                                     HEADERS_HEADERS_KEYS,
                                     HEADERS_KEYS_COLUMNS,
                                     HEADERS_KEYS_HEADERS,
                                     SORT_ORDER,
                                     SORT_COLUMNS_INDEX,
                                     SPACE,
                                     WINDOW_FLAGS)
from Nagstamon.qui.globals import (dbus_connection,
                                   font,
                                   font_default,
                                   font_icons,
                                   status_window_properties)
from Nagstamon.qui.helpers import (check_servers,
                                   hide_macos_dock_icon)
from Nagstamon.qui.widgets.buttons import (Button,
                                           CSS_CLOSE_BUTTON,
                                           PushButtonHamburger)
from Nagstamon.qui.dialogs import dialogs
from Nagstamon.qui.dialogs.check_version import CheckVersion
from Nagstamon.qui.qt import (MediaPlayer,
                              Slot)
from Nagstamon.qui.widgets.buttons import PushButtonBrowserURL
from Nagstamon.qui.widgets.draggables import (DraggableLabel,
                                              DraggableWidget)
from Nagstamon.qui.widgets.icon import QIconWithFilename
from Nagstamon.qui.widgets.labels import (LabelAllOK,
                                          ServerStatusLabel)
from Nagstamon.qui.widgets.layout import HBoxLayout
from Nagstamon.qui.widgets.mediaplayer import mediaplayer
from Nagstamon.qui.widgets.menu import (MenuAtCursor,
                                        MenuContext,
                                        MenuContextSystrayicon)
from Nagstamon.qui.widgets.model import Model
from Nagstamon.qui.widgets.status_window import StatusWindow
from Nagstamon.qui.widgets.system_tray_icon import SystemTrayIcon
from Nagstamon.qui.widgets.top_area import TopArea
from Nagstamon.qui.widgets.top_area_widgets import ComboBoxServers

from Nagstamon.qui.widgets.treeview import TreeView
from Nagstamon.qui.widgets.nagstamon_logo import NagstamonLogo
from Nagstamon.qui.widgets.labels import ClosingLabel

from Nagstamon.config import (conf,
                              OS_NON_LINUX,
                              OS,
                              OS_MACOS)

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)


@Slot()
def exit():
    """
    stop all child threads before quitting instance
    """
    # store position of statuswindow/statusbar
    statuswindow.store_position_to_conf()

    # save configuration
    conf.save_config()

    # hide statuswindow first to avoid lag when waiting for finished threads
    statuswindow.hide()

    # stop statuswindow workers
    statuswindow.worker.finish.emit()
    statuswindow.worker_notification.finish.emit()

    # tell all treeview threads to stop
    for server_vbox in statuswindow.servers_vbox.children():
        server_vbox.table.worker.finish.emit()

    app.exit()


# check for updates
check_version = CheckVersion()

# system tray icon
systrayicon = SystemTrayIcon()

# set to none here due to race condition
statuswindow = None
menu = None

# combined statusbar/status window
statuswindow = StatusWindow()

# context menu for statuswindow etc.
menu = MenuContext(parent=statuswindow)

# necessary extra menu due to Qt5-Unity-integration
if not OS in OS_NON_LINUX:
    menu_systray = MenuContextSystrayicon(parent=statuswindow)
    # TODO: in theory COULD NOT work because the signal is emitted before this connection is set ?
    menu_systray.menu_ready.connect(systrayicon.set_menu)
# menu has to be set here to solve Qt-5.10-Windows-systray-mess
# and non-existence of macOS-systray-context-menu
elif conf.icon_in_systray:
    systrayicon.set_menu(menu)


# to be connected someday elsewhere
# server -> statuswindow remove_previous server
dialogs.server.edited_remove_previous.connect(statuswindow.remove_previous_server_vbox)
dialogs.server.create_server_vbox.connect(statuswindow.create_server_vbox)

dialogs.authentication.show_up.connect(statuswindow.hide_window)

dialogs.settings.settings_ok.connect(statuswindow.store_position_to_conf)
# trigger the statuswindow.worker to check if debug loop is neede and if so, start it
dialogs.settings.settings_ok.connect(statuswindow.worker.debug_loop)
dialogs.settings.server_deleted.connect(statuswindow.worker.debug_loop)
dialogs.settings.changed.connect(check_servers.check)
dialogs.settings.changed.connect(statuswindow.label_all_ok.set_color)
dialogs.settings.cancelled.connect(check_servers.check)

# when there are new settings/colors recreate icons
dialogs.settings.changed.connect(systrayicon.create_icons)

# when there are new settings/colors refresh labels
dialogs.settings.changed.connect(statuswindow.statusbar.reset)

# when new setings are applied to adjust font size
dialogs.settings.changed.connect(statuswindow.statusbar.adjust_size)

# menu
dialogs.settings.changed.connect(menu.initialize)

menu.action_settings.triggered.connect(statuswindow.hide_window)
menu.action_settings.triggered.connect(dialogs.settings.show)
menu.action_save_position.triggered.connect(statuswindow.store_position_to_conf)
menu.action_about.triggered.connect(statuswindow.hide_window)
menu.action_about.triggered.connect(dialogs.about.show)

# statuswindow
statuswindow.toparea.button_filters.clicked.connect(dialogs.settings.show_filters)
statuswindow.toparea.button_settings.clicked.connect(dialogs.settings.show)
# hide if settings dialog pops up
dialogs.settings.show_dialog.connect(statuswindow.hide_window)
# refresh all information after changed settings
dialogs.settings.changed.connect(statuswindow.refresh)
dialogs.settings.changed.connect(statuswindow.toparea.combobox_servers.fill)
# hide status window if version check finished
check_version.version_info_retrieved.connect(statuswindow.hide_window)
# start debug loop by signal
dialogs.settings.start_debug_loop.connect(statuswindow.worker.debug_loop)
# systray connections
# show status popup when systray icon was clicked
systrayicon.show_popwin.connect(statuswindow.show_window_systrayicon)
systrayicon.hide_popwin.connect(statuswindow.hide_window)
# flashing statusicon
statuswindow.worker_notification.start_flash.connect(systrayicon.flash)
statuswindow.worker_notification.stop_flash.connect(systrayicon.reset)

# trigger showing and hiding of systray icon depending on display mode
statuswindow.systrayicon_enabled.connect(systrayicon.show)
statuswindow.systrayicon_disabled.connect(systrayicon.hide)

# let statuswindow show message
mediaplayer.send_message.connect(statuswindow.show_message)
# connect with statuswindow notification worker
statuswindow.worker_notification.load_sound.connect(mediaplayer.set_media)
statuswindow.worker_notification.play_sound.connect(mediaplayer.play)

# necessary extra menu due to Qt5-Unity-integration
if not OS in OS_NON_LINUX:
    # change menu if there are changes in settings/servers
    dialogs.settings.changed.connect(menu_systray.initialize)
    menu_systray.action_settings.triggered.connect(statuswindow.hide_window)
    menu_systray.action_settings.triggered.connect(dialogs.settings.show)
    menu_systray.action_save_position.triggered.connect(statuswindow.store_position_to_conf)
    menu_systray.action_about.triggered.connect(statuswindow.hide_window)
    menu_systray.action_about.triggered.connect(dialogs.about.show)
    menu_systray.menu_ready.connect(systrayicon.set_menu)
    menu_systray.menu_ready.emit(menu_systray)

# needs to be emitted adter signal/slots are connected,
# might be necessary for others too
if conf.icon_in_systray:
    statuswindow.systrayicon_enabled.emit()
else:
    statuswindow.systrayicon_disabled.emit()
# tell the widgets that the menu is ready
menu.menu_ready.emit(menu)
