# encoding: utf-8
# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2023 Henri Wahl <henri@nagstamon.de> et al.
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

# for details of imports look into qt.py
from .qt import *

from Nagstamon.Config import (Action,
                              AppInfo,
                              BOOLPOOL,
                              conf,
                              CONFIG_STRINGS,
                              debug_queue,
                              DESKTOP_NEEDS_FIX,
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

from Nagstamon.Helpers import (is_found_by_re,
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

# DBus only interesting for Linux too
if OS not in OS_NON_LINUX:
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

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)

# check ECP authentication support availability
try:
    from requests_ecp import HTTPECPAuth
    ECP_AVAILABLE = True
except ImportError:
    ECP_AVAILABLE = False

# since Qt6 HighDPI-awareness is default behaviour
if QT_VERSION_MAJOR < 6:
    # enable HighDPI-awareness to avoid https://github.com/HenriWahl/Nagstamon/issues/618
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    except AttributeError:
        pass
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# global application instance
APP = QApplication(sys.argv)

# fixed shortened and lowered color names for cells, also used by statusbar label snippets
COLORS = OrderedDict([('DOWN', 'color_down_'),
                      ('UNREACHABLE', 'color_unreachable_'),
                      ('DISASTER', 'color_disaster_'),
                      ('CRITICAL', 'color_critical_'),
                      ('HIGH', 'color_high_'),
                      ('AVERAGE', 'color_average_'),
                      ('WARNING', 'color_warning_'),
                      ('INFORMATION', 'color_information_'),
                      ('UNKNOWN', 'color_unknown_')])

# states to be used in statusbar if long version is used
COLOR_STATE_NAMES = {'DOWN': {True: 'DOWN', False: ''},
                     'UNREACHABLE': {True: 'UNREACHABLE', False: ''},
                     'DISASTER': {True: 'DISASTER', False: ''},
                     'CRITICAL': {True: 'CRITICAL', False: ''},
                     'HIGH': {True: 'HIGH', False: ''},
                     'AVERAGE': {True: 'AVERAGE', False: ''},
                     'WARNING': {True: 'WARNING', False: ''},
                     'INFORMATION': {True: 'INFORMATION', False: ''},
                     'UNKNOWN': {True: 'UNKNOWN', False: ''}}

# colors for server status label in ServerVBox
COLOR_STATUS_LABEL = {'critical': 'lightsalmon',
                      'error': 'orange',
                      'unknown': 'gray'}

# QBrushes made of QColors for treeview model data() method
# 2 flavours for alternating backgrounds
# filled by create_brushes()
QBRUSHES = {0: {}, 1: {}}

# headers for tablewidgets
HEADERS = OrderedDict([('host', {'header': 'Host',
                                 'column': 0}),
                       ('host_flags', {'header': '',
                                       'column': 0}),
                       ('service', {'header': 'Service',
                                    'column': 2}),
                       ('service_flags', {'header': '',
                                          'column': 2}),
                       ('status', {'header': 'Status',
                                   'column': 4}),
                       ('last_check', {'header': 'Last Check',
                                       'column': 5}),
                       ('duration', {'header': 'Duration',
                                     'column': 6}),
                       ('attempt', {'header': 'Attempt',
                                    'column': 7}),
                       ('status_information', {'header': 'Status Information',
                                               'column': 8}),
                       ('dummy_column', {'header': '',
                                         'column': 8})])

# various headers-key-columns variations needed in different parts
HEADERS_HEADERS = list()
for item in HEADERS.values():
    HEADERS_HEADERS.append(item['header'])

HEADERS_HEADERS_COLUMNS = dict()
for item in HEADERS.values():
    HEADERS_HEADERS_COLUMNS[item['header']] = item['column']

HEADERS_HEADERS_KEYS = dict()
for item in HEADERS.keys():
    HEADERS_HEADERS_KEYS[HEADERS[item]['header']] = item

HEADERS_KEYS_COLUMNS = dict()
for item in HEADERS.keys():
    HEADERS_KEYS_COLUMNS[item] = HEADERS[item]['column']

HEADERS_KEYS_HEADERS = dict()
for item in HEADERS.keys():
    HEADERS_KEYS_HEADERS[item] = HEADERS[item]['header']

# sorting order for tablewidgets
SORT_ORDER = {'descending': 1, 'ascending': 0, 0: Qt.SortOrder.DescendingOrder, 1: Qt.SortOrder.AscendingOrder}

# bend columns 1 and 3 to 0 and 2 to avoid sorting the extra flag icons of hosts and services
SORT_COLUMNS_INDEX = {0: 0,
                      1: 0,
                      2: 2,
                      3: 2,
                      4: 4,
                      5: 5,
                      6: 6,
                      7: 7,
                      8: 8,
                      9: 8}

# space used in LayoutBoxes
SPACE = 10

# save default font to be able to reset to it
DEFAULT_FONT = APP.font()

# take global FONT from conf if it exists
if conf.font != '':
    FONT = QFont()
    FONT.fromString(conf.font)
else:
    FONT = DEFAULT_FONT

# add nagstamon.ttf with icons to fonts
QFontDatabase.addApplicationFont('{0}{1}nagstamon.ttf'.format(RESOURCES, os.sep))

# always stay in normal weight without any italic
ICONS_FONT = QFont('Nagstamon', FONT.pointSize() + 2, QFont.Weight.Normal, False)

# completely silly but no other rescue for Windows-hides-statusbar-after-display-mode-change problem
NUMBER_OF_DISPLAY_CHANGES = 0

# Flags for statusbar - experiment with Qt.ToolTip for Windows because
# statusbar permanently seems to vanish at some users desktops
# see https://github.com/HenriWahl/Nagstamon/issues/222
WINDOW_FLAGS = Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool

# icon for dialogs
ICON = QIcon('{0}{1}nagstamon.ico'.format(RESOURCES, os.sep))

# set style for tooltips globally - to sad not all properties can be set here
APP.setStyleSheet('''QToolTip { margin: 3px;
                                }''')

# store default sounds as buffers to avoid https://github.com/HenriWahl/Nagstamon/issues/578
# meanwhile used as backup copy in case they had been deleted by macOS
# https://github.com/HenriWahl/Nagstamon/issues/578
RESOURCE_FILES = FilesDict(RESOURCES)


class HBoxLayout(QHBoxLayout):
    """
        Apparently necessary to get a HBox which is able to hide its children
    """

    def __init__(self, spacing=None, parent=None):
        QHBoxLayout.__init__(self, parent)

        if spacing is None:
            self.setSpacing(0)
        else:
            self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)  # no margin


class QIconWithFilename(QIcon):
    """
    extend QIcon with a filename property
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if type(args[0]) == str:
            self.filename = args[0]


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
        if conf.debug_mode:
            debug_queue.append('DEBUG: Initializing SystemTrayIcon')

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
        if conf.debug_mode:
            debug_queue.append('DEBUG: SystemTrayIcon initial icon: {}'.format(self.currentIconName()))

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


class MenuAtCursor(QMenu):
    """
        open menu at position of mouse pointer - normal .exec() shows menu at (0, 0)
    """
    # flag to avoid too fast popping up menus
    # available = True

    is_shown = Signal(bool)

    def __init__(self, parent=None):
        QMenu.__init__(self, parent=parent)

    @Slot()
    def show_at_cursor(self):
        """
            pop up at mouse pointer position, lock itself to avoid permamently popping menus on Windows
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
        del (x, y)


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
            self.action_save_position.triggered.connect(self.save_position)
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

    def save_position(self):
        """
            save position from window into config
        """

        statuswindow.store_position_to_conf()
        conf.SaveConfig()


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


class FlatButton(QToolButton):
    """
        QToolButton acting as push button
    """

    def __init__(self, text='', parent=None, server=None, url_type=''):
        QToolButton.__init__(self, parent=parent)
        self.setAutoRaise(True)
        self.setStyleSheet('''padding: 3px;''')
        self.setText(text)


# OSX does not support flat QToolButtons so keep the neat default ones
if OS == OS_MACOS:
    Button = QPushButton
    CSS_CLOSE_BUTTON = '''QPushButton {border-width: 0px;
                                       border-style: none;
                                       margin-right: 5px;}
                          QPushButton:hover {background-color: white;
                                             border-radius: 4px;}'''
    CSS_HAMBURGER_MENU = '''QPushButton {border-width: 0px;
                                         border-style: none;}
                            QPushButton::menu-indicator{image:url(none.jpg)};
                            QPushButton:hover {background-color: white;
                                               border-radius: 4px;}'''
else:
    Button = FlatButton
    CSS_CLOSE_BUTTON = '''margin-right: 5px;'''
    CSS_HAMBURGER_MENU = '''FlatButton::menu-indicator{image:url(none.jpg);}'''


class PushButton_Hamburger(Button):
    """
        Pushbutton with menu for hamburger
    """

    pressed = Signal()

    def __init__(self):
        # ##QPushButton.__init__(self)
        Button.__init__(self)
        self.setStyleSheet(CSS_HAMBURGER_MENU)

    def mousePressEvent(self, event):
        self.pressed.emit()
        self.showMenu()

    @Slot(QMenu)
    def set_menu(self, menu):
        self.setMenu(menu)


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
            self.server.Debug(server=self.server.get_name(), debug='Open {0} web page {1}'.format(self.url_type, url))

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

    def save_position(self):
        """
            save position from window into config
        """
        statuswindow.store_position_to_conf()
        conf.SaveConfig()

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


class AllOKLabel(QLabel):
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
        APP.setQuitOnLastWindowClosed(False)

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

        self.label_all_ok = AllOKLabel(parent=self)
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
            should actually fit into qt.py but due to the reference to APP it could only
            be solved here
        """
        # Qt6 has .screen() as replacement for QDesktopWidget...
        if QT_VERSION_MAJOR > 5:
            return self.screen()
        # ...and .screen() exists since Qt5 5.15...
        elif QT_VERSION_MINOR < 15:
            return APP.desktop()
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
                not APP.activePopupWidget() is None or \
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

    @Slot(str, str)
    def show_message(self, msg_type, message):
        """
            show message from other thread like MediaPlayer
        """
        title = " ".join((AppInfo.NAME, msg_type))
        if msg_type == 'warning':
            return QMessageBox.warning(statuswindow, title, message)

        elif msg_type == 'information':
            return QMessageBox.information(statuswindow,title, message)

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
                server.Debug(server=server.name, debug='Refreshing all hosts and services')

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
                APP.activePopupWidget() == None:
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
                servers[server_name].Debug(debug='NOTIFICATION: ' + custom_action_string)
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
        #height = 0

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
        self.button_hamburger_menu = PushButton_Hamburger()
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
        r, g, b, a = APP.palette().color(QPalette.ColorRole.Text).getRgb()

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
        #self.table.is_shown = True

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
        #self.table.is_shown = False

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
        #self.table.is_shown = False

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
        #self.is_shown = False

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
            address = self.server.GetHost(miserable_host).result
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
                    'address': self.server.GetHost(host).result,
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
            text += 'Host: {0}\n'.format(host)
            # if it is a service switch to service object
            if service != '' and item.services.get(service):
                item = item.services[service]
                text += 'Service: {0}\n'.format(service)
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
                #if len(self.model().data_array) > 0:
                #    self.is_shown = True
                #else:
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
                if not APP.keyboardModifiers() and APP.activePopupWidget() is None:
                    # reflect status retrieval attempt on server vbox label
                    self.change_label_status.emit('Refreshing...', '')

                    status = self.server.GetStatus()

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
            if not APP.activePopupWidget():
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
                    self.server.Debug(server=self.server.name, debug='Rechecking host {0}'.format(info_dict['host']))
                else:
                    self.server.Debug(server=self.server.name,
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
                    self.server.Debug(server=self.server.name, debug='Start rechecking all')
                # special treatment for Checkmk Multisite because there is only one URL call necessary
                if self.server.type != 'Checkmk Multisite':
                    # make a copy to preserve hosts/service to recheck - just in case something changes meanwhile
                    nagitems_filtered = deepcopy(self.server.nagitems_filtered)
                    for status in nagitems_filtered['hosts'].items():
                        for host in status[1]:
                            if conf.debug_mode:
                                self.server.Debug(server=self.server.name,
                                                  debug='Rechecking host {0}'.format(host.name))
                            # call server recheck method
                            self.server.set_recheck({'host': host.name, 'service': ''})
                    for status in nagitems_filtered['services'].items():
                        for service in status[1]:
                            if conf.debug_mode:
                                self.server.Debug(server=self.server.name,
                                                  debug='Rechecking service {0} on host {1}'.format(service.name,
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
                    self.server.Debug(server=self.server.name, debug='Already rechecking all')

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
                        self.server.Debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: BROWSER ' + string)
                    webbrowser_open(string)
                elif action['type'] == 'command':
                    # debug
                    if conf.debug_mode is True:
                        self.server.Debug(server=self.server.name, host=info['host'], service=info['service'],
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
                        self.server.Debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: URL in background ' + string)
                    servers[info['server']].FetchURL(string)
                # used for example by Op5Monitor.py
                elif action['type'] == 'url-post':
                    # make string ready for URL
                    string = self._URLify(string)
                    # debug
                    if conf.debug_mode is True:
                        self.server.Debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: URL-POST in background ' + string)
                    servers[info['server']].FetchURL(string, cgi_data=cgi_data, multipart=True)

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


class Dialogs(object):
    """
        class for accessing all dialogs
    """
    windows = list()

    def __init__(self):
        # settings main dialog
        self.settings = Dialog_Settings('settings_main')
        self.settings.initialize()
        self.windows.append(self.settings.window)

        # server settings dialog
        self.server = Dialog_Server('settings_server')
        self.server.initialize()
        self.windows.append(self.server.window)

        # action settings dialog
        self.action = Dialog_Action('settings_action')
        self.action.initialize()
        self.windows.append(self.action.window)

        # acknowledge dialog for miserable item context menu
        self.acknowledge = Dialog_Acknowledge('dialog_acknowledge')
        self.acknowledge.initialize()
        self.windows.append(self.acknowledge.window)

        # downtime dialog for miserable item context menu
        self.downtime = Dialog_Downtime('dialog_downtime')
        self.downtime.initialize()
        self.windows.append(self.downtime.window)

        # open defaults settings on button click
        self.downtime.window.button_change_defaults_downtime.clicked.connect(self.settings.show_defaults)
        self.downtime.window.button_change_defaults_downtime.clicked.connect(self.downtime.window.close)
        self.acknowledge.window.button_change_defaults_acknowledge.clicked.connect(self.settings.show_defaults)
        self.acknowledge.window.button_change_defaults_acknowledge.clicked.connect(self.acknowledge.window.close)

        # downtime dialog for miserable item context menu
        self.submit = Dialog_Submit('dialog_submit')
        self.submit.initialize()
        self.windows.append(self.submit.window)

        # authentication dialog for username/password
        self.authentication = Dialog_Authentication('dialog_authentication')
        self.authentication.initialize()
        self.windows.append(self.authentication.window)

        # dialog for asking about disabled or not configured servers
        self.server_missing = Dialog_Server_missing('dialog_server_missing')
        self.server_missing.initialize()
        self.windows.append(self.server_missing.window)

        # open server creation dialog
        self.server_missing.window.button_create_server.clicked.connect(self.settings.show_new_server)
        self.server_missing.window.button_enable_server.clicked.connect(self.settings.show)

        # about dialog
        self.about = Dialog_About('dialog_about')
        self.windows.append(self.about.window)

        # file chooser Dialog
        self.file_chooser = QFileDialog()

        # check if special widgets have to be shown
        self.server.edited.connect(self.settings.toggle_zabbix_widgets)
        self.server.edited.connect(self.settings.toggle_op5monitor_widgets)
        self.server.edited.connect(self.settings.toggle_expire_time_widgets)

    def get_shown_dialogs(self):
        """
            get list of currently show dialog windows - needed for macOS hide dock icon stuff
        """
        return [x for x in self.windows if x.isVisible()]


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


class Dialog_Settings(Dialog):
    """
        class for settings dialog
    """

    # signal to be fired if OK button was clicked and new setting are applied
    changed = Signal()

    # send signal if check for new version is wanted
    check_for_new_version = Signal(bool, QWidget)

    # used to tell debug loop it should start
    start_debug_loop = Signal()

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)
        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in list
        self.TOGGLE_DEPS = {
            # debug mode
            self.window.input_checkbox_debug_mode: [self.window.input_checkbox_debug_to_file,
                                                    self.window.input_lineedit_debug_file],
            # regular expressions for filtering hosts
            self.window.input_checkbox_re_host_enabled: [self.window.input_lineedit_re_host_pattern,
                                                         self.window.input_checkbox_re_host_reverse],
            # regular expressions for filtering services
            self.window.input_checkbox_re_service_enabled: [self.window.input_lineedit_re_service_pattern,
                                                            self.window.input_checkbox_re_service_reverse],
            # regular expressions for filtering status information
            self.window.input_checkbox_re_status_information_enabled: [
                self.window.input_lineedit_re_status_information_pattern,
                self.window.input_checkbox_re_status_information_reverse],
            # regular expressions for filtering duration
            self.window.input_checkbox_re_duration_enabled: [self.window.input_lineedit_re_duration_pattern,
                                                             self.window.input_checkbox_re_duration_reverse],
            # regular expressions for filtering duration
            self.window.input_checkbox_re_attempt_enabled: [self.window.input_lineedit_re_attempt_pattern,
                                                            self.window.input_checkbox_re_attempt_reverse],
            # regular expressions for filtering groups
            self.window.input_checkbox_re_groups_enabled: [self.window.input_lineedit_re_groups_pattern,
                                                           self.window.input_checkbox_re_groups_reverse],
            # offset for statuswindow when using systray
            self.window.input_radiobutton_icon_in_systray: [self.window.input_checkbox_systray_offset_use],
            self.window.input_checkbox_systray_offset_use: [self.window.input_spinbox_systray_offset,
                                                            self.window.label_offset_statuswindow],
            # display to use in fullscreen mode
            self.window.input_radiobutton_fullscreen: [self.window.label_fullscreen_display,
                                                       self.window.input_combobox_fullscreen_display],
            # notifications in general
            self.window.input_checkbox_notification: [self.window.notification_groupbox],
            # sound at all
            self.window.input_checkbox_notification_sound: [self.window.notification_sounds_groupbox],
            # custom sounds
            self.window.input_radiobutton_notification_custom_sound: [self.window.notification_custom_sounds_groupbox],
            # notification actions
            self.window.input_checkbox_notification_actions: [self.window.notification_actions_groupbox],
            # several notification actions depending on status
            self.window.input_checkbox_notification_action_warning: [
                self.window.input_lineedit_notification_action_warning_string],
            self.window.input_checkbox_notification_action_critical: [
                self.window.input_lineedit_notification_action_critical_string],
            self.window.input_checkbox_notification_action_down: [
                self.window.input_lineedit_notification_action_down_string],
            self.window.input_checkbox_notification_action_ok: [
                self.window.input_lineedit_notification_action_ok_string],
            # single custom notification action
            self.window.input_checkbox_notification_custom_action: [self.window.notification_custom_action_groupbox],
            # use event separator or not
            self.window.input_checkbox_notification_custom_action_single: [
                self.window.label_notification_custom_action_separator,
                self.window.input_lineedit_notification_custom_action_separator],
            # customized color alternation
            self.window.input_checkbox_show_grid: [self.window.input_checkbox_grid_use_custom_intensity],
            self.window.input_checkbox_grid_use_custom_intensity: [self.window.input_slider_grid_alternation_intensity,
                                                                   self.window.label_intensity_information_0,
                                                                   self.window.label_intensity_information_1,
                                                                   self.window.label_intensity_warning_0,
                                                                   self.window.label_intensity_warning_1,
                                                                   self.window.label_intensity_average_0,
                                                                   self.window.label_intensity_average_1,
                                                                   self.window.label_intensity_high_0,
                                                                   self.window.label_intensity_high_1,
                                                                   self.window.label_intensity_critical_0,
                                                                   self.window.label_intensity_critical_1,
                                                                   self.window.label_intensity_disaster_0,
                                                                   self.window.label_intensity_disaster_1,
                                                                   self.window.label_intensity_down_0,
                                                                   self.window.label_intensity_down_1,
                                                                   self.window.label_intensity_unreachable_0,
                                                                   self.window.label_intensity_unreachable_1,
                                                                   self.window.label_intensity_unknown_0,
                                                                   self.window.label_intensity_unknown_1],
            self.window.input_radiobutton_use_custom_browser: [self.window.groupbox_custom_browser,
                                                               self.window.input_lineedit_custom_browser,
                                                               self.window.button_choose_browser]}

        self.TOGGLE_DEPS_INVERTED = [self.window.input_checkbox_notification_custom_action_single]

        # because this makes only sense in macOS these dependencies will be added here
        if OS == OS_MACOS:
            # offer option to hide icon in dock on macOS
            self.TOGGLE_DEPS.update({
                self.window.input_radiobutton_icon_in_systray: [self.window.input_checkbox_hide_macos_dock_icon]})

        # show option to enable position fix only on Unices
        if not OS in OS_NON_LINUX:
            self.window.input_checkbox_enable_position_fix.show()
        else:
            self.window.input_checkbox_enable_position_fix.hide()

        # set title to current version
        self.window.setWindowTitle(' '.join((AppInfo.NAME, AppInfo.VERSION)))

        # connect server buttons to server dialog
        self.window.button_new_server.clicked.connect(self.new_server)
        self.window.button_edit_server.clicked.connect(self.edit_server)
        self.window.button_copy_server.clicked.connect(self.copy_server)
        self.window.button_delete_server.clicked.connect(self.delete_server)

        # double click on server to edit
        self.window.list_servers.doubleClicked.connect(self.edit_server)

        # connect check-for-updates button to update check
        # self.window.button_check_for_new_version_now.clicked.connect(check_version.check)
        self.window.button_check_for_new_version_now.clicked.connect(self.button_check_for_new_version_clicked)
        self.check_for_new_version.connect(check_version.check)

        # avoid offset spinbox if offset is not enabled
        self.window.input_radiobutton_windowed.clicked.connect(self.toggle_systray_icon_offset)
        self.window.input_radiobutton_fullscreen.clicked.connect(self.toggle_systray_icon_offset)
        self.window.input_radiobutton_icon_in_systray.clicked.connect(self.toggle_systray_icon_offset)
        self.window.input_radiobutton_statusbar_floating.clicked.connect(self.toggle_systray_icon_offset)

        # connect font chooser button to font choosing dialog
        self.window.button_fontchooser.clicked.connect(self.font_chooser)
        # connect revert-to-default-font button
        self.window.button_default_font.clicked.connect(self.font_default)
        # store font as default
        self.font = FONT
        # show current font in label_font
        self.window.label_font.setFont(FONT)

        # connect action buttons to action dialog
        self.window.button_new_action.clicked.connect(self.new_action)
        self.window.button_edit_action.clicked.connect(self.edit_action)
        self.window.button_copy_action.clicked.connect(self.copy_action)
        self.window.button_delete_action.clicked.connect(self.delete_action)

        # double click on action to edit
        self.window.list_actions.doubleClicked.connect(self.edit_action)

        # connect custom sound file buttons
        self.window.button_choose_warning.clicked.connect(self.choose_sound_file_warning)
        self.window.button_choose_critical.clicked.connect(self.choose_sound_file_critical)
        self.window.button_choose_down.clicked.connect(self.choose_sound_file_down)

        # connect custom sound file buttons
        self.window.button_play_warning.clicked.connect(self.play_sound_file_warning)
        self.window.button_play_critical.clicked.connect(self.play_sound_file_critical)
        self.window.button_play_down.clicked.connect(self.play_sound_file_down)

        # only show desktop notification on systems that support it
        if not dbus_connection.connected:
            self.window.input_checkbox_notification_desktop.hide()

        # set folder and play symbols to choose and play buttons
        self.window.button_choose_warning.setText('')
        self.window.button_choose_warning.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.button_play_warning.setText('')
        self.window.button_play_warning.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        self.window.button_choose_critical.setText('')
        self.window.button_choose_critical.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.button_play_critical.setText('')
        self.window.button_play_critical.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        self.window.button_choose_down.setText('')
        self.window.button_choose_down.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.button_play_down.setText('')
        self.window.button_play_down.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        # set browser file chooser icon and current custom browser path
        self.window.button_choose_browser.setText('')
        self.window.button_choose_browser.setIcon(
            self.window.button_play_warning.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.window.input_lineedit_custom_browser.setText(conf.custom_browser)
        # connect choose browser button with file dialog
        self.window.button_choose_browser.clicked.connect(self.choose_browser_executable)

        # QSignalMapper needed to connect all color buttons to color dialogs
        self.signalmapper_colors = QSignalMapper()

        # connect color buttons with color dialog
        for widget in [x for x in self.window.__dict__ if x.startswith('input_button_color_')]:
            button = self.window.__dict__[widget]
            item = widget.split('input_button_color_')[1]
            # multiplex slot for open color dialog by signal-mapping
            self.signalmapper_colors.setMapping(button, item)
            button.clicked.connect(self.signalmapper_colors.map)

        # connect reset and defaults buttons
        self.window.button_colors_reset.clicked.connect(self.paint_colors)
        self.window.button_colors_reset.clicked.connect(self.paint_color_alternation)
        self.window.button_colors_reset.clicked.connect(self.change_color_alternation_by_value)
        self.window.button_colors_defaults.clicked.connect(self.colors_defaults)
        self.window.button_colors_defaults.clicked.connect(self.paint_color_alternation)
        self.window.button_colors_defaults.clicked.connect(self.change_color_alternation_by_value)

        # paint alternating colors when example is wanted for customized intensity
        self.window.input_checkbox_grid_use_custom_intensity.clicked.connect(self.paint_color_alternation)
        self.window.input_checkbox_grid_use_custom_intensity.clicked.connect(self.change_color_alternation_by_value)
        self.window.input_checkbox_grid_use_custom_intensity.clicked.connect(self.toggle_zabbix_widgets)

        # finally map signals with .sender() - [<type>] is important!
        self.signalmapper_colors.mappedString[str].connect(self.color_chooser)

        # connect slider to alternating colors
        self.window.input_slider_grid_alternation_intensity.valueChanged.connect(self.change_color_alternation)

        # apply toggle-dependencies between checkboxes and certain widgets
        self.toggle_toggles()

        # workaround to avoid gigantic settings dialog
        # list of Zabbix-related widgets, only to be shown if there is a Zabbix monitor server configured
        self.ZABBIX_WIDGETS = [self.window.input_checkbox_filter_all_average_services,
                               self.window.input_checkbox_filter_all_disaster_services,
                               self.window.input_checkbox_filter_all_high_services,
                               self.window.input_checkbox_filter_all_information_services,
                               self.window.input_checkbox_notify_if_average,
                               self.window.input_checkbox_notify_if_disaster,
                               self.window.input_checkbox_notify_if_high,
                               self.window.input_checkbox_notify_if_information,
                               self.window.input_button_color_average_text,
                               self.window.input_button_color_average_background,
                               self.window.input_button_color_disaster_text,
                               self.window.input_button_color_disaster_background,
                               self.window.input_button_color_high_text,
                               self.window.input_button_color_high_background,
                               self.window.input_button_color_information_text,
                               self.window.input_button_color_information_background,
                               self.window.label_color_average,
                               self.window.label_color_disaster,
                               self.window.label_color_high,
                               self.window.label_color_information]

        # Labes for customized color intensity
        self.ZABBIX_COLOR_INTENSITY_LABELS = [self.window.label_intensity_average_0,
                                              self.window.label_intensity_average_1,
                                              self.window.label_intensity_disaster_0,
                                              self.window.label_intensity_disaster_1,
                                              self.window.label_intensity_high_0,
                                              self.window.label_intensity_high_1,
                                              self.window.label_intensity_information_0,
                                              self.window.label_intensity_information_1]

        # the next workaround...
        self.OP5MONITOR_WIDGETS = [self.window.input_checkbox_re_groups_enabled,
                                   self.window.input_lineedit_re_groups_pattern,
                                   self.window.input_checkbox_re_groups_reverse]

        # ...and another...
        self.EXPIRE_TIME_WIDGETS = [self.window.input_checkbox_defaults_acknowledge_expire,
                                    self.window.label_expire_in,
                                    self.window.label_expire_in_hours,
                                    self.window.label_expire_in_minutes,
                                    self.window.input_spinbox_defaults_acknowledge_expire_duration_hours,
                                    self.window.input_spinbox_defaults_acknowledge_expire_duration_minutes]

    def initialize(self):
        # apply configuration values
        # start with servers tab
        self.window.tabs.setCurrentIndex(0)
        for widget in dir(self.window):
            if widget.startswith('input_'):
                if widget.startswith('input_checkbox_'):
                    if conf.__dict__[widget.split('input_checkbox_')[1]] is True:
                        self.window.__dict__[widget].toggle()
                elif widget.startswith('input_radiobutton_'):
                    if conf.__dict__[widget.split('input_radiobutton_')[1]] is True:
                        self.window.__dict__[widget].toggle()
                elif widget.startswith('input_lineedit_'):
                    # older versions of Nagstamon have a bool value for custom_action_separator
                    # which leads to a crash here - thus str() to solve this
                    self.window.__dict__[widget].setText(str(conf.__dict__[widget.split('input_lineedit_')[1]]))
                elif widget.startswith('input_spinbox_'):
                    self.window.__dict__[widget].setValue(int(conf.__dict__[widget.split('input_spinbox_')[1]]))
                elif widget.startswith('input_slider_'):
                    self.window.__dict__[widget].setValue(int(conf.__dict__[widget.split('input_slider_')[1]]))
            # bruteforce size smallification, lazy try/except variant
            try:
                self.window.__dict__[widget].adjustSize()
            except:
                pass
        # fill default order fields combobox with s names
        # kick out empty headers for hosts and services flags
        sort_fields = copy.copy(HEADERS_HEADERS)
        while '' in sort_fields:
            sort_fields.remove('')

        self.window.input_combobox_default_sort_field.addItems(sort_fields)
        # catch exception which will occur when older settings are used which have real header names as values
        try:
            self.window.input_combobox_default_sort_field.setCurrentText(HEADERS_KEYS_HEADERS[conf.default_sort_field])
        except Exception:
            self.window.input_combobox_default_sort_field.setCurrentText(conf.default_sort_field)

        # fill default sort order combobox
        self.window.input_combobox_default_sort_order.addItems(['Ascending', 'Descending'])
        # .title() to get upper first letter
        self.window.input_combobox_default_sort_order.setCurrentText(conf.default_sort_order.title())

        # fill combobox with screens for fullscreen
        for screen in APP.screens():
            self.window.input_combobox_fullscreen_display.addItem(str(screen.name()))
        self.window.input_combobox_fullscreen_display.setCurrentText(str(conf.fullscreen_display))

        # fill servers listwidget with servers
        self.fill_list(self.window.list_servers, conf.servers)

        # select first item
        self.window.list_servers.setCurrentRow(0)

        # fill actions listwidget with actions
        self.fill_list(self.window.list_actions, conf.actions)

        # select first item
        self.window.list_actions.setCurrentRow(0)

        # paint colors onto color selection buttons and alternation example
        self.paint_colors()
        self.paint_color_alternation()
        self.change_color_alternation(conf.grid_alternation_intensity)

        # hide keyring setting if keyring is not available
        if KEYRING:
            self.window.input_checkbox_use_system_keyring.show()
        else:
            self.window.input_checkbox_use_system_keyring.hide()

        # hide 'Hide macOS Dock icon' if not on macOS
        if OS != OS_MACOS:
            self.window.input_checkbox_hide_macos_dock_icon.hide()

        # avoid showing offset setting if not icon in systray is configured
        if not OS in OS_NON_LINUX and not conf.icon_in_systray:
            self.toggle_systray_icon_offset()

        # important final size adjustment
        self.window.adjustSize()

    def show(self, tab=0):
        # hide them and thus be able to fix size if no extra Zabbix/Op5Monitor/IcingaWeb2 widgets are shown
        self.toggle_zabbix_widgets()
        self.toggle_op5monitor_widgets()
        self.toggle_expire_time_widgets()

        # small workaround for timestamp trick to avoid flickering
        # if the 'Settings' button was clicked too fast the timestamp difference
        # is too short and the statuswindow will keep open
        # modifying the timestamp could help
        statuswindow.is_shown_timestamp -= 1

        # tell the world that dialog pops up
        self.show_dialog.emit()

        # jump to requested tab in settings dialog
        self.window.tabs.setCurrentIndex(tab)

        # reset window if only needs smaller screen estate
        #self.window.adjustSize()
        #self.window.exec()
        super().show()

    @Slot()
    def show_new_server(self):
        """
            opens settings and new server dialogs - used by dialogs.server_missing
        """
        # emulate button click
        self.window.button_new_server.clicked.emit()

    @Slot()
    def show_filters(self):
        """
            opens filters settings after clicking button_filters in toparea
        """
        self.show(tab=2)

    @Slot()
    def show_defaults(self):
        """
            opens default settings after clicking button in acknowledge/downtime dialog
        """
        self.show(tab=6)

    def ok(self):
        """
            what to do if OK was pressed
        """
        global FONT, ICONS_FONT, statuswindow, menu, NUMBER_OF_DISPLAY_CHANGES

        # store position of statuswindow/statusbar only if statusbar is floating
        if conf.statusbar_floating:
            statuswindow.store_position_to_conf()

        # store hash of all display settings as display_mode to decide if statuswindow has to be recreated
        display_mode = str(conf.statusbar_floating) + \
                       str(conf.icon_in_systray) + \
                       str(conf.fullscreen) + \
                       str(conf.fullscreen_display) + \
                       str(conf.windowed)

        # do all stuff necessary after OK button was clicked
        # put widget values into conf
        for widget in self.window.__dict__.values():
            if widget.objectName().startswith('input_checkbox_'):
                conf.__dict__[widget.objectName().split('input_checkbox_')[1]] = widget.isChecked()
            elif widget.objectName().startswith('input_radiobutton_'):
                conf.__dict__[widget.objectName().split('input_radiobutton_')[1]] = widget.isChecked()
            elif widget.objectName().startswith("input_lineedit_"):
                conf.__dict__[widget.objectName().split('input_lineedit_')[1]] = widget.text()
            elif widget.objectName().startswith('input_spinbox_'):
                conf.__dict__[widget.objectName().split('input_spinbox_')[1]] = str(widget.value())
            elif widget.objectName().startswith('input_slider_'):
                conf.__dict__[widget.objectName().split('input_slider_')[1]] = str(widget.value())
            elif widget.objectName().startswith('input_combobox_'):
                conf.__dict__[widget.objectName().split('input_combobox_')[1]] = widget.currentText()
            elif widget.objectName().startswith('input_button_color_'):
                # get color value from color button stylesheet
                color = self.window.__dict__[widget.objectName()].styleSheet()
                color = color.split(':')[1].strip().split(';')[0]
                conf.__dict__[widget.objectName().split('input_button_')[1]] = color

        # convert some strings to integers and bools
        for item in conf.__dict__:
            if type(conf.__dict__[item]) == str:
                # when item is not one of those which always have to be strings then it might be OK to convert it
                if not item in CONFIG_STRINGS:
                    if conf.__dict__[item] in BOOLPOOL:
                        conf.__dict__[item] = BOOLPOOL[conf.__dict__[item]]
                    elif conf.__dict__[item].isdecimal():
                        conf.__dict__[item] = int(conf.__dict__[item])

        # start debug loop if debugging is enabled
        if conf.debug_mode:
            # only start debugging loop if it not already loops
            if statuswindow.worker.debug_loop_looping is False:
                self.start_debug_loop.emit()
        else:
            # set flag to tell debug loop it should stop please
            statuswindow.worker.debug_loop_looping = False

        # convert sorting fields to simple keys - maybe one day translated
        conf.default_sort_field = HEADERS_HEADERS_KEYS[conf.default_sort_field]

        # apply font
        conf.font = self.font.toString()
        # update global font and icons font
        FONT = self.font
        ICONS_FONT = QFont('Nagstamon', FONT.pointSize() + 2, QFont.Weight.Normal, False)

        # update brushes for treeview
        create_brushes()

        # save configuration
        conf.SaveConfig()

        # when display mode was changed its the easiest to destroy the old status window and create a new one
        # store display_mode to decide if statuswindow has to be recreated
        if display_mode != str(conf.statusbar_floating) + \
                str(conf.icon_in_systray) + \
                str(conf.fullscreen) + \
                str(conf.fullscreen_display) + \
                str(conf.windowed):

            # increase number of display changes for silly Windows-hides-statusbar-after-display-mode-change problem
            NUMBER_OF_DISPLAY_CHANGES += 1

            # stop statuswindow workers
            statuswindow.worker.running = False
            statuswindow.worker_notification.running = False

            # hide window to avoid laggy GUI - better none than laggy
            statuswindow.hide()

            # tell all treeview threads to stop
            for server_vbox in statuswindow.servers_vbox.children():
                server_vbox.table.worker.finish.emit()

            # stop statuswindow workers
            statuswindow.worker.finish.emit()
            statuswindow.worker_notification.finish.emit()

            # kick out ol' statuswindow
            statuswindow.kill()

            # create new global one
            statuswindow = StatusWindow()

            # context menu for systray and statuswindow
            menu = MenuContext()

        # tell statuswindow to refresh due to new settings
        self.changed.emit()

        # see if there are any servers created and enabled
        check_servers()

        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot()
    def cancel(self):
        """
            check if there are any usable servers configured
        """
        # call close and macOS dock icon treatment from ancestor
        super().cancel()
        check_servers()

    @Slot()
    def new_server(self):
        """
            create new server
        """
        dialogs.server.new()

    @Slot()
    def edit_server(self):
        """
            edit existing server
        """
        dialogs.server.edit()

    @Slot()
    def copy_server(self):
        """
            copy existing server
        """
        dialogs.server.copy()

    @Slot()
    def delete_server(self):
        """
            delete server, stop its thread, remove from config and list
        """
        # server to delete from current row in servers list
        server = conf.servers[self.window.list_servers.currentItem().text()]

        reply = QMessageBox.question(self.window, 'Nagstamon',
                                     f'Do you really want to delete monitor server <b>{server.name}</b>?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # in case server is enabled delete its vbox
            if server.enabled:
                for vbox in statuswindow.servers_vbox.children():
                    if vbox.server.name == server.name:
                        # stop thread by falsificate running flag
                        vbox.table.worker.running = False
                        vbox.table.worker.finish.emit()
                        break

            # kick server out of server instances
            servers.pop(server.name)
            # dito from config items
            conf.servers.pop(server.name)

            # refresh list
            # row index 0 to x
            row = self.window.list_servers.currentRow()
            # count real number, 1 to x
            count = self.window.list_servers.count()

            # if deleted row was the last line the new current row has to be the new last line, accidently the same as count
            if row == count - 1:
                # use the penultimate item as the new current one
                row = count - 2
            else:
                # go down one row
                row = row + 1

            # refresh list and mark new current row
            self.refresh_list(list_widget=self.window.list_servers,
                              list_conf=conf.servers,
                              current=self.window.list_servers.item(row).text())
            del (row, count)

        # delete server config file from disk
        conf.delete_file('servers', 'server_{0}.conf'.format(quote(server.name)))
        del server

    def refresh_list(self, list_widget, list_conf, current=''):
        """
            refresh given 'list_widget' from given 'list_conf' and mark 'current' as current
        """
        # clear list of servers
        list_widget.clear()
        # fill servers listwidget with servers
        self.fill_list(list_widget, list_conf)
        # select current edited item
        # activate currently created/edited server monitor item by first searching it in the list
        list_widget.setCurrentItem(list_widget.findItems(current, Qt.MatchFlag.MatchExactly)[0])

    @Slot()
    def new_action(self):
        """
            create new action
        """
        dialogs.action.new()

    @Slot()
    def edit_action(self):
        """
            edit existing action
        """
        dialogs.action.edit()

    @Slot()
    def copy_action(self):
        """
            copy existing action and edit it
        """
        dialogs.action.copy()

    @Slot()
    def delete_action(self):
        """
            delete action remove from config and list
        """
        # action to delete from current row in actions list
        action = conf.actions[self.window.list_actions.currentItem().text()]

        reply = QMessageBox.question(self.window, 'Nagstamon',
                                     'Do you really want to delete action <b>{action.name}</b>?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # kick action out of config items
            conf.actions.pop(action.name)

            # refresh list
            # row index 0 to x
            row = self.window.list_actions.currentRow()
            # count real number, 1 to x
            count = self.window.list_actions.count()

            # if deleted row was the last line the new current row has to be the new last line, accidently the same as count
            if row == count - 1:
                # use the penultimate item as the new current one
                row = count - 2
            else:
                # go down one row
                row = row + 1

            # refresh list and mark new current row
            self.refresh_list(list_widget=self.window.list_actions, list_conf=conf.actions,
                              current=self.window.list_actions.item(row).text())

            del (row, count)

        # delete action config file from disk
        conf.delete_file('actions', 'action_{0}.conf'.format(quote(action.name)))
        del action

    def choose_sound_file_decoration(method):
        """
            try to decorate sound file dialog
        """

        def decoration_function(self):
            # execute decorated function
            method(self)
            # shortcut for widget to fill and revaluate
            widget = self.window.__dict__['input_lineedit_notification_custom_sound_%s' % self.sound_file_type]

            # use 2 filters, sound files and all files
            file = dialogs.file_chooser.getOpenFileName(self.window,
                                                        filter='Sound files (*.mp3 *.MP3 *.mp4 *.MP4 '
                                                               '*.wav *.WAV *.ogg *.OGG);;'
                                                               'All files (*)')[0]

            # only take filename if QFileDialog gave something useful back
            if file != '':
                widget.setText(file)

        return (decoration_function)

    @choose_sound_file_decoration
    @Slot()
    def choose_sound_file_warning(self):
        self.sound_file_type = 'warning'

    @choose_sound_file_decoration
    @Slot()
    def choose_sound_file_critical(self):
        self.sound_file_type = 'critical'

    @choose_sound_file_decoration
    @Slot()
    def choose_sound_file_down(self):
        self.sound_file_type = 'down'

    def play_sound_file_decoration(method):
        """
            try to decorate sound file dialog
        """

        def decoration_function(self):
            # execute decorated function
            method(self)
            # shortcut for widget to fill and revaluate
            widget = self.window.__dict__['input_lineedit_notification_custom_sound_%s' % self.sound_file_type]

            # get file path from widget
            file = widget.text()

            # tell mediaplayer to play file only if it exists
            if mediaplayer.set_media(file) is True:
                mediaplayer.play()

        return (decoration_function)

    @play_sound_file_decoration
    @Slot()
    def play_sound_file_warning(self):
        self.sound_file_type = 'warning'

    @play_sound_file_decoration
    @Slot()
    def play_sound_file_critical(self):
        self.sound_file_type = 'critical'

    @play_sound_file_decoration
    @Slot()
    def play_sound_file_down(self):
        self.sound_file_type = 'down'

    def paint_colors(self):
        """
            fill color selection buttons with appropriate colors
        """
        # color buttons
        for color in [x for x in conf.__dict__ if x.startswith('color_')]:
            self.window.__dict__['input_button_%s' % (color)].setStyleSheet('''background-color: %s;
                                                                           border-width: 1px;
                                                                           border-color: black;
                                                                           border-style: solid;'''
                                                                            % conf.__dict__[color])
        # example color labels
        for label in [x for x in self.window.__dict__ if x.startswith('label_color_')]:
            status = label.split('label_color_')[1]
            self.window.__dict__[label].setStyleSheet('color: %s; background: %s' %
                                                      (conf.__dict__['color_%s_text' % (status)],
                                                       (conf.__dict__['color_%s_background' % (status)])))

    @Slot()
    def colors_defaults(self):
        """
            apply default colors to buttons
        """
        # color buttons
        for default_color in [x for x in conf.__dict__ if x.startswith('default_color_')]:
            # cut 'default_' off to get color
            color = default_color.split('default_')[1]
            self.window.__dict__['input_button_%s' % (color)].setStyleSheet('''background-color: %s;
                                                                           border-width: 1px;
                                                                           border-color: black;
                                                                           border-style: solid;'''
                                                                            % conf.__dict__[default_color])
        # example color labels
        for label in [x for x in self.window.__dict__ if x.startswith('label_color_')]:
            status = label.split('label_color_')[1]

            # get color values from color button stylesheets
            color_text = self.window.__dict__['input_button_color_' + status + '_text'].styleSheet()
            color_text = color_text.split(':')[1].strip().split(';')[0]
            color_background = self.window.__dict__['input_button_color_' + status + '_background'].styleSheet()
            color_background = color_background.split(':')[1].strip().split(';')[0]

            # apply color values from stylesheet to label
            self.window.__dict__[label].setStyleSheet('color: %s; background: %s' %
                                                      (color_text, color_background))

    @Slot(str)
    def color_chooser(self, item):
        """
            open QColorDialog to choose a color and change it in settings dialog
        """
        color = conf.__dict__['color_%s' % (item)]

        new_color = QColorDialog.getColor(QColor(color), parent=self.window)
        # if canceled the color is invalid
        if new_color.isValid():
            self.window.__dict__['input_button_color_%s' % (item)].setStyleSheet('''background-color: %s;
                                                                                border-width: 1px;
                                                                                border-color: black;
                                                                                border-style: solid;'''
                                                                                 % new_color.name())
            status = item.split('_')[0]
            # get color value from stylesheet to paint example
            text = self.window.__dict__['input_button_color_%s_text' % (status)].styleSheet()
            text = text.split(':')[1].strip().split(';')[0]
            background = self.window.__dict__['input_button_color_%s_background' % (status)].styleSheet()
            background = background.split(':')[1].strip().split(';')[0]
            # set example color
            self.window.__dict__['label_color_%s' % (status)].setStyleSheet('''color: {0};
                                                                           background: {1}
                                                                        '''.format(text, background))
            # update alternation colors
            self.paint_color_alternation()
            self.change_color_alternation(self.window.input_slider_grid_alternation_intensity.value())

    def paint_color_alternation(self):
        """
            paint the intensity example color labels taking actual colors from color
            chooser buttons
            this labels have the color of alteration level 0 aka default
        """
        for state in COLORS:
            # get text color from button CSS
            text = self.window.__dict__['input_button_color_{0}_text'
            .format(state.lower())] \
                .styleSheet() \
                .split(';\n')[0].split(': ')[1]
            # get background color from button CSS
            background = self.window.__dict__['input_button_color_{0}_background'
            .format(state.lower())] \
                .styleSheet() \
                .split(';\n')[0].split(': ')[1]
            # set CSS
            self.window.__dict__['label_intensity_{0}_0'.format(state.lower())] \
                .setStyleSheet('''color: {0};
                                              background-color: {1};
                                              padding-top: 3px;
                                              padding-bottom: 3px;
                                              '''.format(text, background))

    @Slot(int)
    def change_color_alternation(self, value):
        """
            fill alternation level 1 labels with altered color
            derived from level 0 labels aka default
        """
        for state in COLORS:
            # only evaluate colors if there is any stylesheet
            if len(self.window.__dict__['input_button_color_{0}_text'
                    .format(state.lower())] \
                           .styleSheet()) > 0:

                # access both labels
                label_0 = self.window.__dict__['label_intensity_{0}_0'.format(state.lower())]
                label_1 = self.window.__dict__['label_intensity_{0}_1'.format(state.lower())]

                # get text color from text color chooser button
                text = self.window.__dict__['input_button_color_{0}_text'
                .format(state.lower())] \
                    .styleSheet() \
                    .split(';\n')[0].split(': ')[1]

                # get background of level 0 label
                background = label_0.palette().color(QPalette.ColorRole.Window)
                r, g, b, a = background.getRgb()

                # if label background is too dark lighten the color instead of darken it mor
                if background.lightness() < 30:
                    if value > 5:
                        r += 30
                        g += 30
                        b += 30
                    r = round(r / 100 * (100 + value))
                    g = round(g / 100 * (100 + value))
                    b = round(b / 100 * (100 + value))
                else:
                    r = round(r / 100 * (100 - value))
                    g = round(g / 100 * (100 - value))
                    b = round(b / 100 * (100 - value))

                # finally apply new background color
                # easier with style sheets than with QPalette/QColor
                label_1.setStyleSheet('''color: {0};
                                         background-color: rgb({1}, {2}, {3});
                                         padding-top: 3px;
                                         padding-bottom: 3px;
                                      '''.format(text, r, g, b))

    @Slot()
    def change_color_alternation_by_value(self):
        """
            to be fired up when colors are reset
        """
        self.change_color_alternation(self.window.input_slider_grid_alternation_intensity.value())

    @Slot()
    def font_chooser(self):
        """
            use font dialog to choose a font
        """
        self.font = QFontDialog.getFont(self.font, parent=self.window)[0]
        self.window.label_font.setFont(self.font)

    @Slot()
    def font_default(self):
        """
            reset font to default font which was valid when Nagstamon was launched
        """
        self.window.label_font.setFont(DEFAULT_FONT)
        self.font = DEFAULT_FONT

    @Slot()
    def button_check_for_new_version_clicked(self):
        """
            at this point start_mode for version check is definitively False
        """
        self.check_for_new_version.emit(False, self.window)

    @Slot()
    def choose_browser_executable(self):
        """
            show dialog for selection of non-default browser
        """
        # present dialog with OS-specific sensible defaults
        if OS == OS_WINDOWS:
            filter = 'Executables (*.exe *.EXE);; All files (*)'
            directory = os.environ['ProgramFiles']
        elif OS == OS_MACOS:
            filter = ''
            directory = '/Applications'
        else:
            filter = ''
            directory = '/usr/bin'

        file = dialogs.file_chooser.getOpenFileName(self.window,
                                                    directory=directory,
                                                    filter=filter)[0]

        # only take filename if QFileDialog gave something useful back
        if file != '':
            self.window.input_lineedit_custom_browser.setText(file)

    @Slot()
    def toggle_zabbix_widgets(self):
        """
            Depending on the existence of an enabled Zabbix monitor the Zabbix widgets are shown or hidden
        """
        use_zabbix = False
        for server in servers.values():
            if server.enabled:
                if server.type.startswith('Zabbix'):
                    use_zabbix = True
                    break
        # remove extra Zabbix options
        if use_zabbix:
            for widget in self.ZABBIX_WIDGETS:
                widget.show()
        else:
            for widget in self.ZABBIX_WIDGETS:
                widget.hide()
        # remove custom color intensity labels
        if use_zabbix and self.window.input_checkbox_grid_use_custom_intensity.isChecked():
            for widget in self.ZABBIX_COLOR_INTENSITY_LABELS:
                widget.show()
        else:
            for widget in self.ZABBIX_COLOR_INTENSITY_LABELS:
                widget.hide()

    @Slot()
    def toggle_op5monitor_widgets(self):
        """
            Depending on the existence of an enabled Op5Monitor monitor the Op5Monitor widgets are shown or hidden
        """
        use_op5monitor = False
        for server in servers.values():
            if server.enabled:
                if server.type == 'op5Monitor':
                    use_op5monitor = True
                    break
        if use_op5monitor:
            for widget in self.OP5MONITOR_WIDGETS:
                widget.show()
        else:
            for widget in self.OP5MONITOR_WIDGETS:
                widget.hide()

    @Slot()
    def toggle_expire_time_widgets(self):
        """
            Depending on the existence of an enabled IcingaWeb2 or Alertmanager monitor the expire_time widgets are shown or hidden
        """
        use_expire_time = False
        for server in servers.values():
            if server.enabled:
                if server.type in ['IcingaWeb2', 'Alertmanager']:
                    use_expire_time = True
                    break
        if use_expire_time:
            for widget in self.EXPIRE_TIME_WIDGETS:
                widget.show()
        else:
            for widget in self.EXPIRE_TIME_WIDGETS:
                widget.hide()

    @Slot()
    def toggle_systray_icon_offset(self):
        """
            Only show offset spinbox when offset is enabled
        """
        if self.window.input_checkbox_systray_offset_use.isVisible():
            if self.window.input_checkbox_systray_offset_use.isChecked():
                self.window.input_spinbox_systray_offset.show()
                self.window.label_offset_statuswindow.show()
            else:
                self.window.input_spinbox_systray_offset.hide()
                self.window.label_offset_statuswindow.hide()
        else:
            self.window.input_spinbox_systray_offset.hide()
            self.window.label_offset_statuswindow.hide()


class Dialog_Server(Dialog):
    """
        Dialog used to setup one single server
    """

    # tell server has been edited
    edited = Signal()

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)
        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in list
        self.TOGGLE_DEPS = {
            self.window.input_checkbox_use_autologin: [self.window.label_autologin_key,
                                                       self.window.input_lineedit_autologin_key],
            self.window.input_checkbox_use_proxy: [self.window.groupbox_proxy],

            self.window.input_checkbox_use_proxy_from_os: [self.window.label_proxy_address,
                                                           self.window.input_lineedit_proxy_address,
                                                           self.window.label_proxy_username,
                                                           self.window.input_lineedit_proxy_username,
                                                           self.window.label_proxy_password,
                                                           self.window.input_lineedit_proxy_password],
            self.window.input_checkbox_show_options: [self.window.groupbox_options],
            self.window.input_checkbox_custom_cert_use: [self.window.label_custom_ca_file,
                                                         self.window.input_lineedit_custom_cert_ca_file,
                                                         self.window.button_choose_custom_cert_ca_file]}

        self.TOGGLE_DEPS_INVERTED = [self.window.input_checkbox_use_proxy_from_os]

        # these widgets are shown or hidden depending on server type properties
        # the servers listed at each widget do need them
        self.VOLATILE_WIDGETS = {
            self.window.label_monitor_cgi_url: ['Nagios', 'Icinga', 'Thruk', 'Sensu', 'SensuGo'],
            self.window.input_lineedit_monitor_cgi_url: ['Nagios', 'Icinga', 'Thruk', 'Sensu', 'SensuGo'],
            self.window.input_checkbox_use_autologin: ['Centreon', 'monitos4x', 'Thruk'],
            self.window.input_lineedit_autologin_key: ['Centreon', 'monitos4x', 'Thruk'],
            self.window.label_autologin_key: ['Centreon', 'monitos4x', 'Thruk'],
            self.window.input_checkbox_no_cookie_auth: ['IcingaWeb2', 'Sensu'],
            self.window.input_checkbox_use_display_name_host: ['Icinga', 'IcingaWeb2'],
            self.window.input_checkbox_use_display_name_service: ['Icinga', 'IcingaWeb2', 'Thruk'],
            self.window.input_checkbox_use_description_name_service: ['Zabbix'],
            self.window.input_checkbox_force_authuser: ['Checkmk Multisite'],
            self.window.groupbox_checkmk_views: ['Checkmk Multisite'],
            self.window.input_lineedit_host_filter: ['op5Monitor'],
            self.window.input_lineedit_service_filter: ['op5Monitor'],
            self.window.label_service_filter: ['op5Monitor'],
            self.window.label_host_filter: ['op5Monitor'],
            self.window.input_lineedit_hashtag_filter: ['Opsview'],
            self.window.label_hashtag_filter: ['Opsview'],
            self.window.input_checkbox_can_change_only: ['Opsview'],
            self.window.label_monitor_site: ['Sensu'],
            self.window.input_lineedit_monitor_site: ['Sensu'],
            self.window.label_map_to_hostname: ['Prometheus', 'Alertmanager'],
            self.window.input_lineedit_map_to_hostname: ['Prometheus', 'Alertmanager'],
            self.window.label_map_to_servicename: ['Prometheus', 'Alertmanager'],
            self.window.input_lineedit_map_to_servicename: ['Prometheus', 'Alertmanager'],
            self.window.label_map_to_status_information: ['Prometheus', 'Alertmanager'],
            self.window.input_lineedit_map_to_status_information: ['Prometheus', 'Alertmanager'],
            self.window.label_alertmanager_filter: ['Alertmanager'],
            self.window.input_lineedit_alertmanager_filter: ['Alertmanager'],
            self.window.label_map_to_ok: ['Alertmanager'],
            self.window.input_lineedit_map_to_ok: ['Alertmanager'],
            self.window.label_map_to_unknown: ['Alertmanager'],
            self.window.input_lineedit_map_to_unknown: ['Alertmanager'],
            self.window.label_map_to_warning: ['Alertmanager'],
            self.window.input_lineedit_map_to_warning: ['Alertmanager'],
            self.window.label_map_to_critical: ['Alertmanager'],
            self.window.input_lineedit_map_to_critical: ['Alertmanager'],
            self.window.input_lineedit_notification_filter: ['IcingaDBWebNotifications'],
            self.window.label_notification_filter: ['IcingaDBWebNotifications'],
            self.window.input_lineedit_notification_lookback: ['IcingaDBWebNotifications'],
            self.window.label_notification_lookback: ['IcingaDBWebNotifications'],
        }

        # to be used when selecting authentication method Kerberos
        self.AUTHENTICATION_WIDGETS = [
            self.window.label_username,
            self.window.input_lineedit_username,
            self.window.label_password,
            self.window.input_lineedit_password,
            self.window.input_checkbox_save_password]

        self.AUTHENTICATION_BEARER_WIDGETS = [
            self.window.label_username,
            self.window.input_lineedit_username]

        self.AUTHENTICATION_ECP_WIDGETS = [
            self.window.label_idp_ecp_endpoint,
            self.window.input_lineedit_idp_ecp_endpoint]

        # fill default order fields combobox with monitor server types
        self.window.input_combobox_type.addItems(sorted(SERVER_TYPES.keys(), key=str.lower))
        # default to Nagios as it is the mostly used monitor server
        self.window.input_combobox_type.setCurrentText('Nagios')

        # set folder and play symbols to choose and play buttons
        self.window.button_choose_custom_cert_ca_file.setText('')
        self.window.button_choose_custom_cert_ca_file.setIcon(
            self.window.button_choose_custom_cert_ca_file.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        # connect choose custom cert CA file button with file dialog
        self.window.button_choose_custom_cert_ca_file.clicked.connect(self.choose_custom_cert_ca_file)

        # fill authentication combobox
        self.window.input_combobox_authentication.addItems(['Basic', 'Digest', 'Kerberos', 'Bearer'])
        if ECP_AVAILABLE is True:
            self.window.input_combobox_authentication.addItems(['ECP'])

        # detect change of server type which leads to certain options shown or hidden
        self.window.input_combobox_type.activated.connect(self.toggle_type)

        # when authentication is changed to Kerberos then disable username/password as the are now useless
        self.window.input_combobox_authentication.activated.connect(self.toggle_authentication)

        # reset Checkmk views
        self.window.button_checkmk_view_hosts_reset.clicked.connect(self.checkmk_view_hosts_reset)
        self.window.button_checkmk_view_services_reset.clicked.connect(self.checkmk_view_services_reset)

        # mode needed for evaluate dialog after ok button pressed - defaults to 'new'
        self.mode = 'new'

    @Slot(int)
    def toggle_type(self, server_type_index=0):
        # server_type_index is not needed - we get the server type from .currentText()
        # check if server type is listed in volatile widgets to decide if it has to be shown or hidden
        for widget, server_types in self.VOLATILE_WIDGETS.items():
            if self.window.input_combobox_type.currentText() in server_types:
                widget.show()
            else:
                widget.hide()

    @Slot()
    def toggle_authentication(self):
        """
            when authentication is changed to Kerberos then disable username/password as the are now useless
        """
        if self.window.input_combobox_authentication.currentText() == 'Kerberos':
            for widget in self.AUTHENTICATION_WIDGETS:
                widget.hide()
        else:
            for widget in self.AUTHENTICATION_WIDGETS:
                widget.show()

        if self.window.input_combobox_authentication.currentText() == 'ECP':
            for widget in self.AUTHENTICATION_ECP_WIDGETS:
                widget.show()
        else:
            for widget in self.AUTHENTICATION_ECP_WIDGETS:
                widget.hide()

        # change credential input for bearer auth
        if self.window.input_combobox_authentication.currentText() == 'Bearer':
            for widget in self.AUTHENTICATION_BEARER_WIDGETS:
                widget.hide()
                self.window.label_password.setText('Token')
        else:
            for widget in self.AUTHENTICATION_BEARER_WIDGETS:
                widget.show()
                self.window.label_password.setText('Password')

        # after hiding authentication widgets dialog might shrink
        self.window.adjustSize()

    def dialog_decoration(method):
        """
            try with a decorator instead of repeated calls
        """

        # function which decorates method

        def decoration_function(self, **kwargs):
            """
                self.server_conf has to be set by decorated method
            """
            # previous server conf only useful when editing - defaults to None
            self.previous_server_conf = None

            # call decorated method
            method(self, **kwargs)

            # run through all input widgets and and apply defaults from config
            for widget in self.window.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.window.__dict__[widget].setChecked(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.window.__dict__[widget].setChecked(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.window.__dict__[widget].setCurrentText(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.window.__dict__[widget].setText(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_spinbox_'):
                        setting = widget.split('input_spinbox_')[1]
                        self.window.__dict__[widget].setValue(self.server_conf.__dict__[setting])

            # set current authentication type by using capitalized first letter via .title()
            self.window.input_combobox_authentication.setCurrentText(self.server_conf.authentication.title())

            # initially hide not needed widgets
            self.toggle_type()

            # disable unneeded authentication widgets if Kerberos is used
            self.toggle_authentication()

            # apply toggle-dependencies between checkboxes and certain widgets
            self.toggle_toggles()

            # open extra options if wanted e.g. by button_fix_tls_error
            if 'show_options' in self.__dict__:
                if self.show_options:
                    self.window.input_checkbox_show_options.setChecked(True)

            # important final size adjustment
            self.window.adjustSize()

            # if running on macOS with disabled dock icon the dock icon might have to be made visible
            # to make Nagstamon accept keyboard input
            self.show_macos_dock_icon_if_necessary()

            self.window.exec()

            # en reverse the dock icon might be hidden again after a potential keyboard input
            self.hide_macos_dock_icon_if_necessary()

        # give back decorated function
        return (decoration_function)

    @dialog_decoration
    def new(self):
        """
            create new server, set default values
        """
        self.mode = 'new'

        # create new server config object
        self.server_conf = Server()
        # window title might be pretty simple
        self.window.setWindowTitle('New server')

    @dialog_decoration
    def edit(self, server_name=None, show_options=False):
        """
            edit existing server
            when called by Edit button in ServerVBox use given server_name to get server config
        """
        self.mode = 'edit'
        # shorter server conf
        if server_name is None:
            self.server_conf = conf.servers[dialogs.settings.window.list_servers.currentItem().text()]
        else:
            self.server_conf = conf.servers[server_name]
        # store monitor name in case it will be changed
        self.previous_server_conf = deepcopy(self.server_conf)
        # set window title
        self.window.setWindowTitle('Edit %s' % (self.server_conf.name))
        # set self.show_options to give value to decorator
        self.show_options = show_options

    @dialog_decoration
    def copy(self):
        """
            copy existing server
        """
        self.mode = 'copy'
        # shorter server conf
        self.server_conf = deepcopy(conf.servers[dialogs.settings.window.list_servers.currentItem().text()])
        # set window title before name change to reflect copy
        self.window.setWindowTitle('Copy %s' % (self.server_conf.name))
        # indicate copy of other server
        self.server_conf.name = 'Copy of ' + self.server_conf.name

    def ok(self):
        """
            evaluate state of widgets to get new configuration
        """
        # global statement necessary because of reordering of servers OrderedDict
        global servers

        # strip name to avoid whitespace
        server_name = self.window.input_lineedit_name.text().strip()

        # check that no duplicate name exists
        if server_name in conf.servers and \
                (self.mode in ['new', 'copy'] or
                 self.mode == 'edit' and self.server_conf != conf.servers[server_name]):
            # cry if duplicate name exists
            QMessageBox.critical(self.window,
                        'Nagstamon',
                        f'The monitor server name <b>{server_name}</b> is already used.',
                        QMessageBox.StandardButton.Ok)
        else:
            # get configuration from UI
            for widget in self.window.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].isChecked()
                    elif widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].isChecked()
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].currentText()
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].text()
                    elif widget.startswith('input_spinbox_'):
                        setting = widget.split('input_spinbox_')[1]
                        self.server_conf.__dict__[setting] = self.window.__dict__[widget].value()

            # URLs should not end with / - clean it
            self.server_conf.monitor_url = self.server_conf.monitor_url.rstrip('/')
            self.server_conf.monitor_cgi_url = self.server_conf.monitor_cgi_url.rstrip('/')

            # convert some strings to integers and bools
            for item in self.server_conf.__dict__:
                if type(self.server_conf.__dict__[item]) == str:
                    # when item is not one of those which always have to be strings then it might be OK to convert it
                    if not item in CONFIG_STRINGS:
                        if self.server_conf.__dict__[item] in BOOLPOOL:
                            self.server_conf.__dict__[item] = BOOLPOOL[self.server_conf.__dict__[item]]
                        elif self.server_conf.__dict__[item].isdecimal():
                            self.server_conf.__dict__[item] = int(self.server_conf.__dict__[item])

            # store lowered authentication type
            self.server_conf.authentication = self.server_conf.authentication.lower()

            # edited servers will be deleted and recreated with new configuration
            if self.mode == 'edit':
                # remove old server vbox from status window if still running
                for vbox in statuswindow.servers_vbox.children():
                    if vbox.server.name == self.previous_server_conf.name:
                        # disable server
                        vbox.server.enabled = False
                        # stop thread by falsificate running flag
                        vbox.table.worker.running = False
                        vbox.table.worker.finish.emit()
                        # nothing more to do
                        break

                # delete previous name
                conf.servers.pop(self.previous_server_conf.name)

                # delete edited and now not needed server instance - if it exists
                if self.previous_server_conf.name in servers.keys():
                    servers.pop(self.previous_server_conf.name)

            # some monitor servers do not need cgi-url - reuse self.VOLATILE_WIDGETS to find out which one
            if self.server_conf.type not in self.VOLATILE_WIDGETS[self.window.input_lineedit_monitor_cgi_url]:
                self.server_conf.monitor_cgi_url = self.server_conf.monitor_url

            # add new server configuration in every case and use stripped name to avoid spaces
            self.server_conf.name = server_name
            conf.servers[server_name] = self.server_conf

            # add new server instance to global servers dict
            servers[server_name] = create_server(self.server_conf)
            if self.server_conf.enabled is True:
                servers[server_name].enabled = True
                # create vbox
                statuswindow.servers_vbox.addLayout(statuswindow.create_ServerVBox(servers[server_name]))
                # renew list of server vboxes in status window
                statuswindow.sort_ServerVBoxes()

            # reorder servers in dict to reflect changes
            servers_freshly_sorted = sorted(servers.items())
            servers.clear()
            servers.update(servers_freshly_sorted)
            del (servers_freshly_sorted)

            # refresh list of servers, give call the current server name to highlight it
            dialogs.settings.refresh_list(list_widget=dialogs.settings.window.list_servers,
                                          list_conf=conf.servers,
                                          current=self.server_conf.name)

            # tell main window about changes (Zabbix, Opsview for example)
            self.edited.emit()

            # delete old server .conf file to reflect name changes
            # new one will be written soon
            if self.previous_server_conf is not None:
                conf.delete_file('servers', 'server_{0}.conf'.format(quote(self.previous_server_conf.name)))

            # store server settings
            conf.SaveMultipleConfig('servers', 'server')

        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot()
    def choose_custom_cert_ca_file(self):
        """
            show dialog for selection of non-default browser
        """
        filter = 'All files (*)'
        file = dialogs.file_chooser.getOpenFileName(self.window,
                                                    directory=os.path.expanduser('~'),
                                                    filter=filter)[0]

        # only take filename if QFileDialog gave something useful back
        if file != '':
            self.window.input_lineedit_custom_cert_ca_file.setText(file)

    @Slot()
    def checkmk_view_hosts_reset(self):
        self.window.input_lineedit_checkmk_view_hosts.setText('nagstamon_hosts')

    @Slot()
    def checkmk_view_services_reset(self):
        self.window.input_lineedit_checkmk_view_services.setText('nagstamon_svc')


class Dialog_Action(Dialog):
    """
        Dialog used to setup one single action
    """

    # mapping between action types and combobox content
    ACTION_TYPES = {'browser': 'Browser',
                    'command': 'Command',
                    'url': 'URL'}

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)

        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in list
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

    def dialog_decoration(method):
        """
            try with a decorator instead of repeated calls
        """

        # function which decorates method

        def decoration_function(self):
            """
                self.server_conf has to be set by decorated method
            """

            # previous action conf only useful when editing - defaults to None
            self.previous_action_conf = None

            # call decorated method
            method(self)

            # run through all input widgets and and apply defaults from config
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

            # if running on macOS with disabled dock icon the dock icon might have to be made visible
            # to make Nagstamon accept keyboard input
            self.show_macos_dock_icon_if_necessary()

            self.window.exec()

            # en reverse the dock icon might be hidden again after a potential keyboard input
            self.hide_macos_dock_icon_if_necessary()

        # give back decorated function
        return (decoration_function)

    @dialog_decoration
    def new(self):
        """
            create new server
        """
        self.mode = 'new'

        # create new server config object
        self.action_conf = Action()
        # window title might be pretty simple
        self.window.setWindowTitle('New action')

    @dialog_decoration
    def edit(self):
        """
            edit existing action
        """
        self.mode = 'edit'
        # shorter action conf
        self.action_conf = conf.actions[dialogs.settings.window.list_actions.currentItem().text()]
        # store action name in case it will be changed
        self.previous_action_conf = deepcopy(self.action_conf)
        # set window title
        self.window.setWindowTitle('Edit %s' % (self.action_conf.name))

    @dialog_decoration
    def copy(self):
        """
            copy existing action
        """
        self.mode = 'copy'
        # shorter action conf
        self.action_conf = deepcopy(conf.actions[dialogs.settings.window.list_actions.currentItem().text()])
        # set window title before name change to reflect copy
        self.window.setWindowTitle('Copy %s' % (self.action_conf.name))
        # indicate copy of other action
        self.action_conf.name = 'Copy of ' + self.action_conf.name

    def ok(self):
        """
            evaluate state of widgets to get new configuration
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

            # Avoid wrong monitor type which blocks display of action
            if self.action_conf.monitor_type not in SERVER_TYPES:
                self.action_conf.monitor_type = ''

            # lower type to recognize action type on monitor
            self.action_conf.type = self.action_conf.type.lower()

            # add edited  or new/copied action
            conf.actions[self.action_conf.name] = self.action_conf

            # refresh list of actions, give call the current action name to highlight it
            dialogs.settings.refresh_list(list_widget=dialogs.settings.window.list_actions,
                                          list_conf=conf.actions,
                                          current=self.action_conf.name)

            # delete old action .conf file to reflect name changes
            # new one will be written soon
            if self.previous_action_conf is not None:
                conf.delete_file('actions', 'action_{0}.conf'.format(quote(self.previous_action_conf.name)))

            # store server settings
            conf.SaveMultipleConfig('actions', 'action')

        # call close and macOS dock icon treatment from ancestor
        super().ok()


class Dialog_Acknowledge(Dialog):
    """
        Dialog for acknowledging host/service problems
    """

    # store host and service to be used for OK button evaluation
    server = None
    host_list = service_list = []

    # tell worker to acknowledge some troublesome item
    acknowledge = Signal(dict)

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)

        self.TOGGLE_DEPS = {
            self.window.input_checkbox_use_expire_time: [self.window.input_datetime_expire_time]
        }

        # still clumsy but better than negating the other server types
        PROMETHEUS_OR_ALERTMANAGER = ['Alertmanager',
                                      'Prometheus']
        NOT_PROMETHEUS_OR_ALERTMANAGER = [x.TYPE for x in SERVER_TYPES.values() if
                                          x.TYPE not in PROMETHEUS_OR_ALERTMANAGER]

        self.VOLATILE_WIDGETS = {
            self.window.input_checkbox_use_expire_time: ['IcingaWeb2'],
            self.window.input_datetime_expire_time: ['IcingaWeb2', 'Alertmanager'],
            self.window.input_checkbox_sticky_acknowledgement: NOT_PROMETHEUS_OR_ALERTMANAGER,
            self.window.input_checkbox_send_notification: NOT_PROMETHEUS_OR_ALERTMANAGER,
            self.window.input_checkbox_persistent_comment: NOT_PROMETHEUS_OR_ALERTMANAGER,
            self.window.input_checkbox_acknowledge_all_services: NOT_PROMETHEUS_OR_ALERTMANAGER
        }

        self.FORCE_DATETIME_EXPIRE_TIME = ['Alertmanager']

    def initialize(self, server=None, host=[], service=[]):
        # store server, host and service to be used for OK button evaluation
        self.server = server
        self.host_list = host
        self.service_list = service

        self.window.setWindowTitle('Acknowledge hosts and services')
        str = ''

        for i in range(len(self.host_list)):
            if self.service_list[i] == "":
                str = str + 'Host <b>%s</b><br>' % (self.host_list[i])
            else:
                str = str + 'Service <b>%s</b> on host <b>%s</b><br>' % (self.service_list[i], self.host_list[i])

        self.window.input_label_description.setText(str)

        # default flags of monitor acknowledgement
        self.window.input_checkbox_sticky_acknowledgement.setChecked(conf.defaults_acknowledge_sticky)
        self.window.input_checkbox_send_notification.setChecked(conf.defaults_acknowledge_send_notification)
        self.window.input_checkbox_persistent_comment.setChecked(conf.defaults_acknowledge_persistent_comment)
        self.window.input_checkbox_use_expire_time.setChecked(conf.defaults_acknowledge_expire)
        if len(self.host_list) == 1:
            self.window.input_checkbox_acknowledge_all_services.setChecked(conf.defaults_acknowledge_all_services)
            self.window.input_checkbox_acknowledge_all_services.show()
        else:
            self.window.input_checkbox_acknowledge_all_services.setChecked(False)
            self.window.input_checkbox_acknowledge_all_services.hide()

        # default author + comment
        self.window.input_lineedit_comment.setText(conf.defaults_acknowledge_comment)
        self.window.input_lineedit_comment.setFocus()

        # set default and minimum value for expire time
        qdatetime = QDateTime.currentDateTime()
        self.window.input_datetime_expire_time.setMinimumDateTime(qdatetime)
        # set default expire time from configuration
        self.window.input_datetime_expire_time.setDateTime(qdatetime.addSecs(
            conf.defaults_acknowledge_expire_duration_hours * 60 * 60 + conf.defaults_acknowledge_expire_duration_minutes * 60
        ))

        # Show or hide widgets based on server
        if self.server is not None:
            for widget, server_types in self.VOLATILE_WIDGETS.items():
                if self.server.TYPE in server_types:
                    widget.show()
                    self.toggle_toggles()
                else:
                    widget.hide()
            if self.server.TYPE in self.FORCE_DATETIME_EXPIRE_TIME:
                self.window.input_datetime_expire_time.show()

        # Adjust to current size if items are hidden in menu
        # Otherwise it will get confused and chop off text
        self.window.options_groupbox.adjustSize()
        self.window.adjustSize()

    def ok(self):
        """
            acknowledge miserable host/service
        """
        # create a list of all service of selected host to acknowledge them all
        all_services = list()
        acknowledge_all_services = self.window.input_checkbox_acknowledge_all_services.isChecked()

        if acknowledge_all_services is True:
            for i in self.server.nagitems_filtered["services"].values():
                for s in i:
                    if s.host in self.host_list:
                        all_services.append(s.name)

        if self.window.input_checkbox_use_expire_time.isChecked() or self.server.TYPE in self.FORCE_DATETIME_EXPIRE_TIME:
            # Format used in UI
            # 2019-11-01T18:17:39
            expire_datetime = self.window.input_datetime_expire_time.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        else:
            expire_datetime = None

        for line_number in range(len(self.host_list)):
            service = self.service_list[line_number]
            host = self.host_list[line_number]

            # send signal to tablewidget worker to care about acknowledging with supplied information
            self.acknowledge.emit({'server': self.server,
                                   'host': host,
                                   'service': service,
                                   'author': self.server.username,
                                   'comment': self.window.input_lineedit_comment.text(),
                                   'sticky': self.window.input_checkbox_sticky_acknowledgement.isChecked(),
                                   'notify': self.window.input_checkbox_send_notification.isChecked(),
                                   'persistent': self.window.input_checkbox_persistent_comment.isChecked(),
                                   'acknowledge_all_services': acknowledge_all_services,
                                   'all_services': all_services,
                                   'expire_time': expire_datetime})
        # call close and macOS dock icon treatment from ancestor
        super().ok()

class Dialog_Downtime(Dialog):
    """
        Dialog for putting hosts/services into downtime
    """

    # send signal to get start and end of a downtime asynchronously
    get_start_end = Signal(str, str)

    # signal to tell worker to commit downtime
    downtime = Signal(dict)

    # store host and service to be used for OK button evaluation
    server = None
    host_list = service_list = []

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)

    def initialize(self, server=None, host=[], service=[]):
        # store server, host and service to be used for OK button evaluation
        self.server = server
        self.host_list = host
        self.service_list = service

        self.window.setWindowTitle('Downtime for host and service')
        str = ''

        for i in range(len(self.host_list)):
            if self.service_list[i] == "":
                str = str + 'Host <b>%s</b><br>' % (self.host_list[i])
            else:
                str = str + 'Service <b>%s</b> on host <b>%s</b><br>' % (self.service_list[i], self.host_list[i])

        self.window.input_label_description.setText(str)

        # default flags of monitor acknowledgement
        self.window.input_spinbox_duration_hours.setValue(int(conf.defaults_downtime_duration_hours))
        self.window.input_spinbox_duration_minutes.setValue(int(conf.defaults_downtime_duration_minutes))
        self.window.input_radiobutton_type_fixed.setChecked(conf.defaults_downtime_type_fixed)
        self.window.input_radiobutton_type_flexible.setChecked(conf.defaults_downtime_type_flexible)

        # hide/show downtime settings according to typw
        self.window.input_radiobutton_type_fixed.clicked.connect(self.set_type_fixed)
        self.window.input_radiobutton_type_flexible.clicked.connect(self.set_type_flexible)

        # show or hide widgets for time settings
        if self.window.input_radiobutton_type_fixed.isChecked():
            self.set_type_fixed()
        else:
            self.set_type_flexible()

        # empty times at start, will be filled by set_start_end
        self.window.input_lineedit_start_time.setText('n/a')
        self.window.input_lineedit_end_time.setText('n/a')

        # default author + comment
        self.window.input_lineedit_comment.setText(conf.defaults_downtime_comment)
        self.window.input_lineedit_comment.setFocus()

        if self.server is not None:
            # at first initialization server is still None
            self.get_start_end.emit(self.server.name, self.host_list[0])

    def ok(self):
        """
            schedule downtime for miserable host/service
        """
        # type of downtime - fixed or flexible
        if self.window.input_radiobutton_type_fixed.isChecked() is True:
            fixed = 1
        else:
            fixed = 0

        for line_number in range(len(self.host_list)):
            service = self.service_list[line_number]
            host = self.host_list[line_number]

            self.downtime.emit({'server': self.server,
                                'host': host,
                                'service': service,
                                'author': self.server.username,
                                'comment': self.window.input_lineedit_comment.text(),
                                'fixed': fixed,
                                'start_time': self.window.input_lineedit_start_time.text(),
                                'end_time': self.window.input_lineedit_end_time.text(),
                                'hours': int(self.window.input_spinbox_duration_hours.value()),
                                'minutes': int(self.window.input_spinbox_duration_minutes.value())})
        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot(str, str)
    def set_start_end(self, start, end):
        """
            put values sent by worker into start and end fields
        """
        self.window.input_lineedit_start_time.setText(start)
        self.window.input_lineedit_end_time.setText(end)

    @Slot()
    def set_type_fixed(self):
        """
            enable/disable appropriate widgets if type is "Fixed"
        """
        self.window.label_duration.hide()
        self.window.label_duration_hours.hide()
        self.window.label_duration_minutes.hide()
        self.window.input_spinbox_duration_hours.hide()
        self.window.input_spinbox_duration_minutes.hide()

    @Slot()
    def set_type_flexible(self):
        """
            enable/disable appropriate widgets if type is "Flexible"
        """
        self.window.label_duration.show()
        self.window.label_duration_hours.show()
        self.window.label_duration_minutes.show()
        self.window.input_spinbox_duration_hours.show()
        self.window.input_spinbox_duration_minutes.show()


class Dialog_Submit(Dialog):
    """
        Dialog for submitting arbitrarily chosen results
    """
    # store host and service to be used for OK button evaluation
    server = None
    host = service = ''

    submit = Signal(dict)

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)

    def initialize(self, server=None, host='', service=''):
        # store server, host and service to be used for OK button evaluation
        self.server = server
        self.host = host
        self.service = service

        # if service is "" it must be a host
        if service == "":
            # set label for acknowledging a host
            self.window.setWindowTitle('Submit check result for host')
            self.window.input_label_description.setText('Host <b>%s</b>' % (host))
            # services do not need all states
            self.window.input_radiobutton_result_up.show()
            self.window.input_radiobutton_result_ok.hide()
            self.window.input_radiobutton_result_warning.hide()
            self.window.input_radiobutton_result_critical.hide()
            self.window.input_radiobutton_result_unknown.show()
            self.window.input_radiobutton_result_unreachable.show()
            self.window.input_radiobutton_result_down.show()
            # activate first radiobutton
            self.window.input_radiobutton_result_up.setChecked(True)
        else:
            # set label for acknowledging a service on host
            self.window.setWindowTitle('Submit check result for service')
            self.window.input_label_description.setText('Service <b>%s</b> on host <b>%s</b>' % (service, host))
            # hosts do not need all states
            self.window.input_radiobutton_result_up.hide()
            self.window.input_radiobutton_result_ok.show()
            self.window.input_radiobutton_result_warning.show()
            self.window.input_radiobutton_result_critical.show()
            self.window.input_radiobutton_result_unknown.show()
            self.window.input_radiobutton_result_unreachable.hide()
            self.window.input_radiobutton_result_down.hide()
            # activate first radiobutton
            self.window.input_radiobutton_result_ok.setChecked(True)

        # clear text fields
        self.window.input_lineedit_check_output.setText('')
        self.window.input_lineedit_performance_data.setText('')
        self.window.input_lineedit_comment.setText(conf.defaults_submit_check_result_comment)
        self.window.input_lineedit_check_output.setFocus()

    def ok(self):
        """
            submit arbitrary check result
        """
        # default state
        state = "ok"

        for button in ["ok", "up", "warning", "critical", "unreachable", "unknown", "down"]:
            if self.window.__dict__['input_radiobutton_result_' + button].isChecked():
                state = button
                break

        # tell worker to submit
        self.submit.emit({'server': self.server,
                          'host': self.host,
                          'service': self.service,
                          'state': state,
                          'comment': self.window.input_lineedit_comment.text(),
                          'check_output': self.window.input_lineedit_check_output.text(),
                          'performance_data': self.window.input_lineedit_performance_data.text()})
        # call close and macOS dock icon treatment from ancestor
        super().ok()


class Dialog_Authentication(Dialog):
    """
        Dialog for authentication
    """
    # store server
    server = None

    # signal for telling server_vbox label to update
    update = Signal(str)

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)

    def initialize(self):
        """
            setup dialog fitting to server
        """
        if self.server is not None:

            self.window.setWindowTitle('Authenticate {0}'.format(self.server.name))
            if self.server.type in ['Centreon', 'Thruk']:
                self.window.input_checkbox_use_autologin.show()
                self.window.input_lineedit_autologin_key.show()
                self.window.input_lineedit_autologin_key.show()
                self.window.label_autologin_key.show()
                # enable switching autologin key and password
                self.window.input_checkbox_use_autologin.clicked.connect(self.toggle_autologin)
                self.window.input_checkbox_use_autologin.setChecked(self.server.use_autologin)
                self.window.input_lineedit_autologin_key.setText(self.server.autologin_key)
                # initialize autologin
                self.toggle_autologin()
            else:
                self.window.input_checkbox_use_autologin.hide()
                self.window.input_lineedit_autologin_key.hide()
                self.window.label_autologin_key.hide()

            # set existing values
            self.window.input_lineedit_username.setText(self.server.username)
            self.window.input_lineedit_password.setText(self.server.password)
            self.window.input_checkbox_save_password.setChecked(conf.servers[self.server.name].save_password)

    @Slot(str)
    def show_auth_dialog(self, server):
        """
            initialize and show authentication dialog
        """
        self.server = servers[server]
        self.initialize()
        # workaround instead of sent signal
        if not statuswindow is None:
            statuswindow.hide_window()
        self.window.adjustSize()
        
        # the dock icon might be needed to be shown for a potential keyboard input
        self.show_macos_dock_icon_if_necessary()
        
        self.window.exec()
        
        # en reverse the dock icon might be hidden again after a potential keyboard input
        self.hide_macos_dock_icon_if_necessary()

    def ok(self):
        """
            Take username and password
        """

        # close window fist to avoid lagging UI
        self.window.close()

        self.server.username = self.window.input_lineedit_username.text()
        self.server.password = self.window.input_lineedit_password.text()
        self.server.refresh_authentication = False

        # store password if it should be saved
        if self.window.input_checkbox_save_password.isChecked():
            conf.servers[self.server.name].username = self.server.username
            conf.servers[self.server.name].password = self.server.password
            conf.servers[self.server.name].save_password = self.window.input_checkbox_save_password.isChecked()
            # store server settings
            conf.SaveMultipleConfig('servers', 'server')

        # Centreon
        if self.server.type in ['Centreon', 'Thruk']:
            if self.window.input_checkbox_use_autologin:
                conf.servers[self.server.name].use_autologin = self.window.input_checkbox_use_autologin.isChecked()
                conf.servers[self.server.name].autologin_key = self.window.input_lineedit_autologin_key.text()
                # store server settings
                conf.SaveMultipleConfig('servers', 'server')

        # reset server connection
        self.server.reset_HTTP()

        # force server to recheck right now
        self.server.thread_counter = conf.update_interval_seconds

        # update server_vbox label
        self.update.emit(self.server.name)

        # call close and macOS dock icon treatment from ancestor
        super().ok()

    @Slot()
    def toggle_autologin(self):
        """
            toolge autologin option for Centreon
        """
        if self.window.input_checkbox_use_autologin.isChecked():
            self.window.label_username.hide()
            self.window.label_password.hide()
            self.window.input_lineedit_username.hide()
            self.window.input_lineedit_password.hide()
            self.window.input_checkbox_save_password.hide()

            self.window.label_autologin_key.show()
            self.window.input_lineedit_autologin_key.show()
        else:
            self.window.label_username.show()
            self.window.label_password.show()
            self.window.input_lineedit_username.show()
            self.window.input_lineedit_password.show()
            self.window.input_checkbox_save_password.show()

            self.window.label_autologin_key.hide()
            self.window.input_lineedit_autologin_key.hide()

        # adjust dialog window size after UI changes
        self.window.adjustSize()


class Dialog_Server_missing(Dialog):
    """
        small dialog to ask about disabled ot not configured servers
    """

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)

        # hide dialog when server is to be created or enabled
        self.window.button_create_server.clicked.connect(self.window.hide)
        self.window.button_enable_server.clicked.connect(self.window.hide)
        self.window.button_ignore.clicked.connect(self.ok)
        # simply hide window if ignore button chosen
        self.window.button_ignore.clicked.connect(self.window.hide)
        self.window.button_ignore.clicked.connect(self.cancel)
        # byebye if exit button was pressed
        self.window.button_exit.clicked.connect(self.window.hide)
        self.window.button_exit.clicked.connect(exit)

    def initialize(self, mode='no_server'):
        """
            use dialog for missing and not enabled servers, depending on mode
        """
        if mode == 'no_server':
            self.window.label_no_server_configured.show()
            self.window.label_no_server_enabled.hide()
            self.window.button_enable_server.hide()
            self.window.button_create_server.show()
        else:
            self.window.label_no_server_configured.hide()
            self.window.label_no_server_enabled.show()
            self.window.button_enable_server.show()
            self.window.button_create_server.hide()


class Dialog_About(Dialog):
    """
        About information dialog
    """

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)
        # first add the logo on top - no idea how to achive in Qt Designer
        logo = QSvgWidget(f'{RESOURCES}{os.sep}nagstamon.svg')
        logo.setFixedSize(100, 100)
        self.window.vbox_about.insertWidget(1, logo, 0, Qt.AlignmentFlag.AlignHCenter)
        # update version information
        self.window.label_nagstamon.setText(f'<h1>{AppInfo.NAME} {AppInfo.VERSION}</h1>')
        self.window.label_nagstamon_long.setText('<h2>Nagios¹ status monitor for your desktop</2>')
        self.window.label_copyright.setText(AppInfo.COPYRIGHT)
        self.window.label_website.setText(f'<a href={AppInfo.WEBSITE}>{AppInfo.WEBSITE}</a>')
        self.window.label_website.setOpenExternalLinks(True)
        self.window.label_versions.setText(f'Python: {platform.python_version()}, Qt: {QT_VERSION_STR}')
        self.window.label_contribution.setText(f'<a href={AppInfo.WEBSITE}/contribution>Contribution</a> | <a href=https://paypal.me/nagstamon>Donation</a>')
        self.window.label_footnote.setText('<small>¹ meanwhile many more monitors...</small>')

        # fill in license information
        license_file = open('{0}{1}LICENSE'.format(RESOURCES, os.sep))
        license = license_file.read()
        license_file.close()
        self.window.textedit_license.setPlainText(license)
        self.window.textedit_license.setReadOnly(True)

        # fill in credits information
        credits_file = open(f'{RESOURCES}{os.sep}CREDITS', encoding='utf-8')
        credits = credits_file.read()
        credits_file.close()
        self.window.textedit_credits.setText(credits)
        self.window.textedit_credits.setOpenExternalLinks(True)
        self.window.textedit_credits.setReadOnly(True)

        self.window.tabs.setCurrentIndex(0)


class CheckVersion(QObject):
    """
        checking for updates
    """

    is_checking = False

    version_info_retrieved = Signal()

    @Slot(bool, QWidget)
    def check(self, start_mode=False, parent=None):

        if self.is_checking is False:

            # lock checking thread
            self.is_checking = True

            # list of enabled servers which connections outside should be used to check
            self.enabled_servers = get_enabled_servers()

            # set mode to be evaluated by worker
            self.start_mode = start_mode

            # store caller of dialog window - not if at start because this will disturb EWMH
            if start_mode is True:
                self.parent = None
            else:
                self.parent = parent

            # thread for worker to avoid
            self.worker_thread = QThread(parent=self)
            self.worker = self.Worker()

            # if update check is ready it sends the message to GUI thread
            self.worker.ready.connect(self.show_message)

            # stop thread if worker has finished
            self.worker.finished.connect(self.worker_thread.quit)
            # reset checking lock if finished
            self.worker.finished.connect(self.reset_checking)

            self.worker.moveToThread(self.worker_thread)
            # run check when thread starts
            self.worker_thread.started.connect(self.worker.check)
            self.worker_thread.start(QThread.Priority.LowestPriority)

    @Slot()
    def reset_checking(self):
        """
            reset checking flag to avoid QThread crashes
        """
        self.is_checking = False

    @Slot(str)
    def show_message(self, message):
        """
            message dialog must be shown from GUI thread
        """
        self.version_info_retrieved.emit()

        # attempt to solve https://github.com/HenriWahl/Nagstamon/issues/303
        # might be working this time
        if statuswindow.is_shown:
            parent = statuswindow
        else:
            parent = self.parent

        messagebox = QMessageBox(QMessageBox.Icon.Information,
                                 'Nagstamon version check',
                                 message,
                                 QMessageBox.StandardButton.Ok,
                                 parent,
                                 Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        messagebox.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        messagebox.setWindowModality(Qt.WindowModality.NonModal)
        messagebox.exec()

    class Worker(QObject):

        """
            check for new version in background
        """
        # send signal if some version information is available
        ready = Signal(str)

        finished = Signal()

        def __init__(self):
            QObject.__init__(self)

        def check(self):
            """
                check for update using server connection
            """
            # get servers to be used for checking version
            enabled_servers = get_enabled_servers()

            # default latest version is 'unavailable' and message empty
            latest_version = 'unavailable'
            message = ''

            # find at least one server which allows to get version information
            for server in enabled_servers:
                for download_server, download_url in AppInfo.DOWNLOAD_SERVERS.items():
                    # dummy message just in case version check does not work
                    message = 'Cannot reach version check at <a href={0}>{0}</<a>.'.format(
                        f'https://{download_server}{AppInfo.VERSION_PATH}')
                    # retrieve VERSION_URL without auth information
                    response = server.FetchURL(f'https://{download_server}{AppInfo.VERSION_PATH}',
                                               giveback='raw',
                                               no_auth=True)
                    # stop searching the available download URLs
                    if response.error == "" and not response.result.startswith('<'):
                        latest_version = response.result.strip()
                        break
                # ignore TLS error in case it was caused by requesting latest version - not important for monitoring
                server.tls_error = False

                # stop searching via enabled servers
                if response.error == "" and not response.result.startswith('<'):
                    latest_version = response.result.strip()
                    break

            # compose message according to version information
            if latest_version != 'unavailable':
                if latest_version == AppInfo.VERSION:
                    message = 'You are using the latest version <b>Nagstamon {0}</b>.'.format(AppInfo.VERSION)
                elif latest_version > AppInfo.VERSION:
                    message = 'The new version <b>Nagstamon {0}</b> is available.<p>' \
                              'Get it at <a href={1}>{1}</a>.'.format(latest_version, AppInfo.WEBSITE + '/download')
                elif latest_version < AppInfo.VERSION:
                    # for some reason the local version is newer than that remote one - just ignore
                    message = ''

            # check if there is anything to tell
            if message != '':
                # if run from startup do not cry if any error occured or nothing new is available
                if check_version.start_mode is False or \
                        (check_version.start_mode is True and latest_version not in ('unavailable', AppInfo.VERSION)):
                    self.ready.emit(message)

            # tell thread to finish
            self.finished.emit()


class DBus(QObject):
    """
        Create connection to DBus for desktop notification for Linux/Unix
    """

    open_statuswindow = Signal()

    # random ID needed because otherwise all instances of Nagstamon
    # will get commands by clicking on notification bubble via DBUS
    random_id = str(int(random.random() * 100000))

    def __init__(self):
        QObject.__init__(self)

        # get DBUS availability - still possible it does not work due to missing
        # .sevice file on certain distributions
        global DBUS_AVAILABLE

        self.id = 0
        self.actions = [('open' + self.random_id), 'Open status window']
        self.timeout = 0
        # use icon from resources in hints, not the package icon - doesn't work neither
        self.icon = ''
        # use Nagstamon image if icon is not available from system
        # see https://developer.gnome.org/notification-spec/#icons-and-images
        # self.hints = {'image-path': '%s%snagstamon.svg' % (RESOURCES, os.sep)}
        self.hints = {'image-path': '{0}{1}nagstamon.svg'.format(RESOURCES, os.sep)}

        if not OS in OS_NON_LINUX and DBUS_AVAILABLE:
            if 'dbus' in sys.modules:
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
                    traceback.print_exc(file=sys.stdout)
                    self.connected = False
        else:
            self.connected = False

    def show(self, summary, message):
        """
            simply show message
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


def create_brushes():
    """
        fill static brushes with current colors for treeview
    """
    # if not customized use default intensity
    if conf.grid_use_custom_intensity:
        intensity = 100 + conf.grid_alternation_intensity
    else:
        intensity = 115

    # every state has 2 labels in both alteration levels 0 and 1
    for state in STATES[1:]:
        for role in ('text', 'background'):
            QBRUSHES[0][COLORS[state] + role] = QColor(conf.__dict__[COLORS[state] + role])
            # if background is too dark to be litten split it into RGB values
            # and increase them sepeartely
            # light/darkness spans from 0 to 255 - 30 is just a guess
            if role == 'background' and conf.show_grid:
                if QBRUSHES[0][COLORS[state] + role].lightness() < 30:
                    r, g, b, a = (QBRUSHES[0][COLORS[state] + role].getRgb())
                    r += 30
                    g += 30
                    b += 30
                    QBRUSHES[1][COLORS[state] + role] = QColor(r, g, b).lighter(intensity)
                else:
                    # otherwise just make it a little bit darker
                    QBRUSHES[1][COLORS[state] + role] = QColor(conf.__dict__[COLORS[state] +
                                                                             role]).darker(intensity)
            else:
                # only make background darker; text should stay as it is
                QBRUSHES[1][COLORS[state] + role] = QBRUSHES[0][COLORS[state] + role]


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
        screen = APP.screenAt(QPoint(x, y))
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
    for screen in APP.screens():
        if screen.name() == screen_name:
            return screen.geometry()

    # if screen_name didn't match available use primary screen
    return APP.primaryScreen().geometry()


@Slot()
def exit():
    """
        stop all child threads before quitting instance
    """
    # store position of statuswindow/statusbar
    statuswindow.store_position_to_conf()

    # save configuration
    conf.SaveConfig()

    # hide statuswindow first to avoid lag when waiting for finished threads
    statuswindow.hide()

    # stop statuswindow workers
    statuswindow.worker.finish.emit()
    statuswindow.worker_notification.finish.emit()

    # tell all treeview threads to stop
    for server_vbox in statuswindow.servers_vbox.children():
        server_vbox.table.worker.finish.emit()

    APP.exit()


def check_servers():
    """
        check if there are any servers configured and enabled
    """
    # no server is configured
    if len(servers) == 0:
        dialogs.server_missing.show()
        dialogs.server_missing.initialize('no_server')
    # no server is enabled
    elif len([x for x in conf.servers.values() if x.enabled is True]) == 0:
        dialogs.server_missing.show()
        dialogs.server_missing.initialize('no_server_enabled')

def hide_macos_dock_icon(hide=False):
    """
    small helper to make dock icon visible or not in macOS
    inspired by https://stackoverflow.com/questions/6796028/start-a-gui-process-in-mac-os-x-without-dock-icon
    """
    if hide:
        NSApp.setActivationPolicy_(NSApplicationPresentationHideDock)
    else:
        NSApp.setActivationPolicy_(NSApplicationPresentationDefault)

# check for updates
check_version = CheckVersion()

# access to clipboard
clipboard = APP.clipboard()

# DBus initialization
dbus_connection = DBus()

# access dialogs
dialogs = Dialogs()

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
