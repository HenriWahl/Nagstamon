# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2015 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

"""Module QUI"""

import os
import os.path
import urllib.parse
import webbrowser
import subprocess
import sys
import platform
import time

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtSvg import *
from PyQt5.QtMultimedia import *

from operator import methodcaller
from collections import OrderedDict
from copy import deepcopy

from Nagstamon.Config import (conf,
                              Server,
                              Action,
                              RESOURCES,
                              AppInfo)

from Nagstamon.Servers import (SERVER_TYPES,
                               servers,
                               create_server,
                               get_enabled_servers,
                               get_worst_status,
                               get_status_count)

from Nagstamon.Helpers import (is_found_by_re,
                               debug_queue,
                               STATES,
                               STATES_SOUND,
                               BOOLPOOL)

# dialogs
from Nagstamon.QUI.settings_main import Ui_settings_main
from Nagstamon.QUI.settings_server import Ui_settings_server
from Nagstamon.QUI.settings_action import Ui_settings_action
from Nagstamon.QUI.dialog_acknowledge import Ui_dialog_acknowledge
from Nagstamon.QUI.dialog_downtime import Ui_dialog_downtime
from Nagstamon.QUI.dialog_submit import Ui_dialog_submit

# only on X11/Linux thirdparty path should be added because it contains the Xlib module
# needed to tell window manager via EWMH to keep Nagstamon window on all virtual desktops
# TODO: test if X11 or Wayland is used
if not platform.system() in ['Darwin', 'Windows']:
    # extract thirdparty path from resources path - make submodules accessible by thirdparty modules
    THIRDPARTY = os.sep.join(RESOURCES.split(os.sep)[0:-1] + ['thirdparty'])
    sys.path.insert(0, THIRDPARTY)
    from Nagstamon.thirdparty.ewmh import EWMH

if not platform.system() in ['Darwin', 'Windows']:
    try:
        from dbus import (Interface,
                          SessionBus)
        from dbus.mainloop.pyqt5 import DBusQtMainLoop
    except:
        print('No DBus for desktop notification available.')

# fixed icons for hosts/services attributes
ICONS = dict()

# fixed shortened and lowered color names for cells, also used by statusbar label snippets
COLORS = OrderedDict([('DOWN', 'color_down_'),
                      ('UNREACHABLE', 'color_unreachable_'),
                      ('CRITICAL', 'color_critical_'),
                      ('UNKNOWN', 'color_unknown_'),
                      ('WARNING', 'color_warning_')])

# states to be used in statusbar if long version is used
COLOR_STATE_NAMES = {'DOWN': {True: 'DOWN', False: ''},
                     'UNREACHABLE': { True: 'UNREACHABLE', False: ''},
                     'CRITICAL': { True: 'CRITICAL', False: ''},
                     'UNKNOWN': { True: 'UNKNOWN', False: ''},
                     'WARNING': { True: 'WARNING', False: ''}}

# headers for tablewidgets
HEADERS = OrderedDict([('host', 'Host'), ('service', 'Service'),
                       ('status', 'Status'), ('last_check', 'Last Check'),
                       ('duration', 'Duration'), ('attempt', 'Attempt'),
                       ('status_information', 'Status Information')])

# list of headers keywords for action context menu
HEADERS_LIST = list(HEADERS)

# sorting order for tablewidgets
SORT_ORDER = {'descending': True, 'ascending': False, 0: True, 1: False}

# space used in LayoutBoxes
SPACE = 10


class HBoxLayout(QHBoxLayout):
    """
        Apparently necessary to get a HBox which is able to hide its children
    """
    def __init__(self, spacing=None, parent=None):
        QHBoxLayout.__init__(self, parent)

        if spacing == None:
            self.setSpacing(0)
        else:
            self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)     # no margin


    def hide_items(self):
        """
            cruise through all child widgets and hide them
            self,count()-1 is needed because the last item is None
        """
        for item in range(self.count()-1):
            self.itemAt(item).widget().hide()


    def show_items(self):
        """
            cruise through all child widgets and show them
            self,count()-1 is needed because the last item is None
        """
        for item in range(self.count()-1):
            self.itemAt(item).widget().show()


#class SystemTrayIcon(QSystemTrayIcon):
class SystemTrayIcon(QSystemTrayIcon):
    """
        Icon in system tray, works at least in Windows and OSX
        Qt5 shows an empty icon in GNOME3
    """

    show_popwin = pyqtSignal()
    hide_popwin = pyqtSignal()

    def __init__(self):
        QSystemTrayIcon.__init__(self)

        # icons are in dictionary
        self.icons = {}
        self.create_icons()
        # empty icon for flashing notification
        self.icons['EMPTY'] = QIcon('{0}{1}nagstamon_systrayicon_empty.svg'.format(RESOURCES, os.sep))
        # little workaround to match statuswindow.worker_notification.worst_notification_status
        self.icons['UP'] = self.icons['OK']
        # default icon is OK
        self.setIcon(self.icons['OK'])

        # store icon for flashing
        self.current_icon = None

        # timer for singleshots for flashing
        self.timer = QTimer()

        # when there are new settings/colors recreate icons
        dialogs.settings.changed.connect(self.create_icons)

        # treat clicks
        self.activated.connect(self.icon_clicked)

        # store x and y of coursor when being clicked as there seems to be no way
        # to get the systray icons position
        self.x_cursor = False
        self.y_cursor = False


    @pyqtSlot(QMenu)
    def set_menu(self, menu):
        """
            create current menu for right clicks
        """
        # MacOSX does not distinguish between left and right click so menu will go to upper menu bar
        if platform.system() != 'Darwin':
            self.setContextMenu(menu)


    @pyqtSlot()
    def create_icons(self):
        """
            create icons from template, applying colors
        """
        # get template from file
        svg_template_file = open('{0}{1}nagstamon_systrayicon_template.svg'.format(RESOURCES, os.sep))
        svg_template_xml = svg_template_file.readlines()

        # create icons for all states
        for state in  ['OK', 'UNKNOWN', 'WARNING', 'CRITICAL', 'UNREACHABLE', 'DOWN', 'ERROR']:
            # current SVG XML for state icon, derived from svg_template_cml
            svg_state_xml = list()

            # replace dummy text and background colors with configured ones
            for line in svg_template_xml:
                line = line.replace('fill:#ff00ff', 'fill:' + conf.__dict__['color_' + state.lower() + '_text'])
                line = line.replace('fill:#00ff00', 'fill:' + conf.__dict__['color_' + state.lower() + '_background'])
                svg_state_xml.append(line)

            # create XML stream of SVG
            svg_xml_stream = QXmlStreamReader(''.join(svg_state_xml))
            # create renderer for SVG and put SVG XML into renderer
            svg_renderer = QSvgRenderer(svg_xml_stream)
            # pixmap to be painted on
            svg_pixmap = QPixmap(128, 128)
            # initiate painter which paints onto paintdevice pixmap
            svg_painter = QPainter(svg_pixmap)
            # render svg to pixmap
            svg_renderer.render(svg_painter)
            # close painting
            svg_painter.end()
            # put pixmap into icon
            self.icons[state] = QIcon(svg_pixmap)


    @pyqtSlot(QEvent)
    def icon_clicked(self, event):
        """
            evaluate mouse click
        """
        # only react on left mouse click
        if event == (QSystemTrayIcon.Trigger or QSystemTrayIcon.DoubleClick):
            self.x_cursor = QCursor.pos().x()
            self.y_cursor = QCursor.pos().y()
            if statuswindow.is_shown:
                self.hide_popwin.emit()
            else:
                self.show_popwin.emit()


    @pyqtSlot()
    def show_state(self):
        """
            get worst status and display it in systray
        """
        worst_status = get_worst_status()
        self.setIcon(self.icons[worst_status])
        # set current icon for flshing
        self.current_icon = self.icons[worst_status]
        del(worst_status)


    @pyqtSlot()
    def flash(self):
        """
            send color inversion signal to labels
        """
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            # store current icon to get it reset back
            if self.current_icon == None:
                self.current_icon = self.icons[statuswindow.worker_notification.worst_notification_status]
            # use empty SVG icon to display emptiness
            self.setIcon(self.icons['EMPTY'])
            # fire up  a singleshot to reset color soon
            self.timer.singleShot(500, self.reset)


    @pyqtSlot()
    def reset(self):
        """
            tell labels to set original colors
        """
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            # set curent status icon
            self.setIcon(self.current_icon)
            # even later call itself to invert colors as flash
            self.timer.singleShot(500, self.flash)
        else:
            if self.current_icon != None:
                self.setIcon(self.current_icon)
            self.current_icon = None


class MenuAtCursor(QMenu):
    """
        open menu at position of mouse pointer - normal .exec() shows menu at (0, 0)
    """
    # flag to avoid too fast popping up menus
    available = True

    def __init__(self, parent=None):
        QMenu.__init__(self, parent=parent)


    @pyqtSlot()
    def show_at_cursor(self):
        """
            pop up at mouse pointer position, lock itself to avoid permamently popping menus on Windows
        """
        # get cursor coordinates and decrease them to show menu under mouse pointer
        x = QCursor.pos().x() - 10
        y = QCursor.pos().y() - 10
        self.exec(QPoint(x, y))
        del(x, y)


class MenuContext(MenuAtCursor):
    """
        class for universal context menu, used at systray icon and hamburger menu
    """

    menu_ready = pyqtSignal(QMenu)

    def __init__(self):
        MenuAtCursor.__init__(self)

        # connect all relevant widgets which should show the context menu
        self.menu_ready.connect(systrayicon.set_menu)
        self.menu_ready.connect(statuswindow.toparea.button_hamburger_menu.set_menu)
        self.menu_ready.connect(statuswindow.toparea.logo.set_menu)
        self.menu_ready.connect(statuswindow.toparea.label_version.set_menu)
        self.menu_ready.connect(statuswindow.toparea.label_empty_space.set_menu)
        self.menu_ready.connect(statuswindow.statusbar.logo.set_menu)
        for color_label in statuswindow.statusbar.color_labels.values():
            self.menu_ready.connect(color_label.set_menu)
        dialogs.settings.changed.connect(self.initialize)

        self.initialize()

    @pyqtSlot()
    def initialize(self):
        """
            add actions and servers to menu
        """

        # first clear to get rid of old servers
        self.clear()

        self.action_refresh = QAction('Refresh', self)
        self.action_refresh.triggered.connect(statuswindow.refresh)
        self.addAction(self.action_refresh)

        self.action_recheck = QAction('Recheck', self)
        self.action_recheck.triggered.connect(statuswindow.recheck_all)
        self.addAction(self.action_recheck)

        self.addSeparator()

        # dict to hold all servers - more flexible this way
        self.action_servers = dict()

        # connect every server to its monitoring webpage
        for server in servers:
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


class PushButton_Hamburger(QPushButton):
    """
        Pushbutton with menu for hamburger
    """

    pressed = pyqtSignal()

    def __init__(self):
        QPushButton.__init__(self)


    def mousePressEvent(self, event):
        self.pressed.emit()
        self.showMenu()

    pyqtSlot(QMenu)
    def set_menu(self, menu):
        self.setMenu(menu)


class PushButton_BrowserURL(QPushButton):
    """
        QPushButton for ServerVBox which opens certain URL if clicked
    """
    def __init__(self, text='', parent=None, server=None, url_type=''):
        QPushButton.__init__(self, text, parent=parent)
        self.server = server
        self.url_type = url_type

    @pyqtSlot()
    def open_url(self):
        """
            open URL from BROWSER_URLS in webbrowser
        """
        # BROWSER_URLS come with $MONITOR$ instead of real monitor url - heritage from actions
        url = self.server.BROWSER_URLS[self.url_type].replace('$MONITOR$', self.server.monitor_url)

        if conf.debug_mode:
            self.Debug(server=self.server.get_name(), debug='Open {0} web page {1}'.format(self.url_type, url))

        # use Python method to open browser
        webbrowser.open(url)

        # hide statuswindow to get screen space for browser
        statuswindow.hide_window()


class ComboBox_Servers(QComboBox):
    """
        combobox which does lock statuswindow so it does not close when opening combobox
    """
    monitor_opened = pyqtSignal()

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
        self.addItems(sorted(conf.servers.keys(), key=str.lower))


    @pyqtSlot()
    def response(self):
        """
            respnose to activated item in servers combobox
        """
        if self.currentText() in servers:
            # open webbrowser with server URL
            webbrowser.open(servers[self.currentText()].monitor_url)

            # hide window to make room for webbrowser
            self.monitor_opened.emit()

        self.setCurrentIndex(0)


class _Draggable_Widget(QWidget):
    """
        Used to give various toparea and statusbar widgets draggability
    """
    # yell if statusbar is moved
    window_moved = pyqtSignal()

    # needed for popup after hover
    mouse_entered = pyqtSignal()

    # needed for popup after click
    mouse_pressed = pyqtSignal()
    mouse_released = pyqtSignal()


    pyqtSlot(QMenu)
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
        if event.button() == 1:
            self.mouse_pressed.emit()
            # keep x and y relative to statusbar
        # if not set calculate relative position
        if not statuswindow.relative_x and not statuswindow.relative_y:
            statuswindow.relative_x = event.globalX() - statuswindow.x()
            statuswindow.relative_y = event.globalY() - statuswindow.y()


    def mouseReleaseEvent(self, event):
        """
            decide if moving or menu should be treated after mouse button was released
        """
        if event.button() == 1:
            # if popup window should be closed by clicking do it now
            if statuswindow.is_shown and conf.close_details_clicking:
                statuswindow.hide_window()
            elif statuswindow.is_shown == False:
                self.mouse_released.emit()

            # reset all helper values
            statuswindow.relative_x = False
            statuswindow.relative_y = False
            statuswindow.moving = False

        elif event.button() == 2:
            self.menu.show_at_cursor()


    def mouseMoveEvent(self, event):
        """
            do the moving action
        """
        # lock window as moving
        # if not set calculate relative position
        if not statuswindow.relative_x and not statuswindow.relative_y:
            statuswindow.relative_x = event.globalX() - statuswindow.x()
            statuswindow.relative_y = event.globalY() - statuswindow.y()

        statuswindow.moving = True
        statuswindow.move(event.globalX()-statuswindow.relative_x, event.globalY()-statuswindow.relative_y)

        # needed for OSX - otherwise statusbar stays blank while moving
        statuswindow.update()
        
        self.window_moved.emit()


    def enterEvent(self, event):
        """
            tell the world that mouse entered the widget - interesting for hover popup
        """
        if statuswindow.is_shown == False:
            self.mouse_entered.emit()


class Draggable_Label(QLabel, _Draggable_Widget):
    """
       label with dragging capabilities used by toparea
    """
    # yell if statusbar is moved
    window_moved = pyqtSignal()

    # needed for popup after hover
    mouse_entered = pyqtSignal()

    # needed for popup after click
    mouse_pressed = pyqtSignal()
    mouse_released = pyqtSignal()


    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text, parent=parent)


class StatusWindow(QWidget):
    """
        Consists of statusbar, toparea and scrolling area.
        Either statusbar is shown or (toparea + scrolling area)
    """

    # sent by .resize_window()
    resizing = pyqtSignal()

    # send when windows opens, e.g. for stopping notifications
    showing = pyqtSignal()

    # send when window shrinks down to statusbar or closes
    hiding = pyqtSignal()

    # signal to be sent to all server workers to recheck all
    recheck = pyqtSignal()

    def __init__(self):
        """
            Status window combined from status bar and popup window
        """
        QWidget.__init__(self)
        # immediately hide to avoid flicker on Windows and OSX
        self.hide()

        # avoid quitting when using Qt.Tool flag and closing settings dialog
        QApplication.setQuitOnLastWindowClosed(False)

        # statusbar and detail window should be frameless and stay on top
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)

        # show tooltips even if popup window has no focus
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        # avoid hiding window if it has no focus - necessary on OSX
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)

        self.setWindowTitle(AppInfo.NAME)
        self.setWindowIcon(QIcon('%s%snagstamon.svg' % (RESOURCES, os.sep)))

        self.vbox = QVBoxLayout(self)          # global VBox
        self.vbox.setSpacing(0)                     # no spacing
        self.vbox.setContentsMargins(0, 0, 0, 0)    # no margin

        self.statusbar = StatusBar(parent=self)                # statusbar HBox
        self.toparea = TopArea(parent=self)                    # toparea HBox
        # no need to be seen first
        self.toparea.hide()

        self.servers_scrollarea = QScrollArea(self)     # scrollable area for server vboxes
        # avoid horizontal scrollbars
        self.servers_scrollarea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.servers_scrollarea_widget = QWidget(self.servers_scrollarea)  # necessary widget to contain vbox for servers
        self.servers_scrollarea.hide()

        self.vbox.addWidget(self.statusbar)
        self.vbox.addWidget(self.toparea)
        self.vbox.addWidget(self.servers_scrollarea)

        self.servers_vbox = QVBoxLayout(self.servers_scrollarea)           # VBox full of servers
        self.servers_vbox.setSpacing(0)
        self.servers_vbox.setContentsMargins(0, 0, 0, 0)

        #self.menu = QMenuBar()

        # connect logo of statusbar
        self.statusbar.logo.window_moved.connect(self.store_position)
        self.statusbar.logo.window_moved.connect(self.hide_window)
        self.statusbar.logo.window_moved.connect(self.correct_moving_position)
        self.statusbar.logo.mouse_pressed.connect(self.store_position)
        ###self.statusbar.logo.mouse_pressed.connect(self.hide_window)

        # after status summarization check if window has to be resized
        self.statusbar.resize.connect(self.adjust_size)

        # statusbar label has been entered by mouse -> show
        for label in self.statusbar.color_labels.values():
            label.mouse_entered.connect(self.show_window_after_checking_for_hover)
            label.mouse_released.connect(self.show_window_after_checking_for_clicking)

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
        ###self.toparea.label_empty_space.mouse_pressed.connect(self.hide_window)

        # buttons in toparea
        self.toparea.button_recheck_all.clicked.connect(self.recheck_all)
        self.toparea.button_refresh.clicked.connect(self.refresh)
        self.toparea.button_settings.clicked.connect(self.hide_window)
        self.toparea.button_settings.clicked.connect(dialogs.settings.show)
        self.toparea.button_close.clicked.connect(self.hide_window)

        # if monitor was selected in combobox its monitor window is opened
        self.toparea.combobox_servers.monitor_opened.connect(self.hide_window)

        # change to systray or floating statusbar if changed
        dialogs.settings.changed.connect(self.switch_mode)

        # refresh all information after changed settings
        dialogs.settings.changed.connect(self.refresh)

        # show status popup when systray icon was clicked
        systrayicon.show_popwin.connect(self.show_window_systrayicon)
        systrayicon.hide_popwin.connect(self.hide_window)

        # worker and thread duo needed for notifications
        self.worker_notification_thread = QThread()
        self.worker_notification = self.Worker_Notification()
        # flashing statusbar
        self.worker_notification.start_flash.connect(self.statusbar.flash)
        self.worker_notification.stop_flash.connect(self.statusbar.reset)
        # flashing statusicon
        self.worker_notification.start_flash.connect(systrayicon.flash)
        self.worker_notification.stop_flash.connect(systrayicon.reset)
        # desktop notification
        self.worker_notification.desktop_notification.connect(self.desktop_notification)

        # stop notification if window gets shown or hidden
        self.hiding.connect(self.worker_notification.stop)

        self.worker_notification.moveToThread(self.worker_notification_thread)
        # start with priority 0 = lowest
        self.worker_notification_thread.start(0)

        # create vbox for each enabled server
        for server in servers.values():
            if server.enabled:
                self.servers_vbox.addLayout(self.create_ServerVBox(server))
        self.servers_vbox.addStretch()

        self.servers_scrollarea_widget.setLayout(self.servers_vbox)
        self.servers_scrollarea.setWidget(self.servers_scrollarea_widget)
        self.servers_scrollarea.setWidgetResizable(True)

        # icons in ICONS have to be sized as fontsize
        _create_icons(self.statusbar.fontMetrics().height())

        # needed for moving the statuswindow
        self.moving = False
        self.relative_x = False
        self.relative_y = False

        # helper values for QTimer.singleShot move attempt
        self.move_to_x = self.move_to_y = 0

        # flag to mark if window is shown or nor
        self.is_shown = False

        # if status_ok is true no server_vboxes are needed
        self.status_ok = True

        # timer for waiting to set is_shown flag
        self.timer = QTimer(self)

        # flag to avoid hiding window when a menu is shown
        self.locked = False

        # a thread + worker is necessary to do actions thread-safe in background
        # like debugging
        self.worker_thread = QThread()
        self.worker = self.Worker()
        self.worker.moveToThread(self.worker_thread)
        # start thread and debugging loop if debugging is enabled
        if conf.debug_mode:
            self.worker_thread.started.connect(self.worker.debug_loop)
        # start debug loop by signal
        self.worker.start_debug_loop.connect(self.worker.debug_loop)
        # start with priority 0 = lowest
        self.worker_thread.start(0)

        # finally show up
        self.switch_mode()

        # X11/Linux needs some special treetment to get the statusbar floating on all virtual desktops
        if not platform.system() in ('Darwin', 'Windows'):
            # ewmh.py in thirdparty directory
            ewmh = EWMH()
            # get all windows...
            windows = list(ewmh.getClientList())
            # and check their wm_class_name, hoping to find Nagstamon
            for window in windows:
                if window.get_wm_class()[0] == os.path.basename(sys.argv[0]):
                    # tell windowmanager via EWMH to display statusbar everywhere
                    ewmh.setWmDesktop(window.id, 0xffffffff)
                    # apply wish
                    ewmh.display.flush()
                    break


    def switch_mode(self):
        """
            apply presentation mode
        """
        if conf.statusbar_floating:
            # no need for systray
            systrayicon.hide()
            self.hide_window()
            self.statusbar.show()
            # show statusbar/statuswindow on last saved position
            # when coordinates are inside known screens
            if get_screen(conf.position_x, conf.position_y) != None:
                self.move(conf.position_x, conf.position_y)
            else:
                # get available desktop specs
                available_x = desktop.availableGeometry(self).x()
                available_y = desktop.availableGeometry(self).y()
                self.move(available_x, available_y)


        elif conf.icon_in_systray:
            # yeah! systray!
            systrayicon.show()
            # no need for window and its parts
            self.statusbar.hide()
            self.hide()

        # store position for showing/hiding statuswindow
        self.stored_x = self.x()
        self.stored_y = self.y()


    def create_ServerVBox(self, server):
        """
            internally used to create enabled servers to be displayed
        """
        # create server vboxed from current running servers
        if server.enabled:
            # without parent there is some flickering when starting
            server_vbox = ServerVBox(server, parent=self)

            # connect to global resize signal
            server_vbox.table.ready_to_resize.connect(self.adjust_size)

            # tell statusbar to summarize after table was refreshed
            server_vbox.table.worker.new_status.connect(self.statusbar.summarize_states)
            server_vbox.table.worker.new_status.connect(systrayicon.show_state)

            # if problems go themselves there is no need to notify user anymore
            server_vbox.table.worker.problems_vanished.connect(self.worker_notification.stop)

            # tell notification worker to do something AFTER the table was updated
            server_vbox.table.status_changed.connect(self.worker_notification.start)

            # and to update status window
            server_vbox.table.refreshed.connect(self.update_window)

            # tell table it should remove freshness of formerly new items when window closes
            # because apparently the new events have been seen now
            self.hiding.connect(server_vbox.table.worker.unfresh_event_history)

            # stop notifcation if statuswindow pops up
            self.showing.connect(self.worker_notification.stop)

            # tell server worker to recheck all hosts and services
            self.recheck.connect(server_vbox.table.worker.recheck_all)

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
        servers_vbox_new = QVBoxLayout()           # VBox full of servers
        servers_vbox_new.setContentsMargins(0, 0, 0, 0)
        servers_vbox_new.setSpacing(0)

        # sort server vboxes
        for vbox in sorted(vboxes_dict):
            vboxes_dict[vbox].setParent(None)
            vboxes_dict[vbox].setParent(None)
            servers_vbox_new.addLayout(vboxes_dict[vbox])

        # switch to new servers_vbox
        self.servers_vbox = servers_vbox_new
        self.servers_scrollarea_widget = QWidget()  # necessary widget to contain vbox for servers
        self.servers_scrollarea_widget.setLayout(self.servers_vbox)
        self.servers_scrollarea.setWidget(self.servers_scrollarea_widget)

        del(vboxes_dict)


    @pyqtSlot()
    def show_window_after_checking_for_clicking(self):
        """
            being called after clicking statusbar - check if window should be showed
        """
        if conf.popup_details_clicking:
            self.show_window()


    @pyqtSlot()
    def show_window_after_checking_for_hover(self):
        """
            being called after hovering over statusbar - check if wondiw should be showed
        """
        if conf.popup_details_hover:
            self.show_window()


    @pyqtSlot()
    def show_window_systrayicon(self):
        """
            handle clicks onto systray icon
        """

        # where is the pointer which clicked onto systray icon
        mouse_x = QCursor.pos().x()
        mouse_y = QCursor.pos().y()

        # move into direction of systray - where the cursor hangs around too
        self.move(mouse_x, mouse_y)

        # get available desktop specs
        available_width = desktop.availableGeometry(self).width()
        available_height = desktop.availableGeometry(self).height()
        available_x = desktop.availableGeometry(self).x()
        available_y = desktop.availableGeometry(self).y()

        x = 0
        y = 0

        if not self.is_shown:

            if mouse_x > (available_width + available_x)/2:
                x = available_x + available_width - self.statusbar.width()
            else:
                x = available_x +  self.statusbar.width()

            if mouse_y > (available_height - available_y)/2:
                y = available_height - available_y

            self.move(x,y)

            # under unfortunate circumstances statusbar might have the the moving flag true
            # fix it here because it makes no sense
            self.moving = False

            self.show_window()
        else:
            self.hide_window()


    @pyqtSlot()
    def show_window(self, event=None):
        """
            used to show status window when its appearance is triggered, also adjusts geometry
        """
        # do not show up when being dragged around
        if not self.moving:
            for vbox in self.servers_vbox.children():
                if vbox.server.all_ok and vbox.server.status == '':
                    self.status_ok = True
                else:
                    self.status_ok = False
                    break

            # here we should check if scroll_area should be shown at all
            if not self.status_ok:
                # attempt to avoid flickering on MacOSX - already hide statusbar here
                self.statusbar.hide()

                # show the other status window components
                self.toparea.show()
                self.servers_scrollarea.show()

                for vbox in self.servers_vbox.children():
                    if not vbox.server.all_ok:
                        vbox.show_all()
                    elif vbox.server.all_ok and vbox.server.status == '':
                        vbox.hide_all()
                    # show at least server vbox header to notify about connection or other errors
                    elif vbox.server.status != '':
                        vbox.show_only_header()
                # theory...
                width, height, x, y = self.calculate_size()
                # ...and practice
                self.resize_window(width, height, x, y)
                # switch on
                if platform.system() == 'Darwin':
                    # delayed because of flickering window in OSX
                    self.timer.singleShot(200, self.set_shown)
                else:
                    self.set_shown()

                self.show()

                # tell others like notification that statuswindow shows up now
                self.showing.emit()


    @pyqtSlot()
    def update_window(self):
        """
            redraw window content, to be effective only when window is shown
        """
        if self.is_shown:
            self.show_window()


    @pyqtSlot()
    def hide_window(self):
        """
            hide window if not needed
        """
        # only hide if shown and not locked or if not yet hidden if moving
        if self.is_shown == True or\
           self.is_shown == True and self.moving == True:
            if conf.statusbar_floating:
                self.statusbar.show()
                self.statusbar.adjustSize()
            self.toparea.hide()
            self.servers_scrollarea.hide()
            self.setMinimumSize(1, 1)
            self.adjustSize()
            self.move(self.stored_x, self.stored_y)

            # switch off
            self.is_shown = False

            # flag to reflect top-ness of window/statusbar
            self.top = False

            # tell the world that window goes down
            self.hiding.emit()


    @pyqtSlot()
    def correct_moving_position(self):
        """
            correct position if moving and cursor startet outside statusbar
        """
        if self.moving:
            mouse_x = QCursor.pos().x()
            mouse_y = QCursor.pos().y()
            # when cursor is outside moved window correct the coordinates of statusbar/statuswindow
            if not statuswindow.geometry().contains(mouse_x, mouse_y):
                rect = statuswindow.geometry()
                corrected_x = int(mouse_x - rect.width()/2)
                corrected_y = int(mouse_y - rect.height()/2)
                # calculate new relative values
                self.relative_x = mouse_x - corrected_x
                self.relative_y = mouse_y - corrected_y
                statuswindow.move(corrected_x, corrected_y)
                del(mouse_x, mouse_y, corrected_x, corrected_y)


    def calculate_size(self):
        """
            get size of popup window
        """
        if conf.statusbar_floating:
            screen_or_widget = self
        elif conf.icon_in_systray:
            screen_or_widget = get_screen(systrayicon.x_cursor, systrayicon.y_cursor)
        available_width = desktop.availableGeometry(screen_or_widget).width()
        available_height = desktop.availableGeometry(screen_or_widget).height()
        available_x = desktop.availableGeometry(screen_or_widget).x()
        available_y = desktop.availableGeometry(screen_or_widget).y()
        del(screen_or_widget)

        # take whole screen height into account when deciding about upper/lower-ness
        # add available_y because it might vary on differently setup screens
        # calculate top-ness only if window is closed
        if conf.statusbar_floating:
            if self.is_shown == False:
                if self.y() < desktop.screenGeometry(self).height()/2 + available_y:
                    self.top = True
                else:
                    self.top = False
        elif conf.icon_in_systray:
            if systrayicon.y_cursor:
                if systrayicon.y_cursor < desktop.screenGeometry(self).height()/2 + available_y:
                    self.top = True
                else:
                    self.top = False

        # get height from tablewidgets
        real_height = self.get_real_height()

        # width simply will be the current screen maximal width - less hassle!
        width = available_width

        if conf.statusbar_floating:
            # when statusbar resides in uppermost part of current screen extend from top to bottom
            if self.top == True:
                y = self.y()
                if self.y() + real_height < available_height + available_y:
                    height = real_height
                else:
                    height = available_height - self.y() + available_y
            # when statusbar hangs around in lowermost part of current screen extend from bottom to top
            else:
                # when height is to large for current screen cut it
                if self.y() + self.height() - real_height < available_y:
                    height = desktop.screenGeometry().height() - available_y -\
                             (desktop.screenGeometry().height() - (self.y() + self.height()))
                    y = available_y
                else:
                    height = real_height
                    y = self.y() + self.height() - height

        elif conf.icon_in_systray:
            # when systrayicon resides in uppermost part of current screen extend from top to bottom
            if self.top == True:
                # when being top y is of course the available one
                y = available_y
                if self.y() + real_height < available_height + available_y:
                    height = real_height
                else:
                    # if bigger than screen shrink to maximal real_height
                    height = available_height - available_y
            # when statusbar hangs around in lowermost part of current screen extend from bottom to top
            else:
                # when height is to large for current screen cut it
                if self.y() + self.height() - real_height < available_y:
                    height = desktop.screenGeometry().height() - available_y -\
                             (desktop.screenGeometry().height() - (self.y() + self.height()))
                    y = available_y
                else:
                    height = real_height
                    y = available_height - real_height

        return width, height, available_x, y


    def resize_window(self, width, height, x, y):
        """
            resize status window according to its new size
        """

        # store position for restoring it when hiding - only if not shown of course
        if self.is_shown == False:
            self.stored_x = self.x()
            self.stored_y = self.y()

        if platform.system() == 'Windows':
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

        # always stretch over whole screen width - thus x = screen_x, the leftmost pixel
        self.setMaximumSize(width, height)
        self.setMinimumSize(width, height)
        self.adjustSize()

        return True


    @pyqtSlot()
    def move_timer(self):
        """
            helper for move by QTimer.singleShot - attempt to avoid flickering on Windows
        """
        self.move(self.move_to_x, self.move_to_y)


    @pyqtSlot()
    def adjust_size(self):
        """
            resize window if shown and needed
        """
        self.adjusting_size_lock = True
        # fully displayed statuswindow
        if self.is_shown == True:
            width, height, x, y = self.calculate_size()
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
            del(hint)
        self.resize_window(width, height, x, y)
        del(width, height, x, y)



    @pyqtSlot()
    def store_position(self):
        # store position for restoring it when hiding
        if not self.is_shown:
            self.stored_x = self.x()
            self.stored_y = self.y()


    def leaveEvent(self, event):
        """
            check if popup has to be hidden depending ou mouse position
        """
        # check first if popup has to be shown by hovering or clicking
        if conf.close_details_hover:
            # only hide window if cursor is outside of it
            mouse_x = QCursor.pos().x()
            mouse_y = QCursor.pos().y()
            # <= and >= necessary because sometimes mouse_* is the same as self.*()
            if mouse_x <= self.x() or mouse_x >= self.x() + self.width() or\
               mouse_y <= self.y() or mouse_y >= self.y() + self.height():
                self.hide_window()

            del(mouse_x, mouse_y)


    def get_real_width(self):
        """
            calculate widest width of all server tables
        """
        width = 0
        for server in self.servers_vbox.children():
            ###if server.table.get_real_width() > width:
            if server.table.real_width > width:
                width = server.table.get_real_width()

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


    @pyqtSlot(str, str)
    def show_message(self, msg_type, message):
        """
            show message from other thread like MediaPlayer
        """
        title = " ".join((AppInfo.NAME, msg_type))
        if msg_type == 'warning':
            QMessageBox.warning(None, title, message)

        elif msg_type == 'information':
            QMessageBox.information(None, title, message)


    @pyqtSlot()
    def recheck_all(self):
        """
            tell servers to recheck all hosts and services
        """
        self.recheck.emit()


    @pyqtSlot()
    def refresh(self):
        """
            tell all enabled servers to refresh their information
        """
        for server in get_enabled_servers():
            if conf.debug_mode:
                server.Debug(server=server.name, debug='Refreshing all hosts and services')

            # manipulate server thread counter so get_status loop will refresh when next looking
            # at thread counter
            server.thread_counter = conf.update_interval_seconds


    @pyqtSlot(dict)
    def desktop_notification(self, current_status_count):
        """
            show desktop notification - must be called from same thread as DBus intialization
        """
        # compile message from status counts
        message = ''
        for state in ['DOWN', 'UNREACHABLE', 'CRITICAL', 'WARNING', 'UNKNOWN']:
            if current_status_count[state] > 0:
                message += '{0} {1} '.format(str(current_status_count[state]), state)
        dbus_connection.show(AppInfo.NAME, message)


    class Worker(QObject):
        """
           run a thread for example for debugging
        """

        # used by DialogSettings.ok() to tell debug loop it should start
        start_debug_loop = pyqtSignal()

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


        @pyqtSlot()
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
                            if self.debug_file == None:
                                self.open_debug_file()
                            # log line per line
                            self.debug_file.write(debug_line + "\n")
                    # wait second until next poll
                    time.sleep(1)

                # unset looping
                self.debug_mode_looping = False
                # close file if any
                if self.debug_file != None:
                    self.close_debug_file()


    class Worker_Notification(QObject):
        """
           run a thread for doing all notification stuff
        """

        # tell statusbar labels to flash
        start_flash = pyqtSignal()
        stop_flash = pyqtSignal()
        # tell mediaplayer to load and play sound file
        load_sound = pyqtSignal(str)
        play_sound = pyqtSignal()

        # tell statuswindow to use desktop notification
        desktop_notification = pyqtSignal(dict)

        # flag about current notification state
        is_notifying = False

        # only one enabled server should have the right to send play_sound signal
        notifying_server = ''

        # current worst state worth a notification
        worst_notification_status = 'UP'

        # desktop notification needs to store count of states
        status_count = dict()


        def __init__(self):
            QObject.__init__(self)


        @pyqtSlot(str, str)
        def start(self, server_name, worst_status_diff):
            """
                start notification
            """
            # only if not notifying yet or the current state is worse than the prior AND
            # only when the current state is configured to be honking about
            if (STATES.index(worst_status_diff) > STATES.index(self.worst_notification_status) or\
               self.is_notifying == False) and\
               conf.__dict__['notify_if_{0}'.format(worst_status_diff.lower())] == True:
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
                            sound_file = conf.__dict__['notification_custom_sound_{0}'.format(worst_status_diff.lower())]

                        # once loaded file will be played by every server, even if it is
                        # not the self.notifying_server that loaded it
                        self.load_sound.emit(sound_file)

                        # only one enabled server should access the mediaplayer
                        if self.notifying_server == server_name:
                            self.play_sound.emit()

                # Notification actions
                if conf.notification_actions:
                    if conf.notification_action_warning == True and worst_status_diff == 'WARNING':
                        self.execute_action(server_name, conf.notification_action_warning_string)
                    if conf.notification_action_critical == True and worst_status_diff == 'CRITICAL':
                        self.execute_action(server_name, conf.notification_action_critical_string)
                    if conf.notification_action_down == True and worst_status_diff == 'DOWN':
                        self.execute_action(server_name, conf.notification_action_down_string)

            # Custom event notification - valid vor ALL events, thus without status comparison
            if conf.notification_actions == True and conf.notification_custom_action == True:
                # temporarily used to collect executed events
                events_list= []
                events_string = ''

                # if no single notifications should be used (default) put all events into one string, separated by separator
                if conf.notification_custom_action_single == False:
                    for server in get_enabled_servers():
                        # list comprehension only considers events which are new, ergo True
                        events_list += [k for k,v in server.events_notification.items() if v == True]

                    # create string for no-single-event-notification of events separated by separator
                    events_string = conf.notification_custom_action_separator.join(events_list)

                    # clear already notified events setting them to False
                    for server in get_enabled_servers():
                        for event in [k for k,v in server.events_notification.items() if v == True]:
                            server.events_notification[event] = False
                else:
                    for server in get_enabled_servers():
                        for event in [k for k,v in server.events_notification.items() if v == True]:
                            custom_action_string = conf.notification_custom_action_string.replace('$EVENTS$', event)
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
            if self.is_notifying and\
               conf.notification_sound_repeat and\
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
                del(current_status_count)


        @pyqtSlot()
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


class NagstamonLogo(QSvgWidget, _Draggable_Widget):
    """
        SVG based logo, used for statusbar and toparea logos
    """
    # yell if statusbar is moved
    window_moved = pyqtSignal()

    # needed for popup after hover
    mouse_entered = pyqtSignal()

    # needed for popup after click
    mouse_pressed = pyqtSignal()
    mouse_released = pyqtSignal()

    def __init__(self, file, width=None, height=None, parent=None):
        QSvgWidget.__init__(self, parent=parent)
        self.load(file)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # size needed for small Nagstamon logo in statusbar
        if width != None and height != None:
            self.setMinimumSize(width, height)
            self.setMaximumSize(width, height)


class StatusBar(QWidget):
    """
        status bar for short display of problems
    """

    # send signal to statuswindow
    resize = pyqtSignal()

    # needed to maintain flashing labels
    labels_invert = pyqtSignal()
    labels_reset = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.hbox = HBoxLayout(spacing=0, parent=parent)
        self.setLayout(self.hbox)

        # define labels first to get their size for svg logo dimensions
        self.color_labels = OrderedDict()
        self.color_labels['OK'] = StatusBarLabel('OK', parent=parent)
        for state in COLORS:
            self.color_labels[state] =  StatusBarLabel(state, parent=parent)
            self.labels_invert.connect(self.color_labels[state].invert)
            self.labels_reset.connect(self.color_labels[state].reset)

        # derive logo dimensions from status label
        self.logo = NagstamonLogo("%s%snagstamon_logo_bar.svg" % (RESOURCES, os.sep),
                            self.color_labels['OK'].fontMetrics().height(),
                            self.color_labels['OK'].fontMetrics().height(),
                            parent=parent)
        # add widgets
        self.hbox.addWidget(self.logo)
        self.hbox.addWidget(self.color_labels['OK'])
        self.color_labels['OK'].show()

        # add state labels
        for state in COLORS:
            self.hbox.addWidget(self.color_labels[state])

        # when there are new settings/colors refresh labels
        dialogs.settings.changed.connect(self.reset)

        # timer for singleshots for flashing
        self.timer = QTimer()

        # first summary
        self.summarize_states()


    @pyqtSlot()
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

        if all_numbers == 0:
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


    @pyqtSlot()
    def flash(self):
        """
            send color inversion signal to labels
        """
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            self.labels_invert.emit()
            # fire up  a singleshot to reset color soon
            self.timer.singleShot(500, self.reset)


    @pyqtSlot()
    def reset(self):
        """
            tell labels to set original colors
        """
        self.labels_reset.emit()
        # only if currently a notification is necessary
        if statuswindow.worker_notification.is_notifying:
            # even later call itself to invert colors as flash
            self.timer.singleShot(500, self.flash)


class StatusBarLabel(Draggable_Label):
    """
        one piece of the status bar labels for one state
    """

    # yell if statusbar is moved
    window_moved = pyqtSignal()

    # needed for popup after hover
    mouse_entered = pyqtSignal()

    # needed for popup after click
    mouse_pressed = pyqtSignal()
    mouse_released = pyqtSignal()

    def __init__(self, state, parent=None):
        Draggable_Label.__init__(self, parent=parent)
        self.setStyleSheet('padding-left: 1px;'
                           'padding-right: 1px;'
                           ###'font-size: 20px;'
                           'color: %s; background-color: %s;' % (conf.__dict__['color_%s_text' % (state.lower())],
                                                                 conf.__dict__['color_%s_background' % (state.lower())]))
        # just let labels grow as much as they need
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        # hidden per default
        self.hide()

        # default text - only useful in case of OK Label
        self.setText(state)

        # number of hosts/services of this state
        self.number = 0

        # store state of label to access long state names in .summarize_states()
        self.state = state


    @pyqtSlot()
    def invert(self):
        self.setStyleSheet('padding-left: 1px;'
                           'padding-right: 1px;'
                           ###'font-size: 20px;'
                           'color: %s; background-color: %s;' % (conf.__dict__['color_%s_background' % (self.state.lower())],
                                                                 conf.__dict__['color_%s_text' % (self.state.lower())]))


    @pyqtSlot()
    def reset(self):
        self.setStyleSheet('padding-left: 1px;'
                           'padding-right: 1px;'
                           ###'font-size: 20px;'
                           'color: %s; background-color: %s;' % (conf.__dict__['color_%s_text' % (self.state.lower())],
                                                                 conf.__dict__['color_%s_background' % (self.state.lower())]))


class TopArea(QWidget):
    """
        Top area of status window
    """

    mouse_entered = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self)
        self.hbox = HBoxLayout(spacing=SPACE, parent=self)      # top HBox containing buttons

        # top button box
        self.logo = NagstamonLogo('%s%snagstamon_logo_toparea.svg' % (RESOURCES, os.sep), width=144, height=42, parent=self)
        self.label_version = Draggable_Label(text=AppInfo.VERSION, parent=self)
        self.label_empty_space = Draggable_Label(text='', parent=self)
        self.label_empty_space.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.combobox_servers = ComboBox_Servers(parent=self)
        self.button_filters = QPushButton("Filters", parent=self)
        self.button_recheck_all = QPushButton("Recheck all", parent=self)
        self.button_refresh = QPushButton("Refresh", parent=self)
        self.button_settings = QPushButton("Settings", parent=self)

        # fill default order fields combobox with server names
        self.combobox_servers.fill()

        self.button_hamburger_menu = PushButton_Hamburger()
        self.button_hamburger_menu.setIcon(QIcon('%s%smenu.svg' % (RESOURCES, os.sep)))
        self.button_hamburger_menu.setStyleSheet('QPushButton {border-width: 0px;'
                                                              'border-style: none;}'
                                                 'QPushButton:hover {background-color: white;'
                                                                    'border-radius: 4px;}'
                                                 'QPushButton::menu-indicator{image:url(none.jpg);}')
        self.hamburger_menu = MenuAtCursor()
        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(exit)
        self.hamburger_menu.addAction(action_exit)

        self.button_hamburger_menu.setMenu(self.hamburger_menu)

        self.button_close = QPushButton()
        self.button_close.setIcon(QIcon('%s%sclose.svg' % (RESOURCES, os.sep)))
        self.button_close.setStyleSheet('QPushButton {border-width: 0px;'
                                                     'border-style: none;'
                                                     'margin-right: 5px;}'
                                        'QPushButton:hover {background-color: red;'
                                                           'border-radius: 4px;}')

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


class ServerStatusLabel(Draggable_Label):
    """
        label for ServerVBox to show server connection state
        extra class to apply simple slots for changing text or color
    """

    # storage for label text if it needs to be restored
    text_old = ''

    def __init__(self, parent=None):
        QLabel.__init__(self, parent=parent)


    @pyqtSlot(str)
    def change(self, text):
        # store old text in case it needs to be reused
        self.text_old = self.text()
        # set new text
        self.setText(text)


    @pyqtSlot()
    def reset(self):
        self.setText('')


    @pyqtSlot()
    def restore(self):
        # restore text, used by recheck_all of tablewidget worker
        self.setText(self.text_old)


class ServerVBox(QVBoxLayout):
    """
        one VBox per server containing buttons and hosts/services listview
    """
    # used to update status label text like 'Connected-'
    change_label_status = pyqtSignal(str)

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

        self.label = QLabel("<big><b>%s@%s</b></big>" % (server.username, server.name), parent=parent)
        # let label padding keep top and bottom space - apparently not necessary on OSX
        if platform.system() != 'Darwin':
            self.label.setStyleSheet('padding-top: {0}px; padding-bottom: {0}px;'.format(SPACE))

        self.button_edit = QPushButton('Edit', parent=parent)
        self.button_monitor = PushButton_BrowserURL(text='Monitor', parent=parent, server=self.server, url_type='monitor')
        self.button_hosts = PushButton_BrowserURL(text='Hosts', parent=parent, server=self.server, url_type='hosts')
        self.button_services = PushButton_BrowserURL(text='Services', parent=parent, server=self.server, url_type='services')
        self.button_history = PushButton_BrowserURL(text='History', parent=parent, server=self.server, url_type='history')
        self.label_status = ServerStatusLabel(parent=parent)

        self.button_edit.clicked.connect(self.edit_server)

        self.button_monitor.clicked.connect(self.button_monitor.open_url)
        self.button_hosts.clicked.connect(self.button_hosts.open_url)
        self.button_services.clicked.connect(self.button_services.open_url)
        self.button_history.clicked.connect(self.button_history.open_url)

        self.header.addWidget(self.label)
        self.header.addWidget(self.button_edit)
        self.header.addWidget(self.button_monitor)
        self.header.addWidget(self.button_hosts)
        self.header.addWidget(self.button_services)
        self.header.addWidget(self.button_history)
        self.header.addWidget(self.label_status)
        self.header.addStretch()

        sort_column = conf.default_sort_field.lower()
        order = conf.default_sort_order.lower()

        self.table = TableWidget(0, len(HEADERS), sort_column, order, self.server, parent=parent)

        # delete vbox if thread quits
        self.table.worker_thread.finished.connect(self.delete)

        # connect worker to status label to reflect connectivity
        self.table.worker.change_label_status.connect(self.label_status.change)
        self.table.worker.restore_label_status.connect(self.label_status.restore)

        self.addWidget(self.table, 1)

        # as default do not show anything
        self.show_only_header()


    def get_real_height(self):
        """
            return summarized real height of hbox items and table
        """

        ###height = self.table.get_real_height()
        height = self.table.real_height
        if self.label.isVisible() and self.button_monitor.isVisible():
            # compare item heights, decide to take the largest and add 2 time the MARGIN (top and bottom)
            if self.label.sizeHint().height() > self.button_monitor.sizeHint().height():
                height += self.label.sizeHint().height()
            else:
                height += self.button_monitor.sizeHint().height()
        return height


    @pyqtSlot()
    def show_all(self):
        """
            show all items in server vbox except the table - not needed if empty
        """
        self.label.show()
        self.button_edit.show()
        self.button_monitor.show()
        self.button_hosts.show()
        self.button_services.show()
        self.button_history.show()
        self.label_status.show()

        # special table treatment
        self.table.show()
        self.table.is_shown = True


    @pyqtSlot()
    def show_only_header(self):
        """
            show all items in server vbox except the table - not needed if empty
        """
        self.label.show()
        self.button_edit.show()
        self.button_monitor.show()
        self.button_hosts.show()
        self.button_services.show()
        self.button_history.show()
        self.label_status.show()

        # special table treatment
        self.table.hide()
        self.table.is_shown = False


    @pyqtSlot()
    def hide_all(self):
        """
            hide all items in server vbox
        """
        #self.setContentsMargins(0, 0, 0, 0)
        self.label.hide()
        self.button_edit.hide()
        self.button_monitor.hide()
        self.button_hosts.hide()
        self.button_services.hide()
        self.button_history.hide()
        self.label_status.hide()

        # special table treatment
        self.table.hide()
        self.table.is_shown = False


    @pyqtSlot()
    def delete(self):
        """
            delete VBox and its children
        """
        for widget in (self.label,
                       self.button_edit,
                       self.button_monitor,
                       self.button_hosts,
                       self.button_services,
                       self.button_history,
                       self.label_status):
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
        statuswindow.hide_window()
        dialogs.server.edit(server_name=self.server.name)


class CellWidget(QWidget):
    """
        widget to be used as cells in tablewidgets
    """

    # send to tablewidget if cell clicked
    clicked = pyqtSignal()

    def __init__(self, column=0, row=0, text='', color='black', background='white', icons='', tooltip='', parent=None):
        QWidget.__init__(self, parent=parent)

        self.column = column
        self.row = row
        self.text = text
        self.color = color
        self.background = background

        self.hbox = QHBoxLayout(self)
        self.setLayout(self.hbox)

        # text field
        self.label = QLabel(self.text, parent=self)

        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.addWidget(self.label, 1)
        self.hbox.setSpacing(0)

        self.setToolTip(tooltip)

        self.label.setStyleSheet('padding: 5px;')
        ###                         'font-size: 20px;')

        # hosts and services might contain attribute icons
        if column in (0, 1) and icons is not [False]:
            for icon in icons:
                icon_label = QLabel(parent=self)
                icon_label.setPixmap(icon.pixmap(self.label.fontMetrics().height(), self.label.fontMetrics().height()))
                icon_label.setStyleSheet('padding-right: 5px;')
                self.hbox.addWidget(icon_label)

        # paint cell appropriately
        self.colorize()


    def colorize(self):
        self.setStyleSheet('color: %s; background-color: %s;' % (self.color, self.background))


    def highlight(self):
        self.setStyleSheet('color: %s; background-color: %s;' % (self.color, 'darkgrey'))


    def enterEvent(self, eventt):
        if not self.parent().parent().action_menu.isVisible():
            self.parent().parent().highlight_row(self.row)


    def leaveEvent(self, event):
        self.parent().parent().colorize_row(self.row)


    def mouseReleaseEvent(self, event):
        """
            send signal of clicked cell to table widget which cares further
        """
        self.clicked.emit()


class TableWidget(QTableWidget):
    """
        Contains information for one monitor server as a table
    """

    # send new data to worker
    new_data = pyqtSignal(list, str, bool)

    # tell global window that it should be resized
    ready_to_resize = pyqtSignal()

    # sent by refresh() for statusbar
    refreshed = pyqtSignal()

    # tell worker to get status after a recheck has been solicited
    recheck = pyqtSignal(dict)

    # tell notification that status of server has changed
    status_changed = pyqtSignal(str, str)

    # action to be executed by worker
    # 2 values: action and host/service info
    request_action = pyqtSignal(dict, dict)


    def __init__(self, columncount, rowcount, sort_column, order, server, parent=None):
        QTableWidget.__init__(self, columncount, rowcount, parent=parent)

        self.sort_column = sort_column
        self.order = order
        self.server = server

        # no vertical header needed
        self.verticalHeader().hide()

        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        # has to be necessarily false to keep sanity if calculating table height
        self.setShowGrid(False)
        # no scrollbars at tables because they will be scrollable by the global vertical scrollbar
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAutoScroll(False)
        self.setSortingEnabled(True)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)

        self.setHorizontalHeaderLabels(HEADERS.values())
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSortIndicator(list(HEADERS).index(self.sort_column), SORT_ORDER[self.order])
        self.horizontalHeader().sortIndicatorChanged.connect(self.sort_columns)

        # store width and height if they do not need to be recalculated
        self.real_width = 0
        self.real_height = 0

        # store currentrly activated row
        self.highlighted_row = 0

        # action context menu
        self.action_menu = MenuAtCursor(parent=self)
        # flag to avoid popping up menus when clicking somehwere
        self.action_menu.available = True
        # signalmapper for getting triggered actions
        self.signalmapper_action_menu = QSignalMapper()
        # connect menu to responder
        self.signalmapper_action_menu.mapped[str].connect(self.action_menu_custom_response)

        # a thread + worker is necessary to get new monitor server data in the background and
        # to refresh the table cell by cell after new data is available
        self.worker_thread = QThread()
        self.worker = self.Worker(server=server)
        self.worker.moveToThread(self.worker_thread)

        # if worker got new status data from monitor server get_status the table should be refreshed
        self.worker.new_status.connect(self.refresh)
        # if worker calculated next cell send it to GUI thread
        self.worker.next_cell.connect(self.set_cell)
        # when worker walked through all cells send a signal to table so it could get_status itself
        self.worker.table_ready.connect(self.adjust_table)
        # quit thread if worker has finished
        #self.worker.finish.connect(self.worker_thread.quit)
        self.worker.finish.connect(self.finish_worker_thread)
        # get status if started
        self.worker_thread.started.connect(self.worker.get_status)
        # start with priority 0 = lowest
        self.worker_thread.start(0)

        # connect signal new_data to worker slot fill_rows
        self.new_data.connect(self.worker.fill_rows)

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

        # display mode - all or only header to display error
        self.is_shown = False


    @pyqtSlot()
    def refresh(self):
        """
            refresh status display
        """
        # do nothing if window is moving to avoid lagging movement
        if not statuswindow.moving:
            # get_status table cells with new data by thread
            data = list(self.server.GetItemsGenerator())
            if len(data) > 0:
                self.set_data(data)
                # display table if there is something to display
                self.is_shown = True
            else:
                self.is_shown = False

            # pre-calculate dimensions
            self.real_height = self.get_real_height()
            self.real_width = self.get_real_width()

            # tell statusbar it should update
            self.refreshed.emit()

            # check if status changed and notification is necessary
            # send signal because there are unseen events
            if self.server.get_events_history_count() > 0:
                self.status_changed.emit(self.server.name, self.server.worst_status_diff)


    @pyqtSlot(int, int, str, str, str, list, str)
    def set_cell(self, row, column, text, color, background, icons, tooltip):
        """
            set data and widget for one cell
        """
        widget = CellWidget(text=text, color=color, background=background,
                            row=row, column=column, icons=icons, tooltip=tooltip,
                            parent=self)

        # if cell got clicked evaluate that click
        widget.clicked.connect(self.cell_clicked)

        # fill cells with data
        self.setCellWidget(row, column, widget)


    def set_data(self, data=None):
        """
            fill table cells with data from filtered Nagios items
        """
        # maximum size needs no more than amount of data
        self.setRowCount(self.server.nagitems_filtered_count)

        # send signal to worker
        self.new_data.emit(data, self.sort_column, SORT_ORDER[self.order])


    @pyqtSlot()
    def adjust_table(self):
        """
            adjust table dimensions after filling it
        """
        # seems to be important for not getting somehow squeezed cells
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.horizontalHeader().setStretchLastSection(True)

        # force table to its maximal height, calculated by .get_real_height()
        self.setMinimumHeight(self.get_real_height())
        self.setMaximumHeight(self.get_real_height())
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Maximum)

        # after setting table whole window can be repainted
        self.ready_to_resize.emit()


    @pyqtSlot()
    def cell_clicked(self):
        """
            Windows reacts different to clicks into table cells than Linux and MacOSX
            Therefore the .available flag is necessary
        """
        if self.action_menu.available or platform.system() != 'Windows':

            # set flag for Windows
            self.action_menu.available = False

            # simply use currently highlighted row as an index
            self.miserable_host = self.cellWidget(self.highlighted_row, HEADERS_LIST.index('host')).text
            self.miserable_service = self.cellWidget(self.highlighted_row, HEADERS_LIST.index('service')).text
            self.miserable_status_info = self.cellWidget(self.highlighted_row, HEADERS_LIST.index('status_information')).text

            # empty the menu
            self.action_menu.clear()

            # clear signal mappings
            self.signalmapper_action_menu.removeMappings(self.signalmapper_action_menu)

            # add custom actions
            actions_list = list(conf.actions)
            actions_list.sort(key=str.lower)
            for a in actions_list:
                # shortcut for next lines
                action = conf.actions[a]
                if action.enabled == True and action.monitor_type in ['', self.server.TYPE]:
                    # menu item visibility flag
                    item_visible = False
                    # check if clicked line is a service or host
                    # if it is check if the action is targeted on hosts or services
                    if self.miserable_service:
                        if action.filter_target_service == True:
                            # only check if there is some to check
                            if action.re_host_enabled == True:
                                if is_found_by_re(self.miserable_host,
                                                       action.re_host_pattern,
                                                       action.re_host_reverse):
                                    item_visible = True
                            # dito
                            if action.re_service_enabled == True:
                                if is_found_by_re(self.miserable_service,
                                                       action.re_service_pattern,
                                                       action.re_service_reverse):
                                    item_visible = True
                            # dito
                            if action.re_status_information_enabled == True:
                                if is_found_by_re(self.miserable_service,
                                                       action.re_status_information_pattern,
                                                       action.re_status_information_reverse):
                                    item_visible = True

                            # fallback if no regexp is selected
                            if action.re_host_enabled == action.re_service_enabled == \
                               action.re_status_information_enabled == False:
                                item_visible = True

                    else:
                        # hosts should only care about host specific actions, no services
                        if action.filter_target_host == True:
                            if action.re_host_enabled == True:
                                if is_found_by_re(self.miserable_host,\
                                                       action.re_host_pattern,\
                                                       action.re_host_reverse):
                                    item_visible = True
                            else:
                                # a non specific action will be displayed per default
                                item_visible = True
                else:
                    item_visible = False

                # populate context menu with service actions
                if item_visible == True:
                    # create action
                    action_menuentry = QAction(a, self)
                    #add action
                    self.action_menu.addAction(action_menuentry)
                    # action to signalmapper
                    self.signalmapper_action_menu.setMapping(action_menuentry, a)
                    action_menuentry.triggered.connect(self.signalmapper_action_menu.map)

                del action, item_visible

            # create adn add default actions
            action_edit_actions = QAction('Edit actions...', self)
            action_edit_actions.triggered.connect(self.action_edit_actions)

            action_monitor = QAction('Monitor', self)
            action_monitor.triggered.connect(self.action_monitor)

            action_recheck = QAction('Recheck', self)
            action_recheck.triggered.connect(self.action_recheck)

            action_acknowledge = QAction('Acknowledge', self)
            action_acknowledge.triggered.connect(self.action_acknowledge)

            action_downtime = QAction('Downtime', self)
            action_downtime.triggered.connect(self.action_downtime)

            # put actions into menu after separator
            self.action_menu.addAction(action_edit_actions)
            self.action_menu.addSeparator()
            self.action_menu.addAction(action_monitor)
            self.action_menu.addAction(action_recheck)
            self.action_menu.addAction(action_acknowledge)
            self.action_menu.addAction(action_downtime)

            # not all servers allow to submit fake check results
            if 'Submit check result' in self.server.MENU_ACTIONS:
                action_submit = QAction('Submit check result', self)
                action_submit.triggered.connect(self.action_submit)
                self.action_menu.addAction(action_submit)

            # show menu
            self.action_menu.show_at_cursor()
        else:
            self.action_menu.available = True


    @pyqtSlot(str)
    def action_menu_custom_response(self, action):
        # avoid blocked context menu
        self.action_menu.available = True
        # send dict with action info and dict with host/service info
        self.request_action.emit(conf.actions[action].__dict__, {'server': self.server.get_name(),
                                                                 'host': self.miserable_host,
                                                                 'service': self.miserable_service,
                                                                 'status-info': self.miserable_status_info,
                                                                 'address': self.server.GetHost(self.miserable_host).result,
                                                                 'monitor': self.server.monitor_url,
                                                                 'monitor-cgi': self.server.monitor_cgi_url,
                                                                 'username': self.server.username,
                                                                 'password': self.server.password,
                                                                 'comment-ack': conf.defaults_acknowledge_comment,
                                                                 'comment-down': conf.defaults_downtime_comment,
                                                                 'comment-submit': conf.defaults_submit_check_result_comment
                                                                 })

        # if action wants a closed status window it should be closed now
        if conf.actions[action].close_popwin:
            statuswindow.hide_window()


    @pyqtSlot()
    def action_response_decorator(method):
        """
            decorate repeatedly called stuff
        """
        def decoration_function(self):
            # avoid blocked context menu
            self.action_menu.available = True
            # run decorated method
            method(self)
            # default actions need closed statuswindow to display own dialogs
            statuswindow.hide_window()
        return(decoration_function)


    @action_response_decorator
    def action_edit_actions(self):
        # buttons in toparee
        statuswindow.hide_window()
        # open actions tab (#3) of settings dialog
        dialogs.settings.show(tab=3)


    @action_response_decorator
    def action_monitor(self):
        # open host/service monitor in browser
        self.server.open_monitor(self.miserable_host, self.miserable_service)


    @action_response_decorator
    def action_recheck(self):
        # send signal to worker recheck slot
        self.recheck.emit({'host':    self.miserable_host,
                           'service': self.miserable_service})


    @action_response_decorator
    def action_acknowledge(self):
        # running worker method is left to OK button of dialog
        dialogs.acknowledge.show()
        dialogs.acknowledge.initialize(server=self.server,
                                       host=self.miserable_host,
                                       service=self.miserable_service)


    @action_response_decorator
    def action_downtime(self):
        # running worker method is left to OK button of dialog
        dialogs.downtime.show()
        dialogs.downtime.initialize(server=self.server,
                                    host=self.miserable_host,
                                    service=self.miserable_service)


    @action_response_decorator
    def action_submit(self):
        # running worker method is left to OK button of dialog
        dialogs.submit.show()
        dialogs.submit.initialize(server=self.server,
                                    host=self.miserable_host,
                                    service=self.miserable_service)


    @pyqtSlot(int, int)
    def sort_columns(self, column, order):
        """
            set data according to sort criteria
        """
        self.sort_column = list(HEADERS.keys())[column]
        self.order = SORT_ORDER[order]
        self.set_data(list(self.server.GetItemsGenerator()))


    def real_size(self):
        """
            width, height
        """
        return self.get_real_width(), self.get_real_height()


    def get_real_width(self):
        """
            calculate real table width as there is no method included
        """
        self.real_width = 0
        for column in range(0, self.columnCount()):
            # if there is no with yet at the start take some reasonable value
            try:
                self.real_width += self.cellWidget(0, column).width()
            except:
                self.real_width += 100
        del(column)

        return self.real_width


    def get_real_height(self):
        """
            calculate real table height as there is no method included
        """
        if self.is_shown:
            # height summary starts with headers' height
            # apparently height works better/without scrollbar if some pixels are added
            self.real_height = self.horizontalHeader().sizeHint().height() + 2
            # it is necessary to ask every row directly because their heights differ :-(
            row = 0
            for row in range(0, self.rowCount()):
                try:
                    self.real_height += (self.cellWidget(row, 0).sizeHint().height())
                except:
                    self.real_height += 30
            del(row)
        else:
            self.real_height = 0
        """
        # height summary starts with headers' height
        # apparently height works better/without scrollbar if some pixels are added
        self.real_height = self.horizontalHeader().sizeHint().height() + 2
        # it is necessary to ask every row directly because their heights differ :-(
        row = 0
        for row in range(0, self.rowCount()):
            try:
                self.real_height += (self.cellWidget(row, 0).sizeHint().height())
            except Exception as err:
                print(err)
                self.real_height += 30
        del(row)
        """

        return self.real_height


    def highlight_row(self, row):
        for column in range(0, self.columnCount()):
            if self.cellWidget(row, column) != None:
                self.cellWidget(row, column).highlight()

        # store current highlighted row for context menu
        self.highlighted_row = row


    def colorize_row(self, row):
        for column in range(0, self.columnCount()):
            if self.cellWidget(row, column) != None:
                self.cellWidget(row, column).colorize()


    @pyqtSlot()
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
        new_status = pyqtSignal()

        # send signal if next cell can be filled
        next_cell = pyqtSignal(int, int, str, str, str, list, str)

        # send signal if all cells are filled and table can be adjusted
        table_ready = pyqtSignal()

        # send signal if ready to stop
        finish = pyqtSignal()

        # send start and end of downtime
        set_start_end = pyqtSignal(str, str)

        # try to stop thread by evaluating this flag
        running = True

        # signal to be sent to slot "change" of ServerStatusLabel
        change_label_status = pyqtSignal(str)

        # signal to be sent to slot "restore" of ServerStatusLabel
        restore_label_status = pyqtSignal()

        # send notification a stop message if problems vanished without being noticed
        problems_vanished = pyqtSignal()

        # flag to keep recheck_all from being started more than once
        rechecking_all = False


        def __init__(self, parent=None, server=None):
            QObject.__init__(self)
            self.server = server
            # needed for update interval
            self.timer = QTimer(self)
            self.server.init_config()


        @pyqtSlot()
        def get_status(self):
            """
                check every second if thread still has to run
                if interval time is reached get status
            """
            # if counter is at least update interval get status
            if self.server.thread_counter >= conf.update_interval_seconds:
                # reflect status retrieval attempt on server vbox label
                self.change_label_status.emit('Refreshing...')
                # get status from server instance
                status = self.server.GetStatus()
                # all is OK if no error info came back
                if self.server.status_description == '':
                    self.change_label_status.emit('Connected')
                else:
                    # try to display some more user friendly error description
                    if status.error.startswith('requests.exceptions.ConnectTimeout'):
                        self.change_label_status.emit('Connection timeout')
                    elif status.error.startswith('requests.exceptions.ConnectionError'):
                        self.change_label_status.emit('Connection error')
                    else:
                        # kick out line breaks to avoid broken status window
                        self.change_label_status.emit(self.server.status_description.replace('\n', ''))

                # reset counter for this thread
                self.server.thread_counter = 0

                # if failures have gone and nobody took notice switch notification off again
                if len([k for k,v in self.server.events_history.items() if v == True]) == 0 and\
                        statuswindow.worker_notification.is_notifying == True and\
                        statuswindow.worker_notification.notifying_server == self.server.name:
                    # tell notification that unnoticed problems are gone
                    self.problems_vanished.emit()

                # tell news about new status available
                self.new_status.emit()

            # increase thread counter
            self.server.thread_counter += 1

            # if running flag is still set call myself after 1 second
            if self.running == True:
                self.timer.singleShot(1000, self.get_status)
            else:
                # tell tableview to finish worker_thread
                self.finish.emit()


        @pyqtSlot(list, str, bool)
        def fill_rows(self, data, sort_column, reverse):
            # to keep GTK Treeview sort behaviour first by services
            first_sort = sorted(data, key=methodcaller('compare_host'))
            for row, nagitem in enumerate(sorted(first_sort, key=methodcaller('compare_%s' % \
                                                    (sort_column)), reverse=reverse)):

                # on Qt 5.5.0 there is a bug in OSX version which renders tooltips useless
                # see https://bugreports.qt.io/browse/QTBUG-26669
                # thus disable tooltips on MacOSX
                # seems strange to use string '5.4.1' here but this is the PyQt version on Fink based OSX environment
                if not (platform.system() == 'Darwin' and QT_VERSION_STR == '5.4.1'):
                    # only if tooltips are wanted take status_information for the whole row
                    if conf.show_tooltips:
                        tooltip = '<div style=color:black;' \
                                  '           white-space:pre><b>{0}: {1}</b></div>' \
                                  '<div style=color:black>{2}</div>'.format(nagitem.host,
                                                        nagitem.service,
                                                        nagitem.status_information)
                    else:
                        tooltip = ''
                else:
                    tooltip = ''

                # store icon calculations in row_cache to increase painting speed
                row_cache = list()

                # lists in rows list are columns
                # create every cell per row
                for column, text in enumerate(nagitem.get_columns(HEADERS)):
                    # check for icons to be used in cell widget
                    if column in (0, 1):
                        # icons to be added
                        icons = list()
                        # hash for freshness comparison
                        hash = nagitem.get_hash()
                        # add host icons
                        if nagitem.is_host() and column == 0:
                            if nagitem.is_acknowledged():
                                icons.append(ICONS['acknowledged'])
                            if nagitem.is_flapping():
                                icons.append(ICONS['flapping'])
                            if nagitem.is_passive_only():
                                icons.append(ICONS['passive'])
                            if nagitem.is_in_scheduled_downtime():
                                icons.append(ICONS['downtime'])
                            if hash in self.server.events_history and\
                                       self.server.events_history[hash] == True:
                                        icons.append(ICONS['new'])
                        # add host icons for service item - e.g. in case host is in downtime
                        elif not nagitem.is_host() and column == 0:
                            if self.server.hosts[nagitem.host].is_acknowledged():
                                icons.append(ICONS['acknowledged'])
                            if self.server.hosts[nagitem.host].is_flapping():
                                icons.append(ICONS['flapping'])
                            if self.server.hosts[nagitem.host].is_passive_only():
                                icons.append(ICONS['passive'])
                            if self.server.hosts[nagitem.host].is_in_scheduled_downtime():
                                icons.append(ICONS['downtime'])
                        # add service icons
                        elif not nagitem.is_host() and column == 1:
                            if nagitem.is_acknowledged():
                                icons.append(ICONS['acknowledged'])
                            if nagitem.is_flapping():
                                icons.append(ICONS['flapping'])
                            if nagitem.is_passive_only():
                                icons.append(ICONS['passive'])
                            if nagitem.is_in_scheduled_downtime():
                                icons.append(ICONS['downtime'])
                            if hash in self.server.events_history and\
                                       self.server.events_history[hash] == True:
                                        icons.append(ICONS['new'])
                    else:
                        icons = [False]

                    # store text and icons in cache
                    row_cache.append({ 'text': text, 'icons': icons})

                # paint cells without extra icon calculation - done before
                for column in range(len(row_cache)):
                    # send signal to paint next cell
                    self.next_cell.emit(row, column, row_cache[column]['text'],
                                        conf.__dict__[COLORS[nagitem.status] + 'text'],
                                        conf.__dict__[COLORS[nagitem.status] + 'background'],
                                        row_cache[column]['icons'],
                                        tooltip)

                del(row_cache)

                # sleep some milliceconds to let the GUI thread do some work too
                self.thread().msleep(5)

            # after running through
            self.table_ready.emit()


        @pyqtSlot(dict)
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


        @pyqtSlot(dict)
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


        @pyqtSlot(dict)
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


        @pyqtSlot(dict)
        def recheck(self, info_dict):
            """
                Slot to start server recheck method, getting signal from TableWidget context menu
            """
            if conf.debug_mode:
                # host
                if info_dict['service'] == '':
                    self.server.Debug(server=self.server.name, debug='Rechecking host {0}'.format(info_dict['host']))
                else:
                    self.server.Debug(server=self.server.name, debug='Rechecking service {0} on host {1}'.format(info_dict['service'], info_dict['host']))
            # call server recheck method
            self.server.set_recheck(info_dict)


        @pyqtSlot()
        def recheck_all(self):
            """
                call server.set_recheck for every single host/service
            """
            # only if no already rechecking
            if self.rechecking_all == False:
                # block rechecking
                self.rechecking_all = True
                # change label of server vbox
                self.change_label_status.emit('Rechecking all...')
                if conf.debug_mode:
                    self.server.Debug(server=self.server.name, debug='Start rechecking all')
                # special treatment for Check_MK Multisite because there is only one URL call necessary
                if self.server.type != 'Check_MK Multisite':
                    # make a copy to preserve hosts/service to recheck - just in case something changes meanwhile
                    nagitems_filtered = deepcopy(self.server.nagitems_filtered)
                    for status in nagitems_filtered['hosts'].items():
                        for host in status[1]:
                            if conf.debug_mode:
                                self.server.Debug(server=self.server.name, debug='Rechecking host {0}'.format(host.name))
                            # call server recheck method
                            self.server.set_recheck({'host': host.name, 'service': ''})
                    for status in nagitems_filtered['services'].items():
                        for service in status[1]:
                            if conf.debug_mode:
                                self.server.Debug(server=self.server.name, debug='Rechecking service {0} on host {1}'.format(service.name, service.host))
                            # call server recheck method
                            self.server.set_recheck({'host': service.host, 'service': service.name})
                    del(nagitems_filtered, status)
                else:
                    # Check_MK Multisite does it its own way
                    self.server.recheck_all()
                # release rechecking lock
                self.rechecking = False
                # restore server status label
                self.restore_label_status.emit()
            else:
                if conf.debug_mode:
                    self.server.Debug(server=self.server.name, debug='Already rechecking all')

        @pyqtSlot(str, str)
        def get_start_end(self, server_name, host):
            """
                Investigates start and end time of a downtime asynchronously
            """
            # because every server listens to this signal the name has to be filtered
            if server_name == self.server.name:
                start, end = self.server.get_start_end(host)
                # send start/end time to slot
                self.set_start_end.emit(start, end)


        @pyqtSlot(dict, str)
        def execute_action(self, action, info):
            """
                runs action, may it be custom or included like the Check_MK actions
            """
            # first replace placeholder variables in string with actual values
            #
            #Possible values for variables:
            #$HOST$             - host as in monitor
            #$SERVICE$          - service as in monitor
            #$MONITOR$          - monitor address - not yet clear what exactly for
            #$MONITOR-CGI$      - monitor CGI address - not yet clear what exactly for
            #$ADDRESS$          - address of host, investigated by Server.GetHost()
            #$STATUS-INFO$      - status information
            #$USERNAME$         - username on monitor
            #$PASSWORD$         - username's password on monitor - whatever for
            #$COMMENT-ACK$      - default acknowledge comment
            #$COMMENT-DOWN$     - default downtime comment
            #$COMMENT-SUBMIT$   - default submit check result comment

            try:
                """

                what?

                # if run as custom action use given action definition from conf, otherwise use for URLs
                if 'action' in action:
                    string = action['string']
                    action_type = self.action.type
                else:
                    string = self.string
                    action_type = self.type
                """
                # used for POST request
                if 'cgi_data' in action:
                    cgi_data = action['cgi_data']
                else:
                    cgi_data = ''

                # mapping of variables and values
                mapping = { '$HOST$': info['host'],
                            '$SERVICE$': info['service'],
                            '$ADDRESS$': info['address'],
                            '$MONITOR$': info['monitor'],
                            '$MONITOR-CGI$': info['monitor-cgi'],
                            '$STATUS-INFO$': info['status-info'],
                            '$USERNAME$': info['username'],
                            '$PASSWORD$': info['password'],
                            '$COMMENT-ACK$': info['comment-ack'],
                            '$COMMENT-DOWN$': info['comment-down'],
                            '$COMMENT-SUBMIT$': info['comment-submit'],
                            }

                # take string form action
                string = action['string']

                # mapping mapping
                for i in mapping:
                    string = string.replace(i, mapping[i])

                # see what action to take
                if action['type'] == 'browser':
                    # debug
                    if conf.debug_mode == True:
                        self.server.Debug(server=self.server.name, host=self.host, service=self.service, debug='ACTION: BROWSER ' + string)
                    webbrowser.open(string)
                elif action['type'] == 'command':
                    # debug
                    if conf.debug_mode == True:
                        self.server.Debug(server=self.server.name, host=self.host, service=self.service, debug='ACTION: COMMAND ' + string)
                    subprocess.Popen(string, shell=True)
                elif action['type'] == 'url':
                    # Check_MK uses transids - if this occurs in URL its very likely that a Check_MK-URL is called
                    if '$TRANSID$' in string:
                        transid = servers[info['server']]._get_transid(info['host'], info['service'])
                        string = string.replace('$TRANSID$', transid).replace(' ', '+')
                    else:
                        # make string ready for URL
                        string = self._URLify(string)
                    # debug
                    if conf.debug_mode == True:
                        self.server.Debug(server=self.server.name, host=self.host, service=self.service, debug='ACTION: URL in background ' + string)
                    servers[info['server']].FetchURL(string)
                # used for example by Op5Monitor.py
                elif action['type'] == 'url-post':
                    # make string ready for URL
                    string = self._URLify(string)
                    # debug
                    if conf.debug_mode == True:
                        self.server.Debug(server=self.server.name, host=self.host, service=self.service, debug='ACTION: URL-POST in background ' + string)
                    servers[info['server']].FetchURL(string, cgi_data=cgi_data, multipart=True)
                """
                # special treatment for Check_MK/Multisite Transaction IDs, called by Multisite._action()
                elif ['action_type'] == 'url-check_mk-multisite':
                    if '?_transid=-1&' in string:
                        # Python format is of no use her, only web interface gives an transaction id
                        # since werk #0766 http://mathias-kettner.de/check_mk_werks.php?werk_id=766 a real transid is needed
                        transid = self.server._get_transid(self.host, self.service)
                        # insert fresh transid
                        string = string.replace('?_transid=-1&', '?_transid=%s&' % (transid))
                        string = string + '&actions=yes'
                        if info['service'] != '':
                            # if service exists add it and convert spaces to +
                            string = string + '&service=%s' % (info['service'].replace(' ', '+'))
                        # debug
                        if conf.debug_mode == True:
                            self.server.Debug(server=self.server.name, host=self.host, service=self.service, debug='ACTION: URL-Check_MK in background ' + string)

                        servers[info['server']].FetchURL(string)
                """
            except:
                import traceback
                traceback.print_exc(file=sys.stdout)

        def _URLify(self, string):
            """
                return a string that fulfills requirements for URLs
                exclude several chars
            """
            return urllib.parse.quote(string, ":/=?&@+")


        @pyqtSlot()
        def unfresh_event_history(self):
            # set all flagged-as-fresh-events to un-fresh
            for event in self.server.events_history.keys():
                self.server.events_history[event] = False


class Dialogs(object):
    """
        class for accessing all dialogs
    """
    def __init__(self):
        # settings main dialog
        self.settings = Dialog_Settings(Ui_settings_main)
        self.settings.initialize()

        # server settings dialog
        self.server = Dialog_Server(Ui_settings_server)
        self.server.initialize()

        # action settings dialog
        self.action = Dialog_Action(Ui_settings_action)
        self.action.initialize()

        # acknowledge dialog for miserable item context menu
        self.acknowledge = Dialog_Acknowledge(Ui_dialog_acknowledge)
        self.acknowledge.initialize()

        # downtime dialog for miserable item context menu
        self.downtime = Dialog_Downtime(Ui_dialog_downtime)
        self.downtime.initialize()

        # downtime dialog for miserable item context menu
        self.submit = Dialog_Submit(Ui_dialog_submit)
        self.submit.initialize()

        # file chooser Dialog
        self.file_chooser = QFileDialog()


class Dialog(QObject):
    """
        one single dialog
    """
    # dummy toggle dependencies
    TOGGLE_DEPS = {}
    # auxiliary list of checkboxes which HIDE some other widgets if triggered - for example proxy OS settings
    TOGGLE_DEPS_INVERTED = []
    # widgets that might be enabled/disebled depending on monitor server type
    VOLATILE_WIDGETS = {}
    # names of widgets and their defaults
    WIDGET_NAMES = {}
    # style stuff used by settings dialog for servers/actions listwidget
    GRAY = QBrush(Qt.gray)


    def __init__(self, dialog):
        QObject.__init__(self)
        self.window = QDialog()
        self.ui = dialog()
        self.ui.setupUi(self.window)
        # treat dialog content after pressing OK button
        self.ui.button_box.accepted.connect(self.ok)
        self.ui.button_box.rejected.connect(self.window.close)

        # QSignalMapper needed to connect all toggle-needing-checkboxes/radiobuttons to one .toggle()-method which
        # decides which sender to use as key in self.TOGGLE_DEPS
        self.signalmapper_toggles = QSignalMapper()

        # window position to be used to fix strange movement bug
        ###self.x = 0
        ###self.y = 0


    def initialize(self):
        """
            dummy initialize method
        """
        pass


    def show(self, tab=0):
        """
            simple how method, to be enriched
        """
        # reset window if only needs smaller screen estate
        self.window.adjustSize()
        self.window.show()


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
        # normal case - clock on checkbox activates more options
        else:
            if checkbox.isChecked():
                for widget in widgets:
                    widget.show()
            else:
                for widget in widgets:
                    widget.hide()


    @pyqtSlot(QWidget, bool)
    def toggle(self, checkbox, inverted=False):
        """
            change state of depending widgets, slot for signals from checkboxes in UI
        """
        self.toggle_visibility(checkbox, self.TOGGLE_DEPS[checkbox])


    def toggle_toggles(self):
        # apply toggle-dependencies between checkboxes as certain widgets
        for checkbox, widgets in self.TOGGLE_DEPS.items():
            # toggle visibility
            self.toggle_visibility(checkbox, widgets)
            # multiplex slot .toggle() by signal-mapping
            self.signalmapper_toggles.setMapping(checkbox, checkbox)
            checkbox.toggled.connect(self.signalmapper_toggles.map)

        # finally map signals with .sender() - [QWidget] is important!
        self.signalmapper_toggles.mapped[QWidget].connect(self.toggle)


    def fill_list(self, listwidget, config):
        """
             fill listwidget with items from config
        """
        for configitem in sorted(config, key=str.lower):
            listitem = QListWidgetItem(configitem)
            if config[configitem].enabled == False:
                listitem.setForeground(self.GRAY)
            listwidget.addItem(listitem)


    @pyqtSlot()
    def ok(self):
        # dummy OK treatment
        pass


class Dialog_Settings(Dialog):
    """
        class for settings dialog
    """

    # signal to be fired if OK button was clicked and new settinga applied
    changed = pyqtSignal()

    def __init__(self, dialog):
        Dialog.__init__(self, dialog)
        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in list
        self.TOGGLE_DEPS = {
                            # debug mode
                            self.ui.input_checkbox_debug_mode : [self.ui.input_checkbox_debug_to_file,
                                                         self.ui.input_lineedit_debug_file],
                            # regular expressions for filtering hosts
                            self.ui.input_checkbox_re_host_enabled : [self.ui.input_lineedit_re_host_pattern,
                                                                      self.ui.input_checkbox_re_host_reverse],
                             # regular expressions for filtering services
                            self.ui.input_checkbox_re_service_enabled : [self.ui.input_lineedit_re_service_pattern,
                                                                        self.ui.input_checkbox_re_service_reverse],
                            # regular expressions for filtering status information
                            self.ui.input_checkbox_re_status_information_enabled : [self.ui.input_lineedit_re_status_information_pattern,
                                                                                   self.ui.input_checkbox_re_status_information_reverse],
                            # display to use in fullscreen mode
                            self.ui.input_radiobutton_fullscreen : [self.ui.label_fullscreen_display,
                                                                    self.ui.input_combobox_fullscreen_display],
                            # notifications in general
                            self.ui.input_checkbox_notification : [self.ui.notification_groupbox],
                            # sound at all
                            self.ui.input_checkbox_notification_sound : [self.ui.notification_sounds_groupbox],
                            # custom sounds
                            self.ui.input_radiobutton_notification_custom_sound : [self.ui.notification_custom_sounds_groupbox],
                            # notification actions
                            self.ui.input_checkbox_notification_actions : [self.ui.notification_actions_groupbox],
                            # several notification actions depending on status
                            self.ui.input_checkbox_notification_action_warning : [self.ui.input_lineedit_notification_action_warning_string],
                            self.ui.input_checkbox_notification_action_critical : [self.ui.input_lineedit_notification_action_critical_string],
                            self.ui.input_checkbox_notification_action_down : [self.ui.input_lineedit_notification_action_down_string],
                            self.ui.input_checkbox_notification_action_ok : [self.ui.input_lineedit_notification_action_ok_string],

                            # single custom notification action
                            self.ui.input_checkbox_notification_custom_action : [self.ui.notification_custom_action_groupbox]
                            }

        # connect server buttons to server dialog
        self.ui.button_new_server.clicked.connect(self.new_server)
        self.ui.button_edit_server.clicked.connect(self.edit_server)
        self.ui.button_copy_server.clicked.connect(self.copy_server)
        self.ui.button_delete_server.clicked.connect(self.delete_server)

        # connect check-for-updates button to update check
        self.ui.button_check_for_new_version_now.clicked.connect(check_version.check)

        # connect action buttons to action dialog
        self.ui.button_new_action.clicked.connect(self.new_action)
        self.ui.button_edit_action.clicked.connect(self.edit_action)
        self.ui.button_copy_action.clicked.connect(self.copy_action)
        self.ui.button_delete_action.clicked.connect(self.delete_action)

        # connect custom sound file buttons
        self.ui.button_choose_warning.clicked.connect(self.choose_sound_file_warning)
        self.ui.button_choose_critical.clicked.connect(self.choose_sound_file_critical)
        self.ui.button_choose_down.clicked.connect(self.choose_sound_file_down)

        # connect custom sound file buttons
        self.ui.button_play_warning.clicked.connect(self.play_sound_file_warning)
        self.ui.button_play_critical.clicked.connect(self.play_sound_file_critical)
        self.ui.button_play_down.clicked.connect(self.play_sound_file_down)

        # only show desktop notification on systems that support it
        if not dbus_connection.connected:
            self.ui.input_checkbox_notification_desktop.hide()

        # set folder and play symbols to choose and play buttons
        self.ui.button_choose_warning.setText('')
        self.ui.button_choose_warning.setIcon(self.ui.button_play_warning.style().standardIcon(QStyle.SP_DirIcon))
        self.ui.button_play_warning.setText('')
        self.ui.button_play_warning.setIcon(self.ui.button_play_warning.style().standardIcon(QStyle.SP_MediaPlay))

        self.ui.button_choose_critical.setText('')
        self.ui.button_choose_critical.setIcon(self.ui.button_play_warning.style().standardIcon(QStyle.SP_DirIcon))
        self.ui.button_play_critical.setText('')
        self.ui.button_play_critical.setIcon(self.ui.button_play_warning.style().standardIcon(QStyle.SP_MediaPlay))

        self.ui.button_choose_down.setText('')
        self.ui.button_choose_down.setIcon(self.ui.button_play_warning.style().standardIcon(QStyle.SP_DirIcon))
        self.ui.button_play_down.setText('')
        self.ui.button_play_down.setIcon(self.ui.button_play_warning.style().standardIcon(QStyle.SP_MediaPlay))

        # QSignalMapper needed to connect all color buttons to color dialogs
        self.signalmapper_colors = QSignalMapper()

        # connect color buttons with color dialog
        for widget in [x for x in self.ui.__dict__ if x.startswith('input_button_color_')]:
            button = self.ui.__dict__[widget]
            item = widget.split('input_button_color_')[1]
            # multiplex slot for open color dialog by signal-mapping
            self.signalmapper_colors.setMapping(button, item)
            button.clicked.connect(self.signalmapper_colors.map)

        # connect reset and defaults buttons
        self.ui.button_colors_reset.clicked.connect(self.paint_colors)
        self.ui.button_colors_defaults.clicked.connect(self.colors_defaults)

        # finally map signals with .sender() - [<type>] is important!
        self.signalmapper_colors.mapped[str].connect(self.color_chooser)

        # apply toggle-dependencies between checkboxes as certain widgets
        self.toggle_toggles()


    #def initialize(self, start_tab=0):
    def initialize(self):
        # apply configuration values
        # start with servers tab
        self.ui.tabs.setCurrentIndex(0)
        for widget in dir(self.ui):
            if widget.startswith('input_'):
                if widget.startswith('input_checkbox_'):
                    if conf.__dict__[widget.split('input_checkbox_')[1]] == True:
                        self.ui.__dict__[widget].toggle()
                if widget.startswith('input_radiobutton_'):
                    if conf.__dict__[widget.split('input_radiobutton_')[1]] == True:
                        self.ui.__dict__[widget].toggle()
                if widget.startswith('input_lineedit_'):
                    # older versions of Nagstamon have a bool value for custom_action_separator
                    # which leads to a crash here - thus str() to solve this
                    self.ui.__dict__[widget].setText(str(conf.__dict__[widget.split('input_lineedit_')[1]]))
                if widget.startswith('input_spinbox_'):
                    self.ui.__dict__[widget].setValue(int(conf.__dict__[widget.split('input_spinbox_')[1]]))

        # just for fun: compare the next lines with the corresponding GTK madness... :-)

        # fill default order fields combobox with headers names
        self.ui.input_combobox_default_sort_field.addItems(HEADERS.values())
        self.ui.input_combobox_default_sort_field.setCurrentText(conf.default_sort_field)

        # fill default sort order combobox
        self.ui.input_combobox_default_sort_order.addItems(['Ascending', 'Descending'])
        self.ui.input_combobox_default_sort_order.setCurrentText(conf.default_sort_order)

        # fill combobox with screens for fullscreen
        for display in range(desktop.screenCount()):
            self.ui.input_combobox_fullscreen_display.addItem(str(display))
        self.ui.input_combobox_fullscreen_display.setCurrentText(str(conf.fullscreen_display))

        # fill servers listwidget with servers
        self.fill_list(self.ui.list_servers, conf.servers)

        # select first item
        self.ui.list_servers.setCurrentRow(0)

        # fill actions listwidget with actions
        ###for action in sorted(conf.actions, key=unicode.lower):
        for action in sorted(conf.actions, key=str.lower):
            self.ui.list_actions.addItem(action)
        # select first item
        self.ui.list_actions.setCurrentRow(0)

        # paint colors onto color selection buttons
        self.paint_colors()

        # important final size adjustment
        self.window.adjustSize()


    def show(self, tab=0):
        # jump to actions tab in settings dialog
        self.ui.tabs.setCurrentIndex(tab)

        # reset window if only needs smaller screen estate
        self.window.adjustSize()
        self.window.show()


    def  ok(self):
        # store position of statuswindow/statusbar only if statusbar is floating
        if conf.statusbar_floating:
            statuswindow.store_position_to_conf()

        # do all stuff necessary after OK button was clicked
        # put widget values into conf
        for widget in self.ui.__dict__.values():
            if widget.objectName().startswith('input_checkbox_'):
                conf.__dict__[widget.objectName().split('input_checkbox_')[1]] = widget.isChecked()
            if widget.objectName().startswith('input_radiobutton_'):
                conf.__dict__[widget.objectName().split('input_radiobutton_')[1]] = widget.isChecked()
            if widget.objectName().startswith("input_lineedit_"):
                conf.__dict__[widget.objectName().split('input_lineedit_')[1]] = widget.text()
            if widget.objectName().startswith('input_spinbox_'):
                conf.__dict__[widget.objectName().split('input_spinbox_')[1]] = str(widget.value())
            if widget.objectName().startswith('input_button_color_'):
                # get color value from color button stylesheet
                color = self.ui.__dict__[widget.objectName()].styleSheet()
                color = color.split(':')[1].strip().split(';')[0]
                conf.__dict__[widget.objectName().split('input_button_')[1]] = color

        # convert some strings to integers and bools
        for item in conf.__dict__:
            if type(conf.__dict__[item]) == str:
                if conf.__dict__[item] in BOOLPOOL:
                    conf.__dict__[item] = BOOLPOOL[conf.__dict__[item]]
                elif conf.__dict__[item].isdecimal():
                    conf.__dict__[item] = int(conf.__dict__[item])

        # start debug loop if debugging is enabled
        if conf.debug_mode:
            # only start debugging loop if it not already loops
            if statuswindow.worker.debug_loop_looping == False:
                statuswindow.worker.start_debug_loop.emit()
        else:
            # set flag to tell debug loop it should stop please
            statuswindow.worker.debug_loop_looping = False

        # store configuration
        conf.SaveConfig()

        # tell statuswindow to refresh due to new settings
        self.changed.emit()


    @pyqtSlot()
    def new_server(self):
        """
            create new server
        """
        dialogs.server.new()


    @pyqtSlot()
    def edit_server(self):
        """
            edit existing server
        """
        dialogs.server.edit()


    @pyqtSlot()
    def copy_server(self):
        """
            copy existing server
        """
        dialogs.server.copy()


    @pyqtSlot()
    def delete_server(self):
        """
            delete server, stop its thread, remove from config and list
        """
        # server to delete from current row in servers list
        server = conf.servers[self.ui.list_servers.currentItem().text()]

        reply = QMessageBox.question(self.window, 'Nagstamon',
                                     'Do you really want to delete monitor server <b>%s</b>?' % (server.name),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
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
            row = self.ui.list_servers.currentRow()
            # count real number, 1 to x
            count = self.ui.list_servers.count()

            # if deleted row was the last line the new current row has to be the new last line, accidently the same as count
            if row == count - 1:
                # use the penultimate item as the new current one
                row = count - 2
            else:
                # go down one row
                row = row + 1

            # refresh list and mark new current row
            self.refresh_list(list_widget=self.ui.list_servers,
                              list_conf=conf.servers,
                              current=self.ui.list_servers.item(row).text())

            del(row, count)

        del(server)


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
        list_widget.setCurrentItem(list_widget.findItems(current, Qt.MatchExactly)[0])


    @pyqtSlot()
    def new_action(self):
        """
            create new action
        """
        dialogs.action.new()


    @pyqtSlot()
    def edit_action(self):
        """
            edit existing action
        """
        dialogs.action.edit()


    @pyqtSlot()
    def copy_action(self):
        """
            copy existing action and edit it
        """
        dialogs.action.copy()


    @pyqtSlot()
    def delete_action(self):
        """
            delete action remove from config and list
        """
        # action to delete from current row in actions list
        action = conf.actions[self.ui.list_actions.currentItem().text()]

        reply = QMessageBox.question(self.window, 'Nagstamon',
                                     'Do you really want to delete action <b>%s</b>?' % (action.name),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # kick action out of config items
            conf.actions.pop(action.name)

            # refresh list
            # row index 0 to x
            row = self.ui.list_actions.currentRow()
            # count real number, 1 to x
            count = self.ui.list_actions.count()

            # if deleted row was the last line the new current row has to be the new last line, accidently the same as count
            if row == count - 1:
                # use the penultimate item as the new current one
                row = count - 2
            else:
                # go down one row
                row = row + 1

            # refresh list and mark new current row
            self.refresh_list(list_widget=self.ui.list_actions, list_conf=conf.actions, current=self.ui.list_actions.item(row).text())

            del(row, count)

        del(action)


    def choose_sound_file_decoration(method):
        """
            try to decorate sound file dialog
        """
        def decoration_function(self):
            # execute decorated function
            method(self)
            # shortcut for widget to fill and revaluate
            widget = self.ui.__dict__['input_lineedit_notification_custom_sound_%s' % self.sound_file_type]

            # use 2 filters, sound files and all files
            file = dialogs.file_chooser.getOpenFileName(self.window,
                                                       filter = 'Sound files (*.mp3 *.MP3 *.mp4 *.MP4 '
                                                                             '*.wav *.WAV *.ogg *.OGG);;'
                                                                'All files (*)')[0]

            # only take filename if QFileDialog gave something useful back
            if file != "":
                widget.setText(file)

        return(decoration_function)

    @choose_sound_file_decoration
    @pyqtSlot()
    def choose_sound_file_warning(self):
        self.sound_file_type = 'warning'


    @choose_sound_file_decoration
    @pyqtSlot()
    def choose_sound_file_critical(self):
        self.sound_file_type = 'critical'


    @choose_sound_file_decoration
    @pyqtSlot()
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
            widget = self.ui.__dict__['input_lineedit_notification_custom_sound_%s' % self.sound_file_type]

            # get file path from widget
            file = widget.text()

            # tell mediaplayer to play file only if it exists
            if mediaplayer.set_media(file) == True:
                mediaplayer.play.emit()

        return(decoration_function)

    @play_sound_file_decoration
    @pyqtSlot()
    def play_sound_file_warning(self):
        self.sound_file_type = 'warning'


    @play_sound_file_decoration
    @pyqtSlot()
    def play_sound_file_critical(self):
        self.sound_file_type = 'critical'


    @play_sound_file_decoration
    @pyqtSlot()
    def play_sound_file_down(self):
        self.sound_file_type = 'down'


    def paint_colors(self):
        """
            fill color selection buttons with appropriate colors
        """
        # color buttons
        for color in [x for x in conf.__dict__ if x.startswith('color_')]:
            self.ui.__dict__['input_button_%s' % (color)].setStyleSheet('background-color: %s;'
                                                                        'border-width: 1px;'
                                                                        'border-color: black;'
                                                                        'border-style: solid;'
                                                                         % conf.__dict__[color])
        # example color labels
        for label in [x for x in self.ui.__dict__ if x.startswith('label_color_')]:
            status = label.split('label_color_')[1]
            self.ui.__dict__[label].setStyleSheet('color: %s; background: %s' %
                                                  (conf.__dict__['color_%s_text' % (status)],
                                                  (conf.__dict__['color_%s_background' % (status)])))


    @pyqtSlot()
    def colors_defaults(self):
        """
            apply default colors to buttons
        """
        # color buttons
        for default_color in [x for x in conf.__dict__ if x.startswith('default_color_')]:
            # cut 'default_' off to get color
            color = default_color.split('default_')[1]
            self.ui.__dict__['input_button_%s' % (color)].setStyleSheet('background-color: %s;'
                                                                        'border-width: 1px;'
                                                                        'border-color: black;'
                                                                        'border-style: solid;'
                                                                         % conf.__dict__[default_color])
        # example color labels
        for label in [x for x in self.ui.__dict__ if x.startswith('label_color_')]:
            status = label.split('label_color_')[1]

            # get color values from color button stylesheets
            color_text = self.ui.__dict__['input_button_color_' + status + '_text'].styleSheet()
            color_text = color_text.split(':')[1].strip().split(';')[0]
            color_background = self.ui.__dict__['input_button_color_' + status + '_background'].styleSheet()
            color_background = color_background.split(':')[1].strip().split(';')[0]

            # apply color values from stylesheet to label
            self.ui.__dict__[label].setStyleSheet('color: %s; background: %s' %
                                                  (color_text, color_background))

    @pyqtSlot(str)
    def color_chooser(self, item):
        """
            open QColorDialog to choose a color and change it in settings dialog
        """
        color = conf.__dict__['color_%s' % (item)]

        new_color = QColorDialog.getColor(QColor(color), parent=self.window)
        # if canceled the color is invalid
        if new_color.isValid():
            self.ui.__dict__['input_button_color_%s' % (item)].setStyleSheet('background-color: %s;'
                                                                             'border-width: 1px;'
                                                                             'border-color: black;'
                                                                             'border-style: solid;'
                                                                             % new_color.name())
            status = item.split('_')[0]
            # get color value from stylesheet to paint example
            text = self.ui.__dict__['input_button_color_%s_text' % (status)].styleSheet()
            text = text.split(':')[1].strip().split(';')[0]
            background = self.ui.__dict__['input_button_color_%s_background' % (status)].styleSheet()
            background = background.split(':')[1].strip().split(';')[0]
            # set example color
            self.ui.__dict__['label_color_%s' % (status)].setStyleSheet('color: %s; background: %s' %
                                                                       (text, background))


class Dialog_Server(Dialog):
    """
        Dialog used to setup one single server
    """
    def __init__(self, dialog):
        Dialog.__init__(self, dialog)
        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in list
        self.TOGGLE_DEPS = {
                            self.ui.input_checkbox_use_autologin : [self.ui.label_autologin_key,
                                                                    self.ui.input_lineedit_autologin_key],
                            self.ui.input_checkbox_use_proxy : [self.ui.proxy_groupbox],

                            self.ui.input_checkbox_use_proxy_from_os : [self.ui.label_proxy_address,
                                                                        self.ui.input_lineedit_proxy_address,
                                                                        self.ui.label_proxy_username,
                                                                        self.ui.input_lineedit_proxy_username,
                                                                        self.ui.label_proxy_password,
                                                                        self.ui.input_lineedit_proxy_password]
                            }

        self.TOGGLE_DEPS_INVERTED = [self.ui.input_checkbox_use_proxy_from_os]

        # these widgets are shown or hidden depending on server type properties
        # the servers listed at each widget do need them
        self.VOLATILE_WIDGETS = {
                                 self.ui.label_monitor_cgi_url : ['Nagios', 'Icinga', 'Opsview','Thruk'],
                                 self.ui.input_lineedit_monitor_cgi_url : ['Nagios', 'Icinga', 'Opsview','Thruk'],
                                 self.ui.input_checkbox_use_autologin : ['Centreon'],
                                 self.ui.input_lineedit_autologin_key : ['Centreon'],
                                 self.ui.label_autologin_key : ['Centreon'],
                                 self.ui.input_checkbox_use_display_name_host : ['Icinga'],
                                 self.ui.input_checkbox_use_display_name_service : ['Icinga']
                                }

        # fill default order fields combobox with monitor server types
        self.ui.input_combobox_type.addItems(sorted(SERVER_TYPES.keys(), key=str.lower))
        # default to Nagios as it is the mostly used monitor server
        self.ui.input_combobox_type.setCurrentText('Nagios')

        # detect change of server type which leads to certain options shown or hidden
        self.ui.input_combobox_type.activated.connect(self.server_type_changed)

        # mode needed for evaluate dialog after ok button pressed - defaults to 'new'
        self.mode = 'new'


    @pyqtSlot(int)
    def server_type_changed(self, server_type_index=0):
        # server_type_index is not needed - we get the server type from .currentText()
        # check if server type is listed in volatile widgets to decide if it has to be shown or hidden
        for widget, server_types in self.VOLATILE_WIDGETS.items():
            if self.ui.input_combobox_type.currentText() in server_types:
                widget.show()
            else:
                widget.hide()


    def dialog_decoration(method):
        """
            try with a decorator instead of repeated calls
        """
        # function which decorates method
        def decoration_function(self, **kwargs):
            """
                self.server_conf has to be set by decorated method
            """

            # call decorated method
            method(self, **kwargs)

            # run through all input widgets and and apply defaults from config
            for widget in self.ui.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.ui.__dict__[widget].setChecked(self.server_conf.__dict__[setting])
                    if widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.ui.__dict__[widget].setChecked(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.ui.__dict__[widget].setCurrentText(self.server_conf.__dict__[setting])
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.ui.__dict__[widget].setText(self.server_conf.__dict__[setting])

            # initially hide not needed widgets
            self.server_type_changed()

            # apply toggle-dependencies between checkboxes and certain widgets
            self.toggle_toggles()

            # important final size adjustment
            self.window.adjustSize()

            self.window.show()

        # give back decorated function
        return(decoration_function)


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
    def edit(self, server_name=None):
        """
            edit existing server
            when called by Edit button in ServerVBox use given server_name to get server config
        """
        self.mode = 'edit'
        # shorter server conf
        if server_name == None:
            self.server_conf = conf.servers[dialogs.settings.ui.list_servers.currentItem().text()]
        else:
            self.server_conf = conf.servers[server_name]
        # store monitor name in case it will be changed
        self.previous_server_conf = deepcopy(self.server_conf)
        # set window title
        self.window.setWindowTitle('Edit %s' % (self.server_conf.name))


    @dialog_decoration
    def copy(self):
        """
            copy existing server
        """
        self.mode = 'copy'
        # shorter server conf
        self.server_conf = deepcopy(conf.servers[dialogs.settings.ui.list_servers.currentItem().text()])
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

        # check that no duplicate name exists
        if self.ui.input_lineedit_name.text() in conf.servers and \
          (self.mode in ['new', 'copy'] or
           self.mode == 'edit' and self.server_conf != conf.servers[self.ui.input_lineedit_name.text()]):
            # cry if duplicate name exists
            QMessageBox.critical(self.window, 'Nagstamon',
                                 'The monitor server name <b>%s</b> is already used.' %\
                                 (self.ui.input_lineedit_name.text()),
                                 QMessageBox.Ok)
        else:
            # get configuration from UI
            for widget in self.ui.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.server_conf.__dict__[setting] = self.ui.__dict__[widget].isChecked()
                    if widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.server_conf.__dict__[setting] = self.ui.__dict__[widget].isChecked()
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.server_conf.__dict__[setting] = self.ui.__dict__[widget].currentText()
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.server_conf.__dict__[setting] =  self.ui.__dict__[widget].text()

            # URLs should not end with / - clean it
            self.server_conf.monitor_url = self.server_conf.monitor_url.rstrip('/')
            self.server_conf.monitor_cgi_url = self.server_conf.monitor_cgi_url.rstrip('/')

            # convert some strings to integers and bools
            for item in self.server_conf.__dict__:
                if type(self.server_conf.__dict__[item]) == str:
                    if self.server_conf.__dict__[item] in BOOLPOOL:
                        self.server_conf.__dict__[item] = BOOLPOOL[self.server_conf.__dict__[item]]
                    elif self.server_conf.__dict__[item].isdecimal():
                        self.server_conf.__dict__[item] = int(self.server_conf.__dict__[item])

            # edited servers will be deleted and recreated with new configuration
            if self.mode == 'edit':
                # remove old server vbox from status window if still running
                for vbox in statuswindow.servers_vbox.children():
                    if vbox.server.name == self.previous_server_conf.name:
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

            # add new server configuration in every case
            conf.servers[self.server_conf.name] = self.server_conf

            # add new server instance to global servers dict
            servers[self.server_conf.name] = create_server(self.server_conf)

            if self.server_conf.enabled == True:
                # create vbox
                statuswindow.servers_vbox.addLayout(statuswindow.create_ServerVBox(servers[self.server_conf.name]))
                # renew list of server vboxes in status window
                statuswindow.sort_ServerVBoxes()

            # reorder servers in dict to reflect changes
            servers = OrderedDict(sorted(servers.items()))

            # some monitor servers do not need cgi-url - reuse self.VOLATILE_WIDGETS to find out which one
            if not self.server_conf.type in self.VOLATILE_WIDGETS[self.ui.input_lineedit_monitor_cgi_url]:
                self.server_conf.monitor_cgi_url = self.server_conf.monitor_url

            # refresh list of servers, give call the current server name to highlight it
            dialogs.settings.refresh_list(list_widget=dialogs.settings.ui.list_servers,
                                          list_conf=conf.servers,
                                          current=self.server_conf.name)

            self.window.close()

            # store server settings
            conf.SaveMultipleConfig("servers", "server")


class Dialog_Action(Dialog):
    """
        Dialog used to setup one single action
    """
    def __init__(self, dialog):
        Dialog.__init__(self, dialog)

        # define checkbox-to-widgets dependencies which apply at initialization
        # which widgets have to be hidden because of irrelevance
        # dictionary holds checkbox/radiobutton as key and relevant widgets in list
        self.TOGGLE_DEPS = {
                            self.ui.input_checkbox_re_host_enabled : [self.ui.input_lineedit_re_host_pattern,
                                                                      self.ui.input_checkbox_re_host_reverse],
                            self.ui.input_checkbox_re_service_enabled : [self.ui.input_lineedit_re_service_pattern,
                                                                         self.ui.input_checkbox_re_service_reverse],

                            self.ui.input_checkbox_re_status_information_enabled : [self.ui.input_lineedit_re_status_information_pattern,
                                                                        self.ui.input_checkbox_re_status_information_reverse]
                            }

        # fill action types into combobox
        self.ui.input_combobox_type.addItems(["Browser", "Command", "URL"])

        # fill default order fields combobox with monitor server types
        self.ui.input_combobox_monitor_type.addItem("All monitor servers")
        self.ui.input_combobox_monitor_type.addItems(sorted(SERVER_TYPES.keys(), key=str.lower))
        # default to Nagios as it is the mostly used monitor server
        self.ui.input_combobox_monitor_type.setCurrentIndex(0)


    def dialog_decoration(method):
        """
            try with a decorator instead of repeated calls
        """
        # function which decorates method
        def decoration_function(self):
            """
                self.server_conf has to be set by decorated method
            """
            # call decorated method
            method(self)

            # run through all input widgets and and apply defaults from config
            for widget in self.ui.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.ui.__dict__[widget].setChecked(self.action_conf.__dict__[setting])
                    if widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.ui.__dict__[widget].setChecked(self.action_conf.__dict__[setting])
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.ui.__dict__[widget].setCurrentText(self.action_conf.__dict__[setting])
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.ui.__dict__[widget].setText(self.action_conf.__dict__[setting])
                    elif widget.startswith('input_textedit_'):
                        setting = widget.split('input_textedit_')[1]
                        self.ui.__dict__[widget].setText(self.action_conf.__dict__[setting])

            # apply toggle-dependencies between checkboxes and certain widgets
            self.toggle_toggles()

            # important final size adjustment
            self.window.adjustSize()

            self.window.show()

        # give back decorated function
        return(decoration_function)


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
        self.action_conf = conf.actions[dialogs.settings.ui.list_actions.currentItem().text()]
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
        self.action_conf = deepcopy(conf.actions[dialogs.settings.ui.list_actions.currentItem().text()])
        # set window title before name change to reflect copy
        self.window.setWindowTitle('Copy %s' % (self.action_conf.name))
        # indicate copy of other action
        self.action_conf.name = 'Copy of ' + self.action_conf.name


    def ok(self):
        """
            evaluate state of widgets to get new configuration
        """
        # check that no duplicate name exists
        if self.ui.input_lineedit_name.text() in conf.actions and \
          (self.mode in ['new', 'copy'] or
           self.mode == 'edit' and self.action_conf != conf.actions[self.ui.input_lineedit_name.text()]):
            # cry if duplicate name exists
            QMessageBox.critical(self.window, 'Nagstamon',
                                 'The action name <b>%s</b> is already used.' %\
                                 (self.ui.input_lineedit_name.text()),
                                 QMessageBox.Ok)
        else:
            # get configuration from UI
            for widget in self.ui.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.action_conf.__dict__[setting] = self.ui.__dict__[widget].isChecked()
                    if widget.startswith('input_radiobutton_'):
                        setting = widget.split('input_radiobutton_')[1]
                        self.action_conf.__dict__[setting] = self.ui.__dict__[widget].isChecked()
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.action_conf.__dict__[setting] = self.ui.__dict__[widget].currentText()
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.action_conf.__dict__[setting] =  self.ui.__dict__[widget].text()
                    elif widget.startswith('input_textedit_'):
                        setting = widget.split('input_textedit_')[1]
                        self.action_conf.__dict__[setting] =  self.ui.__dict__[widget].toPlainText()

            # edited action will be deleted and recreated with new configuration
            if self.mode == 'edit':
                # delete previous name
                conf.actions.pop(self.previous_action_conf.name)

            # add edited  or new/copied action
            conf.actions[self.action_conf.name] = self.action_conf

            # refresh list of servers, give call the current server name to highlight it
            dialogs.settings.refresh_list(list_widget=dialogs.settings.ui.list_actions,
                                          list_conf=conf.actions,
                                          current=self.action_conf.name)

            # store server settings
            conf.SaveMultipleConfig("actions", "action")


class Dialog_Acknowledge(Dialog):
    """
        Dialog for acknowledging host/service problems
    """

    # store host and service to be used for OK button evaluation
    server = None
    host = service = ''

    # tell worker to acknowledge some troublesome item
    acknowledge = pyqtSignal(dict)


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
            self.window.setWindowTitle('Acknowledge host')
            self.ui.input_label_description.setText('Host <b>%s</b>' % (host))
        else:
            # set label for acknowledging a service on host
            self.window.setWindowTitle('Acknowledge service')
            self.ui.input_label_description.setText('Service <b>%s</b> on host <b>%s</b>' % (service, host))

        # default flags of monitor acknowledgement
        self.ui.input_checkbox_sticky_acknowledgement.setChecked(conf.defaults_acknowledge_sticky)
        self.ui.input_checkbox_send_notification.setChecked(conf.defaults_acknowledge_send_notification)
        self.ui.input_checkbox_persistent_comment.setChecked(conf.defaults_acknowledge_persistent_comment)
        self.ui.input_checkbox_acknowledge_all_services.setChecked(conf.defaults_acknowledge_all_services)

        # default author + comment
        self.ui.input_lineedit_comment.setText(conf.defaults_acknowledge_comment)
        self.ui.input_lineedit_comment.setFocus()


    def ok(self):
        """
            acknowledge miserable host/service
        """
        # create a list of all service of selected host to acknowledge them all
        all_services = list()
        acknowledge_all_services = self.ui.input_checkbox_acknowledge_all_services.isChecked()

        if acknowledge_all_services == True:
            for i in self.server.nagitems_filtered["services"].values():
                for s in i:
                    if s.host == self.host:
                        all_services.append(s.name)

        # send signal to tablewidget worker to care about acknowledging with supplied information
        self.acknowledge.emit({'server': self.server,
                               'host': self.host,
                               'service': self.service,
                               'author': self.server.username,
                               'comment': self.ui.input_lineedit_comment.text(),
                               'sticky': self.ui.input_checkbox_sticky_acknowledgement.isChecked(),
                               'notify': self.ui.input_checkbox_send_notification.isChecked(),
                               'persistent': self.ui.input_checkbox_persistent_comment.isChecked(),
                               'acknowledge_all_services': acknowledge_all_services,
                               'all_services': all_services})


class Dialog_Downtime(Dialog):
    """
        Dialog for putting hosts/services into downtime
    """

    # send signal to get start and end of a downtime asynchronously
    get_start_end = pyqtSignal(str, str)

    # signal to tell worker to commit downtime
    downtime = pyqtSignal(dict)

    # store host and service to be used for OK button evaluation
    server = None
    host = service = ''

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
            self.window.setWindowTitle('Downtime for host')
            self.ui.input_label_description.setText('Host <b>%s</b>' % (host))
        else:
            # set label for acknowledging a service on host
            self.window.setWindowTitle('Downtime for service')
            self.ui.input_label_description.setText('Service <b>%s</b> on host <b>%s</b>' % (service, host))

        # default flags of monitor acknowledgement
        self.ui.input_spinbox_duration_hours.setValue(int(conf.defaults_downtime_duration_hours))
        self.ui.input_spinbox_duration_minutes.setValue(int(conf.defaults_downtime_duration_minutes))
        self.ui.input_radiobutton_type_fixed.setChecked(conf.defaults_downtime_type_fixed)
        self.ui.input_radiobutton_type_flexible.setChecked(conf.defaults_downtime_type_flexible)

        self.ui.input_lineedit_start_time.setText('n/a')
        self.ui.input_lineedit_end_time.setText('n/a')

        # default author + comment
        self.ui.input_lineedit_comment.setText(conf.defaults_downtime_comment)
        self.ui.input_lineedit_comment.setFocus()

        if self.server != None:
            # at first initialization server is still None
            self.get_start_end.emit(self.server.name, self.host)


    def ok(self):
        """
            schedule downtime for miserable host/service
        """
        # type of downtime - fixed or flexible
        if self.ui.input_radiobutton_type_fixed.isChecked() == True:
            fixed = 1
        else:
            fixed = 0

        self.downtime.emit({'server': self.server,
                            'host': self.host,
                            'service': self.service,
                            'author': self.server.username,
                            'comment': self.ui.input_lineedit_comment.text(),
                            'fixed': fixed,
                            'start_time': self.ui.input_lineedit_start_time.text(),
                            'end_time': self.ui.input_lineedit_end_time.text(),
                            'hours': int(self.ui.input_spinbox_duration_hours.value()),
                            'minutes': int(self.ui.input_spinbox_duration_minutes.value())})


    pyqtSlot(str, str)
    def set_start_end(self, start, end):
        """
            put values sent by worker into start and end fields
        """
        self.ui.input_lineedit_start_time.setText(start)
        self.ui.input_lineedit_end_time.setText(end)


class Dialog_Submit(Dialog):
    """
        Dialog for submitting arbitrarily chosen results
    """
    # store host and service to be used for OK button evaluation
    server = None
    host = service = ''

    submit = pyqtSignal(dict)

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
            self.ui.input_label_description.setText('Host <b>%s</b>' % (host))
            # services do not need all states
            self.ui.input_radiobutton_result_up.show()
            self.ui.input_radiobutton_result_ok.hide()
            self.ui.input_radiobutton_result_warning.hide()
            self.ui.input_radiobutton_result_critical.hide()
            self.ui.input_radiobutton_result_unknown.show()
            self.ui.input_radiobutton_result_unreachable.show()
            self.ui.input_radiobutton_result_down.show()
            # activate first radiobutton
            self.ui.input_radiobutton_result_up.setChecked(True)
        else:
            # set label for acknowledging a service on host
            self.window.setWindowTitle('Submit check result for service')
            self.ui.input_label_description.setText('Service <b>%s</b> on host <b>%s</b>' % (service, host))
            # hosts do not need all states
            self.ui.input_radiobutton_result_up.hide()
            self.ui.input_radiobutton_result_ok.show()
            self.ui.input_radiobutton_result_warning.show()
            self.ui.input_radiobutton_result_critical.show()
            self.ui.input_radiobutton_result_unknown.show()
            self.ui.input_radiobutton_result_unreachable.hide()
            self.ui.input_radiobutton_result_down.hide()
            # activate first radiobutton
            self.ui.input_radiobutton_result_ok.setChecked(True)

        # clear text fields
        self.ui.input_lineedit_check_output.setText('')
        self.ui.input_lineedit_performance_data.setText('')
        self.ui.input_lineedit_comment.setText(conf.defaults_submit_check_result_comment)
        self.ui.input_lineedit_check_output.setFocus()


    def ok(self):
        """
            submit arbitrary check result
        """
        # default state
        state = "ok"

        for button in ["ok", "up", "warning", "critical", "unreachable", "unknown", "down"]:
            if self.ui.__dict__['input_radiobutton_result_' + button ].isChecked():
                state = button
                break

        # tell worker to submit
        self.submit.emit({'server': self.server,
                          'host': self.host,
                          'service': self.service,
                          'state': state,
                          'comment': self.ui.input_lineedit_comment.text(),
                          'check_output': self.ui.input_lineedit_check_output.text(),
                          'performance_data': self.ui.input_lineedit_performance_data.text()})


class MediaPlayer(QObject):
    """
        play media files for notification
    """
    # needed to show error in a thread-safe way
    send_message = pyqtSignal(str, str)

    def __init__(self):
        QObject.__init__(self)
        self.player = QMediaPlayer(parent=self)

        self.player.setVolume(100)
        self.playlist = QMediaPlaylist()
        self.player.setPlaylist(self.playlist)

        # let statuswindow show message
        self.send_message.connect(statuswindow.show_message)
        # connect with statuswindow notification worker
        statuswindow.worker_notification.load_sound.connect(self.set_media)
        statuswindow.worker_notification.play_sound.connect(self.play)


    @pyqtSlot(str)
    def set_media(self, file):
        # only existing file can be played
        if os.path.exists(file):
            url = QUrl.fromLocalFile(file)
            mediacontent = QMediaContent(url)
            self.player.setMedia(mediacontent)
            del url, mediacontent
            return True
        else:
            # cry and tell no file was found
            self.send_message.emit('warning', 'File <b>\'{0}\'</b> does not exist.'.format(file))
            return False


    @pyqtSlot()
    def play(self):
        # just play sound
        self.player.play()


class CheckVersion(QObject):
    """
        checking for updates
    """

    def check(self, start_mode=False):
        # list of enabled servers which connections outside should be used to check
        self.enabled_servers = get_enabled_servers()

        # set mode to be evaluated by worker
        self.start_mode = start_mode

        # thread for worker to avoid
        self.worker_thread = QThread()
        self.worker = self.Worker()

        # if update check is ready it sends the message to GUI thread
        self.worker.ready.connect(self.show_message)

        # stop thread if worker has finished
        self.worker.finished.connect(self.worker_thread.quit)

        self.worker.moveToThread(self.worker_thread)
        # run check when thread starts
        self.worker_thread.started.connect(self.worker.check)
        self.worker_thread.start(0)


    @pyqtSlot(str)
    def show_message(self, message):
        """
            message dialog must be shown from GUI thread
        """
        QMessageBox.information(None, 'Nagstamon version check',  message, QMessageBox.Ok)


    class Worker(QObject):
        """
            check for new version in background
        """
        # send signal if some version information is available
        ready = pyqtSignal(str)

        finished = pyqtSignal()

        def __init__(self):
            QObject.__init__(self)


        def check(self):
            """
                check for update using server connection
            """
            # get servers to be used for checking version
            enabled_servers = get_enabled_servers()

            # default latest version is 'unavailable'
            latest_version = 'unavailable'
            message = 'Cannot reach version check at <a href={0}>{0}</<a>.'.format(AppInfo.VERSION_URL)

            # find at least one server which allows to get version information
            for server in enabled_servers:

                # retrieve VERSION_URL without auth information
                response = server.FetchURL(AppInfo.VERSION_URL, giveback='raw', no_auth=True)

                # stop searching if some valid information has been found
                if response.error == "" and not response.result.startswith('<'):
                    latest_version = response.result.strip()
                    break

            # compose message according to version information
            if latest_version != 'unavailable':
                if latest_version == AppInfo.VERSION:
                    message = 'You are using the latest version <b>Nagstamon {0}</b>.'.format(AppInfo.VERSION)
                else:
                    message = 'The new version <b> Nagstamon {0}</b> is available.<p>' \
                              'Get it at <a href={1}>{1}</a>.'.format(latest_version, AppInfo.WEBSITE + '/nagstamon-20')

            # if run from startup do not cry if any error occured or nothing new is available
            if check_version.start_mode == False or\
               (check_version.start_mode == True and latest_version not in ('unavailable', AppInfo.VERSION)):
                self.ready.emit(message)

            # tell thread to finish
            self.finished.emit()


class DBus(object):
    """
        Create connection to DBus for desktop notification for Linux/Unix
    """
    def __init__(self):

        self.id = 0
        self.actions = []
        self.timeout = 0
        # in case Nagstamon is installed by package manager use its icon
        self.icon = 'nagstamon'
        # use Nagstamon image if icon is not available from system
        # see https://developer.gnome.org/notification-spec/#icons-and-images
        self.hints = {'image-path': '%s%snagstamon.svg' % (RESOURCES, os.sep)}

        if not platform.system() in ['Darwin', 'Windows']:
            if 'dbus' in sys.modules:
                dbus_mainloop = DBusQtMainLoop(set_as_default=True)
                dbus_bus = SessionBus(dbus_mainloop)
                dbus_object = dbus_bus.get_object('org.freedesktop.Notifications',
                                              '/org/freedesktop/Notifications')
                self.dbus_interface = Interface(dbus_object,
                                                dbus_interface='org.freedesktop.Notifications')
                self.connected = True
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


def _create_icons(fontsize):
    """
        fill global ICONS with pixmaps rendered from SVGs in fontsize dimensions
    """

    print('Reminder: fontsize is not used in _create_icons().')

    for attr in ('acknowledged', 'downtime', 'flapping', 'new', 'passive'):
        icon = QIcon('%s%snagstamon_%s.svg' % (RESOURCES, os.sep, attr))
        ICONS[attr] = icon


def get_screen(x, y):
    """
        find out which screen the given coordinates belong to
        gives back 'None' if coordinates are out of any known screen
    """
    # integerify these values as they *might* be strings
    x = int(x)
    y = int(y)

    number_of_screens = desktop.screenCount()
    for screen in range(number_of_screens + 1):
        # if coordinates are inside screen just break and return screen
        if (desktop.screenGeometry(screen).contains(x, y)):
            break

    del(x,y)

    # when 'screen' reached number_of_screens no screen was found, thus return None
    if screen == number_of_screens:
        return None
    else:
        return screen


@pyqtSlot()
def exit():
    """
        stop all child threads before quitting instance
    """
    # store position of statuswindow/statusbar
    statuswindow.store_position_to_conf()

    # hide statuswindow first ro avoid lag when waiting for finished threads
    statuswindow.hide()

    # stop statuswindow worker
    statuswindow.worker.running = False

    # save configuration
    conf.SaveConfig()

    # tell all tableview threads to stop
    for server_vbox in statuswindow.servers_vbox.children():
        server_vbox.table.worker.finish.emit()
    # wait until all threads are stopped
    for server_vbox in statuswindow.servers_vbox.children():
        server_vbox.table.worker_thread.wait(1)

    # wait until statuswindow notification worker has finished
    statuswindow.worker_notification_thread.wait(1)

    # wait until statuswindow worker has finished
    statuswindow.worker_thread.wait(1)

    # bye bye
    QApplication.instance().quit()


# check for updates
check_version = CheckVersion()

# access to variuos desktop parameters
desktop = QApplication.desktop()

# DBus initialization
dbus_connection = DBus()

# access dialogs
dialogs = Dialogs()

# system tray icon
systrayicon = SystemTrayIcon()

# combined statusbar/status window
statuswindow = StatusWindow()

# context menu for systray and statuswindow
menu = MenuContext()

# versatile mediaplayer
mediaplayer = MediaPlayer()
