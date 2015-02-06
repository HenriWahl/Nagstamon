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
        QWidget.__init__(self)
        #self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APPINFO.Name)
        self.setWindowIcon(QIcon("%s%snagstamon.svg" % (RESOURCES, os.sep)))

        self.vbox = QVBoxLayout()                   # global VBox
        self.vbox.setContentsMargins(0, 0, 0, 0)    # no margin

        self.hbox_bar = HBoxLayout(spacing=0)               # statusbar HBox
        self.hbox_top = HBoxLayout()               # top VBox containing buttons

        self.vbox.addLayout(self.hbox_bar)
        self.vbox.addLayout(self.hbox_top)

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
        self.combobox_monitors = QComboBox()
        self.button_filters = QPushButton("Filters")
        self.button_recheck_all = QPushButton("Recheck all")
        self.button_refresh = QPushButton("Refresh")
        self.button_settings = QPushButton("Settings")
        self.vseparator = QFrame()
        self.vseparator.setFrameShape(QFrame.VLine)
        self.vseparator.setFrameShadow(QFrame.Sunken)
        self.button_hamburger_menu = QToolButton()
        self.button_hamburger_menu.setIcon(QIcon("%s%smenu.svg" % (RESOURCES, os.sep)))
        self.button_close = QToolButton()
        self.button_close.setIcon(QIcon("%s%sclose.svg" % (RESOURCES, os.sep)))

        self.hbox_top.addWidget(self.logo)
        self.hbox_top.addWidget(self.label_version)
        self.hbox_top.addStretch()
        self.hbox_top.addWidget(self.combobox_monitors)
        self.hbox_top.addWidget(self.button_filters)
        self.hbox_top.addWidget(self.button_recheck_all)
        self.hbox_top.addWidget(self.button_refresh)
        self.hbox_top.addWidget(self.button_settings)
        self.hbox_top.addWidget(self.vseparator)
        self.hbox_top.addWidget(self.button_hamburger_menu)
        self.hbox_top.addWidget(self.button_close)


        self.setLayout(self.vbox)


systrayicon = SystemTrayIcon(QIcon("%s%snagstamon.svg" % (RESOURCES, os.sep)))
statuswindow = StatusWindow()