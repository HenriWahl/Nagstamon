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

import base64
from collections import OrderedDict
import copy
from copy import deepcopy
import datetime
import os
import os.path
import platform
import random
import subprocess
import sys
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
                                   DEFAULT_FONT,
                                   FONT,
                                   NUMBER_OF_DISPLAY_CHANGES)
from Nagstamon.qui.helpers import (hide_macos_dock_icon,
                                   create_brushes)
from Nagstamon.qui.widgets.button import (Button,
                                          CSS_CLOSE_BUTTON,
                                          PushButtonHamburger)
from Nagstamon.qui.widgets.dialogs import dialogs
from Nagstamon.qui.widgets.dialogs import Dialog
from Nagstamon.qui.widgets.dialogs.check_version import CheckVersion
from Nagstamon.qui.widgets.icon import QIconWithFilename
from Nagstamon.qui.widgets.layout import HBoxLayout
from Nagstamon.qui.widgets.menu import MenuAtCursor

# for details of imports look into qt.py
from Nagstamon.qui.qt import *

from Nagstamon.config import (Action,
                              AppInfo,
                              BOOLPOOL,
                              conf,
                              CONFIG_STRINGS,
                              debug_queue,
                              KEYRING,
                              OS_NON_LINUX,
                              OS,
                              OS_MACOS,
                              OS_WINDOWS,
                              RESOURCES,
                              Server,
                              DESKTOP_WAYLAND)

from Nagstamon.Servers import (SERVER_TYPES,
                               servers,
                               create_server,
                               get_enabled_servers,
                               get_worst_status,
                               get_status_count,
                               get_errors)

from Nagstamon.helpers import (is_found_by_re,
                               webbrowser_open,
                               FilesDict,
                               STATES,
                               STATES_SOUND,
                               SORT_COLUMNS_FUNCTIONS)

# only on X11/Linux thirdparty path should be added because it contains the Xlib module
# needed to tell window manager via EWMH to keep Nagstamon window on all virtual desktops
if OS not in OS_NON_LINUX and not DESKTOP_WAYLAND:
    # extract thirdparty path from resources path - make submodules accessible by thirdparty modules
    THIRDPARTY = os.sep.join(RESOURCES.split(os.sep)[0:-1] + ['thirdparty'])
    sys.path.insert(0, THIRDPARTY)

    # Xlib for EWMH needs the file ~/.Xauthority and crashes if it does not exist
    if not os.path.exists(os.path.expanduser('~') + os.sep + '.Xauthority'):
        open(os.path.expanduser('~') + os.sep + '.Xauthority', 'a').close()

    from Nagstamon.thirdparty.ewmh import EWMH

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)

# add nagstamon.ttf with icons to fonts
QFontDatabase.addApplicationFont('{0}{1}nagstamon.ttf'.format(RESOURCES, os.sep))

# always stay in normal weight without any italic
ICONS_FONT = QFont('Nagstamon', FONT.pointSize() + 2, QFont.Weight.Normal, False)

# set style for tooltips globally - to sad not all properties can be set here
app.setStyleSheet('''QToolTip { margin: 3px;
                                }''')

# store default sounds as buffers to avoid https://github.com/HenriWahl/Nagstamon/issues/578
# meanwhile used as backup copy in case they had been deleted by macOS
# https://github.com/HenriWahl/Nagstamon/issues/578
RESOURCE_FILES = FilesDict(RESOURCES)


class SystemTrayIcon(QSystemTrayIcon):
    """
    Icon in system tray, works at least in Windows and OSX
    Several Linux desktop environments have different problems

    For some dark, very dark reason systray menu does NOT work in
    Windows if run on commandline as nagstamon.py - the binary .exe works
    """
    show_popwin = Signal()
    hide_popwin = Signal()

    # flag for displaying error icon in case of error
    error_shown = False

    def __init__(self):
        # debug environment variables
        if conf.debug_mode:
            for environment_key, environment_value in os.environ.items():
                debug_queue.append(f'DEBUG: Environment variable: {environment_key}={environment_value}')

        # initialize systray icon
        QSystemTrayIcon.__init__(self)

        # icons are in dictionary
        self.icons = {}
        self.create_icons()
        # empty icon for flashing notification
        self.icons['EMPTY'] = QIconWithFilename('{0}{1}nagstamon_systrayicon_empty.svg'.format(RESOURCES, os.sep))
        # little workaround to match statuswindow.worker_notification.worst_notification_status
        self.icons['UP'] = self.icons['OK']
        # default icon is OK
        if conf.icon_in_systray:
            self.setIcon(self.icons['OK'])

        # store icon for flashing
        self.current_icon = None

        # no menu at first
        self.menu = None

        # timer for singleshots for flashing
        self.timer = QTimer()

        # when there are new settings/colors recreate icons
        dialogs.settings.changed.connect(self.create_icons)

        # treat clicks
        self.activated.connect(self.icon_clicked)

    def currentIconName(self):
        """
            internal function useful for debugging, returns the name of the
            current icon
        """
        curIcon = self.icon()
        if curIcon is None:
            return '<none>'
        return str(curIcon)

    @Slot(QMenu)
    def set_menu(self, menu):
        """
            create current menu for right clicks
        """
        # store menu for future use, especially for MacOSX
        self.menu = menu

        # MacOSX does not distinguish between left and right click so menu will go to upper menu bar
        # update: apparently not, but own context menu will be shown when icon is clicked an all is OK = green
        if OS != OS_MACOS:
            self.setContextMenu(self.menu)

    @Slot()
    def create_icons(self):
        """
            create icons from template, applying colors
        """
        svg_template = '{0}{1}nagstamon_systrayicon_template.svg'.format(RESOURCES, os.sep)
        # get template from file
        # by using RESOURCE_FILES the file path will be checked on macOS and the file restored if necessary
        with open(RESOURCE_FILES[svg_template]) as svg_template_file:
            svg_template_xml = svg_template_file.readlines()

            # create icons for all states
            for state in ['OK', 'INFORMATION', 'UNKNOWN', 'WARNING', 'AVERAGE', 'HIGH', 'CRITICAL', 'DISASTER',
                          'UNREACHABLE', 'DOWN', 'ERROR']:
                # current SVG XML for state icon, derived from svg_template_cml
                svg_state_xml = list()

                # replace dummy text and background colors with configured ones
                for line in svg_template_xml:
                    line = line.replace('fill:#ff00ff', 'fill:' + conf.__dict__['color_' + state.lower() + '_text'])
                    line = line.replace('fill:#00ff00',
                                        'fill:' + conf.__dict__['color_' + state.lower() + '_background'])
                    svg_state_xml.append(line)

                # create XML stream of SVG
                svg_xml_stream = QXmlStreamReader(''.join(svg_state_xml))
                # create renderer for SVG and put SVG XML into renderer
                svg_renderer = QSvgRenderer(svg_xml_stream)
                # pixmap to be painted on - arbitrarily choosen 128x128 px
                svg_pixmap = QPixmap(128, 128)
                # fill transparent backgound
                svg_pixmap.fill(Qt.GlobalColor.transparent)
                # initiate painter which paints onto paintdevice pixmap
                svg_painter = QPainter(svg_pixmap)
                # render svg to pixmap
                svg_renderer.render(svg_painter)
                # close painting
                svg_painter.end()
                # put pixmap into icon
                self.icons[state] = QIconWithFilename(svg_pixmap)

                debug_queue.append(
                    'DEBUG: SystemTrayIcon created icon {} for state "{}"'.format(self.icons[state], state))

    @Slot(QSystemTrayIcon.ActivationReason)
    def icon_clicked(self, reason):
        """
            evaluate mouse click
        """
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick,
                      QSystemTrayIcon.ActivationReason.MiddleClick):
            # when green icon is displayed and no popwin is about to pop up...
            if get_worst_status() == 'UP':
                # ...nothing to do except on macOS where menu should be shown
                if OS == OS_MACOS:
                    # in case there is some error show popwin rather than context menu
                    if not self.error_shown:
                        self.menu.show_at_cursor()
                    else:
                        self.show_popwin.emit()
            else:
                # show status window if there is something to tell
                if statuswindow.is_shown:
                    self.hide_popwin.emit()
                else:
                    self.show_popwin.emit()

    @Slot()
    def show_state(self):
        """
            get worst status and display it in systray
        """
        if self.error_shown is False:
            worst_status = get_worst_status()
            self.setIcon(self.icons[worst_status])
            # set current icon for flashing
            self.current_icon = self.icons[worst_status]
            del worst_status
        else:
            self.setIcon(self.icons['ERROR'])

    @Slot()
    def flash(self):
        """
            send color inversion signal to labels
        """
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            # store current icon to get it reset back
            if self.current_icon is None:
                if self.error_shown is False:
                    self.current_icon = self.icons[statuswindow.worker_notification.get_worst_notification_status()]
                else:
                    self.current_icon = self.icons['ERROR']
            # use empty SVG icon to display emptiness
            if RESOURCE_FILES[self.icons['EMPTY'].filename]:
                self.setIcon(self.icons['EMPTY'])
            # fire up  a singleshot to reset color soon
            self.timer.singleShot(500, self.reset)

    @Slot()
    def reset(self):
        """
            tell labels to set original colors
        """
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            try:
                # set curent status icon
                self.setIcon(self.current_icon)
                # even later call itself to invert colors as flash
                self.timer.singleShot(500, self.flash)
            except:
                traceback.print_exc(file=sys.stdout)
        else:
            if self.current_icon is not None:
                self.setIcon(self.current_icon)
            self.current_icon = None

    @Slot()
    def set_error(self):
        self.error_shown = True

    @Slot()
    def reset_error(self):
        self.error_shown = False


class MenuContext(MenuAtCursor):
    """
        class for universal context menu, used at systray icon and hamburger menu
    """

    menu_ready = Signal(QMenu)

    def __init__(self, parent=None):
        MenuAtCursor.__init__(self, parent=parent)

        # connect all relevant widgets which should show the context menu
        for widget in [statuswindow.toparea.button_hamburger_menu,
                       statuswindow.toparea.label_version,
                       statuswindow.toparea.label_empty_space,
                       statuswindow.toparea.logo,
                       statuswindow.statusbar.logo,
                       statuswindow.statusbar.label_message]:
            self.menu_ready.connect(widget.set_menu)

        for color_label in statuswindow.statusbar.color_labels.values():
            self.menu_ready.connect(color_label.set_menu)

        dialogs.settings.changed.connect(self.initialize)

        self.initialize()

    @Slot()
    def initialize(self):
        """
            add actions and servers to menu
        """

        # first clear to get rid of old servers
        self.clear()

        self.action_refresh = QAction('Refresh', self)
        self.action_refresh.triggered.connect(statuswindow.refresh)
        self.addAction(self.action_refresh)

        self.action_recheck = QAction('Recheck all', self)
        self.action_recheck.triggered.connect(statuswindow.recheck_all)
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
        self.action_settings.triggered.connect(statuswindow.hide_window)
        self.action_settings.triggered.connect(dialogs.settings.show)
        self.addAction(self.action_settings)

        if conf.statusbar_floating:
            self.action_save_position = QAction('Save position', self)
            self.action_save_position.triggered.connect(statuswindow.store_position_to_conf)
            self.addAction(self.action_save_position)

        self.addSeparator()

        self.action_about = QAction('About...', self)
        self.action_about.triggered.connect(statuswindow.hide_window)
        self.action_about.triggered.connect(dialogs.about.show)
        self.addAction(self.action_about)
        self.action_exit = QAction('Exit', self)
        self.action_exit.triggered.connect(exit)
        self.addAction(self.action_exit)

        # tell all widgets to use the new menu
        self.menu_ready.emit(self)


class MenuContextSystrayicon(MenuContext):
    """
        Necessary for Ubuntu 16.04 new Qt5-Systray-AppIndicator meltdown
        Maybe in general a good idea to offer status window popup here
    """

    def __init__(self, parent=None):
        """
            clone of normal MenuContext which serves well in all other places
            but no need of signal/slots initialization
        """
        QMenu.__init__(self, parent=parent)

        # initialize as default + extra
        self.initialize()

        self.menu_ready.connect(systrayicon.set_menu)
        self.menu_ready.emit(self)

        # change menu if there are changes in settings/servers
        dialogs.settings.changed.connect(self.initialize)

    def initialize(self):
        """
            initialize as inherited + a popup menu entry mostly useful in Ubuntu Unity
        """
        MenuContext.initialize(self)
        # makes even less sense on OSX
        if OS != OS_MACOS:
            self.action_status = QAction('Show status window', self)
            self.action_status.triggered.connect(statuswindow.show_window_systrayicon)
            self.insertAction(self.action_refresh, self.action_status)
            self.insertSeparator(self.action_refresh)


# ##class PushButton_BrowserURL(QPushButton):
class PushButton_BrowserURL(Button):
    """
        QPushButton for ServerVBox which opens certain URL if clicked
    """

    def __init__(self, text='', parent=None, server=None, url_type=''):
        Button.__init__(self, text, parent=parent)
        self.server = server
        self.url_type = url_type

    @Slot()
    def open_url(self):
        """
            open URL from BROWSER_URLS in webbrowser
        """
        # BROWSER_URLS come with $MONITOR$ instead of real monitor url - heritage from actions
        url = self.server.BROWSER_URLS[self.url_type]
        url = url.replace('$MONITOR$', self.server.monitor_url)
        url = url.replace('$MONITOR-CGI$', self.server.monitor_cgi_url)

        if conf.debug_mode:
            self.server.debug(server=self.server.get_name(), debug='Open {0} web page {1}'.format(self.url_type, url))

        # use Python method to open browser
        webbrowser_open(url)

        # hide statuswindow to get screen space for browser
        if not conf.fullscreen and not conf.windowed:
            statuswindow.hide_window()


class ComboBox_Servers(QComboBox):
    """
        combobox which does lock statuswindow so it does not close when opening combobox
    """
    monitor_opened = Signal()

    # flag to avoid silly focusOutEvent
    freshly_opened = False

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent=parent)
        # react to clicked monitor
        self.activated.connect(self.response)

    def mousePressEvent(self, event):
        # first click opens combobox popup
        self.freshly_opened = True
        # tell status window that there is no combobox anymore
        self.showPopup()

    def fill(self):
        """
            fill default order fields combobox with server names
        """
        self.clear()
        self.addItem('Go to monitor...')
        self.addItems(sorted([x.name for x in conf.servers.values() if x.enabled], key=str.lower))

    @Slot()
    def response(self):
        """
            respnose to activated item in servers combobox
        """
        if self.currentText() in servers:
            # open webbrowser with server URL
            webbrowser_open(servers[self.currentText()].monitor_url)

            # hide window to make room for webbrowser
            self.monitor_opened.emit()

        self.setCurrentIndex(0)


class DraggableWidget(QWidget):
    """
        Used to give various toparea and statusbar widgets draggability
    """
    # yell if statusbar is moved
    window_moved = Signal()

    # needed for popup after hover
    mouse_entered = Signal()

    # needed for popup after click
    mouse_pressed = Signal()
    mouse_released = Signal()

    # keep state of right button pressed to avoid dragging and
    # unwanted repositioning of statuswindow
    right_mouse_button_pressed = False

    # Maybe due to the later mixin usage, but somehow the pyqtSlot decorator is ignored here when used by NagstamonLogo
    # and DraggableLabel
    # @Slot(QMenu)
    def set_menu(self, menu):
        self.menu = menu

    def mousePressEvent(self, event):
        """
            react differently to mouse button presses:
            1 - left button, move window
            2 - right button, popup menu
        """

        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed.emit()
        if event.button() == Qt.MouseButton.RightButton:
            self.right_mouse_button_pressed = True

        # keep x and y relative to statusbar
        # if not set calculate relative position
        if not statuswindow.relative_x and \
                not statuswindow.relative_y:
            # Qt5 & Qt6 have different methods for getting the global position so take it from qt.py
            global_position = get_global_position(event)
            statuswindow.relative_x = global_position.x() - statuswindow.x()
            statuswindow.relative_y = global_position.y() - statuswindow.y()

    def mouseReleaseEvent(self, event):
        """
            decide if moving or menu should be treated after mouse button was released
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # if popup window should be closed by clicking do it now
            if statuswindow.is_shown and \
                    (conf.close_details_clicking or
                     conf.close_details_clicking_somewhere) and \
                    not conf.fullscreen and not conf.windowed:
                statuswindow.is_hiding_timestamp = time.time()
                statuswindow.hide_window()
            elif not statuswindow.is_shown:
                self.mouse_released.emit()

            # reset all helper values
            statuswindow.relative_x = False
            statuswindow.relative_y = False
            statuswindow.moving = False

        if event.button() == Qt.MouseButton.RightButton:
            self.right_mouse_button_pressed = False
            self.menu.show_at_cursor()

    def mouseMoveEvent(self, event):
        """
            do the moving action
        """

        # if window should close when being clicked it might be problematic if it
        # will be moved unintendedly so try to filter this events out by waiting 0.5 seconds
        if not (conf.close_details_clicking and
                statuswindow.is_shown and
                statuswindow.is_shown_timestamp + 0.5 < time.time()):
            if not conf.fullscreen and not conf.windowed and not self.right_mouse_button_pressed:
                # Qt5 & Qt6 have different methods for getting the global position so take it from qt.py
                global_position = get_global_position(event)
                # lock window as moving
                # if not set calculate relative position
                if not statuswindow.relative_x and not statuswindow.relative_y:
                    statuswindow.relative_x = global_position.x() - statuswindow.x()
                    statuswindow.relative_y = global_position.y() - statuswindow.y()
                statuswindow.moving = True
                statuswindow.move(int(global_position.x() - statuswindow.relative_x),
                                  int(global_position.y() - statuswindow.relative_y))

            # needed for OSX - otherwise statusbar stays blank while moving
            statuswindow.update()

            self.window_moved.emit()

    def enterEvent(self, event):
        """
            tell the world that mouse entered the widget - interesting for hover popup and only if toparea hasn't been
            clickend a moment ago
        """
        if statuswindow.is_shown is False and \
                statuswindow.is_hiding_timestamp + 0.2 < time.time():
            self.mouse_entered.emit()


class DraggableLabel(QLabel, DraggableWidget):
    """
       label with dragging capabilities used by toparea
    """
    # yell if statusbar is moved
    window_moved = Signal()

    # needed for popup after hover
    mouse_entered = Signal()

    # needed for popup after click
    mouse_pressed = Signal()
    mouse_released = Signal()

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text, parent=parent)


class ClosingLabel(QLabel):
    """
        modified QLabel which might close the statuswindow if leftclicked
    """

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text, parent=parent)

    def mouseReleaseEvent(self, event):
        """
            left click and configured close-if-clicking-somewhere makes statuswindow close
        """
        if event.button() == Qt.MouseButton.LeftButton and conf.close_details_clicking_somewhere:
            # if popup window should be closed by clicking do it now
            if statuswindow.is_shown and \
                    not conf.fullscreen and \
                    not conf.windowed:
                statuswindow.is_hiding_timestamp = time.time()
                statuswindow.hide_window()


class LabelAllOK(QLabel):
    """
        Label which is shown in fullscreen and windowed mode when all is OK - pretty seldomly
    """

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text='OK', parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_color()
        dialogs.settings.changed.connect(self.set_color)

    @Slot()
    def set_color(self):
        self.setStyleSheet('''padding-left: 1px;
                              padding-right: 1px;
                              color: %s;
                              background-color: %s;
                              font-size: 92px;
                              font-weight: bold;'''
                           % (conf.__dict__['color_ok_text'],
                              conf.__dict__['color_ok_background']))


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
        self.setWindowIcon(QIcon('{0}{1}nagstamon.svg'.format(RESOURCES, os.sep)))

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
        self.worker_notification = self.Worker_Notification()

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

        self.create_ServerVBoxes()

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
        self.moving = False
        self.relative_x = False
        self.relative_y = False

        # helper values for QTimer.singleShot move attempt
        self.move_to_x = self.move_to_y = 0

        # stored x y values for systemtray icon
        self.icon_x = 0
        self.icon_y = 0

        # flag to mark if window is shown or not
        if conf.windowed:
            self.is_shown = True
        else:
            self.is_shown = False

        # store show_window timestamp to avoid flickering window in KDE5 with systray
        self.is_shown_timestamp = time.time()

        # store timestamp to avoid reappearing window shortly after clicking onto toparea
        self.is_hiding_timestamp = time.time()

        # if status_ok is true no server_vboxes are needed
        self.status_ok = True

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

    def create_ServerVBox(self, server):
        """
            internally used to create enabled servers to be displayed
        """
        # create server vboxed from current running servers
        if server.enabled:
            # display authentication dialog if password is not known
            if not conf.servers[server.name].save_password and \
                    not conf.servers[server.name].use_autologin and \
                    conf.servers[server.name].password == '' and \
                    not conf.servers[server.name].authentication == 'kerberos':
                dialogs.authentication.show_auth_dialog(server.name)

            # without parent there is some flickering when starting
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

            # show error message in statusbar
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

            # stop notifcation if statuswindow pops up
            self.showing.connect(self.worker_notification.stop)

            # tell server worker to recheck all hosts and services
            self.recheck.connect(server_vbox.table.worker.recheck_all)

            # refresh table after changed settings
            dialogs.settings.changed.connect(server_vbox.table.refresh)

            # listen if statuswindow cries for event history clearance
            self.clear_event_history.connect(server_vbox.table.worker.unfresh_event_history)

            return server_vbox
        else:
            return None

    def sort_ServerVBoxes(self):
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

    def create_ServerVBoxes(self):
        # create vbox for each enabled server
        for server in servers.values():
            if server.enabled:
                self.servers_vbox.addLayout(self.create_ServerVBox(server))

        self.sort_ServerVBoxes()

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
        if not self.is_shown:
            # under unfortunate circumstances statusbar might have the the moving flag true
            # fix it here because it makes no sense but might cause non-appearing statuswindow‚
            self.moving = False

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
        if not self.moving:
            # check if really all is OK
            for vbox in self.servers_vbox.children():
                if vbox.server.all_ok and \
                        vbox.server.status == '' and \
                        not vbox.server.refresh_authentication and \
                        not vbox.server.tls_error:
                    self.status_ok = True
                else:
                    self.status_ok = False
                    break

            # here we should check if scroll_area should be shown at all
            if not self.status_ok:
                # store timestamp to avoid flickering as in https://github.com/HenriWahl/Nagstamon/issues/184
                self.is_shown_timestamp = time.time()

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
                    self.is_shown and \
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
                self.is_shown:
            return False

        self.hide_window()
        return True

    @Slot()
    def update_window(self):
        """
            redraw window content, to be effective only when window is shown
        """
        if self.is_shown or \
                conf.fullscreen or \
                (conf.windowed and self.is_shown):
            self.show_window()

    @Slot()
    def hide_window(self):
        """
            hide window if not needed
        """
        if not conf.fullscreen and not conf.windowed:
            # only hide if shown and not locked or if not yet hidden if moving
            if self.is_shown is True or \
                    self.is_shown is True and \
                    self.moving is True:
                # only hide if shown at least a fraction of a second
                # or has not been hidden a too short time ago
                if self.is_shown_timestamp + 0.5 < time.time() or \
                        self.is_hiding_timestamp + 0.2 < time.time():
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
                    self.is_shown = False

                    # flag to reflect top-ness of window/statusbar
                    self.top = False

                    # reset icon x y
                    self.icon_x = 0
                    self.icon_y = 0

                    # tell the world that window goes down
                    self.hiding.emit()
                    if conf.windowed:
                        self.hide()

                    # store time of hiding
                    self.is_hiding_timestamp = time.time()

                    self.move(self.stored_x, self.stored_y)

    @Slot()
    def correct_moving_position(self):
        """
            correct position if moving and cursor started outside statusbar
        """
        if self.moving:
            mouse_x = QCursor.pos().x()
            mouse_y = QCursor.pos().y()
            # when cursor is outside moved window correct the coordinates of statusbar/statuswindow
            if not statuswindow.geometry().contains(mouse_x, mouse_y):
                rect = statuswindow.geometry()
                corrected_x = int(mouse_x - rect.width() // 2)
                corrected_y = int(mouse_y - rect.height() // 2)
                # calculate new relative values
                self.relative_x = mouse_x - corrected_x
                self.relative_y = mouse_y - corrected_y
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
                if self.icon_x == 0:
                    self.icon_x = QCursor.pos().x()
                elif icon_x != 0:
                    self.icon_x = icon_x
            else:
                # strangely enough on KDE the systray icon geometry gives back 0, 0 as coordinates
                # also at Ubuntu Unity 16.04
                if icon_x == 0 and self.icon_x == 0:
                    self.icon_x = QCursor.pos().x()
                elif icon_x != 0:
                    self.icon_x = icon_x

            if icon_y == 0 and self.icon_y == 0:
                self.icon_y = QCursor.pos().y()

            if OS in OS_NON_LINUX:
                if self.icon_y == 0:
                    self.icon_y = QCursor.pos().y()
                elif icon_y != 0:
                    self.icon_y = icon_y

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
                self.top = True
            else:
                self.top = False

            # always take the stored position of the statusbar
            x = self.stored_x

        elif conf.icon_in_systray or conf.windowed:
            if self.icon_y < self.get_screen().geometry().height() // 2 + available_y:
                self.top = True
            else:
                self.top = False
            x = self.icon_x

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
            if self.top is True:
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
            if self.top is True:
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
        if self.is_shown is False:
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
                if self.is_shown is True:
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
        if not self.is_shown:
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
                self.is_shown_timestamp + leave_time_offset < time.time():
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
        self.is_shown = True

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
        self.worker.debug_loop_looping = False
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

    class Worker(QObject):
        """
           run a thread for example for debugging
        """
        # send signal if ready to stop
        finish = Signal()

        def __init__(self):
            QObject.__init__(self)
            # flag to decide if thread has to run or to be stopped
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
                self.debug_loop_looping = True

                # as long thread is supposed to run
                while self.running and self.debug_loop_looping:
                    # only log something if there is something to tell
                    while len(debug_queue) > 0:
                        # always get oldest item of queue list - FIFO
                        debug_line = (debug_queue.pop(0))
                        # output to console
                        print(debug_line)
                        if conf.debug_to_file:
                            # if there is no file handle available get it
                            if self.debug_file is None:
                                self.open_debug_file()
                            # log line per line
                            self.debug_file.write(debug_line + "\n")
                    # wait second until next poll
                    time.sleep(1)

                # unset looping
                self.debug_loop_looping = False
                # close file if any
                if self.debug_file is not None:
                    self.close_debug_file()

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

        # flag about current notification state
        is_notifying = False

        # only one enabled server should have the right to send play_sound signal
        notifying_server = ''

        # current worst state worth a notification
        worst_notification_status = 'UP'

        # desktop notification needs to store count of states
        status_count = dict()

        # send signal if ready to stop
        finish = Signal()

        def __init__(self):
            QObject.__init__(self)

        @Slot(str, str, str)
        def start(self, server_name, worst_status_diff, worst_status_current):
            """
                start notification
            """
            if conf.notification:
                # only if not notifying yet or the current state is worse than the prior AND
                # only when the current state is configured to be honking about
                if (STATES.index(worst_status_diff) > STATES.index(self.worst_notification_status) or
                    self.is_notifying is False) and \
                        conf.__dict__['notify_if_{0}'.format(worst_status_diff.lower())] is True:
                    # keep last worst state worth a notification for comparison 3 lines above
                    self.worst_notification_status = worst_status_diff
                    # set flag to avoid innecessary notification
                    self.is_notifying = True
                    if self.notifying_server == '':
                        self.notifying_server = server_name

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
                                sound_file = '{0}{1}{2}.wav'.format(RESOURCES, os.sep, worst_status_diff.lower())
                            elif conf.notification_custom_sound:
                                sound_file = conf.__dict__[
                                    'notification_custom_sound_{0}'.format(worst_status_diff.lower())]

                            # only one enabled server should access the mediaplayer
                            if self.notifying_server == server_name:
                                # once loaded file will be played by every server, even if it is
                                # not the self.notifying_server that loaded it
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
                if self.is_notifying and \
                        conf.notification_sound_repeat and \
                        self.notifying_server == server_name:
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
            if self.is_notifying:
                self.worst_notification_status = 'UP'
                self.is_notifying = False

                # no more flashing statusbar and systray
                self.stop_flash.emit()

                # reset notifying server, waiting for next notification
                self.notifying_server = ''

        def execute_action(self, server_name, custom_action_string):
            """
                execute custom action
            """
            if conf.debug_mode:
                servers[server_name].debug(debug='NOTIFICATION: ' + custom_action_string)
            subprocess.Popen(custom_action_string, shell=True)

        def get_worst_notification_status(self):
            """
                hand over the current worst status notification
            """
            return self.worst_notification_status


class NagstamonLogo(QSvgWidget, DraggableWidget):
    """
        SVG based logo, used for statusbar and toparea logos
    """
    # yell if statusbar is moved
    window_moved = Signal()

    # needed for popup after hover
    mouse_entered = Signal()

    # needed for popup after click
    mouse_pressed = Signal()
    mouse_released = Signal()

    def __init__(self, file, width=None, height=None, parent=None):
        QSvgWidget.__init__(self, parent=parent)
        # either filepath or QByteArray for toparea logo
        self.load(file)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # size needed for small Nagstamon logo in statusbar
        if width is not None and height is not None:
            self.setMinimumSize(width, height)
            self.setMaximumSize(width, height)

    def adjust_size(self, height=None, width=None):
        if width is not None and height is not None:
            self.setMinimumSize(width, height)
            self.setMaximumSize(width, height)


class StatusBar(QWidget):
    """
        status bar for short display of problems
    """

    # send signal to statuswindow
    resize = Signal()

    # needed to maintain flashing labels
    labels_invert = Signal()
    labels_reset = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.hbox = HBoxLayout(spacing=0, parent=parent)
        self.setLayout(self.hbox)

        # define labels first to get their size for svg logo dimensions
        self.color_labels = OrderedDict()
        self.color_labels['OK'] = StatusBarLabel('OK', parent=parent)

        for state in COLORS:
            self.color_labels[state] = StatusBarLabel(state, parent=parent)
            self.labels_invert.connect(self.color_labels[state].invert)
            self.labels_reset.connect(self.color_labels[state].reset)

        # label for error message(s)
        self.label_message = StatusBarLabel('error', parent=parent)
        self.labels_invert.connect(self.label_message.invert)
        self.labels_reset.connect(self.label_message.reset)

        # derive logo dimensions from status label
        self.logo = NagstamonLogo('{0}{1}nagstamon_logo_bar.svg'.format(RESOURCES, os.sep),
                                  self.color_labels['OK'].fontMetrics().height(),
                                  self.color_labels['OK'].fontMetrics().height(),
                                  parent=parent)

        # add logo
        self.hbox.addWidget(self.logo)

        # label for error messages
        self.hbox.addWidget(self.label_message)
        self.label_message.hide()

        # add state labels
        self.hbox.addWidget(self.color_labels['OK'])
        for state in COLORS:
            self.hbox.addWidget(self.color_labels[state])

        # when there are new settings/colors refresh labels
        dialogs.settings.changed.connect(self.reset)

        # when new setings are applied adjust font size
        dialogs.settings.changed.connect(self.adjust_size)

        # timer for singleshots for flashing
        self.timer = QTimer()

        self.adjust_size()

    @Slot()
    def summarize_states(self):
        """
            display summaries of states in statusbar
        """
        # initial zeros
        for label in self.color_labels.values():
            label.number = 0

        # only count numbers of enabled monitor servers
        for server in (filter(lambda s: s.enabled, servers.values())):
            for state in COLORS:
                self.color_labels[state].number += server.__dict__[state.lower()]

        # summarize all numbers - if all_numbers keeps 0 everything seems to be OK
        all_numbers = 0

        # repaint colored labels or hide them if necessary
        for label in self.color_labels.values():
            if label.number == 0:
                label.hide()
            else:
                label.setText(' '.join((str(label.number),
                                        COLOR_STATE_NAMES[label.state][conf.long_display])))
                label.show()
                label.adjustSize()
                all_numbers += label.number

        if all_numbers == 0 and not get_errors() and not self.label_message.isVisible():
            self.color_labels['OK'].show()
            self.color_labels['OK'].adjustSize()
        else:
            self.color_labels['OK'].hide()

        # fix size after refresh - better done here to avoid ugly artefacts
        hint = self.sizeHint()
        self.setMaximumSize(hint)
        self.setMinimumSize(hint)
        del hint
        # tell statuswindow its size might be adjusted
        self.resize.emit()

    @Slot()
    def flash(self):
        """
            send color inversion signal to labels
        """
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            self.labels_invert.emit()
            # fire up  a singleshot to reset color soon
            self.timer.singleShot(500, self.reset)

    @Slot()
    def reset(self):
        """
            tell labels to set original colors
        """
        self.labels_reset.emit()
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            # even later call itself to invert colors as flash
            self.timer.singleShot(500, self.flash)

    @Slot()
    def adjust_size(self):
        """
            apply new size of widgets, especially Nagstamon logo
            run through all labels to the the max height in case not all labels
            are shown at the same time - which is very likely the case
        """
        # take height for logo
        # height = 0

        # run through labels to set font and get height for logo
        for label in self.color_labels.values():
            label.setFont(FONT)
        #    if label.fontMetrics().height() > height:
        #        height = label.fontMetrics().height()

        self.label_message.setFont(FONT)
        height = self.label_message.sizeHint().height()

        # adjust logo size to fit to label size - due to being a square height and width are the same
        self.logo.adjust_size(height, height)

        # avoid flickering/artefact by updating immediately
        self.summarize_states()

    @Slot(str)
    def set_error(self, message):
        """
            display error message if any error exists
        """
        self.label_message.setText(message)
        self.label_message.show()

    @Slot()
    def reset_error(self):
        """
            delete error message if there is no error
        """
        if not get_errors():
            self.label_message.setText('')
            self.label_message.hide()


class StatusBarLabel(DraggableLabel):
    """
        one piece of the status bar labels for one state
    """

    # yell if statusbar is moved
    window_moved = Signal()

    # needed for popup after hover
    mouse_entered = Signal()

    # needed for popup after click
    mouse_pressed = Signal()
    mouse_released = Signal()

    def __init__(self, state, parent=None):
        DraggableLabel.__init__(self, parent=parent)
        self.setStyleSheet('''padding-left: 1px;
                              padding-right: 1px;
                              color: %s; background-color: %s;'''
                           % (conf.__dict__['color_%s_text' % (state.lower())],
                              conf.__dict__['color_%s_background' % (state.lower())]))
        # just let labels grow as much as they need
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        # hidden per default
        self.hide()

        # default text - only useful in case of OK Label
        self.setText(state)

        # number of hosts/services of this state
        self.number = 0

        # store state of label to access long state names in .summarize_states()
        self.state = state

    @Slot()
    def invert(self):
        self.setStyleSheet('''padding-left: 1px;
                              padding-right: 1px;
                              color: %s; background-color: %s;'''
                           % (conf.__dict__['color_%s_background' % (self.state.lower())],
                              conf.__dict__['color_%s_text' % (self.state.lower())]))

    @Slot()
    def reset(self):
        self.setStyleSheet('''padding-left: 1px;
                              padding-right: 1px;
                              color: %s; background-color: %s;'''
                           % (conf.__dict__['color_%s_text' % (self.state.lower())],
                              conf.__dict__['color_%s_background' % (self.state.lower())]))


class TopArea(QWidget):
    """
        Top area of status window
    """

    mouse_entered = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self)
        self.hbox = HBoxLayout(spacing=SPACE, parent=self)  # top HBox containing buttons
        self.hbox.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMinimumSize)

        self.icons = dict()
        self.create_icons()

        # top button box
        self.logo = NagstamonLogo(self.icons['nagstamon_logo_toparea'], width=150, height=42, parent=self)
        self.label_version = DraggableLabel(text=AppInfo.VERSION, parent=self)
        self.label_empty_space = DraggableLabel(text='', parent=self)
        self.label_empty_space.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.combobox_servers = ComboBox_Servers(parent=self)
        self.button_filters = Button("Filters", parent=self)
        self.button_recheck_all = Button("Recheck all", parent=self)
        self.button_refresh = Button("Refresh", parent=self)
        self.button_settings = Button("Settings", parent=self)

        # fill default order fields combobox with server names
        self.combobox_servers.fill()

        # hambuger menu
        self.button_hamburger_menu = PushButtonHamburger()
        self.button_hamburger_menu.setIcon(self.icons['menu'])
        self.hamburger_menu = MenuAtCursor()
        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(exit)
        self.hamburger_menu.addAction(action_exit)
        self.button_hamburger_menu.setMenu(self.hamburger_menu)

        # X
        self.button_close = Button()
        self.button_close.setIcon(self.icons['close'])
        self.button_close.setStyleSheet(CSS_CLOSE_BUTTON)

        self.hbox.addWidget(self.logo)
        self.hbox.addWidget(self.label_version)
        self.hbox.addWidget(self.label_empty_space)
        self.hbox.addWidget(self.combobox_servers)
        self.hbox.addWidget(self.button_filters)
        self.hbox.addWidget(self.button_recheck_all)
        self.hbox.addWidget(self.button_refresh)
        self.hbox.addWidget(self.button_settings)
        self.hbox.addWidget(self.button_hamburger_menu)
        self.hbox.addWidget(self.button_close)

        self.setLayout(self.hbox)

    def enterEvent(self, event):
        # unlock statuswindow if pointer touches statusbar
        self.mouse_entered.emit()

    @Slot()
    def create_icons(self):
        """
            create icons from template, applying colors
        """

        # get rgb values of current foreground color to be used for SVG icons (menu)
        r, g, b, a = app.palette().color(QPalette.ColorRole.Text).getRgb()

        for icon in 'nagstamon_logo_toparea', 'close', 'menu':
            # get template from file
            svg_template_file = open('{0}{1}{2}_template.svg'.format(RESOURCES, os.sep, icon))
            svg_template_xml = svg_template_file.readlines()

            # current SVG XML for state icon, derived from svg_template_cml
            svg_icon_xml = list()

            # replace dummy text and background colors with configured ones
            for line in svg_template_xml:
                line = line.replace('fill:#ff00ff', 'fill:#{0:x}{1:x}{2:x}'.format(r, g, b))
                svg_icon_xml.append(line)

            # create XML stream of SVG
            svg_xml_stream = QXmlStreamReader(''.join(svg_icon_xml))

            # create renderer for SVG and put SVG XML into renderer
            svg_renderer = QSvgRenderer(svg_xml_stream)
            # pixmap to be painted on - arbitrarily choosen 128x128 px
            svg_pixmap = QPixmap(128, 128)
            # fill transparent backgound
            svg_pixmap.fill(Qt.GlobalColor.transparent)
            # initiate painter which paints onto paintdevice pixmap
            svg_painter = QPainter(svg_pixmap)
            # render svg to pixmap
            svg_renderer.render(svg_painter)
            # close painting
            svg_painter.end()

            # two ways...
            if icon == 'nagstamon_logo_toparea':
                # first get a base64 version of the SVG
                svg_base64 = base64.b64encode(bytes(''.join(svg_icon_xml), 'utf8'))
                # create a QByteArray for NagstamonLogo aka QSvgWidget
                svg_bytes = QByteArray.fromBase64(svg_base64)
                self.icons[icon] = svg_bytes
            else:
                # put pixmap into icon
                self.icons[icon] = QIcon(svg_pixmap)


class ServerStatusLabel(ClosingLabel):
    """
        label for ServerVBox to show server connection state
        extra class to apply simple slots for changing text or color
    """

    # storage for label text if it needs to be restored
    text_old = ''

    def __init__(self, parent=None):
        QLabel.__init__(self, parent=parent)

    @Slot(str, str)
    def change(self, text, style=''):
        # store old text and stylesheet in case it needs to be reused
        self.text_old = self.text()
        self.stylesheet_old = self.styleSheet()

        # set stylesheet depending on submitted style
        if style in COLOR_STATUS_LABEL:
            if OS == OS_MACOS:
                self.setStyleSheet('''background: {0};
                                      border-radius: 3px;
                                      '''.format(COLOR_STATUS_LABEL[style]))
            else:
                self.setStyleSheet('''background: {0};
                                      margin-top: 8px;
                                      padding-top: 3px;
                                      margin-bottom: 8px;
                                      padding-bottom: 3px;
                                      border-radius: 4px;
                                      '''.format(COLOR_STATUS_LABEL[style]))
        elif style == '':
            self.setStyleSheet('')

        # in case of unknown errors try to avoid freaking out status window with too
        # big status label
        if style != 'unknown':
            # set new text with some space
            self.setText(' {0} '.format(text))
            self.setToolTip('')
        else:
            # set new text to first word of text, delegate full text to tooltip
            self.setText(text.split(' ')[0])
            self.setToolTip(text)

    @Slot()
    def reset(self):
        self.setStyleSheet(self.stylesheet_old)
        self.setText('')

    @Slot()
    def restore(self):
        # restore text, used by recheck_all of tablewidget worker
        self.setStyleSheet(self.stylesheet_old)
        self.setText(self.text_old)


class ServerVBox(QVBoxLayout):
    """
        one VBox per server containing buttons and hosts/services listview
    """
    # used to update status label text like 'Connected-'
    change_label_status = Signal(str, str)

    # signal to submit server to authentication dialog
    authenticate = Signal(str)

    button_fix_tls_error_show = Signal()
    button_fix_tls_error_hide = Signal()

    def __init__(self, server, parent=None):
        QVBoxLayout.__init__(self, parent)

        # no space around
        self.setSpacing(0)
        self.setContentsMargins(0, 0, 0, 0)

        # server the vbox belongs to
        self.server = server

        # header containing monitor name, buttons and status
        self.header = HBoxLayout(spacing=SPACE, parent=parent)
        self.addLayout(self.header)
        # top and bottom should be kept by padding
        self.header.setContentsMargins(0, 0, SPACE, 0)

        # self.label = QLabel(parent=parent)
        self.label = ClosingLabel(parent=parent)
        self.update_label()
        self.button_monitor = PushButton_BrowserURL(text='Monitor', parent=parent, server=self.server,
                                                    url_type='monitor')
        self.button_hosts = PushButton_BrowserURL(text='Hosts', parent=parent, server=self.server, url_type='hosts')
        self.button_services = PushButton_BrowserURL(text='Services', parent=parent, server=self.server,
                                                     url_type='services')
        self.button_history = PushButton_BrowserURL(text='History', parent=parent, server=self.server,
                                                    url_type='history')
        self.button_edit = Button('Edit', parent=parent)

        # .setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)

        # use label instead of spacer to be clickable
        self.label_stretcher = ClosingLabel('', parent=parent)
        self.label_stretcher.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)

        self.label_status = ServerStatusLabel(parent=parent)
        self.label_status.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.button_authenticate = QPushButton('Authenticate', parent=parent)

        self.button_fix_tls_error = QPushButton('Fix error', parent=parent)

        # avoid useless spaces in macOS when server has nothing to show
        # see https://bugreports.qt.io/browse/QTBUG-2699
        self.button_monitor.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_history.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_services.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_hosts.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_edit.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_authenticate.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        self.button_fix_tls_error.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)

        self.button_monitor.clicked.connect(self.button_monitor.open_url)
        self.button_hosts.clicked.connect(self.button_hosts.open_url)
        self.button_services.clicked.connect(self.button_services.open_url)
        self.button_history.clicked.connect(self.button_history.open_url)
        self.button_edit.clicked.connect(self.edit_server)

        self.header.addWidget(self.label)
        self.header.addWidget(self.button_monitor)
        self.header.addWidget(self.button_hosts)
        self.header.addWidget(self.button_services)
        self.header.addWidget(self.button_history)
        self.header.addWidget(self.button_edit)

        self.header.addWidget(self.label_stretcher)

        self.header.addWidget(self.label_status)
        self.header.addWidget(self.button_authenticate)
        self.header.addWidget(self.button_fix_tls_error)

        # attempt to get header strings
        try:
            # when stored as simple lowercase keys
            sort_column = HEADERS_KEYS_COLUMNS[conf.default_sort_field]
        except Exception:
            # when as legacy stored as presentation string
            sort_column = HEADERS_HEADERS_COLUMNS[conf.default_sort_field]

        # convert sort order to number as used in Qt.SortOrder
        sort_order = SORT_ORDER[conf.default_sort_order.lower()]

        self.table = TreeView(len(HEADERS) + 1, 0, sort_column, sort_order, self.server, parent=parent)

        # delete vbox if thread quits
        self.table.worker_thread.finished.connect(self.delete)

        # connect worker to status label to reflect connectivity
        self.table.worker.change_label_status.connect(self.label_status.change)
        self.table.worker.restore_label_status.connect(self.label_status.restore)

        # care about authentications
        self.button_authenticate.clicked.connect(self.authenticate_server)
        self.authenticate.connect(dialogs.authentication.show_auth_dialog)
        dialogs.authentication.update.connect(self.update_label)

        # start ignoring TLS trouble when button clicked
        self.button_fix_tls_error.clicked.connect(self.fix_tls_error)

        self.addWidget(self.table, 1)

        # as default do not show anything
        self.show_only_header()

    def get_real_height(self):
        """
            return summarized real height of hbox items and table
        """
        height = self.table.get_real_height()
        if self.label.isVisible() and self.button_monitor.isVisible():
            # compare item heights, decide to take the largest and add 2 time the MARGIN (top and bottom)
            if self.label.sizeHint().height() > self.button_monitor.sizeHint().height():
                height += self.label.sizeHint().height() + 2
            else:
                height += self.button_monitor.sizeHint().height() + 2
        return height

    @Slot()
    def show_all(self):
        """
            show all items in server vbox
        """
        self.button_authenticate.hide()
        self.button_edit.show()
        self.button_fix_tls_error.hide()
        self.button_history.show()
        self.button_hosts.show()
        self.button_monitor.show()
        self.button_services.show()
        self.label.show()
        self.label_status.show()
        self.label_stretcher.show()
        # special table treatment
        self.table.show()
        # self.table.is_shown = True

    @Slot()
    def show_only_header(self):
        """
            show all items in server vbox except the table - not needed if empty or major connection problem
        """
        self.button_authenticate.hide()
        self.button_edit.show()
        self.button_history.show()
        self.button_hosts.show()
        self.button_fix_tls_error.hide()
        self.button_monitor.show()
        self.button_services.show()
        self.label.show()
        self.label_status.show()
        self.label_stretcher.show()
        # special table treatment
        self.table.hide()
        # self.table.is_shown = False

    @Slot()
    def hide_all(self):
        """
            hide all items in server vbox
        """
        self.button_authenticate.hide()
        self.button_edit.hide()
        self.button_fix_tls_error.hide()
        self.button_history.hide()
        self.button_hosts.hide()
        self.button_monitor.hide()
        self.button_services.hide()
        self.label.hide()
        self.label_status.hide()
        self.label_stretcher.hide()
        # special table treatment
        self.table.hide()
        # self.table.is_shown = False

    @Slot()
    def delete(self):
        """
            delete VBox and its children
        """
        for widget in (self.label,
                       self.button_monitor,
                       self.button_hosts,
                       self.button_services,
                       self.button_history,
                       self.button_edit,
                       self.label_status,
                       self.label_stretcher,
                       self.button_authenticate,
                       self.button_fix_tls_error):
            widget.hide()
            widget.deleteLater()
        self.removeItem(self.header)
        self.header.deleteLater()
        self.table.hide()
        self.table.deleteLater()
        self.deleteLater()

    def edit_server(self):
        """
            call dialogs.server.edit() with server name
        """
        if not conf.fullscreen and not conf.windowed:
            statuswindow.hide_window()
        dialogs.server.edit(server_name=self.server.name)

    def authenticate_server(self):
        """
            send signal to open authentication dialog with self.server.name
        """
        self.authenticate.emit(self.server.name)

    @Slot()
    def update_label(self):
        self.label.setText('<big><b>&nbsp;{0}@{1}</b></big>'.format(self.server.username, self.server.name))
        # let label padding keep top and bottom space - apparently not necessary on OSX
        if OS != OS_MACOS:
            self.label.setStyleSheet('''padding-top: {0}px;
                                        padding-bottom: {0}px;'''.format(SPACE))

    @Slot()
    def fix_tls_error(self):
        """
            call dialogs.server.edit() with server name and showing extra options
        """
        if not conf.fullscreen and not conf.windowed:
            statuswindow.hide_window()
        dialogs.server.edit(server_name=self.server.name, show_options=True)


class Model(QAbstractTableModel):
    """
        Model for storing status data to be presented in Treeview-table
    """

    model_data_array_filled = Signal()

    # list of lists for storage of status data
    data_array = list()

    # cache row and column count
    row_count = 0
    column_count = len(HEADERS_HEADERS)

    # tell treeview if flags columns should be hidden or not
    hosts_flags_column_needed = Signal(bool)
    services_flags_column_needed = Signal(bool)

    def __init__(self, server, parent=None):
        QAbstractTableModel.__init__(self, parent=parent)
        self.server = server

    def rowCount(self, parent):
        """
            overridden method to get number of rows
        """
        return self.row_count

    def columnCount(self, parent):
        """
            overridden method to get number of columns
        """
        return self.column_count

    def headerData(self, column, orientation, role):
        """
            overridden method to get headers of columns
        """
        if role == Qt.ItemDataRole.DisplayRole:
            return HEADERS_HEADERS[column]

    @Slot(list, dict)
    # @Slot(list)
    def fill_data_array(self, data_array, info):
        """
            fill data_array for model
        """
        # tell treeview that model is about to change - necessary because
        # otherwise new number of rows would not be applied
        self.beginResetModel()

        # first empty the data storage
        del self.data_array[:]

        # use delivered data array
        self.data_array = data_array

        # cache row_count
        self.row_count = len(self.data_array)

        # tell treeview if flags columns are needed
        self.hosts_flags_column_needed.emit(info['hosts_flags_column_needed'])
        self.services_flags_column_needed.emit(info['services_flags_column_needed'])

        # new model applied
        self.endResetModel()

        self.model_data_array_filled.emit()

    def data(self, index, role):
        """
            overridden method for data delivery for treeview
        """
        if role == Qt.ItemDataRole.DisplayRole:
            return self.data_array[index.row()][index.column()]

        elif role == Qt.ItemDataRole.ForegroundRole:
            return self.data_array[index.row()][10]

        elif role == Qt.ItemDataRole.BackgroundRole:
            return self.data_array[index.row()][11]

        elif role == Qt.ItemDataRole.FontRole:
            if index.column() == 1:
                return ICONS_FONT
            elif index.column() == 3:
                return ICONS_FONT
            else:
                return QVariant
        # provide icons via Qt.UserRole
        elif role == Qt.ItemDataRole.UserRole:
            # depending on host or service column return host or service icon list
            return self.data_array[index.row()][7 + index.column()]

        elif role == Qt.ItemDataRole.ToolTipRole:
            # only if tooltips are wanted show them, combining host + service + status_info
            if conf.show_tooltips:
                return '''<div style=white-space:pre;margin:3px;><b>{0}: {1}</b></div>
                             {2}'''.format(self.data_array[index.row()][0],
                                           self.data_array[index.row()][2],
                                           self.data_array[index.row()][8])
            else:
                return QVariant


class TreeView(QTreeView):
    """
        attempt to get a less resource-hungry table/tree
    """

    # tell global window that it should be resized
    ready_to_resize = Signal()

    # sent by refresh() for statusbar
    refreshed = Signal()

    # tell worker to get status after a recheck has been solicited
    recheck = Signal(dict)

    # tell notification that status of server has changed
    status_changed = Signal(str, str, str)

    # action to be executed by worker
    # 2 values: action and host/service info
    request_action = Signal(dict, dict)

    # tell worker it should sort columns after someone pressed the column header
    sort_data_array_for_columns = Signal(int, int, bool)

    def __init__(self, columncount, rowcount, sort_column, sort_order, server, parent=None):
        QTreeView.__init__(self, parent=parent)

        self.sort_column = sort_column
        self.sort_order = sort_order
        self.server = server

        # no handling of selection by treeview
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # disable space at the left side
        self.setRootIsDecorated(False)
        self.setIndentation(0)

        self.setUniformRowHeights(True)

        # no scrollbars at tables because they will be scrollable by the global vertical scrollbar
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAutoScroll(False)
        self.setSortingEnabled(True)

        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        self.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSortIndicatorShown(True)
        self.header().setStretchLastSection(True)

        self.header().setSortIndicator(sort_column, SORT_ORDER[self.sort_order])

        # small method needed to tell worker which column and sort order to use
        self.header().sortIndicatorChanged.connect(self.sort_columns)

        # set overall margin and hover colors - to be refined
        self.setStyleSheet('''QTreeView::item {margin: 5px;}
                              QTreeView::item:hover {margin: 0px;
                                                     color: white;
                                                     background-color: dimgrey;}
                              QTreeView::item:selected {margin: 0px;
                                                        color: white;
                                                        background-color: grey;}
                            ''')

        # set application font
        self.set_font()
        # change font if it has been changed by settings
        dialogs.settings.changed.connect(self.set_font)

        # action context menu
        self.action_menu = MenuAtCursor(parent=self)
        # signalmapper for getting triggered actions
        self.signalmapper_action_menu = QSignalMapper()
        # connect menu to responder
        self.signalmapper_action_menu.mappedString[str].connect(self.action_menu_custom_response)

        # clipboard actions
        self.clipboard_menu = QMenu('Copy to clipboard', self)

        self.clipboard_action_host = QAction('Host', self)
        self.clipboard_action_host.triggered.connect(self.action_clipboard_action_host)
        self.clipboard_menu.addAction(self.clipboard_action_host)

        self.clipboard_action_service = QAction('Service', self)
        self.clipboard_action_service.triggered.connect(self.action_clipboard_action_service)
        self.clipboard_menu.addAction(self.clipboard_action_service)

        self.clipboard_action_statusinformation = QAction('Status information', self)
        self.clipboard_action_statusinformation.triggered.connect(self.action_clipboard_action_statusinformation)
        self.clipboard_menu.addAction(self.clipboard_action_statusinformation)

        self.clipboard_action_all = QAction('All information', self)
        self.clipboard_action_all.triggered.connect(self.action_clipboard_action_all)
        self.clipboard_menu.addAction(self.clipboard_action_all)

        self.setModel(Model(server=self.server, parent=self))
        self.model().model_data_array_filled.connect(self.adjust_table)
        self.model().hosts_flags_column_needed.connect(self.show_hosts_flags_column)
        self.model().services_flags_column_needed.connect(self.show_services_flags_column)

        # a thread + worker is necessary to get new monitor server data in the background and
        # to refresh the table cell by cell after new data is available
        self.worker_thread = QThread(parent=self)
        self.worker = self.Worker(server=server, sort_column=self.sort_column, sort_order=self.sort_order)
        self.worker.moveToThread(self.worker_thread)

        # if worker got new status data from monitor server get_status
        # the treeview model has to be updated
        self.worker.worker_data_array_filled.connect(self.model().fill_data_array)

        # fill array again if data has been sorted after a header column click
        self.worker.data_array_sorted.connect(self.model().fill_data_array)

        # tell worker to sort data_array depending on sort_column and sort_order
        self.sort_data_array_for_columns.connect(self.worker.sort_data_array)

        # if worker got new status data from monitor server get_status the table should be refreshed
        self.worker.new_status.connect(self.refresh)

        # quit thread if worker has finished
        self.worker.finish.connect(self.finish_worker_thread)

        # get status if started
        self.worker_thread.started.connect(self.worker.get_status)
        # start with priority 0 = lowest
        self.worker_thread.start()

        # connect signal for acknowledge
        dialogs.acknowledge.acknowledge.connect(self.worker.acknowledge)

        # connect signal to get start end time for downtime from worker
        dialogs.downtime.get_start_end.connect(self.worker.get_start_end)
        self.worker.set_start_end.connect(dialogs.downtime.set_start_end)

        # connect signal for downtime
        dialogs.downtime.downtime.connect(self.worker.downtime)

        # connect signal for submit check result
        dialogs.submit.submit.connect(self.worker.submit)

        # connect signal for recheck action
        self.recheck.connect(self.worker.recheck)

        # execute action by worker
        self.request_action.connect(self.worker.execute_action)

        ## display mode - all or only header to display error
        # self.is_shown = False

    @Slot()
    def set_font(self):
        """
            change font if it has been changed by settings
        """
        self.setFont(FONT)

    @Slot(bool)
    def show_hosts_flags_column(self, value):
        """
            show hosts flags column if needed
            'value' is True if there is a need so it has to be converted
        """
        self.setColumnHidden(1, not value)

    @Slot(bool)
    def show_services_flags_column(self, value):
        """
            show service flags column if needed
            'value' is True if there is a need so it has to be converted
        """
        self.setColumnHidden(3, not value)

    def get_real_height(self):
        """
            calculate real table height as there is no method included
        """
        height = 0

        mddl = self.model()

        rwcnt = mddl.rowCount(self)

        # only count if there is anything to display - there is no use of the headers only
        if self.model().rowCount(self) > 0:
            # height summary starts with headers' height
            # apparently height works better/without scrollbar if some pixels are added
            height = self.header().sizeHint().height() + 2

            # maybe simply take nagitems_filtered_count?
            height += self.indexRowSizeHint(self.model().index(0, 0)) * self.model().rowCount(self)

        return height

    def get_real_width(self):
        width = 0
        # avoid the last dummy column to be counted
        for column in range(len(HEADERS) - 1):
            width += self.columnWidth(column)
        return (width)

    @Slot()
    def adjust_table(self):
        """
            adjust table dimensions after filling it
        """
        # force table to its maximal height, calculated by .get_real_height()
        self.setMinimumHeight(self.get_real_height())
        self.setMaximumHeight(self.get_real_height())
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        # after setting table whole window can be repainted
        self.ready_to_resize.emit()

    def count_selected_rows(self):
        """
        find out if rows are selected and return their number
        """
        rows = []
        for index in self.selectedIndexes():
            if index.row() not in rows:
                rows.append(index.row())
        return len(rows)

    def mouseReleaseEvent(self, event):
        """
            forward clicked cell info from event
        """
        # special treatment if window should be closed when left-clicking somewhere
        # it is important to check if CTRL or SHIFT key is presses while clicking to select lines
        modifiers = event.modifiers()
        if conf.close_details_clicking_somewhere:
            if event.button() == Qt.MouseButton.LeftButton:
                # count selected rows - if more than 1 do not close popwin
                if modifiers or self.count_selected_rows() > 1:
                    super(TreeView, self).mouseReleaseEvent(event)
                else:
                    statuswindow.hide_window()
                return
            elif event.button() == Qt.MouseButton.RightButton:
                self.cell_clicked()
                return
        elif not modifiers or \
                event.button() == Qt.MouseButton.RightButton:
            self.cell_clicked()
            return
        else:
            super(TreeView, self).mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """
            avoid scrollable single treeview in Linux and GNOME3 by simply do nothing when getting a wheel event
        """
        event.ignore()

    def keyPressEvent(self, event):
        """
            Use to handle copy from keyboard
        """
        if event.matches(QKeySequence.StandardKey.Copy):
            self.action_clipboard_action_all()
            return
        super(TreeView, self).keyPressEvent(event)

    @Slot()
    def cell_clicked(self):
        """
            Windows reacts differently to clicks into table cells than Linux and MacOSX
            Therefore the .available flag is necessary
        """
        # empty the menu
        self.action_menu.clear()

        # clear signal mappings
        self.signalmapper_action_menu.removeMappings(self.signalmapper_action_menu)

        # add custom actions
        actions_list = list(conf.actions)
        actions_list.sort(key=str.lower)

        # How many rows do we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        # dummy definition to avoid crash if no actions are enabled - asked for some lines later
        miserable_service = None

        # Add custom actions if all selected rows want them, one per one
        for a in actions_list:
            # shortcut for next lines
            action = conf.actions[a]

            # check if current monitor server type is in action
            # second check for server type is legacy-compatible with older settings
            if action.enabled is True and (action.monitor_type in ['', self.server.TYPE] or
                                           action.monitor_type not in SERVER_TYPES):

                # menu item visibility flag
                item_visible = None

                for lrow in list_rows:
                    # temporary menu item visibility flag to collect all visibility info
                    item_visible_temporary = False
                    # take data from model data_array
                    miserable_host = self.model().data_array[lrow][0]
                    miserable_service = self.model().data_array[lrow][2]
                    miserable_duration = self.model().data_array[lrow][6]
                    miserable_attempt = self.model().data_array[lrow][7]
                    miserable_status_information = self.model().data_array[lrow][8]
                    # check if clicked line is a service or host
                    # if it is check if the action is targeted on hosts or services
                    if miserable_service:
                        if action.filter_target_service is True:
                            # only check if there is some to check
                            if action.re_host_enabled is True:
                                if is_found_by_re(miserable_host,
                                                  action.re_host_pattern,
                                                  action.re_host_reverse):
                                    item_visible_temporary = True
                            # dito
                            if action.re_service_enabled is True:
                                if is_found_by_re(miserable_service,
                                                  action.re_service_pattern,
                                                  action.re_service_reverse):
                                    item_visible_temporary = True
                            # dito
                            if action.re_status_information_enabled is True:
                                if is_found_by_re(miserable_status_information,
                                                  action.re_status_information_pattern,
                                                  action.re_status_information_reverse):
                                    item_visible_temporary = True
                            # dito
                            if action.re_duration_enabled is True:
                                if is_found_by_re(miserable_duration,
                                                  action.re_duration_pattern,
                                                  action.re_duration_reverse):
                                    item_visible_temporary = True

                            # dito
                            if action.re_attempt_enabled is True:
                                if is_found_by_re(miserable_attempt,
                                                  action.re_attempt_pattern,
                                                  action.re_attempt_reverse):
                                    item_visible_temporary = True

                            # dito - how is this supposed to work?
                            if action.re_groups_enabled is True:
                                if is_found_by_re(miserable_service,
                                                  action.re_groups_pattern,
                                                  action.re_groups_reverse):
                                    item_visible_temporary = True

                            # fallback if no regexp is selected
                            if action.re_host_enabled == action.re_service_enabled == \
                                    action.re_status_information_enabled == action.re_duration_enabled == \
                                    action.re_attempt_enabled == action.re_groups_enabled is False:
                                item_visible_temporary = True

                    else:
                        # hosts should only care about host specific actions, no services
                        if action.filter_target_host is True:
                            if action.re_host_enabled is True:
                                if is_found_by_re(miserable_host,
                                                  action.re_host_pattern,
                                                  action.re_host_reverse):
                                    item_visible_temporary = True
                            else:
                                # a non specific action will be displayed per default
                                item_visible_temporary = True

                    # when item_visible never has been set it shall be false
                    # also if at least one row leads to not-showing the item it will be false
                    if item_visible_temporary and item_visible is None:
                        item_visible = True
                    if not item_visible_temporary:
                        item_visible = False

            else:
                item_visible = False

            # populate context menu with service actions
            if item_visible is True:
                # create action
                action_menuentry = QAction(a, self)
                # add action
                self.action_menu.addAction(action_menuentry)
                # action to signalmapper
                self.signalmapper_action_menu.setMapping(action_menuentry, a)
                action_menuentry.triggered.connect(self.signalmapper_action_menu.map)

            del action, item_visible

        # create and add default actions
        action_edit_actions = QAction('Edit actions...', self)
        action_edit_actions.triggered.connect(self.action_edit_actions)
        self.action_menu.addAction(action_edit_actions)
        # put actions into menu after separator

        self.action_menu.addSeparator()
        if 'Monitor' in self.server.MENU_ACTIONS and len(list_rows) == 1:
            action_monitor = QAction('Monitor', self)
            action_monitor.triggered.connect(self.action_monitor)
            self.action_menu.addAction(action_monitor)

        if 'Recheck' in self.server.MENU_ACTIONS:
            action_recheck = QAction('Recheck', self)
            action_recheck.triggered.connect(self.action_recheck)
            self.action_menu.addAction(action_recheck)

        if 'Acknowledge' in self.server.MENU_ACTIONS:
            action_acknowledge = QAction('Acknowledge', self)
            action_acknowledge.triggered.connect(self.action_acknowledge)
            self.action_menu.addAction(action_acknowledge)

        if 'Downtime' in self.server.MENU_ACTIONS:
            action_downtime = QAction('Downtime', self)
            action_downtime.triggered.connect(self.action_downtime)
            self.action_menu.addAction(action_downtime)

        # special menu entry for Checkmk Multisite for archiving events
        if self.server.type == 'Checkmk Multisite' and len(list_rows) == 1:
            if miserable_service == 'Events':
                action_archive_event = QAction('Archive event', self)
                action_archive_event.triggered.connect(self.action_archive_event)
                self.action_menu.addAction(action_archive_event)

        # not all servers allow to submit fake check results
        if 'Submit check result' in self.server.MENU_ACTIONS and len(list_rows) == 1:
            action_submit = QAction('Submit check result', self)
            action_submit.triggered.connect(self.action_submit)
            self.action_menu.addAction(action_submit)

        # experimental clipboard submenu
        self.action_menu.addMenu(self.clipboard_menu)

        # show menu
        self.action_menu.show_at_cursor()

    @Slot(str)
    def action_menu_custom_response(self, action):
        # How many rows do we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            miserable_host = self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole)
            miserable_service = self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole)
            miserable_status_info = self.model().data(self.model().createIndex(lrow, 8), Qt.ItemDataRole.DisplayRole)

            # get data to send to action
            server = self.server.get_name()
            address = self.server.get_host(miserable_host).result
            monitor = self.server.monitor_url
            monitor_cgi = self.server.monitor_cgi_url
            username = self.server.username
            password = self.server.password
            comment_ack = conf.defaults_acknowledge_comment
            comment_down = conf.defaults_downtime_comment
            comment_submit = conf.defaults_submit_check_result_comment

            # send dict with action info and dict with host/service info
            self.request_action.emit(conf.actions[action].__dict__,
                                     {'server': server,
                                      'host': miserable_host,
                                      'service': miserable_service,
                                      'status-info': miserable_status_info,
                                      'address': address,
                                      'monitor': monitor,
                                      'monitor-cgi': monitor_cgi,
                                      'username': username,
                                      'password': password,
                                      'comment-ack': comment_ack,
                                      'comment-down': comment_down,
                                      'comment-submit': comment_submit
                                      }
                                     )

            # if action wants a closed status window it should be closed now
            if conf.actions[action].close_popwin and not conf.fullscreen and not conf.windowed:
                statuswindow.hide_window()

        # clean up
        del list_rows

    @Slot()
    def action_response_decorator(method):
        """
            decorate repeatedly called stuff
        """

        def decoration_function(self):
            # run decorated method
            method(self)
            # default actions need closed statuswindow to display own dialogs
            if not conf.fullscreen and not conf.windowed and \
                    not method.__name__ == 'action_recheck' and \
                    not method.__name__ == 'action_archive_event':
                statuswindow.hide_window()

        return (decoration_function)

    @action_response_decorator
    def action_edit_actions(self):
        # buttons in toparee
        if not conf.fullscreen and not conf.windowed:
            statuswindow.hide_window()
        # open actions tab (#3) of settings dialog
        dialogs.settings.show(tab=3)

    @action_response_decorator
    def action_monitor(self):
        # only on 1 row
        indexes = self.selectedIndexes()
        if len(indexes) > 0:
            index = indexes[0]
            miserable_host = self.model().data(self.model().createIndex(index.row(), 0), Qt.ItemDataRole.DisplayRole)
            miserable_service = self.model().data(self.model().createIndex(index.row(), 2), Qt.ItemDataRole.DisplayRole)

            # open host/service monitor in browser
            self.server.open_monitor(miserable_host, miserable_service)

    @action_response_decorator
    def action_recheck(self):
        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            miserable_host = self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole)
            miserable_service = self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole)

            # send signal to worker recheck slot
            self.recheck.emit({'host': miserable_host,
                               'service': miserable_service})

    @action_response_decorator
    def action_acknowledge(self):
        list_host = []
        list_service = []

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        # running worker method is left to OK button of dialog
        dialogs.acknowledge.initialize(server=self.server,
                                       host=list_host,
                                       service=list_service)
        dialogs.acknowledge.show()

    @action_response_decorator
    def action_downtime(self):
        list_host = []
        list_service = []

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        # running worker method is left to OK button of dialog
        dialogs.downtime.initialize(server=self.server,
                                    host=list_host,
                                    service=list_service)
        dialogs.downtime.show()

    @action_response_decorator
    def action_archive_event(self):
        """
            archive events in Checkmk Multisite Event Console
        """

        # fill action and info dict for thread-safe action request
        action = {
            'string': '$MONITOR$/view.py?_transid=$TRANSID$&_do_actions=yes&_do_confirm=Yes!&output_format=python&view_name=ec_events_of_monhost&host=$HOST$&_mkeventd_comment=archived&_mkeventd_acknowledge=on&_mkeventd_state=2&_delete_event=Archive Event&event_first_from=&event_first_until=&event_last_from=&event_last_until=',
            'type': 'url', 'recheck': True}

        list_host = []
        list_service = []
        list_status = []

        # How many rows we have
        list_rows = []
        indexes = self.selectedIndexes()
        for index in indexes:
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))
            list_status.append(self.model().data(self.model().createIndex(lrow, 8), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_host)):
            host = list_host[line_number]
            service = list_service[line_number]
            status = list_status[line_number]

            info = {'server': self.server.get_name(),
                    'host': host,
                    'service': service,
                    'status-info': status,
                    'address': self.server.get_host(host).result,
                    'monitor': self.server.monitor_url,
                    'monitor-cgi': self.server.monitor_cgi_url,
                    'username': self.server.username,
                    'password': self.server.password,
                    'comment-ack': conf.defaults_acknowledge_comment,
                    'comment-down': conf.defaults_downtime_comment,
                    'comment-submit': conf.defaults_submit_check_result_comment
                    }

            # tell worker to do the action
            self.request_action.emit(action, info)

        # clean up
        del index, indexes, list_rows, list_host, list_service, list_status

    @action_response_decorator
    def action_submit(self):
        # only on 1 row
        indexes = self.selectedIndexes()
        index = indexes[0]
        miserable_host = self.model().data(self.model().createIndex(index.row(), 0), Qt.ItemDataRole.DisplayRole)
        miserable_service = self.model().data(self.model().createIndex(index.row(), 2), Qt.ItemDataRole.DisplayRole)

        # running worker method is left to OK button of dialog
        dialogs.submit.initialize(server=self.server,
                                  host=miserable_host,
                                  service=miserable_service)
        dialogs.submit.show()

    @Slot()
    def action_clipboard_action_host(self):
        """
            copy host name to clipboard
        """

        list_host = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_host)):
            text = text + list_host[line_number]
            if line_number + 1 < len(list_host):
                text += '\n'

        clipboard.setText(text)

    @Slot()
    def action_clipboard_action_service(self):
        """
            copy service name to clipboard
        """

        list_service = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_service)):
            text = text + list_service[line_number]
            if line_number + 1 < len(list_service):
                text += '\n'

        clipboard.setText(text)

    @Slot()
    def action_clipboard_action_statusinformation(self):
        """
            copy status information to clipboard
        """
        list_status = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_status.append(self.model().data(self.model().createIndex(lrow, 8), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_status)):
            text = text + list_status[line_number]
            if line_number + 1 < len(list_status):
                text += '\n'

        clipboard.setText(text)

    @Slot()
    def action_clipboard_action_all(self):
        """
            copy all information to clipboard
        """

        list_host = []
        list_service = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_host)):
            host = list_host[line_number]
            service = list_service[line_number]

            # item to access all properties of host/service object
            # defaults to host
            item = self.server.hosts[host]
            text += f'Host: {host}\n'
            # if it is a service switch to service object
            if service != '':
                if item.services.get(service):
                    item = item.services[service]
                    text += f'Service: {service}\n'
                # finally solve https://github.com/HenriWahl/Nagstamon/issues/1024
                elif self.server.TYPE == 'Zabbix':
                    for service_item in item.services.values():
                        if service_item.name == service:
                            item = service_item
                            text += f'Service: {service}\n'
                            break

            # the other properties belong to both hosts and services
            text += 'Status: {0}\n'.format(item.status)
            text += 'Last check: {0}\n'.format(item.last_check)
            text += 'Duration: {0}\n'.format(item.duration)
            text += 'Attempt: {0}\n'.format(item.attempt)
            text += 'Status information: {0}\n'.format(item.status_information)
            if line_number + 1 < len(list_host):
                text += '\n'

        # copy text to clipboard
        clipboard.setText(text)

    @Slot()
    def refresh(self):
        """
            refresh status display
        """
        # avoid race condition when waiting for password dialog
        if statuswindow is not None:
            # do nothing if window is moving to avoid lagging movement
            if not statuswindow.moving:
                ## get_status table cells with new data by thread
                # if len(self.model().data_array) > 0:
                #    self.is_shown = True
                # else:
                #    self.is_shown = False
                # tell statusbar it should update
                self.refreshed.emit()

                # check if status changed and notification is necessary
                # send signal because there are unseen events
                # status has changed if there are unseen events in the list OR (current status is up AND has been changed since last time)
                if (self.server.get_events_history_count() > 0) or \
                        ((self.server.worst_status_current == 'UP') and (
                                self.server.worst_status_current != self.server.worst_status_last)):
                    self.status_changed.emit(self.server.name, self.server.worst_status_diff,
                                             self.server.worst_status_current)

    @Slot(int, Qt.SortOrder)
    def sort_columns(self, sort_column, sort_order):
        """
            forward sorting task to worker
        """
        # better int() the Qt.* values because they partly seem to be
        # intransmissible
        # get_sort_order_value() cures the differences between Qt5 and Qt6
        self.sort_data_array_for_columns.emit(int(sort_column), int(get_sort_order_value(sort_order)), True)

    @Slot()
    def finish_worker_thread(self):
        """
            attempt to shutdown thread cleanly
        """
        # tell thread to quit
        self.worker_thread.quit()
        # wait until thread is really stopped
        self.worker_thread.wait()

    class Worker(QObject):
        """
            attempt to run a server status update thread - only needed by table so it is defined here inside table
        """

        # send signal if monitor server has new status data
        new_status = Signal()

        # send signal if next cell can be filled
        next_cell = Signal(int, int, str, str, str, list, str)

        # send signal if all cells are filled and table can be adjusted
        table_ready = Signal()

        # send signal if ready to stop
        finish = Signal()

        # send start and end of downtime
        set_start_end = Signal(str, str)

        # try to stop thread by evaluating this flag
        running = True

        # signal to be sent to slot "change" of ServerStatusLabel
        change_label_status = Signal(str, str)

        # signal to be sent to slot "restore" of ServerStatusLabel
        restore_label_status = Signal()

        # send notification a stop message if problems vanished without being noticed
        problems_vanished = Signal()

        # flag to keep recheck_all from being started more than once
        rechecking_all = False

        # signals to control error message in statusbar
        show_error = Signal(str)
        hide_error = Signal()

        # sent to treeview with new data_array
        worker_data_array_filled = Signal(list, dict)

        # sendt to treeview if data has been sorted by click on column header
        data_array_sorted = Signal(list, dict)

        # keep track of last sorting column and order to pre-sort by it
        # start with sorting by host
        last_sort_column_cached = 0
        last_sort_column_real = 0
        last_sort_order = 0

        # keep track of action menu being shown or not to avoid refresh while selecting multiple items
        # action_menu_shown = False

        def __init__(self, parent=None, server=None, sort_column=0, sort_order=0):
            QObject.__init__(self)
            self.server = server
            # needed for update interval
            self.timer = QTimer(self)
            self.server.init_config()

            self.sort_column = sort_column
            self.sort_order = sort_order

        @Slot()
        def get_status(self):
            """
                check every second if thread still has to run
                if interval time is reached get status
            """
            # if counter is at least update interval get status
            if self.server.thread_counter >= conf.update_interval_seconds:
                # only if no multiple selection is done at the moment and no context action menu is open
                if not app.keyboardModifiers() and app.activePopupWidget() is None:
                    # reflect status retrieval attempt on server vbox label
                    self.change_label_status.emit('Refreshing...', '')

                    status = self.server.get_status()

                    # all is OK if no error info came back
                    if self.server.status_description == '' and \
                            self.server.status_code < 400 and \
                            not self.server.refresh_authentication and \
                            not self.server.tls_error:
                        # show last update time
                        self.change_label_status.emit(
                            'Last updated at {0}'.format(datetime.datetime.now().strftime('%X')), '')

                        # reset server error flag, needed for error label in statusbar
                        self.server.has_error = False

                        # tell statusbar there is no error
                        self.hide_error.emit()
                    else:
                        # try to display some more user friendly error description
                        if self.server.status_code == 404:
                            self.change_label_status.emit('Monitor URL not valid', 'critical')
                        elif status.error.startswith('requests.exceptions.ConnectTimeout'):
                            self.change_label_status.emit('Connection timeout', 'error')
                        elif status.error.startswith('requests.exceptions.ConnectionError'):
                            self.change_label_status.emit('Connection error', 'error')
                        elif status.error.startswith('requests.exceptions.ReadTimeout'):
                            self.change_label_status.emit('Connection timeout', 'error')
                        elif status.error.startswith('requests.exceptions.ProxyError'):
                            self.change_label_status.emit('Proxy error', 'error')
                        elif status.error.startswith('requests.exceptions.MaxRetryError'):
                            self.change_label_status.emit('Max retry error', 'error')
                        elif self.server.tls_error:
                            self.change_label_status.emit('SSL/TLS problem', 'critical')
                        elif self.server.status_code in self.server.STATUS_CODES_NO_AUTH or \
                                self.server.refresh_authentication:
                            self.change_label_status.emit('Authentication problem', 'critical')
                        elif self.server.status_code == 503:
                            self.change_label_status.emit('Service unavailable', 'error')
                        else:
                            # kick out line breaks to avoid broken status window
                            if self.server.status_description == '':
                                self.server.status_description = 'Unknown error'
                            self.change_label_status.emit(self.server.status_description.replace('\n', ''), 'error')

                        # set server error flag, needed for error label in statusbar
                        self.server.has_error = True

                        # tell statusbar there is some error to display
                        self.show_error.emit('ERROR')

                    # reset counter for this thread
                    self.server.thread_counter = 0

                    # if failures have gone and nobody took notice switch notification off again
                    if len([k for k, v in self.server.events_history.items() if v is True]) == 0 and \
                            statuswindow and \
                            statuswindow.worker_notification.is_notifying is True and \
                            statuswindow.worker_notification.notifying_server == self.server.name:
                        # tell notification that unnoticed problems are gone
                        self.problems_vanished.emit()

                    # stuff data into array and sort it
                    self.fill_data_array(self.sort_column, self.sort_order)

                    # tell news about new status available
                    self.new_status.emit()

            # increase thread counter
            self.server.thread_counter += 1

            # if running flag is still set call myself after 1 second
            if self.running:
                self.timer.singleShot(1000, self.get_status)
            else:
                # tell treeview to finish worker_thread
                self.finish.emit()

        @Slot(int, int)
        def fill_data_array(self, sort_column, sort_order):
            """
                let worker do the dirty job of filling the array
            """

            # data_array to be evaluated in data() of model
            # first 9 items per row come from current status information
            self.data_array = list()

            # dictionary containing extra info about data_array
            self.info = {'hosts_flags_column_needed': False,
                         'services_flags_column_needed': False, }

            # only refresh table if there is no popup opened
            if not app.activePopupWidget():
                # avoid race condition when waiting for password dialog
                if len(QBRUSHES[0]) > 0:
                    # cruising the whole nagitems structure
                    for category in ('hosts', 'services'):
                        for state in self.server.nagitems_filtered[category].values():
                            for item in state:
                                self.data_array.append(list(item.get_columns(HEADERS)))

                                # hash for freshness comparison
                                hash = item.get_hash()

                                if item.is_host():
                                    if hash in self.server.events_history and \
                                            self.server.events_history[hash] is True:
                                        # second item in last data_array line is host flags
                                        self.data_array[-1][1] += 'N'
                                else:
                                    if hash in self.server.events_history and \
                                            self.server.events_history[hash] is True:
                                        # fourth item in last data_array line is service flags
                                        self.data_array[-1][3] += 'N'
                                # add text color as QBrush from status
                                self.data_array[-1].append(
                                    QBRUSHES[len(self.data_array) % 2][COLORS[item.status] + 'text'])
                                # add background color as QBrush from status
                                self.data_array[-1].append(
                                    QBRUSHES[len(self.data_array) % 2][COLORS[item.status] + 'background'])
                                # add text color name for sorting data
                                self.data_array[-1].append(COLORS[item.status] + 'text')
                                # add background color name for sorting data
                                self.data_array[-1].append(COLORS[item.status] + 'background')

                                # check if hosts and services flags should be shown
                                if self.data_array[-1][1] != '':
                                    self.info['hosts_flags_column_needed'] = True
                                if self.data_array[-1][3] != '':
                                    self.info['services_flags_column_needed'] = True

                                self.data_array[-1].append('X')

                # sort data before it gets transmitted to treeview model
                self.sort_data_array(self.sort_column, self.sort_order, False)

                # give sorted data to model
                self.worker_data_array_filled.emit(self.data_array, self.info)

        @Slot(int, int, bool)
        def sort_data_array(self, sort_column, sort_order, header_clicked=False):
            """
                sort list of lists in data_array depending on sort criteria
                used from fill_data_array() and when clicked on table headers
            """
            # store current sort_column and sort_data for next sort actions
            self.sort_column = sort_column
            self.sort_order = sort_order

            # to keep GTK Treeview sort behaviour first by hosts
            first_sort = sorted(self.data_array,
                                key=lambda row: SORT_COLUMNS_FUNCTIONS[self.last_sort_column_real](
                                    row[SORT_COLUMNS_INDEX[self.last_sort_column_real]]),
                                reverse=self.last_sort_order)

            # use SORT_COLUMNS from Helpers to sort column accordingly
            self.data_array = sorted(first_sort,
                                     key=lambda row: SORT_COLUMNS_FUNCTIONS[self.sort_column](
                                         row[SORT_COLUMNS_INDEX[self.sort_column]]),
                                     reverse=self.sort_order)

            # fix alternating colors
            for count, row in enumerate(self.data_array):
                # change text color of sorted rows
                row[10] = QBRUSHES[count % 2][row[12]]
                # change background color of sorted rows
                row[11] = QBRUSHES[count % 2][row[13]]

            # if header was clicked tell model to use new data_array
            if header_clicked:
                self.data_array_sorted.emit(self.data_array, self.info)

            # store last sorting column for next sorting only if header was clicked
            if header_clicked:
                # last sorting column needs to be cached to avoid losing it
                # effective last column is self.last_sort_column_real
                if self.last_sort_column_cached != self.sort_column:
                    self.last_sort_column_real = self.last_sort_column_cached
                    self.last_sort_order = self.sort_order

                self.last_sort_column_cached = self.sort_column

        @Slot(dict)
        def acknowledge(self, info_dict):
            """
                slot waiting for 'acknowledge' signal from ok button from acknowledge dialog
                all information about target server, host, service and flags is contained
                in dictionary 'info_dict'
            """
            # because all monitors are connected to this slot we must check which one sent the signal,
            # otherwise there are several calls and not only one as wanted
            if self.server == info_dict['server']:
                # pass dictionary to server's acknowledge machinery
                self.server.set_acknowledge(info_dict)

        @Slot(dict)
        def downtime(self, info_dict):
            """
                slot waiting for 'downtime' signal from ok button from downtime dialog
                all information about target server, host, service and flags is contained
                in dictionary 'info_dict'
            """
            # because all monitors are connected to this slot we must check which one sent the signal,
            # otherwise there are several calls and not only one as wanted
            if self.server == info_dict['server']:
                # pass dictionary to server's downtime machinery
                self.server.set_downtime(info_dict)

        @Slot(dict)
        def submit(self, info_dict):
            """
                slot waiting for 'submit' signal from ok button from submit dialog
                all information about target server, host, service and flags is contained
                in dictionary 'info_dict'
            """
            # because all monitors are connected to this slot we must check which one sent the signal,
            # otherwise there are several calls and not only one as wanted
            if self.server == info_dict['server']:
                # pass dictionary to server's downtime machinery
                self.server.set_submit_check_result(info_dict)

        @Slot(dict)
        def recheck(self, info_dict):
            """
                Slot to start server recheck method, getting signal from TableWidget context menu
            """
            if conf.debug_mode:
                # host
                if info_dict['service'] == '':
                    self.server.debug(server=self.server.name, debug='Rechecking host {0}'.format(info_dict['host']))
                else:
                    self.server.debug(server=self.server.name,
                                      debug='Rechecking service {0} on host {1}'.format(info_dict['service'],
                                                                                        info_dict['host']))

            # call server recheck method
            self.server.set_recheck(info_dict)

        @Slot()
        def recheck_all(self):
            """
                call server.set_recheck for every single host/service
            """
            # only if no already rechecking
            if self.rechecking_all is False:
                # block rechecking
                self.rechecking_all = True
                # change label of server vbox
                self.change_label_status.emit('Rechecking all...', '')
                if conf.debug_mode:
                    self.server.debug(server=self.server.name, debug='Start rechecking all')
                # special treatment for Checkmk Multisite because there is only one URL call necessary
                if self.server.type != 'Checkmk Multisite':
                    # make a copy to preserve hosts/service to recheck - just in case something changes meanwhile
                    nagitems_filtered = deepcopy(self.server.nagitems_filtered)
                    for status in nagitems_filtered['hosts'].items():
                        for host in status[1]:
                            if conf.debug_mode:
                                self.server.debug(server=self.server.name,
                                                  debug='Rechecking host {0}'.format(host.name))
                            # call server recheck method
                            self.server.set_recheck({'host': host.name, 'service': ''})
                    for status in nagitems_filtered['services'].items():
                        for service in status[1]:
                            if conf.debug_mode:
                                self.server.debug(server=self.server.name,
                                                  debug='Rechecking service {0} on host {1}'.format(
                                                      service.get_service_name(),
                                                      service.host))
                            # call server recheck method
                            self.server.set_recheck({'host': service.host, 'service': service.name})
                    del (nagitems_filtered, status)
                else:
                    # Checkmk Multisite does it its own way
                    self.server.recheck_all()
                # release rechecking lock
                self.rechecking_all = False
                # restore server status label
                self.restore_label_status.emit()
            else:
                if conf.debug_mode:
                    self.server.debug(server=self.server.name, debug='Already rechecking all')

        @Slot(str, str)
        def get_start_end(self, server_name, host):
            """
                Investigates start and end time of a downtime asynchronously
            """
            # because every server listens to this signal the name has to be filtered
            if server_name == self.server.name:
                start, end = self.server.get_start_end(host)
                # send start/end time to slot
                self.set_start_end.emit(start, end)

        @Slot(dict, dict)
        def execute_action(self, action, info):
            """
                runs action, may it be custom or included like the Checkmk Multisite actions
            """
            # first replace placeholder variables in string with actual values
            #
            # Possible values for variables:
            # $HOST$             - host as in monitor
            # $SERVICE$          - service as in monitor
            # $MONITOR$          - monitor address - not yet clear what exactly for
            # $MONITOR-CGI$      - monitor CGI address - not yet clear what exactly for
            # $ADDRESS$          - address of host, investigated by Server.GetHost()
            # $STATUS-INFO$      - status information
            # $USERNAME$         - username on monitor
            # $PASSWORD$         - username's password on monitor - whatever for
            # $COMMENT-ACK$      - default acknowledge comment
            # $COMMENT-DOWN$     - default downtime comment
            # $COMMENT-SUBMIT$   - default submit check result comment

            try:
                # used for POST request
                if 'cgi_data' in action:
                    cgi_data = action['cgi_data']
                else:
                    cgi_data = ''

                # mapping of variables and values
                mapping = {'$HOST$': info['host'],
                           '$SERVICE$': info['service'],
                           '$ADDRESS$': info['address'],
                           '$MONITOR$': info['monitor'],
                           '$MONITOR-CGI$': info['monitor-cgi'],
                           '$STATUS-INFO$': info['status-info'],
                           '$USERNAME$': info['username'],
                           '$PASSWORD$': info['password'],
                           '$COMMENT-ACK$': info['comment-ack'],
                           '$COMMENT-DOWN$': info['comment-down'],
                           '$COMMENT-SUBMIT$': info['comment-submit']}

                # take string form action
                string = action['string']

                # mapping mapping
                for i in mapping:
                    # mapping with urllib.quote
                    string = string.replace("$" + i + "$", quote(mapping[i]))
                    # normal mapping
                    string = string.replace(i, mapping[i])

                # see what action to take
                if action['type'] == 'browser':
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: BROWSER ' + string)
                    webbrowser_open(string)
                elif action['type'] == 'command':
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: COMMAND ' + string)
                    subprocess.Popen(string, shell=True)
                elif action['type'] == 'url':
                    # Checkmk uses transids - if this occurs in URL its very likely that a Checkmk-URL is called
                    if '$TRANSID$' in string:
                        transid = servers[info['server']]._get_transid(info['host'], info['service'])
                        string = string.replace('$TRANSID$', transid).replace(' ', '+')
                    else:
                        # make string ready for URL
                        string = self._URLify(string)
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: URL in background ' + string)
                    servers[info['server']].fetch_url(string)
                # used for example by Op5Monitor.py
                elif action['type'] == 'url-post':
                    # make string ready for URL
                    string = self._URLify(string)
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: URL-POST in background ' + string)
                    servers[info['server']].fetch_url(string, cgi_data=cgi_data, multipart=True)

                if action['recheck']:
                    self.recheck(info)

            except Exception:
                traceback.print_exc(file=sys.stdout)

        def _URLify(self, string):
            """
                return a string that fulfills requirements for URLs
                exclude several chars
            """
            return quote(string, ":/=?&@+")

        @Slot()
        def unfresh_event_history(self):
            # set all flagged-as-fresh-events to un-fresh
            for event in self.server.events_history.keys():
                self.server.events_history[event] = False


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

# access to clipboard
clipboard = app.clipboard()

# system tray icon
systrayicon = SystemTrayIcon()

# set to none here due to race condition
statuswindow = None
menu = None

# combined statusbar/status window
statuswindow = StatusWindow()

# context menu for statuswindow etc.
menu = MenuContext()

# necessary extra menu due to Qt5-Unity-integration
if not OS in OS_NON_LINUX:
    menu_systray = MenuContextSystrayicon()
# menu has to be set here to solve Qt-5.10-Windows-systray-mess
# and non-existence of macOS-systray-context-menu
elif conf.icon_in_systray:
    systrayicon.set_menu(menu)

# versatile mediaplayer
mediaplayer = MediaPlayer(statuswindow, RESOURCE_FILES)
