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

# for python2 and upcomping python3 compatiblity
from __future__ import print_function, absolute_import, unicode_literals

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtSvg import *

import os
from operator import methodcaller
from collections import OrderedDict
from copy import deepcopy

from Nagstamon.Config import (conf, Server, RESOURCES, APPINFO)

from Nagstamon.Servers import (SERVER_TYPES, servers)

# dialogs
from Nagstamon.QUI.settings_main import Ui_settings_main
from Nagstamon.QUI.settings_server import Ui_settings_server
from Nagstamon.QUI.settings_action import Ui_settings_action


# fixed icons for hosts/services attributes
ICONS = dict()

# fixed shortened and lowered color names for cells, also used by statusbar label snippets
COLORS = OrderedDict([('DOWN', 'color_down_'),
                      ('UNREACHABLE', 'color_unreachable_'),
                      ('CRITICAL', 'color_critical_'),
                      ('UNKNOWN', 'color_unknown_'),
                      ('WARNING', 'color_warning_')])

# headers for tablewidgets
HEADERS = OrderedDict([('host', 'Host'), ('service', 'Service'),
                       ('status', 'Status'), ('last_check', 'Last Check'),
                       ('duration', 'Duration'), ('attempt', 'Attempt'),
                       ('status_information', 'Status Information')])

# sorting order for tablewidgets
SORT_ORDER = {'descending': True, 'ascending': False, 0: True, 1: False}


class HBoxLayout(QHBoxLayout):
    """
        Apparently necessary to get a HBox which is able to hide its children
    """
    def __init__(self, spacing=None):
        QHBoxLayout.__init__(self)
        if not spacing == None:
            self.setSpacing(0)                  # no spaces necessary between items
        self.setContentsMargins(0, 0, 0, 0)     # no margin


    def hideItems(self):
        """
            cruise through all child widgets and hide them
            self,count()-1 is needed because the last item is None
        """
        for item in range(self.count()-1):
            self.itemAt(item).widget().hide()


    def showItems(self):
        """
            cruise through all child widgets and show them
            self,count()-1 is needed because the last item is None
        """
        for item in range(self.count()-1):
            self.itemAt(item).widget().show()


class SystemTrayIcon(QSystemTrayIcon):
    """
        Icon in system tray, works at least in Windows and OSX
        Qt5 shows an empty icon in GNOME3
    """
    def __init__(self, icon):
        QSystemTrayIcon.__init__(self, icon)
        self.menu = QMenu()
        exitaction = QAction("Exit", self)
        exitaction.triggered.connect(QCoreApplication.instance().quit)
        self.menu.addAction(exitaction)
        self.setContextMenu(self.menu)


class StatusWindow(QWidget):
    def __init__(self):
        """
            Status window combined from status bar and popup window
        """
        QWidget.__init__(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowTitle(APPINFO.Name)
        self.setWindowIcon(QIcon('%s%snagstamon.svg' % (RESOURCES, os.sep)))

        self.vbox = QVBoxLayout(spacing=0)          # global VBox
        self.vbox.setContentsMargins(0, 0, 0, 0)    # no margin

        self.statusbar = StatusBar()                # statusbar HBox
        self.toparea = TopArea()                    # toparea HBox
        self.toparea.hide()
        self.toparea.button_close.clicked.connect(self.close)

        # connect logo of statusbar
        self.statusbar.logo.window_moved.connect(self.store_position)
        self.statusbar.logo.mouse_pressed.connect(self.store_position)
        self.statusbar.logo.mouse_pressed.connect(self.hide_window)

        # after status summarization check if window hast to be resized
        self.statusbar.resize.connect(self.adjustSize)

        # when logo in toparea was pressed hurry up to save the position so the statusbar will not jump
        self.toparea.logo.window_moved.connect(self.store_position)
        self.toparea.logo.mouse_pressed.connect(self.store_position)
        self.toparea.logo.mouse_pressed.connect(self.hide_window)

        # buttons in toparea
        self.toparea.button_settings.clicked.connect(self.hide_window)
        self.toparea.button_settings.clicked.connect(dialogs.settings.show)

        self.servers_vbox = QVBoxLayout()           # HBox full of servers
        self.servers_vbox.setContentsMargins(0, 0, 0, 0)
        self.servers_scrollarea = QScrollArea()     # scrollable area for server vboxes
        self.servers_scrollarea_widget = QWidget()  # necessary widget to contain vbox for servers
        self.servers_scrollarea.hide()

        self.createServerVBoxes()

        self.servers_scrollarea_widget.setLayout(self.servers_vbox)
        self.servers_scrollarea.setWidget(self.servers_scrollarea_widget)
        self.servers_scrollarea.setWidgetResizable(True)

        self.vbox.addWidget(self.statusbar)
        self.vbox.addWidget(self.toparea)
        self.vbox.addWidget(self.servers_scrollarea)

        self.setLayout(self.vbox)

        # icons in ICONS have to be sized as fontsize
        CreateIcons(self.statusbar.fontMetrics().height())

        # needed for moving the statuswindow
        self.moving = False
        self.relative_x = False
        self.relative_y = False

        # store position for showing/hiding statuswindow
        self.stored_x = self.x()
        self.stored_y = self.y()

        # flag to mark if window is shown or nor
        self.is_shown = False


    def createServerVBoxes(self):
        """
            internally used to create enabled servers to be displayed
        """
        for server in servers.values():
            if server.enabled:
                server_vbox = ServerVBox(server)
                # connect to global resize signal
                server_vbox.table.ready_to_resize.connect(self.adjust_size)
                self.servers_vbox.addLayout(server_vbox)


    def show_window(self, event):
        """
            used to show status window when its appearance is triggered, also adjusts geometry
        """
        if not statuswindow.moving:
            width, height, x, y = self.calculate_size()
            self.resize_window(width, height, x, y)

            # switch on
            self.is_shown = True


    def hide_window(self):
        if self.is_shown == True:
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


    def calculate_size(self):
        """
            get size of popup window
        """
        available_width = desktop.availableGeometry(self).width()
        available_height = desktop.availableGeometry(self).height()
        available_x = desktop.availableGeometry(self).x()
        available_y = desktop.availableGeometry(self).y()

        # take whole screen height into account when deciding about upper/lower-ness
        # add available_y because it might vary on differently setup screens
        # calculate top-ness only if window is closed
        if self.is_shown == False:
            if self.y() < desktop.screenGeometry(self).height()/2 + available_y:
                self.top = True
            else:
                self.top = False

        real_height = self.realHeight()

        # width simply will be the current screen maximal width - less hassle!
        width = available_width

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

        return width, height, available_x, y


    def resize_window(self, width, height, x, y):
        """
            resize status window according to its new
        """
        self.statusbar.hide()
        self.toparea.show()
        self.servers_scrollarea.show()

        # store position for restoring it when hiding - only if not shown of course
        if self.is_shown == False:
            self.stored_x = self.x()
            self.stored_y = self.y()

        # always stretch over whole screen width - thus x = screen_x, the leftmost pixel
        self.move(x, y)
        self.setMaximumSize(width, height)
        self.setMinimumSize(width, height)
        self.adjustSize()

        return True


    def adjust_size(self):
        """
            resize window if shown and needed
        """
        if self.is_shown == True:
            width, height, x, y = self.calculate_size()
            self.resize_window(width, height, x, y)


    def store_position(self):
        # store position for restoring it when hiding
        self.stored_x = self.x()
        self.stored_y = self.y()


    def leaveEvent(self, event):
        self.hide_window()


    def realWidth(self):
        """
            calculate widest width of all server tables
        """
        width = 0
        for server in self.servers_vbox.children():
            if server.table.realWidth() > width:
                width = server.table.realWidth()
        return width


    def realHeight(self):
        """
            calculate summary of all heights of all server tables plus height of toparea
        """
        height = 0
        for server in self.servers_vbox.children():
            height += server.realHeight()
            # add spacing between vbox items
            height += self.servers_vbox.spacing()

        # add size of toparea
        height += self.toparea.sizeHint().height()
        return height


class NagstamonLogo(QSvgWidget):
    """
        SVG based logo, used for statusbar and toparea logos
    """

    window_moved = pyqtSignal()
    mouse_pressed = pyqtSignal()

    def __init__(self, file, size=None):
        QSvgWidget.__init__(self)
        self.load(file)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # size needed for small Nagstamon logo in statusbar
        if size != None:
            self.setMinimumSize(size, size)


    def mousePressEvent(self, event):
        # keep x and y relative to statusbar
        if not statuswindow.relative_x and not statuswindow.relative_y:
            statuswindow.relative_x = event.x()
            statuswindow.relative_y = event.y()
        self.mouse_pressed.emit()


    def mouseReleaseEvent(self, event):
        statuswindow.relative_x = False
        statuswindow.relative_y = False
        statuswindow.moving = False


    def mouseMoveEvent(self, event):
        statuswindow.moving = True
        statuswindow.move(event.globalX()-statuswindow.relative_x, event.globalY()-statuswindow.relative_y)
        self.window_moved.emit()


    def mouseEnterEvent(self, event):
        # store window position if cursor enters logo
        statuswindow.move(event.globalX()-statuswindow.relative_x, event.globalY()-statuswindow.relative_y)
        self.window_moved.emit()


class StatusBar(QWidget):
    """
        status bar for short display of problems
    """

    # send signal to statuswindow
    resize = pyqtSignal()

    def __init__(self):
        QWidget.__init__(self)

        self.hbox = HBoxLayout(spacing=0)
        self.setLayout(self.hbox)

        # define labels first to get its size for svg logo dimensions
        self.color_labels = OrderedDict()
        self.color_labels['OK'] = StatusBarLabel('OK')
        for state in COLORS:
            self.color_labels[state] =  StatusBarLabel(state)

        # derive logo dimensions from status label
        self.logo = NagstamonLogo("%s%snagstamon_logo_bar.svg" % (RESOURCES, os.sep),
                            self.color_labels['OK'].fontMetrics().height())

        # add widgets
        self.hbox.addWidget(self.logo)
        self.hbox.addWidget(self.color_labels['OK'])
        self.color_labels['OK'].show()

        for state in COLORS:
            self.hbox.addWidget(self.color_labels[state])

        # first summary
        self.summarize_states()


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

        # summarize all numbers - if all_numbers keeps 0 everthing seems to be OK
        all_numbers = 0
        # repaint colored labels or hide them if necessary
        for label in self.color_labels.values():
            if label.number == 0:
                label.hide()
            else:
                label.setText(' %s ' % (label.number))
                label.show()
                label.adjustSize()
                all_numbers += label.number

        if all_numbers == 0:
            self.color_labels['OK'].show()
            self.color_labels['OK'].adjustSize()
        else:
            self.color_labels['OK'].hide()

        # fix size after refresh
        self.adjustSize()

        # tell statuswindow its size might be adjusted
        self.resize.emit()


class StatusBarLabel(QLabel):
    """
        one piece of the status bar labels for one state
    """
    def __init__(self, state):
        QLabel.__init__(self)
        self.setStyleSheet('color: %s; background-color: %s;' % (conf.__dict__['color_%s_text' % (state.lower())],
                                                                 conf.__dict__['color_%s_background' % (state.lower())]))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # hidden per default
        self.hide()

        # default text - only useful in case of OK Label
        self.setText(' %s ' % (state))

        # number of hosts/services of this state
        self.number = 0


    def enterEvent(self, event):
        statuswindow.show_window(event)


class TopArea(QWidget):
    """
        Top area of status window
    """
    def __init__(self):
        QWidget.__init__(self)
        self.hbox = HBoxLayout(spacing=10)      # top VBox containing buttons

        # top button box
        self.logo = NagstamonLogo("%s%snagstamon_logo_toparea.svg" % (RESOURCES, os.sep))
        self.label_version = QLabel(APPINFO.Version)
        self.combobox_servers = QComboBox()
        self.button_filters = QPushButton("Filters")
        self.button_recheck_all = QPushButton("Recheck all")
        self.button_refresh = QPushButton("Refresh")
        self.button_settings = QPushButton("Settings")
        self.button_hamburger_menu = QPushButton()
        self.button_hamburger_menu.setIcon(QIcon("%s%smenu.svg" % (RESOURCES, os.sep)))
        self.button_close = QPushButton()
        self.button_close.setIcon(QIcon("%s%sclose.svg" % (RESOURCES, os.sep)))

        self.hbox.addWidget(self.logo)
        self.hbox.addWidget(self.label_version)
        self.hbox.addStretch()
        self.hbox.addWidget(self.combobox_servers)
        self.hbox.addWidget(self.button_filters)
        self.hbox.addWidget(self.button_recheck_all)
        self.hbox.addWidget(self.button_refresh)
        self.hbox.addWidget(self.button_settings)
        self.hbox.addWidget(self.button_hamburger_menu)
        self.hbox.addWidget(self.button_close)

        self.setLayout(self.hbox)


class ServerVBox(QVBoxLayout):
    """
        one VBox per server containing buttons and hosts/services listview
    """

    def __init__(self, server):
        QVBoxLayout.__init__(self)

        self.server = server

        self.hbox = QHBoxLayout(spacing=10)

        self.label = QLabel("<big><b>%s@%s</b></big>" % (server.username, server.name))
        self.button_monitor = QPushButton("Monitor")
        self.button_hosts = QPushButton("Hosts")
        self.button_services = QPushButton("Services")
        self.button_history = QPushButton("History")

        self.hbox.addWidget(self.label)
        self.hbox.addWidget(self.button_monitor)
        self.hbox.addWidget(self.button_hosts)
        self.hbox.addWidget(self.button_services)
        self.hbox.addWidget(self.button_history)
        self.hbox.addStretch()
        self.addLayout(self.hbox)

        sort_column = 'status'
        order = 'descending'
        self.table = TableWidget(0, len(HEADERS), sort_column, order, self.server)

        self.addWidget(self.table, 1)


    def realHeight(self):
        """
            return summarized real height of hbox items and table
        """
        height = self.table.realHeight()
        # compare item heights, decide to take the largest
        if self.label.height() > self.button_monitor.height():
            height += self.label.height()
        else:
            height += self.button_monitor.height()

        # important to add existing spacing
        height += self.spacing()

        return height


    def show_all(self):
        """
            show all items in server vbox
        """
        for child in self.children():
            # not every child item has .show()
            if child.__dict__.has_key('show'):
                child.show()


    def hide_all(self):
        """
            hide all items in server vbox
        """
        for child in self.children():
            # not every child item has .hide()
            if child.__dict__.has_key('hide'):
                child.hide()



class CellWidget(QWidget):
    def __init__(self, column=0, row=0, text='', color='black', background='white', icons=''):
        QWidget.__init__(self)

        self.column = column
        self.row = row
        self.text = text
        self.color = color
        self.background = background

        self.hbox = QHBoxLayout(self)
        self.setLayout(self.hbox)

        # text field
        self.label = QLabel(self.text)

        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.addWidget(self.label, 1)
        self.hbox.setSpacing(0)

        self.label.setStyleSheet('padding: 5px;')

        # hosts and services might contain attribute icons
        if column in (0, 1) and icons is not [False]:
            for icon in icons:
                icon_label = QLabel()
                icon_label.setPixmap(icon.pixmap(self.label.fontMetrics().height(), self.label.fontMetrics().height()))
                icon_label.setStyleSheet('padding-right: 5px;')
                self.hbox.addWidget(icon_label)

        # paint cell appropriately
        self.colorize()


    def colorize(self):
        self.setStyleSheet('color: %s; background-color: %s;' % (self.color, self.background))


    def highlight(self):
        self.setStyleSheet('color: %s; background-color: %s;' % (self.color, 'darkgrey'))


    def enterEvent(self, event):
         self.parent().parent().highlightRow(self.row)


    def leaveEvent(self, event):
        self.parent().parent().colorizeRow(self.row)


class TableWidget(QTableWidget):
    """
        Contains information for one monitor server as a table
    """

    # send new data to worker
    new_data = pyqtSignal(list, str, bool)

    # tell global window that it should be resized
    ready_to_resize = pyqtSignal()


    def __init__(self, columncount, rowcount, sort_column, order, server):
        QTableWidget.__init__(self, columncount, rowcount)

        self.sort_column = sort_column
        self.order = order
        self.server = server

        # no vertical header needed
        self.verticalHeader().hide()

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
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
        self.horizontalHeader().setStyleSheet('font-weight: bold;')
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSortIndicator(list(HEADERS).index(self.sort_column), SORT_ORDER[self.order])
        self.horizontalHeader().sortIndicatorChanged.connect(self.sortColumn)

        # store width and height if they do not need to be recalculated
        self.real_width = 0
        self.real_height = 0

        # a thread + worker is necessary to get new monitor server data in the background and
        # to refresh the table cell by cell after new data is available
        self.worker_thread = QThread()
        self.worker = self.Worker(server=server)
        self.worker.moveToThread(self.worker_thread)

        # if worker got new status data from monitor server get_status the table
        self.worker.new_status.connect(self.refresh)
        # if worker calculated next cell send it to GUI thread
        self.worker.next_cell.connect(self.set_cell)
        # when worker walked through all cells send a signal to table so it could get_status itself
        self.worker.table_ready.connect(self.adjust_table)
        # get status if started
        self.worker_thread.started.connect(self.worker.get_status)
        # start with priority 0 = lowest
        self.worker_thread.start(0)

        # connect signal new_data to worker slot fill_rows
        self.new_data.connect(self.worker.fill_rows)


    def refresh(self):
        """
            refresh status display
        """
        if not statuswindow.moving:
            # get_status table cells with new data by thread
            data = list(self.server.GetItemsGenerator())
            self.set_data(data)
            # get_status statusbar
            statuswindow.statusbar.summarize_states()


    def set_cell(self, row, column, text, color, background, icons):
        """
            set data and widget for one cell
        """
        widget = CellWidget(text=text, color=color, background=background,
                            row=row, column=column, icons=icons)
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


    def adjust_table(self):
        """
            adjust table dimensions after filling it
        """
        # seems to be important for not getting somehow squeezed cells
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.horizontalHeader().setStretchLastSection(True)

        # force table to its maximal height, calculated by .realHeight()
        self.setMinimumHeight(self.realHeight())
        self.setMaximumHeight(self.realHeight())
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Maximum)

        # after setting table whole window can be repainted
        self.ready_to_resize.emit()


    class Worker(QObject):
        """
            attempt to run a server status update thread - only needed by table so it is defined here inside table
        """

        # send signal if monitor server has new status data
        new_status = pyqtSignal()
        # send signal if next cell can be filled
        next_cell = pyqtSignal(int, int, str, str, str, list)
        # send signal if all cells are filled and table can be adjusted
        table_ready = pyqtSignal()

        def __init__(self, parent=None, server=None):
            QObject.__init__(self)
            self.server = server
            self.timer = QTimer(self)
            self.server.init_config()


        def get_status(self):
            status =  self.server.GetStatus()
            self.new_status.emit()

            # avoid memory leak by singleshooting next get_status after this one is finished
            self.timer.singleShot(10000, self.get_status)


        def fill_rows(self, data, sort_column, reverse):
            # to keep GTK Treeview sort behaviour first by services
            first_sort = sorted(data, key=methodcaller('compare_host'))
            for row, nagitem in enumerate(sorted(first_sort, key=methodcaller('compare_%s' % \
                                                    (sort_column)), reverse=reverse)):
                # lists in rows list are columns
                # create every cell per row
                for column, text in enumerate(nagitem.get_columns(HEADERS)):
                    # check for icons to be used in cell widget
                    if column in (0, 1):
                        icons = list()
                        # add host icons
                        if nagitem.is_host() and column == 0:
                            if nagitem.is_acknowledged():
                                icons.append(ICONS["acknowledged"])
                            if nagitem.is_flapping():
                                icons.append(ICONS["flapping"])
                            if nagitem.is_passive_only():
                                icons.append(ICONS["passive"])
                            if nagitem.is_in_scheduled_downtime():
                                icons.append(ICONS["downtime"])
                        # add host icons for service item - e.g. in case host is in downtime
                        elif not nagitem.is_host() and column == 0:
                            if self.server.hosts[nagitem.host].is_acknowledged():
                                icons.append(ICONS["acknowledged"])
                            if self.server.hosts[nagitem.host].is_flapping():
                                icons.append(ICONS["flapping"])
                            if self.server.hosts[nagitem.host].is_passive_only():
                                icons.append(ICONS["passive"])
                            if self.server.hosts[nagitem.host].is_in_scheduled_downtime():
                                icons.append(ICONS["downtime"])
                        # add service icons
                        elif not nagitem.is_host() and column == 1:
                            if nagitem.is_acknowledged():
                                icons.append(ICONS["acknowledged"])
                            if nagitem.is_flapping():
                                icons.append(ICONS["flapping"])
                            if nagitem.is_passive_only():
                                icons.append(ICONS["passive"])
                            if nagitem.is_in_scheduled_downtime():
                                icons.append(ICONS["downtime"])

                    else:
                        icons = [False]

                    # send signal to paint next cell
                    self.next_cell.emit(row, column, text,
                                        conf.__dict__[COLORS[nagitem.status] + 'text'],
                                        conf.__dict__[COLORS[nagitem.status] + 'background'],
                                        icons)
                # sleep some milliceconds to let the GUI thread do some work too
                self.thread().msleep(5)

            # after running through
            self.table_ready.emit()


    def sortColumn(self, column, order):
        """
            set data according to sort criteria
        """
        self.sort_column = HEADERS.keys()[column]
        self.order = SORT_ORDER[order]
        self.set_data(list(self.server.GetItemsGenerator()))


    def realSize(self):
        """
            width, height
        """
        return self.realWidth(), self.realHeight()


    def realWidth(self):
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


    def realHeight(self):
        """
            calculate real table height as there is no method included
        """
        # height summary starts with headers' height
        # apparently height works better/without scrollbar if some pixels are added
        self.real_height = self.horizontalHeader().height() + 2
        # it is necessary to ask every row directly because their heights differ :-(
        row = 0
        for row in range(0, self.rowCount()):
            try:
                self.real_height += (self.cellWidget(row, 0).height())
            except:
                self.real_height += 30
        del(row)

        return self.real_height


    def highlightRow(self, row):
        for column in range(0, self.columnCount()):
            if self.cellWidget(row, column) != None:
                self.cellWidget(row, column).highlight()


    def colorizeRow(self, row):
        for column in range(0, self.columnCount()):
            if self.cellWidget(row, column) != None:
                self.cellWidget(row, column).colorize()


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


class Dialog(object):
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


    def __init__(self, dialog):
        self.window = QDialog()
        self.ui = dialog()
        self.ui.setupUi(self.window)
        # treat dialog content after pressing OK button
        self.ui.button_box.accepted.connect(self.ok)
        self.ui.button_box.rejected.connect(self.window.close)

        # QSignalMapper needed to connect all toggle-needing-checkboxes/radiobuttons to one .toggle()-method which
        # decides which sender to use as key in self.TOGGLE_DEPS
        self.signalmapper = QSignalMapper()

        # window position to be used to fix strange movement bug
        ###self.x = 0
        ###self.y = 0


    def initialize(self):
        """
            dummy initialize method
        """
        pass


    def show(self):
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
            self.signalmapper.setMapping(checkbox, checkbox)
            checkbox.toggled.connect(self.signalmapper.map)

        # finally map signals with .sender() - [QWidget] is important!
        self.signalmapper.mapped[QWidget].connect(self.toggle)


    def ok(self):
        # dummy OK treatment
        pass


class Dialog_Settings(Dialog):
    """
        class for settings dialog
    """
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
                            # icon in systray and its offset - might became obsolete in Qt5
                            self.ui.input_radiobutton_icon_in_systray : [self.ui.label_systray_popup_offset,
                                                                         self.ui.input_spinbox_systray_popup_offset],
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
                            self.ui.input_checkbutton_notification_actions : [self.ui.notification_actions_groupbox],
                            # several notification actions depending on status
                            self.ui.input_checkbox_notification_action_warning : [self.ui.input_lineedit_notification_action_warning_string],
                            self.ui.input_checkbox_notification_action_critical : [self.ui.input_lineedit_notification_action_critical_string],
                            self.ui.input_checkbox_notification_action_down : [self.ui.input_lineedit_notification_action_down_string],
                            self.ui.input_checkbox_notification_action_ok : [self.ui.input_lineedit_notification_action_ok_string],

                            # single custom notification action
                            self.ui.input_checkbox_notification_custom_action : [self.ui.notification_custom_action_groupbox]
                            }

        # connect server buttons to server dialogs
        self.ui.button_new_server.clicked.connect(self.new_server)
        self.ui.button_edit_server.clicked.connect(self.edit_server)
        self.ui.button_copy_server.clicked.connect(self.copy_server)
        self.ui.button_delete_server.clicked.connect(self.delete_server)

        # apply toggle-dependencies between checkboxes as certain widgets
        self.toggle_toggles()


    def initialize(self, start_tab=0):
        # apply configuration values
        # start with servers tab
        self.ui.tabs.setCurrentIndex(start_tab)
        for widget in dir(self.ui):
            if widget.startswith('input_'):
                if widget.startswith('input_checkbox_'):
                    if conf.__dict__[widget.split('input_checkbox_')[1]] == True:
                        self.ui.__dict__[widget].toggle()
                if widget.startswith('input_radiobutton_'):
                    if conf.__dict__[widget.split('input_radiobutton_')[1]] == True:
                        self.ui.__dict__[widget].toggle()
                if widget.startswith('input_lineedit_'):
                    self.ui.__dict__[widget].setText(conf.__dict__[widget.split('input_lineedit_')[1]])
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
        self.ui.input_combobox_fullscreen_display.setCurrentText(conf.fullscreen_display)

        # fill servers listwidget with servers
        for server in sorted(conf.servers, key=unicode.lower):
           self.ui.list_servers.addItem(server)
        # select first item
        self.ui.list_servers.setCurrentRow(0)

        # fill actions listwidget with actions
        for action in sorted(conf.actions, key=unicode.lower):
           self.ui.list_actions.addItem(action)
        # select first item
        self.ui.list_actions.setCurrentRow(0)

        # important final size adjustment
        self.window.adjustSize()


    def ok(self):
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

        # store configuration
        conf.SaveConfig()


    def new_server(self):
        """
            create new server
        """
        dialogs.server.new()


    def edit_server(self):
        """
            edit existing server
        """
        dialogs.server.edit()


    def copy_server(self):
        """
            copy existing server
        """
        dialogs.server.copy()


    def delete_server(self):
        pass


class Dialog_Server(Dialog):
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
        self.ui.input_combobox_type.addItems(sorted(SERVER_TYPES.keys(), key=unicode.lower))
        # default to Nagios as it is the mostly used monitor server
        self.ui.input_combobox_type.setCurrentText('Nagios')

        # detect change of server type which leads to certain options shown or hidden
        self.ui.input_combobox_type.activated.connect(self.server_type_changed)

        # mode needed for evaluate dialog after ok button pressed - defaults to 'new'
        self.mode = 'new'


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
    def edit(self):
        """
            edit existing server
        """
        self.mode = 'edit'
        # shorter server conf
        self.server_conf = conf.servers[dialogs.settings.ui.list_servers.currentItem().text()]
        # store monitor name in case it will be changed
        self.previous_name = self.server_conf.name
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
        # check that no duplicate name exists
        if self.ui.input_lineedit_name.text() in servers and \
          (self.mode in ['new', 'copy'] or \
           self.mode == 'edit' and self.server_conf != conf.servers[self.ui.input_lineedit_name.text()]):
            # cry if duplicate name exists
            QMessageBox.critical(self.window, 'Nagstamon',
                                 'The monitor server name <b>%s</b> is already used.' %\
                                 (self.ui.input_lineedit_name.text()),
                                 QMessageBox.Ok)
        else:
            for widget in self.ui.__dict__:
                if widget.startswith('input_'):
                    if widget.startswith('input_checkbox_'):
                        setting = widget.split('input_checkbox_')[1]
                        self.server_conf.__dict__[setting] = self.ui.__dict__[widget].isChecked()
                    elif widget.startswith('input_combobox_'):
                        setting = widget.split('input_combobox_')[1]
                        self.server_conf.__dict__[setting] = self.ui.__dict__[widget].currentText()
                    elif widget.startswith('input_lineedit_'):
                        setting = widget.split('input_lineedit_')[1]
                        self.server_conf.__dict__[setting] =  self.ui.__dict__[widget].text()

            # new items have to be added to servers dictionary
            if self.mode in ['new', 'copy']:
                conf.servers[self.server_conf.name] = self.server_conf
            else:
                # if server has been renamed the old name has to disappear
                if self.server_conf.name != self.previous_name:
                    # add edited name
                    conf.servers[self.server_conf.name] = self.server_conf
                    # delete previous name
                    conf.servers.pop(self.previous_name)

            # URLs should not end with / - clean it
            self.server_conf.monitor_url = self.server_conf.monitor_url.rstrip("/")
            self.server_conf.monitor_cgi_url = self.server_conf.monitor_cgi_url.rstrip("/")

            # some monitor servers do not need cgi-url - reuse self.VOLATILE_WIDGETS to find out which one
            if not self.server_conf.type in self.VOLATILE_WIDGETS[self.ui.input_lineedit_monitor_cgi_url]:
                self.server_conf.monitor_cgi_url = self.server_conf.monitor_url

            # clear list of servers
            dialogs.settings.ui.list_servers.clear()
            # fill servers listwidget with servers
            for server in sorted(conf.servers, key=unicode.lower):
                dialogs.settings.ui.list_servers.addItem(server)

            # select current edited item
            # activate currently created/edited server monitor item biy first search it in the list
            dialogs.settings.ui.list_servers.setCurrentItem(
                                dialogs.settings.ui.list_servers.findItems(self.server_conf.name, Qt.MatchExactly)[0])

            self.window.close()


def CreateIcons(fontsize):
    """
        fill global ICONS with pixmaps rendered from SVGs in fontsize dimensions
    """

    print('Reminder: fontsize is not used in CreateIcons().')

    for attr in ('acknowledged', 'downtime', 'flapping', 'new', 'passive'):
        icon = QIcon('%s%snagstamon_%s.svg' % (RESOURCES, os.sep, attr))
        ICONS[attr] = icon


def get_screen(x, y):
    """
        find out which screen the cursor is on
    """
    for screen in range(desktop.screenCount()):
        # if coordinates are inside screen just break and return screen
        if (desktop.screenGeometry(screen).contains(x, y)):
            break
    return screen


# access to variuos desktop parameters
desktop = QApplication.desktop()

# access dialogs
dialogs = Dialogs()

# system tray icon
systrayicon = SystemTrayIcon(QIcon('%s%snagstamon.svg' % (RESOURCES, os.sep)))

# combined statusbar/status window
statuswindow = StatusWindow()



