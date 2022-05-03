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

try:
    from PySide6 import __version__ as QT_VERSION_STR
except ImportError:
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR as QT_VERSION_STR
    except ImportError:
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR as QT_VERSION_STR
        except ImportError:
            sys.exit('Qt is missing')

# as log as Qt6 does not work prefer PyQt5
if 'PyQt5' in sys.modules:
    from PyQt5.QtCore import pyqtSignal as Signal, \
        pyqtSlot as Slot, \
        PYQT_VERSION_STR as QT_VERSION_STR, \
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
elif 'PySide6' in sys.modules:
    from PySide6.QtCore import Signal, \
        Slot, \
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
        QXmlStreamReader
    from PySide6.QtGui import QAction, \
        QBrush, \
        QColor, \
        QCursor, \
        QFont, \
        QFontDatabase, \
        QIcon, \
        QKeySequence, \
        QPainter, \
        QPalette, \
        QPixmap
    from PySide6.QtMultimedia import QMediaContent, \
        QMediaPlayer, \
        QMediaPlaylist
    from PySide6.QtSvg import QSvgRenderer, \
        QSvgWidget
    from PySide6.QtWidgets import QAbstractItemView, \
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
elif 'PyQt6' in sys.modules:
    # PySide/PyQt compatibility
    from PyQt6.QtCore import pyqtSignal as Signal, \
        pyqtSlot as Slot, \
        PYQT_VERSION_STR as QT_VERSION_STR, \
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
        QXmlStreamReader
    from PyQt6.QtGui import QAction, \
        QBrush, \
        QColor, \
        QCursor, \
        QFont, \
        QFontDatabase, \
        QIcon, \
        QKeySequence, \
        QPainter, \
        QPalette, \
        QPixmap
    from PyQt6.QtMultimedia import QMediaContent, \
        QMediaPlayer, \
        QMediaPlaylist
    from PyQt6.QtSvg import QSvgRenderer, \
        QSvgWidget
    from PyQt6.QtWidgets import QAbstractItemView, \
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

# get int-ed version parts
QT_VERSION_MAJOR, QT_VERSION_MINOR, QT_VERSION_BUGFIX = [int(x) for x in QT_VERSION_STR.split('.')]
