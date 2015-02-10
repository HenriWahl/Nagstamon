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

from Nagstamon.Config import (conf, RESOURCES, APPINFO)

from Nagstamon.Servers import servers


class HBoxLayout(QHBoxLayout):
    """
        Apparently necessary to get a HBox which is able to hide its children
    """
    def __init__(self, spacing=None):
        QHBoxLayout.__init__(self)
        if not spacing == None:
            self.setSpacing(0)                      # no spaces necessary between items
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
        #self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APPINFO.Name)
        self.setWindowIcon(QIcon("%s%snagstamon.svg" % (RESOURCES, os.sep)))

        self.vbox = QVBoxLayout(spacing=0)                   # global VBox
        self.vbox.setContentsMargins(0, 0, 0, 0)    # no margin

        self.hbox_bar = HBoxLayout(spacing=0)       # statusbar HBox
        self.hbox_top = HBoxLayout(spacing=10)                # top VBox containing buttons
        self.vbox_servers = QVBoxLayout()            # HBox full of servers

        self.vbox.addLayout(self.hbox_bar)
        self.vbox.addLayout(self.hbox_top)
        self.vbox.addLayout(self.vbox_servers)

        # define label first to get its size for svg logo dimensions
        self.label_bar = QLabel(" 1 2 3 ")
        self.label_bar.setStyleSheet("QLabel { background-color: green; }")

        # derive logo dimensions from status label
        self.logo_bar = QSvgWidget("%s%snagstamon_logo_bar.svg" % (RESOURCES, os.sep))
        self.logo_bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.logo_bar.setMinimumSize(self.label_bar.fontMetrics().height(), self.label_bar.fontMetrics().height())

        self.hbox_bar.addWidget(self.logo_bar)
        self.hbox_bar.addWidget(self.label_bar)
        self.hbox_bar.addStretch()

        # top button box
        self.logo = QSvgWidget("%s%snagstamon_label.svg" % (RESOURCES, os.sep))
        self.logo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

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
        self.button_close.clicked.connect(self.close)

        self.hbox_top.addWidget(self.logo)
        self.hbox_top.addWidget(self.label_version)
        self.hbox_top.addStretch()
        self.hbox_top.addWidget(self.combobox_servers)
        self.hbox_top.addWidget(self.button_filters)
        self.hbox_top.addWidget(self.button_recheck_all)
        self.hbox_top.addWidget(self.button_refresh)
        self.hbox_top.addWidget(self.button_settings)
        self.hbox_top.addWidget(self.button_hamburger_menu)
        self.hbox_top.addWidget(self.button_close)

        self.setLayout(self.vbox)

        self.createServerVBoxes()


    def createServerVBoxes(self):
        for server in servers.values():
            if server.enabled:
                self.vbox_servers.addLayout(ServerVBox(server))


class ServerVBox(QVBoxLayout):
    """
        one VBox per server containing buttons and hosts/services listview
    """
    def __init__(self, server):
        QVBoxLayout.__init__(self)


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

        self.thread = QThread()
        self.worker = ServerThreadWorker(server=server)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.refreshStatus)
        self.thread.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.worker.refreshStatus)
        self.timer.start(1)


class ServerThreadWorker(QObject):
    """
        attempt to run a server status update thread
    """
    def __init__(self, parent=None, server=None):
        QObject.__init__(self)
        self.server = server
        self.server.init_config()

    def refreshStatus(self):
        status =  self.server.GetStatus()


systrayicon = SystemTrayIcon(QIcon("%s%snagstamon.svg" % (RESOURCES, os.sep)))
statuswindow = StatusWindow()