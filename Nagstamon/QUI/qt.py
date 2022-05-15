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
# Prefer in this order: PyQt6 - PyQt5

import sys

# Enough to handle with differences between PyQt5 + PyQt6, so PySide6 will be
# ignored right now
# by the little import the appropriate PyQt version will be loaded
try:
    from PyQt6.QtCore import PYQT_VERSION_STR as QT_VERSION_STR
except ImportError:
    try:
        from PyQt5.QtCore import PYQT_VERSION_STR as QT_VERSION_STR
    except ImportError:
        sys.exit('Qt is missing')

# because 'PyQt6' is in sys.modules even if the import some line befoe failed
# the backup PyQt5 should be loaded earlier if it exists due to exception treatment
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
    from PyQt5 import uic
    # for later decision which differences have to be considered
    QT_FLAVOR = 'PyQt5'

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
    from PyQt6.QtMultimedia import QAudioOutput, \
        QMediaPlayer
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtSvgWidgets import QSvgWidget
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
    from PyQt6 import uic
    # for later decision which differences have to be considered
    QT_FLAVOR = 'PyQt6'

# elif 'PySide6' in sys.modules:
#     from PySide6.QtCore import Signal, \
#         Slot, \
#         QAbstractTableModel, \
#         QByteArray, \
#         QDateTime, \
#         QModelIndex, \
#         QObject, \
#         QPoint, \
#         QSignalMapper, \
#         Qt, \
#         QThread, \
#         QTimer, \
#         QUrl, \
#         QXmlStreamReader
#     from PySide6.QtGui import QAction, \
#     QBrush, \
#     QColor, \
#     QCursor, \
#     QFont, \
#     QFontDatabase, \
#     QIcon, \
#     QKeySequence, \
#     QPainter, \
#     QPalette, \
#     QPixmap
#     from PySide6.QtMultimedia import QAudioOutput, \
#         QMediaPlayer
#     from PySide6.QtSvg import QSvgRenderer
#     from PySide6.QtSvgWidgets import QSvgWidget
#     from PySide6.QtWidgets import QAbstractItemView, \
#         QApplication, \
#         QColorDialog, \
#         QComboBox, \
#         QDialog, \
#         QFileDialog, \
#         QFontDialog, \
#         QHBoxLayout, \
#         QHeaderView, \
#         QListWidgetItem, \
#         QMenu, \
#         QMenuBar, \
#         QMessageBox, \
#         QLabel, \
#         QPushButton, \
#         QScrollArea, \
#         QSizePolicy, \
#         QSpacerItem, \
#         QToolButton, \
#         QTreeView, \
#         QStyle, \
#         QSystemTrayIcon, \
#         QVBoxLayout, \
#         QWidget
#     # for later decision which differences have to be considered
#     QT_FLAVOR = 'PySide6'

# get int-ed version parts
QT_VERSION_MAJOR, QT_VERSION_MINOR, QT_VERSION_BUGFIX = [int(x) for x in QT_VERSION_STR.split('.')]
