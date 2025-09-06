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
                                   statuswindow_properties)
from Nagstamon.qui.helpers import (check_servers,
                                   hide_macos_dock_icon)
from Nagstamon.qui.widgets.buttons import (Button,
                                           CSS_CLOSE_BUTTON,
                                           PushButtonHamburger)
from Nagstamon.qui.dialogs import dialogs
from Nagstamon.qui.dialogs.check_version import CheckVersion
from Nagstamon.qui.qt import (MediaPlayer,
                              Slot)
from Nagstamon.qui.widgets.combobox_servers import ComboBoxServers
from Nagstamon.qui.widgets.buttons import PushButtonBrowserURL
from Nagstamon.qui.widgets.draggables import (DraggableLabel,
                                              DraggableWidget)
from Nagstamon.qui.widgets.icon import QIconWithFilename
from Nagstamon.qui.widgets.labels import (ClosingLabel,
                                          LabelAllOK,
                                          ServerStatusLabel)
from Nagstamon.qui.widgets.layout import HBoxLayout
from Nagstamon.qui.widgets.mediaplayer import mediaplayer
from Nagstamon.qui.widgets.menu import (MenuAtCursor,
                                        MenuContext,
                                        MenuContextSystrayicon)
from Nagstamon.qui.widgets.model import Model
from Nagstamon.qui.widgets.nagstamon_logo import NagstamonLogo
from Nagstamon.qui.widgets.statuswindow import StatusWindow
from Nagstamon.qui.widgets.system_tray_icon import SystemTrayIcon
from Nagstamon.qui.widgets.toparea import TopArea
from Nagstamon.qui.widgets.treeview import TreeView

from Nagstamon.config import (conf,
                              OS_NON_LINUX,
                              OS,
                              OS_MACOS)

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)


# check for updates
check_version = CheckVersion()

# system tray icon
systrayicon = SystemTrayIcon()

# set to none here due to race condition
#statusw indow = None
#menu = None

# combined statusbar/status window
statuswindow = StatusWindow(dialogs=dialogs,
                            systrayicon=systrayicon)

# context menu for statuswindow etc.
menu = MenuContext(parent=statuswindow)

# necessary extra menu due to Qt5-Unity-integration
if not OS in OS_NON_LINUX:
    menu_systray = MenuContextSystrayicon(parent=statuswindow)
    menu_systray.menu_ready.connect(systrayicon.set_menu)
# menu has to be set here to solve Qt-5.10-Windows-systray-mess
# and non-existence of macOS-systray-context-menu
else:
    systrayicon.set_menu(menu)

# to be connected someday elsewhere
# server -> statuswindow remove_previous server
dialogs.server.edited_remove_previous.connect(statuswindow.remove_previous_server_vbox)
dialogs.server.create_server_vbox.connect(statuswindow.create_server_vbox)

dialogs.authentication.show_up.connect(statuswindow.hide_window)
dialogs.weblogin.show_up.connect(statuswindow.hide_window)

dialogs.settings.settings_ok.connect(statuswindow.save_position_to_conf)
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

# statuswindow
statuswindow.toparea.button_filters.clicked.connect(dialogs.settings.show_filters)
statuswindow.toparea.button_settings.clicked.connect(dialogs.settings.show)
statuswindow.toparea.action_exit.triggered.connect(statuswindow.exit)
# hide if settings dialog pops up
dialogs.settings.show_dialog.connect(statuswindow.hide_window)
# workaround for the timestamp trick to avoid flickering
dialogs.settings.show_dialog.connect(statuswindow.decrease_shown_timestamp)
# refresh all information after changed settings
dialogs.settings.changed.connect(statuswindow.refresh)
dialogs.settings.changed.connect(statuswindow.toparea.combobox_servers.fill)
# hide status window if version check finished
check_version.version_info_retrieved.connect(statuswindow.hide_window)
# start debug loop by signal
dialogs.settings.start_debug_loop.connect(statuswindow.worker.debug_loop)

# clenaup vbox after server deletion
dialogs.settings.server_deleted.connect(statuswindow.delete_server_vbox)

# reinitialize statuswindow when display mode settings were changed
dialogs.settings.changed_display_mode.connect(statuswindow.reinitialize)

# connect application exit with server missing dialog
dialogs.server_missing.window.button_exit.clicked.connect(statuswindow.exit)

# connect weblogin browser
dialogs.weblogin.page_loaded.connect(statuswindow.refresh)

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

# retrieve systray icon position for statuswindow position calculation
statuswindow.request_systrayicon_position.connect(systrayicon.retrieve_icon_position)

# connect statuswindow to authentication dialog
statuswindow.authenticate.connect(dialogs.authentication.show_auth_dialog)

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
    menu_systray.action_save_position.triggered.connect(statuswindow.save_position_to_conf)
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

from Nagstamon.servers import servers

# # TODO: need to be connected after server creation or config changes too
# for server in servers.values():
#     server.bridge_to_qt.set_url.connect(dialogs.weblogin.set_url)
#
