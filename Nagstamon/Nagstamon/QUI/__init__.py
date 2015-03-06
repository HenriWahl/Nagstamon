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

from Nagstamon.Config import (conf, RESOURCES, APPINFO)

from Nagstamon.Servers import servers

from Nagstamon.Objects import GenericObject, GenericService

# fixed icons for hosts/services attributes
ICONS = dict()

# fixed shortened and lowered color names for cells, also used by statusbar label snippets
COLORS = OrderedDict([('DOWN', 'color_down_'),
                      ('UNREACHABLE', 'color_unreachable_'),
                      ('CRITICAL', 'color_critical_'),
                      ('UNKNOWN', 'color_unknown_'),
                      ('WARNING', 'color_warning_')])

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
        self.statusbar.logo.mouse_pressed.connect(self.hideFullWindow)

        # when logo in toparea was pressed hurry up to save the position so the statusbar will not jump
        self.toparea.logo.window_moved.connect(self.store_position)
        self.toparea.logo.mouse_pressed.connect(self.store_position)
        self.toparea.logo.mouse_pressed.connect(self.hideFullWindow)

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


    def createServerVBoxes(self):
        """
            internally used to create enabled servers to be displayed
        """
        for server in servers.values():
            if server.enabled:
                server_vbox = ServerVBox(server)
                self.servers_vbox.addLayout(server_vbox)


    def showFullWindow(self, event):
        """
            used to show status window when its appearance is triggered, also adjusts geometry
        """
        if not statuswindow.moving:
            available_width = desktop.availableGeometry(self).width()
            available_height = desktop.availableGeometry(self).height()
            available_x = desktop.availableGeometry(self).x()
            available_y = desktop.availableGeometry(self).y()

            # take whole screen height into account when deciding about upper/lower-ness
            # add available_x because it might vary on differently setup screens
            if self.y() < desktop.screenGeometry(self).height()/2 + available_y:
                top = True
            else:
                top = False

            real_height = self.realHeight()
            # width simply will be the current screen maximal width - less hassle!
            width = available_width

            # when statusbar resides in uppermost part of current screen extend from top to bottom
            if top == True:
                y = self.y()
                if real_height < available_height:
                    height = real_height
                else:
                    height = available_height - self.y() + available_y
            # when statusbar hangs around in lowermost part of current screen extend from bottom to top
            else:
                # when height is to large for current screen cut it
                if self.y() - real_height < available_y:
                    height = desktop.screenGeometry().height() - available_y -\
                             (desktop.screenGeometry().height() - (self.y() + self.height()))
                    y = available_y
                    print(height)
                else:
                    height = real_height
                    y = self.y() + self.height() - height

            self.statusbar.hide()
            self.toparea.show()
            self.servers_scrollarea.show()

            # store position for restoring it when hiding
            self.stored_x = self.x()
            self.stored_y = self.y()

            # always stretch over whole screen width -thus screen_x, the leftmost pixel
            self.move(available_x, y)
            self.setMaximumSize(width, height)
            self.setMinimumSize(width, height)
            self.adjustSize()


    def hideFullWindow(self):
        self.statusbar.show()
        self.statusbar.adjustSize()
        self.toparea.hide()
        self.servers_scrollarea.hide()
        self.setMinimumSize(1, 1)
        self.adjustSize()
        self.move(self.stored_x, self.stored_y)


    def store_position(self):
        # store position for restoring it when hiding
        self.stored_x = self.x()
        self.stored_y = self.y()


    def leaveEvent(self, event):
        self.hideFullWindow()


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
            height += server.table.realHeight()
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
        #statuswindow.hideFullWindow()
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
                all_numbers += label.number

        if all_numbers == 0:
            self.color_labels['OK'].show()
        else:
            self.color_labels['OK'].hide()

        # fix size after refresh
        self.adjustSize()


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
        statuswindow.showFullWindow(event)


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

        hbox = QHBoxLayout(spacing=10)

        label = QLabel("<big><b>%s@%s</b></big>" % (server.username, server.name))
        button_server = QPushButton("Monitor")
        button_hosts = QPushButton("Hosts")
        button_services = QPushButton("Services")
        button_history = QPushButton("History")

        hbox.addWidget(label)
        hbox.addWidget(button_server)
        hbox.addWidget(button_hosts)
        hbox.addWidget(button_services)
        hbox.addWidget(button_history)
        hbox.addStretch()
        self.addLayout(hbox)

        self.headers = OrderedDict([('host', 'Host'), ('service', 'Service'),
                                    ('status', 'Status'), ('last_check', 'Last Check'),
                                    ('duration', 'Duration'), ('attempt', 'Attempt'),
                                    ('status_information', 'Status Information')])
        sort_column = 'status'
        order = 'descending'
        self.table = TableWidget(self.headers, 0, len(self.headers), sort_column, order, self.server)

        self.addWidget(self.table, 1)


    def refresh(self):
        if not statuswindow.moving:
            #get_status table cells with new data by thread
            self.table.set_data(list(self.server.GetItemsGenerator()))
            # get_status statusbar
            statuswindow.statusbar.summarize_states()


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
    new_data = pyqtSignal(list, str, OrderedDict, bool)

    def __init__(self, headers, columncount, rowcount, sort_column, order, server):
        QTableWidget.__init__(self, columncount, rowcount)

        self.SORT_ORDER = {'descending': True, 'ascending': False, 0: True, 1: False}

        self.headers = headers
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

        self.setHorizontalHeaderLabels(self.headers.values())
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.horizontalHeader().setStyleSheet('font-weight: bold;')
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSortIndicator(list(self.headers).index(self.sort_column), self.SORT_ORDER[self.order])
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
        if not statuswindow.moving:
            #get_status table cells with new data by thread
            self.set_data(list(self.server.GetItemsGenerator()))
            # get_status statusbar
            statuswindow.statusbar.summarize_states()


    class Worker(QObject):
        """
            attempt to run a server status update thread
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


        def fill_rows(self, data, sort_column, headers, reverse):
            # to keep GTK Treeview sort behaviour first by services
            first_sort = sorted(data, key=methodcaller('compare_host'))
            for row, nagitem in enumerate(sorted(first_sort, key=methodcaller('compare_%s' % \
                                                    (sort_column)), reverse=reverse)):
                # lists in rows list are columns
                #self.data.append(list())
                # create every cell per row
                for column, text in enumerate(nagitem.get_columns(headers)):
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
        self.new_data.emit(data, self.sort_column, self.headers, self.SORT_ORDER[self.order])


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
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Maximum)


    def sortColumn(self, column, order):
        """
            set data according to sort criteria
        """
        self.sort_column = self.headers.keys()[column]
        self.order = self.SORT_ORDER[order]
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

        # ---> evtl. muss einfach die breite des vertikalen scrollbalkens mit addiert werden?

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


def CreateIcons(fontsize):
    """
        fill global ICONS with pixmpas rendered from SVGs in fontsize dimensions
    """
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


systrayicon = SystemTrayIcon(QIcon("%s%snagstamon.svg" % (RESOURCES, os.sep)))
statuswindow = StatusWindow()
# access to variuos desktop parameters
desktop = QApplication.desktop()