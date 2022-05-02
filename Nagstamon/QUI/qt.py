# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2022 Henri Wahl <henri@nagstamon.de> et al.
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

# Select Qt version based on installation found
# Prefer in this order: Pyside6 - PyQt6 - PyQt5

import sys

if 'PyQt5' in sys.modules:
    from PyQt5.QtCore import pyqtSignal, \
        pyqtSlot, \
        QAbstractTableModel, \
        QByteArray, \
        QDateTime, \
        QModelIndex, \
        QObject, \
        QPoint, \
        QSignalMapper, \
        Qt, \
        QThread, \
        QTimer, \
        QUrl, \
        QVariant, \
        QXmlStreamReader
    from PyQt5.QtGui import QBrush, \
        QColor, \
        QCursor, \
        QFont, \
        QFontDatabase, \
        QIcon, \
        QKeySequence, \
        QPainter, \
        QPalette, \
        QPixmap
    from PyQt5.QtMultimedia import QMediaContent, \
        QMediaPlayer, \
        QMediaPlaylist
    from PyQt5.QtSvg import QSvgRenderer, \
        QSvgWidget

    from PyQt5.QtWidgets import QAbstractItemView, \
        QAction, \
        QApplication, \
        QColorDialog, \
        QComboBox, \
        QDialog, \
        QFileDialog, \
        QFontDialog, \
        QHBoxLayout, \
        QHeaderView, \
        QListWidgetItem, \
        QMenu, \
        QMenuBar, \
        QMessageBox, \
        QLabel, \
        QPushButton, \
        QScrollArea, \
        QSizePolicy, \
        QSpacerItem, \
        QToolButton, \
        QTreeView, \
        QStyle, \
        QSystemTrayIcon, \
        QVBoxLayout, \
        QWidget