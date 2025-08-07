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
import datetime
from os import sep
import os.path
import subprocess
import time
import traceback
from urllib.parse import quote

# it is important that this import is done before importing any other qui module, because
# they may need a QApplication instance to be created
from Nagstamon.qui.widgets.app import app

from Nagstamon.qui.constants import (COLORS,
                                     COLOR_STATE_NAMES,
                                     COLOR_STATUS_LABEL,
                                     QBRUSHES,
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
from Nagstamon.qui.helpers import (create_brushes,
                                   check_servers,
                                   hide_macos_dock_icon)
from Nagstamon.qui.widgets.button import (Button,
                                          CSS_CLOSE_BUTTON,
                                          PushButtonHamburger)
from Nagstamon.qui.dialogs import dialogs
from Nagstamon.qui.dialogs import Dialog
from Nagstamon.qui.dialogs.check_version import CheckVersion
from Nagstamon.qui.widgets.button import PushButtonBrowserURL
from Nagstamon.qui.widgets.draggables import (DraggableLabel,
                                              DraggableWidget)
from Nagstamon.qui.widgets.icon import QIconWithFilename
from Nagstamon.qui.widgets.labels import (LabelAllOK,
                                          ServerStatusLabel)
from Nagstamon.qui.widgets.layout import HBoxLayout
from Nagstamon.qui.widgets.menu import (MenuAtCursor,
                                        MenuContext,
                                        MenuContextSystrayicon)
from Nagstamon.qui.widgets.model import Model
from Nagstamon.qui.widgets.server_vbox import ServerVBox
from Nagstamon.qui.widgets.statusbar import StatusBar
from Nagstamon.qui.widgets.system_tray_icon import SystemTrayIcon
from Nagstamon.qui.widgets.top_area import TopArea
from Nagstamon.qui.widgets.top_area_widgets import ComboBoxServers

from Nagstamon.qui.widgets.treeview import TreeView
from Nagstamon.qui.widgets.nagstamon_logo import NagstamonLogo
from Nagstamon.qui.widgets.labels import ClosingLabel
# for details of imports look into qt.py
from Nagstamon.qui.qt import *

from Nagstamon.config import (AppInfo,
                              conf,
                              debug_queue,
                              OS_NON_LINUX,
                              OS,
                              OS_MACOS,
                              OS_WINDOWS,
                              RESOURCES,
                              DESKTOP_WAYLAND)

from Nagstamon.Servers import (SERVER_TYPES,
                               servers,
                               get_enabled_servers,
                               get_status_count)

from Nagstamon.helpers import (is_found_by_re,
                               webbrowser_open,
                               resource_files,
                               STATES,
                               STATES_SOUND,
                               SORT_COLUMNS_FUNCTIONS,
                               urlify)

# only on X11/Linux thirdparty path should be added because it contains the Xlib module
# needed to tell window manager via EWMH to keep Nagstamon window on all virtual desktops
if OS not in OS_NON_LINUX and not DESKTOP_WAYLAND:
    # extract thirdparty path from resources path - make submodules accessible by thirdparty modules
    THIRDPARTY = sep.join(RESOURCES.split(sep)[0:-1] + ['thirdparty'])
    sys.path.insert(0, THIRDPARTY)

    # Xlib for EWMH needs the file ~/.Xauthority and crashes if it does not exist
    if not os.path.exists(os.path.expanduser('~') + sep + '.Xauthority'):
        open(os.path.expanduser('~') + sep + '.Xauthority', 'a').close()

    from Nagstamon.thirdparty.ewmh import EWMH

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)

# add nagstamon.ttf with icons to fonts
QFontDatabase.addApplicationFont(f'{RESOURCES}{sep}nagstamon.ttf')

# always stay in normal weight without any italic
# ICONS_FONT = QFont('Nagstamon', FONT.pointSize() + 2, QFont.Weight.Normal, False)

# set style for tooltips globally - to sad not all properties can be set here
app.setStyleSheet('''QToolTip { margin: 3px;
                                }''')


class StatusWindow(QWidget):
    """
    Consists of statusbar, toparea and scrolling area.
    Either statusbar is shown or (toparea + scrolling area)
    """
    # sent by .resize_window()
    resizing = Signal()

    # send when windows opens, e.g. for stopping notifications
    showing = Signal()

    # send when window shrinks down to statusbar or closes
    hiding = Signal()

    # signal to be sent to all server workers to recheck all
    recheck = Signal()

    # signal to be sent to all treeview workers to clear server event history
    # after 'Refresh'-button has been pressed
    clear_event_history = Signal()

    def __init__(self):
        """
        Status window combined from status bar and popup window
        """
        QWidget.__init__(self)

        # immediately hide to avoid flicker on Windows and OSX
        self.hide()

        # ewmh.py in thirdparty directory needed to keep floating statusbar on all desktops in Linux
        if not OS in OS_NON_LINUX and not DESKTOP_WAYLAND:
            self.ewmh = EWMH()

        # avoid quitting when using Qt.Tool flag and closing settings dialog
        app.setQuitOnLastWindowClosed(False)

        # show tooltips even if popup window has no focus
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)

        if OS == OS_MACOS:
            # avoid hiding window if it has no focus - necessary on OSX if using flag Qt.Tool
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)

        self.setWindowTitle(AppInfo.NAME)
        self.setWindowIcon(QIcon(f'{RESOURCES}{sep}nagstamon.svg'))

        self.vbox = QVBoxLayout(self)  # global VBox
        self.vbox.setSpacing(0)  # no spacing
        self.vbox.setContentsMargins(0, 0, 0, 0)  # no margin

        self.statusbar = StatusBar(parent=self)  # statusbar HBox
        self.toparea = TopArea(parent=self)  # toparea HBox
        # no need to be seen first
        self.toparea.hide()

        self.servers_scrollarea = QScrollArea(self)  # scrollable area for server vboxes
        # avoid horizontal scrollbars
        self.servers_scrollarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # necessary widget to contain vbox for servers
        self.servers_scrollarea_widget = QWidget(self.servers_scrollarea)
        self.servers_scrollarea.hide()

        self.vbox.addWidget(self.statusbar)
        self.vbox.addWidget(self.toparea)
        self.vbox.addWidget(self.servers_scrollarea)

        self.servers_vbox = QVBoxLayout(self.servers_scrollarea)  # VBox full of servers
        self.servers_vbox.setSpacing(0)
        self.servers_vbox.setContentsMargins(0, 0, 0, 0)

        self.label_all_ok = LabelAllOK(parent=self)
        self.label_all_ok.hide()

        self.servers_vbox.addWidget(self.label_all_ok)

        # test with OSX top menubar
        if OS == OS_MACOS:
            self.menubar = QMenuBar()
            action_exit = QAction('exit', self.menubar)
            action_settings = QAction('settings', self.menubar)
            self.menubar.addAction(action_settings)
            self.menubar.addAction(action_exit)

        # connect logo of statusbar
        self.statusbar.logo.window_moved.connect(self.store_position)
        self.statusbar.logo.window_moved.connect(self.hide_window)
        self.statusbar.logo.window_moved.connect(self.correct_moving_position)
        self.statusbar.logo.mouse_pressed.connect(self.store_position)

        # after status summarization check if window has to be resized
        self.statusbar.resize.connect(self.adjust_size)

        # statusbar label has been entered by mouse -> show
        for label in self.statusbar.color_labels.values():
            label.mouse_entered.connect(self.show_window_after_checking_for_hover)
            label.mouse_released.connect(self.show_window_after_checking_for_clicking)

        # connect message label to hover
        self.statusbar.label_message.mouse_entered.connect(self.show_window_after_checking_for_hover)
        self.statusbar.label_message.mouse_released.connect(self.show_window_after_checking_for_clicking)

        # when logo in toparea was pressed hurry up to save the position so the statusbar will not jump
        self.toparea.logo.window_moved.connect(self.store_position)
        self.toparea.logo.window_moved.connect(self.hide_window)
        self.toparea.logo.window_moved.connect(self.correct_moving_position)
        self.toparea.logo.mouse_pressed.connect(self.store_position)

        # when version label in toparea was pressed hurry up to save the position so the statusbar will not jump
        self.toparea.label_version.window_moved.connect(self.store_position)
        self.toparea.label_version.window_moved.connect(self.hide_window)
        self.toparea.label_version.window_moved.connect(self.correct_moving_position)
        self.toparea.label_version.mouse_pressed.connect(self.store_position)

        # when empty space in toparea was pressed hurry up to save the position so the statusbar will not jump
        self.toparea.label_empty_space.window_moved.connect(self.store_position)
        self.toparea.label_empty_space.window_moved.connect(self.hide_window)
        self.toparea.label_empty_space.window_moved.connect(self.correct_moving_position)
        self.toparea.label_empty_space.mouse_pressed.connect(self.store_position)

        # buttons in toparea
        self.toparea.button_filters.clicked.connect(dialogs.settings.show_filters)
        self.toparea.button_recheck_all.clicked.connect(self.recheck_all)
        self.toparea.button_refresh.clicked.connect(self.refresh)
        self.toparea.button_settings.clicked.connect(self.hide_window)
        self.toparea.button_settings.clicked.connect(dialogs.settings.show)
        self.toparea.button_close.clicked.connect(self.hide_window)

        # if monitor was selected in combobox its monitor window is opened
        self.toparea.combobox_servers.monitor_opened.connect(self.hide_window)

        # hide if settings dialog pops up
        dialogs.settings.show_dialog.connect(self.hide_window)

        # refresh all information after changed settings
        dialogs.settings.changed.connect(self.refresh)
        dialogs.settings.changed.connect(self.toparea.combobox_servers.fill)

        # hide status window if version check finished
        check_version.version_info_retrieved.connect(self.hide_window)

        # worker and thread duo needed for notifications
        self.worker_notification_thread = QThread(parent=self)
        self.worker_notification = self.Worker_Notification(status_window_properties)

        # clean shutdown of thread
        self.worker_notification.finish.connect(self.finish_worker_notification_thread)

        # flashing statusbar
        self.worker_notification.start_flash.connect(self.statusbar.flash)
        self.worker_notification.stop_flash.connect(self.statusbar.reset)

        # desktop notification
        self.worker_notification.desktop_notification.connect(self.desktop_notification)

        # react to open button in notification bubble
        dbus_connection.open_statuswindow.connect(self.show_window_from_notification_bubble)

        # stop notification if window gets shown or hidden
        self.hiding.connect(self.worker_notification.stop)

        # systray connections
        # show status popup when systray icon was clicked
        systrayicon.show_popwin.connect(self.show_window_systrayicon)
        systrayicon.hide_popwin.connect(self.hide_window)
        # flashing statusicon
        self.worker_notification.start_flash.connect(systrayicon.flash)
        self.worker_notification.stop_flash.connect(systrayicon.reset)

        # context menu, checking for existence necessary at startup
        global menu
        if not menu == None:
            systrayicon.set_menu(menu)

        self.worker_notification.moveToThread(self.worker_notification_thread)
        # start with low priority
        self.worker_notification_thread.start(QThread.Priority.LowestPriority)

        self.create_server_vboxes()

        # connect status window server vboxes to systray
        for server_vbox in self.servers_vbox.children():
            if 'server' in server_vbox.__dict__.keys():
                # tell systray after table was refreshed
                server_vbox.table.worker.new_status.connect(systrayicon.show_state)
                # show error icon in systray
                server_vbox.table.worker.show_error.connect(systrayicon.set_error)
                server_vbox.table.worker.hide_error.connect(systrayicon.reset_error)

        self.servers_scrollarea_widget.setLayout(self.servers_vbox)
        self.servers_scrollarea.setWidget(self.servers_scrollarea_widget)
        self.servers_scrollarea.setWidgetResizable(True)

        # create brushes for treeview
        create_brushes()

        # needed for moving the statuswindow
        status_window_properties.moving = False
        status_window_properties.relative_x = False
        status_window_properties.relative_y = False

        # helper values for QTimer.singleShot move attempt
        self.move_to_x = self.move_to_y = 0

        # stored x y values for systemtray icon
        status_window_properties.icon_x = 0
        status_window_properties.icon_y = 0

        # flag to mark if window is shown or not
        if conf.windowed:
            status_window_properties.is_shown = True
        else:
            status_window_properties.is_shown = False

        # store show_window timestamp to avoid flickering window in KDE5 with systray
        status_window_properties.is_shown_timestamp = time.time()

        # store timestamp to avoid reappearing window shortly after clicking onto toparea
        status_window_properties.is_hiding_timestamp = time.time()

        # if status_ok is true no server_vboxes are needed
        status_window_properties.status_ok = True

        # timer for waiting to set is_shown flag
        self.timer = QTimer(self)

        # a thread + worker is necessary to do actions thread-safe in background
        # like debugging
        self.worker_thread = QThread(parent=self)
        self.worker = self.Worker()
        self.worker.moveToThread(self.worker_thread)
        # start thread and debugging loop if debugging is enabled
        if conf.debug_mode:
            self.worker_thread.started.connect(self.worker.debug_loop)
        # start debug loop by signal
        dialogs.settings.start_debug_loop.connect(self.worker.debug_loop)
        # start with low priority
        self.worker_thread.start(QThread.Priority.LowestPriority)

        # clean shutdown of thread
        self.worker.finish.connect(self.finish_worker_thread)

        # finally show up
        self.set_mode()

    def get_screen(self):
        """
        very hackish fix for https://github.com/HenriWahl/Nagstamon/issues/865
        should actually fit into qt.py but due to the reference to `app` it could only
        be solved here
        """
        # Qt6 has .screen() as replacement for QDesktopWidget...
        if QT_VERSION_MAJOR > 5:
            return self.screen()
        # ...and .screen() exists since Qt5 5.15...
        elif QT_VERSION_MINOR < 15:
            return app.desktop()
        # ...so newer ones can use .screen() again
        else:
            return self.screen()

    def set_mode(self):
        """
            apply presentation mode
        """
        # so sorry but how to solve this Qt-5.10-Windows-mess otherwise?
        global systrayicon

        # hide everything first
        self.hide_window()
        self.statusbar.hide()
        self.toparea.hide()
        self.servers_scrollarea.hide()

        if conf.statusbar_floating:
            # show icon in dock if window is set
            if OS == OS_MACOS:
                # in floating mode always show dock icon - right now I am not able to
                # get the icon hidden
                hide_macos_dock_icon(False)

            # no need for systray
            systrayicon.hide()
            self.statusbar.show()

            # show statusbar/statuswindow on last saved position
            # when coordinates are inside known screens
            if get_screen_name(conf.position_x, conf.position_y):
                self.move(conf.position_x, conf.position_y)
            else:
                # get available desktop specs
                available_x = self.get_screen().availableGeometry().x()
                available_y = self.get_screen().availableGeometry().y()
                self.move(available_x, available_y)

            # statusbar and detail window should be frameless and stay on top
            # tool flag helps to be invisible in taskbar
            self.setWindowFlags(WINDOW_FLAGS)

            # show statusbar without being active, just floating
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

            # necessary to be shown before Linux EWMH-mantra can be applied
            self.show()

            # X11/Linux needs some special treatment to get the statusbar floating on all virtual desktops
            if OS not in OS_NON_LINUX and not DESKTOP_WAYLAND:
                # get all windows...
                winid = self.winId().__int__()
                self.ewmh.setWmDesktop(winid, 0xffffffff)
                self.ewmh.display.flush()

            # show statusbar/statuswindow on last saved position
            # when coordinates are inside known screens
            if get_screen_name(conf.position_x, conf.position_y):
                self.move(conf.position_x, conf.position_y)
            else:
                # get available desktop specs
                available_x = self.get_screen().availableGeometry().x()
                available_y = self.get_screen().availableGeometry().y()
                self.move(available_x, available_y)

            # need a close button
            self.toparea.button_close.show()

        elif conf.icon_in_systray:
            # no need for icon in dock if in systray
            if OS == OS_MACOS:
                hide_macos_dock_icon(conf.hide_macos_dock_icon)

            # statusbar and detail window should be frameless and stay on top
            # tool flag helps to be invisible in taskbar
            self.setWindowFlags(WINDOW_FLAGS)

            # show statusbar without being active, just floating
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

            # yeah! systray!
            systrayicon.show()

            # need a close button
            self.toparea.button_close.show()

        elif conf.fullscreen:
            # no need for systray
            systrayicon.hide()

            # needed permanently
            self.toparea.show()
            self.servers_scrollarea.show()

            # get screen geometry to get right screen to position window on
            screen_geometry = get_screen_geometry(conf.fullscreen_display)
            self.move(screen_geometry.x(), screen_geometry.y())

            # keep window entry in taskbar and thus no Qt.Tool
            self.setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)

            # show statusbar actively
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

            # newer Qt5 seem to be better regarding fullscreen mode on non-OSX
            self.show_window()
            # fullscreen mode is rather buggy on everything other than OSX so just use a maximized window
            if OS == OS_MACOS:
                self.showFullScreen()
                # in fullscreen mode dock icon does not disturb because the dock is away anyway
                hide_macos_dock_icon(False)
            else:
                self.show()
                self.showMaximized()

            # no need for close button
            self.toparea.button_close.hide()

        elif conf.windowed:
            # show icon in dock if window is set
            if OS == OS_MACOS:
                # in windowed mode always show dock icon
                hide_macos_dock_icon(False)

            systrayicon.hide()

            # no need for close button
            self.toparea.button_close.hide()
            self.toparea.show()
            self.servers_scrollarea.show()

            # keep window entry in taskbar and thus no Qt.Tool
            self.setWindowFlags(Qt.WindowType.Widget)

            # show statusbar actively
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

            # some maybe sensible default
            self.setMinimumSize(700, 300)
            self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

            # default maximum size
            self.setMaximumSize(16777215, 16777215)

            self.move(conf.position_x, conf.position_y)
            self.resize(conf.position_width, conf.position_height)

            # make sure window is shown
            self.show()
            self.showNormal()
            self.show_window()

            # make sure window comes up
            self.raise_()

        # store position for showing/hiding statuswindow
        self.stored_x = self.x()
        self.stored_y = self.y()
        self.stored_width = self.width()

    def sort_server_vboxes(self):
        """
        sort ServerVBoxes alphabetically
        """
        # shortly after applying changes a QObject might hang around in the children list which should
        # be filtered out this way
        vboxes_dict = dict()
        for child in self.servers_vbox.children():
            if 'server' in child.__dict__.keys():
                vboxes_dict[child.server.name] = child

        # freshly set servers_scrollarea_widget and its layout servers_vbox
        servers_vbox_new = QVBoxLayout()  # VBox full of servers
        servers_vbox_new.setContentsMargins(0, 0, 0, 0)
        servers_vbox_new.setSpacing(0)

        # sort server vboxes
        for vbox in sorted(vboxes_dict):
            vboxes_dict[vbox].setParent(None)
            servers_vbox_new.addLayout(vboxes_dict[vbox])

        # add expanding stretching item at the end for fullscreen beauty
        servers_vbox_new.addSpacerItem(QSpacerItem(0, self.get_screen().availableGeometry().height(),
                                                   QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # switch to new servers_vbox
        self.servers_vbox = servers_vbox_new
        # necessary widget to contain vbox for servers
        self.servers_scrollarea_widget = QWidget()
        self.servers_scrollarea_widget.setLayout(self.servers_vbox)
        self.servers_scrollarea.setWidget(self.servers_scrollarea_widget)

        self.servers_scrollarea.contentsMargins().setTop(0)
        self.servers_scrollarea.contentsMargins().setBottom(0)

        del vboxes_dict

    @Slot(str)
    def create_server_vbox(self, name):
        """
        internally used to create enabled servers to be displayed
        """
        server = servers[name]

        # create server vboxed from current running servers
        if server.enabled:
            # display authentication dialog if password is not known
            if not conf.servers[server.name].save_password and \
                    not conf.servers[server.name].use_autologin and \
                    conf.servers[server.name].password == '' and \
                    not conf.servers[server.name].authentication == 'kerberos':
                dialogs.authentication.show_auth_dialog(server.name)

            # without parent, there is some flickering when starting
            server_vbox = ServerVBox(server, parent=self)

            # important to set correct server to worker, especially after server changes
            server_vbox.table.worker.server = server

            # connect to global resize signal
            server_vbox.table.ready_to_resize.connect(self.adjust_size)

            # tell statusbar to summarize after table was refreshed
            server_vbox.table.worker.new_status.connect(self.statusbar.summarize_states)
            server_vbox.table.worker.new_status.connect(self.raise_window_on_all_desktops)

            # if problems go themselves there is no need to notify user anymore
            server_vbox.table.worker.problems_vanished.connect(self.worker_notification.stop)

            # show the error message in statusbar
            server_vbox.table.worker.show_error.connect(self.statusbar.set_error)
            server_vbox.table.worker.hide_error.connect(self.statusbar.reset_error)

            # tell notification worker to do something AFTER the table was updated
            server_vbox.table.status_changed.connect(self.worker_notification.start)

            # and to update status window
            server_vbox.table.refreshed.connect(self.update_window)

            # hide statuswindow if authentication dialog is to be shown
            server_vbox.button_authenticate.clicked.connect(self.hide_window)

            # tell table it should remove freshness of formerly new items when window closes
            # because apparently the new events have been seen now
            self.hiding.connect(server_vbox.table.worker.unfresh_event_history)

            # stop notification if statuswindow pops up
            self.showing.connect(self.worker_notification.stop)

            # tell server worker to recheck all hosts and services
            self.recheck.connect(server_vbox.table.worker.recheck_all)

            # refresh table after changed settings
            dialogs.settings.changed.connect(server_vbox.table.refresh)

            # listen if statuswindow cries for event history clearance
            self.clear_event_history.connect(server_vbox.table.worker.unfresh_event_history)

            self.sort_server_vboxes()

            return server_vbox
        else:
            return None

    def create_server_vboxes(self):
        """
        create VBox for each enabled server
        """
        for server in servers.values():
            if server.enabled:
                server_vbox = self.create_server_vbox(server.name)
                self.servers_vbox.addLayout(server_vbox)
        self.sort_server_vboxes()

    @Slot(str)
    def delete_server_vbox(self, name):
        """
        delete VBox for server with given name - called by signal from settings dialog
        """
        for vbox in self.servers_vbox.children():
            if vbox.server.name == name:
                # stop thread by falsificate running flag
                vbox.table.worker.running = False
                vbox.table.worker.finish.emit()
                break

    @Slot()
    def show_window_after_checking_for_clicking(self):
        """
        being called after clicking statusbar - check if window should be showed
        """
        if conf.popup_details_clicking:
            self.show_window()

    @Slot()
    def show_window_after_checking_for_hover(self):
        """
        being called after hovering over statusbar - check if window should be showed
        """
        if conf.popup_details_hover:
            self.show_window()

    @Slot()
    def show_window_from_notification_bubble(self):
        """
        show status window after button being clicked in notification bubble
        """
        if conf.statusbar_floating:
            self.show_window()
        elif conf.icon_in_systray:
            self.show_window_systrayicon()

    @Slot()
    def show_window_systrayicon(self):
        """
        handle clicks onto systray icon
        """
        if not status_window_properties.is_shown:
            # under unfortunate circumstances statusbar might have the the moving flag true
            # fix it here because it makes no sense but might cause non-appearing statuswindow‚
            status_window_properties.moving = False

            # already show here because was closed before in hide_window()
            # best results achieved when doing .show() before .show_window()
            self.show()
            self.show_window()
        else:
            self.hide_window()

    @Slot()
    def show_window(self, event=None):
        """
            used to show status window when its appearance is triggered, also adjusts geometry
        """
        # do not show up when being dragged around
        if not status_window_properties.moving:
            # check if really all is OK
            for vbox in self.servers_vbox.children():
                if vbox.server.all_ok and \
                        vbox.server.status == '' and \
                        not vbox.server.refresh_authentication and \
                        not vbox.server.tls_error:
                    status_window_properties.status_ok = True
                else:
                    status_window_properties.status_ok = False
                    break

            # here we should check if scroll_area should be shown at all
            if not status_window_properties.status_ok:
                # store timestamp to avoid flickering as in https://github.com/HenriWahl/Nagstamon/issues/184
                status_window_properties.is_shown_timestamp = time.time()

                if not conf.fullscreen and not conf.windowed:
                    # attempt to avoid flickering on MacOSX - already hide statusbar here
                    self.statusbar.hide()
                    # show the other status window components
                    self.toparea.show()
                    self.servers_scrollarea.show()
                else:
                    self.label_all_ok.hide()

                for vbox in self.servers_vbox.children():
                    if not vbox.server.all_ok:
                        vbox.show_all()
                    # show at least server vbox header to notify about connection or other errors
                    elif vbox.server.status != '' or vbox.server.refresh_authentication or vbox.server.tls_error:
                        vbox.show_only_header()
                    elif vbox.server.all_ok and vbox.server.status == '':
                        vbox.hide_all()

                    # depending on authentication state show reauthentication button
                    if vbox.server.refresh_authentication:
                        vbox.button_authenticate.show()
                    else:
                        vbox.button_authenticate.hide()

                    # depending on TLS error show fix-TLS-button
                    if vbox.server.tls_error:
                        vbox.button_fix_tls_error.show()
                    else:
                        vbox.button_fix_tls_error.hide()

                if not conf.fullscreen and \
                        not conf.windowed:
                    # theory...
                    width, height, x, y = self.calculate_size()
                    # ...and practice
                    self.resize_window(width, height, x, y)
                    # switch on
                    if OS == OS_MACOS:
                        # delayed because of flickering window in OSX
                        self.timer.singleShot(200, self.set_shown)
                    else:
                        self.set_shown()

                    # avoid horizontally scrollable tables
                    self.adjust_dummy_columns()

                    self.show()

                    # Using the EWMH protocol to move the window to the active desktop.
                    # Seemed to be a problem on XFCE
                    # https://github.com/HenriWahl/Nagstamon/pull/199
                    if not OS in OS_NON_LINUX and conf.icon_in_systray:
                        try:
                            winid = self.winId().__int__()
                            deskid = self.ewmh.getCurrentDesktop()
                            self.ewmh.setWmDesktop(winid, deskid)
                            self.ewmh.display.flush()
                            # makes the window manager switch to the desktop where this widget has appeared
                            self.raise_()
                        except Exception:
                            # workaround for https://github.com/HenriWahl/Nagstamon/issues/246#issuecomment-220478066
                            pass

                    # tell others like notification that statuswindow shows up now
                    self.showing.emit()

            else:
                # hide vboxes in fullscreen and whole window in any other case if all is OK
                for vbox in self.servers_vbox.children():
                    vbox.hide_all()
                if conf.fullscreen or conf.windowed:
                    self.label_all_ok.show()
                if conf.icon_in_systray or conf.statusbar_floating:
                    self.hide_window()

            # If the mouse cursor drives too fast over and out the window will not be hidden.
            # Thus we check again with this timer to catch missed mouse-outs.
            # causes trouble in Wayland so is disabled for it
            if conf.close_details_hover and \
                    conf.statusbar_floating and \
                    status_window_properties.is_shown and \
                    not DESKTOP_WAYLAND:
                self.periodically_check_window_under_mouse_and_hide()

    def periodically_check_window_under_mouse_and_hide(self):
        """
        Periodically check if window is under mouse and hide it if not
        """
        if not self.hide_window_if_not_under_mouse():
            self.timer.singleShot(1000, self.periodically_check_window_under_mouse_and_hide)

    def hide_window_if_not_under_mouse(self):
        """
        Hide window if it is under mouse pointer
        """
        mouse_pos = QCursor.pos()
        # Check mouse cursor over window and an opened context menu or dropdown list
        if self.geometry().contains(mouse_pos.x(), mouse_pos.y()) or \
                not app.activePopupWidget() is None or \
                status_window_properties.is_shown:
            return False

        self.hide_window()
        return True

    @Slot()
    def update_window(self):
        """
            redraw window content, to be effective only when window is shown
        """
        if status_window_properties.is_shown or \
                conf.fullscreen or \
                (conf.windowed and status_window_properties.is_shown):
            self.show_window()

    @Slot()
    def hide_window(self):
        """
        hide window if not needed
        """
        if not conf.fullscreen and not conf.windowed:
            # only hide if shown and not locked or if not yet hidden if moving
            if status_window_properties.is_shown is True or \
                    status_window_properties.is_shown is True and \
                    status_window_properties.moving is True:
                # only hide if shown at least a fraction of a second
                # or has not been hidden a too short time ago
                if status_window_properties.is_shown_timestamp + 0.5 < time.time() or \
                        status_window_properties.is_hiding_timestamp + 0.2 < time.time():
                    if conf.statusbar_floating:
                        self.statusbar.show()
                    self.toparea.hide()
                    self.servers_scrollarea.hide()
                    # macOS needs this since Qt6 to avoid statuswindow size changeability
                    # looks silly but works to force using the own hint as hint
                    if OS == OS_MACOS:
                        self.setMinimumSize(self.sizeHint())
                        self.setMaximumSize(self.sizeHint())
                    else:
                        self.setMinimumSize(1, 1)
                    self.adjustSize()

                    if conf.icon_in_systray:
                        self.close()

                    # switch off
                    status_window_properties.is_shown = False

                    # flag to reflect top-ness of window/statusbar
                    status_window_properties.top = False

                    # reset icon x y
                    status_window_properties.icon_x = 0
                    status_window_properties.icon_y = 0

                    # tell the world that window goes down
                    self.hiding.emit()
                    if conf.windowed:
                        self.hide()

                    # store time of hiding
                    status_window_properties.is_hiding_timestamp = time.time()

                    self.move(self.stored_x, self.stored_y)

    @Slot()
    def correct_moving_position(self):
        """
        correct position if moving and cursor started outside statusbar
        """
        if status_window_properties.moving:
            mouse_x = QCursor.pos().x()
            mouse_y = QCursor.pos().y()
            # when cursor is outside moved window correct the coordinates of statusbar/statuswindow
            if not statuswindow.geometry().contains(mouse_x, mouse_y):
                rect = statuswindow.geometry()
                corrected_x = int(mouse_x - rect.width() // 2)
                corrected_y = int(mouse_y - rect.height() // 2)
                # calculate new relative values
                status_window_properties.relative_x = mouse_x - corrected_x
                status_window_properties.relative_y = mouse_y - corrected_y
                statuswindow.move(corrected_x, corrected_y)
                del (mouse_x, mouse_y, corrected_x, corrected_y)

    def calculate_size(self):
        """
            get size of popup window
        """
        if conf.icon_in_systray:
            # where is the pointer which clicked onto systray icon
            icon_x = systrayicon.geometry().x()
            icon_y = systrayicon.geometry().y()
            if OS in OS_NON_LINUX:
                if status_window_properties.icon_x == 0:
                    status_window_properties.icon_x = QCursor.pos().x()
                elif icon_x != 0:
                    status_window_properties.icon_x = icon_x
            else:
                # strangely enough on KDE the systray icon geometry gives back 0, 0 as coordinates
                # also at Ubuntu Unity 16.04
                if icon_x == 0 and status_window_properties.icon_x == 0:
                    status_window_properties.icon_x = QCursor.pos().x()
                elif icon_x != 0:
                    status_window_properties.icon_x = icon_x

            if icon_y == 0 and status_window_properties.icon_y == 0:
                status_window_properties.icon_y = QCursor.pos().y()

            if OS in OS_NON_LINUX:
                if status_window_properties.icon_y == 0:
                    status_window_properties.icon_y = QCursor.pos().y()
                elif icon_y != 0:
                    status_window_properties.icon_y = icon_y

        # only consider offset if it is configured
        if conf.systray_offset_use and conf.icon_in_systray:
            available_height = self.get_screen().availableGeometry().height() - conf.systray_offset
        else:
            available_height = self.get_screen().availableGeometry().height()

        available_width = self.get_screen().availableGeometry().width()
        available_x = self.get_screen().availableGeometry().x()
        available_y = self.get_screen().availableGeometry().y()

        # Workaround for Cinnamon + GNOME Flashback
        if OS not in OS_NON_LINUX and conf.enable_position_fix:
            if available_x == 0:
                available_x = available_width
            if available_y == 0:
                available_y = available_height

        # take whole screen height into account when deciding about upper/lower-ness
        # add available_y because it might vary on differently setup screens
        # calculate top-ness only if window is closed
        if conf.statusbar_floating:
            if self.y() < self.get_screen().geometry().height() // 2 + available_y:
                status_window_properties.top = True
            else:
                status_window_properties.top = False

            # always take the stored position of the statusbar
            x = self.stored_x

        elif conf.icon_in_systray or conf.windowed:
            if status_window_properties.icon_y < self.get_screen().geometry().height() // 2 + available_y:
                status_window_properties.top = True
            else:
                status_window_properties.top = False
            x = status_window_properties.icon_x

        # get height from tablewidgets
        real_height = self.get_real_height()

        # width simply will be the current screen maximal width - less hassle!
        if self.get_real_width() > available_width:
            width = available_width
            x = available_x
        else:
            width = self.get_real_width()

            if width < self.toparea.sizeHint().width():
                width = self.toparea.sizeHint().width()

            # always take the stored width of the statusbar into account
            x = x - int(width // 2) + int(self.stored_width // 2)

            # check left and right limits of x
            if x < available_x:
                x = available_x
            if x + width > available_x + available_width:
                x = available_x + available_width - width

        if conf.statusbar_floating:
            # when statusbar resides in uppermost part of current screen extend from top to bottom
            if status_window_properties.top is True:
                y = self.y()
                if self.y() + real_height < available_height + available_y:
                    height = real_height
                else:
                    height = available_height - self.y() + available_y

            # when statusbar hangs around in lowermost part of current screen extend from bottom to top
            else:
                # when height is too large for current screen cut it
                if self.y() + self.height() - real_height < available_y:
                    height = self.get_screen().geometry().height() - available_y - (
                            self.get_screen().geometry().height() - (self.y() + self.height()))
                    y = available_y
                else:
                    height = real_height
                    y = self.y() + self.height() - height

        elif conf.icon_in_systray or conf.windowed:
            # when systrayicon resides in uppermost part of current screen extend from top to bottom
            if status_window_properties.top is True:
                # when being top y is of course the available one
                y = available_y
                if self.y() + real_height < available_height + available_y:
                    height = real_height
                else:
                    # if bigger than screen shrink to maximal real_height
                    height = available_height - available_y
            # when statusbar hangs around in lowermost part of current screen extend from bottom to top
            else:
                if available_height < real_height:
                    y = available_y
                    height = available_height
                else:
                    y = available_height - real_height
                    height = real_height

        return width, height, x, y

    def resize_window(self, width, height, x, y):
        """
        resize status window according to its new size
        """
        # store position for restoring it when hiding - only if not shown of course
        if status_window_properties.is_shown is False:
            self.stored_x = self.x()
            self.stored_y = self.y()
            self.stored_width = self.width()
            self.stored_height = self.height()

        if OS == OS_WINDOWS:
            # absolutely strange, but no other solution available
            # - Only on Windows the statusbar is moving FIRST before resizing - no matter which
            #   order was used
            # - Dirty workaround:
            #   - store x and y in .move_to_*
            #   - start helper move_timer by timer singleshot to give statusbar some time to hide
            self.move_to_x, self.move_to_y = x, y
            self.timer.singleShot(10, self.move_timer)
        else:
            self.move(x, y)

        self.setMaximumSize(width, height)
        self.setMinimumSize(width, height)

        self.adjustSize()

        return True

    @Slot()
    def move_timer(self):
        """
            helper for move by QTimer.singleShot - attempt to avoid flickering on Windows
        """
        self.move(self.move_to_x, self.move_to_y)

    @Slot()
    def adjust_size(self):
        """
        resize window if shown and needed
        """
        # avoid race condition when waiting for password dialog
        if 'is_shown' in self.__dict__:
            if not conf.fullscreen and not conf.windowed:
                self.adjusting_size_lock = True
                # fully displayed statuswindow
                if status_window_properties.is_shown is True:
                    width, height, x, y = self.calculate_size()
                    self.adjust_dummy_columns()
                else:
                    # statusbar only
                    hint = self.sizeHint()
                    # on MacOSX and Windows statusbar will not shrink automatically, so this workaround hopefully helps
                    width = hint.width()
                    height = hint.height()
                    x = self.x()
                    y = self.y()
                    self.setMaximumSize(hint)
                    self.setMinimumSize(hint)
                    del hint
                self.resize_window(width, height, x, y)

                del width, height, x, y
            else:
                self.adjust_dummy_columns()

    @Slot()
    def adjust_dummy_columns(self):
        """
            calculate widest width of all server tables to hide dummy column at the widest one
        """
        max_width = 0
        max_width_table = None
        for server in self.servers_vbox.children():
            # if table is wider than current max_width take its width as max_width
            if server.table.get_real_width() > max_width:
                max_width = server.table.get_real_width()
                max_width_table = server.table

        # widest table does not need the dummy column #9
        for server in self.servers_vbox.children():
            if max_width_table == server.table and max_width == server.table.width():
                # hide dummy column as here is the most stretched table
                server.table.setColumnHidden(9, True)
                server.table.header().setStretchLastSection(False)
            else:
                # show dummy column because some other table is wider
                server.table.setColumnHidden(9, False)
                server.table.header().setStretchLastSection(True)
        del (max_width, max_width_table)
        return True

    @Slot()
    def store_position(self):
        """
            store position for restoring it when hiding
        """
        if not status_window_properties.is_shown:
            self.stored_x = self.x()
            self.stored_y = self.y()
            self.stored_width = self.width()
            self.stored_height = self.height()

    def leaveEvent(self, event):
        """
            check if popup has to be hidden depending on mouse position
        """
        # depending on display mode the leave time offset shall be different because
        # it may be too short in systray mode and lead to flickering window
        if conf.statusbar_floating:
            leave_time_offset = 0.25
        elif conf.icon_in_systray:
            # offset is max 1 and smaller if window is smaller too
            leave_time_offset = self.height() / self.get_screen().availableGeometry().height()
        else:
            leave_time_offset = 0

        # check first if popup has to be shown by hovering or clicking
        if conf.close_details_hover and \
                not conf.fullscreen and \
                not conf.windowed and \
                status_window_properties.is_shown_timestamp + leave_time_offset < time.time():
            # only hide window if cursor is outside of it
            mouse_x = QCursor.pos().x()
            mouse_y = QCursor.pos().y()
            # <= and >= necessary because sometimes mouse_* is the same as self.*()
            if mouse_x <= self.x() or mouse_x >= self.x() + self.width() or \
                    mouse_y <= self.y() or mouse_y >= self.y() + self.height():
                self.hide_window()

    def closeEvent(self, event):
        """
            window close
        """
        # check first if popup has to be shown by hovering or clicking
        if conf.windowed:
            exit()

    def get_real_width(self):
        """
            calculate widest width of all server tables
        """
        width = 0
        for server in self.servers_vbox.children():
            # if table is wider than window adjust with to table
            if server.table.isVisible() and server.table.get_real_width() > width:
                width = server.table.get_real_width()

            # if header in server vbox is wider than width adjust the latter
            if server.header.sizeHint().width() > width:
                width = server.header.sizeHint().width()
        return width

    def get_real_height(self):
        """
            calculate summary of all heights of all server tables plus height of toparea
        """
        height = 0
        for vbox in self.servers_vbox.children():
            height += vbox.get_real_height()

        # add size of toparea and 2 times the MARGIN (top and bottom)
        height += self.toparea.sizeHint().height() + 2

        return height

    def set_shown(self):
        """
            might help to avoid flickering on MacOSX, in cooperation with QTimer
        """
        status_window_properties.is_shown = True

    @Slot()
    def store_position_to_conf(self):
        """
            store position of statuswindow/statusbar
        """
        # only useful if statusbar is floating
        if conf.statusbar_floating:
            # minimize window to statusbar only to get real position
            self.hide_window()
            conf.position_x = self.x()
            conf.position_y = self.y()
        if conf.windowed:
            conf.position_x = self.x()
            conf.position_y = self.y()
            conf.position_width = self.width()
            conf.position_height = self.height()
        # store position of statuswindow/statusbar
        conf.save_config()

    @Slot(str, str)
    def show_message(self, msg_type, message):
        """
            show message from other thread like MediaPlayer
        """
        title = " ".join((AppInfo.NAME, msg_type))
        if msg_type == 'warning':
            return QMessageBox.warning(statuswindow, title, message)

        elif msg_type == 'information':
            return QMessageBox.information(statuswindow, title, message)

    @Slot()
    def recheck_all(self):
        """
            tell servers to recheck all hosts and services
        """
        self.recheck.emit()

    @Slot()
    def refresh(self):
        """
            tell all enabled servers to refresh their information
        """
        # unfresh event history of servers
        self.clear_event_history.emit()

        for server in get_enabled_servers():
            if conf.debug_mode:
                server.debug(server=server.name, debug='Refreshing all hosts and services')

            # manipulate server thread counter so get_status loop will refresh when next looking
            # at thread counter
            server.thread_counter = conf.update_interval_seconds

    @Slot(dict)
    def desktop_notification(self, current_status_count):
        """
            show desktop notification - must be called from same thread as DBus intialization
        """
        # compile message from status counts
        message = ''
        for state in ['DOWN', 'UNREACHABLE', 'DISASTER', 'CRITICAL', 'HIGH', 'AVERAGE', 'WARNING', 'INFORMATION',
                      'UNKNOWN']:
            if current_status_count[state] > 0:
                message += '{0} {1} '.format(str(current_status_count[state]), state)

        if not message == '':
            # due to mysterious DBus-Crashes
            # see https://github.com/HenriWahl/Nagstamon/issues/320
            try:
                dbus_connection.show(AppInfo.NAME, message)
            except Exception:
                traceback.print_exc(file=sys.stdout)

    @Slot()
    def raise_window_on_all_desktops(self):
        """
            experimental workaround for floating-statusbar-only-on-one-virtual-desktop-after-a-while bug
            see https://github.com/HenriWahl/Nagstamon/issues/217
        """
        if conf.windowed:
            return
        # X11/Linux needs some special treatment to get the statusbar floating on all virtual desktops
        if OS not in OS_NON_LINUX and not DESKTOP_WAYLAND:
            # get all windows...
            winid = self.winId().__int__()
            self.ewmh.setWmDesktop(winid, 0xffffffff)
            self.ewmh.display.flush()

        # apparently sometime the floating statusbar vanishes in the background
        # lets try here to keep it on top - only if not fullscreen
        if not conf.fullscreen and not conf.windowed and not OS == OS_WINDOWS:
            self.setWindowFlags(WINDOW_FLAGS)

        # again and again try to keep that statuswindow on top!
        if OS == OS_WINDOWS and \
                not conf.fullscreen and \
                not conf.windowed and \
                app.activePopupWidget() == None:
            try:
                self.raise_()
            except Exception as error:
                # apparently a race condition could occur on set_mode() - grab it here and continue
                print(error)

    def kill(self):
        """
        Try to remove every piece of statuswindow to avoid artefacts when changing display mode
        :return:
        """
        self.label_all_ok.deleteLater()
        self.toparea.deleteLater()
        self.statusbar.deleteLater()
        self.servers_scrollarea.deleteLater()
        self.servers_scrollarea_widget.deleteLater()
        return self.deleteLater()

    @Slot()
    def finish_worker_thread(self):
        """
            attempt to shutdown thread cleanly
        """
        # stop debugging
        statuswindow_worker_debug_loop_looping = False
        # tell thread to quit
        self.worker_thread.quit()
        # wait until thread is really stopped
        self.worker_thread.wait()

    @Slot()
    def finish_worker_notification_thread(self):
        """
            attempt to shutdown thread cleanly
        """
        # tell thread to quit
        self.worker_notification_thread.quit()
        # wait until thread is really stopped
        self.worker_notification_thread.wait()

    @Slot(str)
    def remove_previous_server_vbox(self, previous_server_name):
        # remove old server vbox from the status window if still running
        for vbox in self.servers_vbox.children():
            if vbox.server.name == previous_server_name:
                # disable server
                vbox.server.enabled = False
                # stop thread by falsificate running flag
                vbox.table.worker.running = False
                vbox.table.worker.finish.emit()
                # nothing more to do
                break

    class Worker(QObject):
        """
        run a thread, for example, for debugging
        """
        # send signal if ready to stop
        finish = Signal()

        def __init__(self):
            QObject.__init__(self)
            # flag to decide if the thread has to run or to be stopped
            self.running = True
            # flag if debug_loop is looping
            self.debug_loop_looping = False
            # default debug dile does not exist
            self.debug_file = None

        def open_debug_file(self):
            # open file and truncate
            self.debug_file = open(conf.debug_file, "w")

        def close_debug_file(self):
            # close and reset file
            self.debug_file.close()
            self.debug_file = None

        @Slot()
        def debug_loop(self):
            """
            if debugging is enabled, poll debug_queue list and print/write its contents
            """
            if conf.debug_mode:
                statuswindow_worker_debug_loop_looping = True

                # as long thread is supposed to run
                while self.running and statuswindow_worker_debug_loop_looping:
                    # only log something if there is something to tell
                    while len(debug_queue) > 0:
                        # always get the oldest item of queue list - FIFO
                        debug_line = (debug_queue.pop(0))
                        # output to console
                        print(debug_line)
                        if conf.debug_to_file:
                            # if there is no file handle available get it
                            if self.debug_file is None:
                                self.open_debug_file()
                            # log line per line
                            self.debug_file.write(debug_line + "\n")
                    # wait second until the next poll
                    time.sleep(1)

                # unset looping
                statuswindow_worker_debug_loop_looping = False
                # close file if any
                if self.debug_file is not None:
                    self.close_debug_file()
            else:
                # set the flag to tell debug loop it should stop, please
                self.debug_loop_looping = False

    class Worker_Notification(QObject):

        """
           run a thread for doing all notification stuff
        """

       # tell statusbar labels to flash
        start_flash = Signal()
        stop_flash = Signal()

        # tell mediaplayer to load and play sound file
        load_sound = Signal(str)
        play_sound = Signal()

        # tell statuswindow to use desktop notification
        desktop_notification = Signal(dict)

        # only one enabled server should have the right to send play_sound signal
        notifying_server = ''

        # desktop notification needs to store count of states
        status_count = dict()

        # send signal if ready to stop
        finish = Signal()

        def __init__(self, status_window_properties = None):
            QObject.__init__(self)
            self.status_window_properties = status_window_properties

        @Slot(str, str, str)
        def start(self, server_name, worst_status_diff, worst_status_current):
            """
            start notification
            """
            if conf.notification:
                # only if not notifying yet or the current state is worse than the prior AND
                # only when the current state is configured to be honking about
                if (STATES.index(worst_status_diff) > STATES.index(self.status_window_properties.worst_notification_status) or
                    self.status_window_properties.is_notifying is False) and \
                        conf.__dict__[f'notify_if_{worst_status_diff.lower()}'] is True:
                    # keep last worst state worth a notification for comparison 3 lines above
                    self.status_window_properties.worst_notification_status = worst_status_diff
                    # set flag to avoid innecessary notification
                    self.status_window_properties.is_notifying = True
                    if self.status_window_properties == '':
                        status_window_properties.notfifying_server = server_name

                    # flashing statusbar
                    if conf.notification_flashing:
                        self.start_flash.emit()

                    # Play default sounds via mediaplayer
                    if conf.notification_sound:
                        sound_file = ''
                        # at the moment there are only sounds for down, critical and warning
                        # only honk if notifications are wanted for this state
                        if worst_status_diff in STATES_SOUND:
                            if conf.notification_default_sound:
                                # default .wav sound files are in resources folder
                                sound_file = '{0}{1}{2}.wav'.format(RESOURCES, sep, worst_status_diff.lower())
                            elif conf.notification_custom_sound:
                                sound_file = conf.__dict__[
                                    'notification_custom_sound_{0}'.format(worst_status_diff.lower())]

                            # only one enabled server should access the mediaplayer
                            if status_window_properties.notifying_server == server_name:
                                # once loaded file will be played by every server, even if it is
                                # not the status_window_properties.notifying_server that loaded it
                                self.load_sound.emit(sound_file)
                                self.play_sound.emit()

                    # Notification actions
                    if conf.notification_actions:
                        if conf.notification_action_warning is True and worst_status_diff == 'WARNING':
                            self.execute_action(server_name, conf.notification_action_warning_string)
                        if conf.notification_action_critical is True and worst_status_diff == 'CRITICAL':
                            self.execute_action(server_name, conf.notification_action_critical_string)
                        if conf.notification_action_down is True and worst_status_diff == 'DOWN':
                            self.execute_action(server_name, conf.notification_action_down_string)

                # Notification action OK
                if worst_status_current == 'UP' and \
                        conf.notification_actions and conf.notification_action_ok:
                    self.execute_action(server_name, conf.notification_action_ok_string)

                # Custom event notification - valid vor ALL events, thus without status comparison
                if conf.notification_actions is True and conf.notification_custom_action is True:
                    # temporarily used to collect executed events
                    events_list = []
                    events_string = ''

                    # if no single notifications should be used (default) put all events into one string, separated by separator
                    if conf.notification_custom_action_single is False:
                        for server in get_enabled_servers():
                            # list comprehension only considers events which are new, ergo True
                            events_list += [k for k, v in
                                            server.events_notification.items() if v is True]

                        # create string for no-single-event-notification of events separated by separator
                        events_string = conf.notification_custom_action_separator.join(events_list)

                        # clear already notified events setting them to False
                        for server in get_enabled_servers():
                            for event in [k for k, v in
                                          server.events_notification.items() if v is True]:
                                server.events_notification[event] = False
                    else:
                        for server in get_enabled_servers():
                            for event in [k for k, v in server.events_notification.items() if v is True]:
                                custom_action_string = conf.notification_custom_action_string.replace('$EVENT$',
                                                                                                      '$EVENTS$')
                                custom_action_string = custom_action_string.replace('$EVENTS$', event)
                                # execute action
                                self.execute_action(server_name, custom_action_string)
                                # clear already notified events setting them to False
                                server.events_notification[event] = False

                    # if events got filled display them now
                    if events_string != '':
                        # in case a single action per event has to be executed
                        custom_action_string = conf.notification_custom_action_string.replace('$EVENT$', '$EVENTS$')
                        # insert real event(s)
                        custom_action_string = custom_action_string.replace('$EVENTS$', events_string)
                        # execute action
                        self.execute_action(server_name, custom_action_string)
                else:
                    # set all events to False to ignore them in the future
                    for event in servers[server_name].events_notification:
                        servers[server_name].events_notification[event] = False

                # repeated sound
                # only let one enabled server play sound to avoid a larger cacophony
                if status_window_properties.is_notifying and \
                        conf.notification_sound_repeat and \
                        status_window_properties == server_name:
                    self.play_sound.emit()

                # desktop notification
                if conf.notification_desktop:
                    # get status count from servers
                    current_status_count = get_status_count()
                    if current_status_count != self.status_count:
                        self.desktop_notification.emit(current_status_count)
                    # store status count for next comparison
                    self.status_count = current_status_count
                    del (current_status_count)

        @Slot()
        def stop(self):
            """
            stop notification if there is no need anymore
            """
            if self.status_window_properties.is_notifying:
                self.status_window_properties.worst_notification_status = 'UP'
                self.status_window_properties.is_notifying = False

                # no more flashing statusbar and systray
                self.stop_flash.emit()

                # reset notifying server, waiting for next notification
                status_window_properties = ''

        def execute_action(self, server_name, custom_action_string):
            """
            execute custom action
            """
            if conf.debug_mode:
                servers[server_name].debug(debug='NOTIFICATION: ' + custom_action_string)
            subprocess.Popen(custom_action_string, shell=True)


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
# menu has to be set here to solve Qt-5.10-Windows-systray-mess
# and non-existence of macOS-systray-context-menu
elif conf.icon_in_systray:
    systrayicon.set_menu(menu)

# versatile mediaplayer
mediaplayer = MediaPlayer(statuswindow, resource_files)

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

# necessary extra menu due to Qt5-Unity-integration
if not OS in OS_NON_LINUX:
    # change menu if there are changes in settings/servers
    dialogs.settings.changed.connect(menu_systray.initialize)
    menu_systray.menu_ready.connect(systrayicon.set_menu)

