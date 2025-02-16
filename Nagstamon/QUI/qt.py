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

# Select Qt version based on installation found
# Prefer in this order: PyQt6 - PyQt5

from pathlib import Path
import sys

# Enough to handle with differences between PyQt5 + PyQt6, so PySide6 will be
# ignored right now
# by the little import the appropriate PyQt version will be loaded
try:
    from PyQt6.QtCore import PYQT_VERSION_STR as QT_VERSION_STR

    # get int-ed version parts
    QT_VERSION_MAJOR, QT_VERSION_MINOR = [int(x) for x in QT_VERSION_STR.split('.')[0:2]]
    # for later decision which differences have to be considered
    QT_FLAVOR = 'PyQt6'
except ImportError:
    try:
        from PyQt5.QtCore import PYQT_VERSION_STR as QT_VERSION_STR
        # get int-ed version parts
        QT_VERSION_MAJOR, QT_VERSION_MINOR = [int(x) for x in QT_VERSION_STR.split('.')[0:2]]
        # for later decision which differences have to be considered
        QT_FLAVOR = 'PyQt5'
    except ImportError:
        sys.exit('Qt is missing')

# because 'PyQt6' is in sys.modules even if the import some line before failed
# the backup PyQt5 should be loaded earlier if it exists due to exception treatment
if QT_FLAVOR == 'PyQt5':
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
    from PyQt5 import uic


    class QSignalMapper(QSignalMapper):
        """
            QSignalMapper has method mappedString since Qt 5.15 which is not available in Ubuntu 20.04
            See https://github.com/HenriWahl/Nagstamon/issues/865 for details
        """
        def __init__(self):
            super().__init__()
            # map mappedString onto mapped
            self.mappedString = self.mapped


    class MediaPlayer(QObject):
        """
            play media files for notification
        """
        # needed to show error in a thread-safe way
        send_message = Signal(str, str)

        def __init__(self, statuswindow, resource_files):
            QObject.__init__(self)
            self.player = QMediaPlayer(parent=self)

            self.player.setVolume(100)
            self.playlist = QMediaPlaylist()
            self.player.setPlaylist(self.playlist)
            self.resource_files = resource_files
            # let statuswindow show message
            self.send_message.connect(statuswindow.show_message)
            # connect with statuswindow notification worker
            statuswindow.worker_notification.load_sound.connect(self.set_media)
            statuswindow.worker_notification.play_sound.connect(self.play)

        @Slot(str)
        def set_media(self, media_file):
            """
            Give media_file to player and if it is one of the default files check first if still exists
            :param media_file:
            :return:
            """
            if media_file in self.resource_files:
                # by using RESOURCE_FILES the file path will be checked on macOS and the file restored if necessary
                media_file = self.resource_files[media_file]
            # only existing file can be played
            if Path(media_file).exists:
                url = QUrl.fromLocalFile(media_file)
                mediacontent = QMediaContent(url)
                self.player.setMedia(mediacontent)
                del url, mediacontent
                return True
            else:
                # cry and tell no file was found
                self.send_message.emit('warning',
                                       'Sound file <b>\'{0}\'</b> not found for playback.'.format(media_file))
                return False

        @Slot()
        def play(self):
            # just play sound
            self.player.play()


    def get_global_position(event):
        '''
        Qt5 uses other method than Qt6
        '''
        return event.globalPos()

    def get_sort_order_value(sort_order):
        '''
        Qt5 has int for Qt.SortOrder but Qt6 has Qt.SortOrder.[Ascending|Descending]Order
        '''
        return sort_order


elif QT_FLAVOR == 'PyQt6':
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
        QVariant, \
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


    class MediaPlayer(QObject):
        """
            play media files for notification
        """
        # needed to show error in a thread-safe way
        send_message = Signal(str, str)

        def __init__(self, statuswindow, resource_files):
            QObject.__init__(self)
            self.audio_output = QAudioOutput()
            self.player = QMediaPlayer(parent=self)
            self.player.setAudioOutput(self.audio_output)
            self.resource_files = resource_files
            # let statuswindow show message
            self.send_message.connect(statuswindow.show_message)
            # connect with statuswindow notification worker
            statuswindow.worker_notification.load_sound.connect(self.set_media)
            statuswindow.worker_notification.play_sound.connect(self.play)

        @Slot(str)
        def set_media(self, media_file):
            """
            Give media_file to player and if it is one of the default files check first if still exists
            :param media_file:
            :return:
            """
            if media_file in self.resource_files:
                # by using RESOURCE_FILES the file path will be checked on macOS and the file restored if necessary
                media_file = self.resource_files[media_file]
            # only existing file can be played
            if Path(media_file).exists():
                self.player.setSource(QUrl.fromLocalFile(media_file))
                return True
            else:
                # cry and tell no file was found
                self.send_message.emit('warning', f'Sound file <b>\'{media_file}\'</b> not found for playback.')
                return False

        @Slot()
        def play(self):
            # just play sound
            self.player.play()


    def get_global_position(event):
        '''
        Qt5 uses other method than Qt6
        '''
        return event.globalPosition()

    def get_sort_order_value(sort_order):
        '''
        Qt5 has int for Qt.SortOrder but Qt6 has Qt.SortOrder.[Ascending|Descending]Order
        '''
        return sort_order.value

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
#         QVariant, \
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
