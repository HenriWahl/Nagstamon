# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.
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

from os import environ
from pathlib import Path
import sys

# Differences in *.ui files between PyQt5 and PyQt6, will be replaced when UI files are loaded
UI_FILE_QT6_QT5_DOWNGRADES = {
    'AnyTerritory': 'AnyCountry',
    'QDialogButtonBox::StandardButton::Cancel': 'QDialogButtonBox::Cancel',
    'QDialogButtonBox::StandardButton::Ok': 'QDialogButtonBox::Ok',
    'QFrame::Shadow::Sunken': 'QFrame::Sunken',
    'QFrame::Shape::Box': 'QFrame::Box',
    'QLayout::SizeConstraint::SetMinimumSize': 'QLayout::SetMinimumSize',
    'QLineEdit::EchoMode::Password': 'QLineEdit::Password',
    'QListView::ResizeMode::Adjust': 'QListView::Adjust',
    'Qt::AlignmentFlag::AlignCenter': 'Qt::AlignCenter',
    'Qt::AlignmentFlag::AlignLeading': 'Qt::AlignLeading',
    'Qt::AlignmentFlag::AlignLeft': 'Qt::AlignLeft',
    'Qt::AlignmentFlag::AlignTop': 'Qt::AlignTop',
    'Qt::AlignmentFlag::AlignVCenter': 'Qt::AlignVCenter',
    'Qt::Orientation::Horizontal': 'Qt::Horizontal',
    'Qt::Orientation::Vertical': 'Qt::Vertical',
    'Qt::TextInteractionFlag::TextBrowserInteraction': 'Qt::TextBrowserInteraction',
    'QTabWidget::TabShape::Rounded': 'QTabWidget::Rounded'
}

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

# useful for testing to force a specific Qt version
if environ.get('NAGSTAMON_QT_FLAVOR'):
    QT_FLAVOR = environ.get('NAGSTAMON_QT_FLAVOR')
    if QT_FLAVOR == 'PyQt6':
        from PyQt6.QtCore import PYQT_VERSION_STR as QT_VERSION_STR

        # get int-ed version parts
        QT_VERSION_MAJOR, QT_VERSION_MINOR = [int(x) for x in QT_VERSION_STR.split('.')[0:2]]
    elif QT_FLAVOR == 'PyQt5':
        from PyQt5.QtCore import PYQT_VERSION_STR as QT_VERSION_STR

        # get int-ed version parts
        QT_VERSION_MAJOR, QT_VERSION_MINOR = [int(x) for x in QT_VERSION_STR.split('.')[0:2]]
    else:
        sys.exit("NAGSTAMON_QT_FLAVOR has invalid value. Use 'PyQt5' or 'PyQt6'.")

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
    from PyQt5.QtNetwork import (QNetworkCookie,
                                 QNetworkProxy,
                                 QNetworkProxyFactory)
    from PyQt5.QtSvg import QSvgRenderer, \
        QSvgWidget
    from PyQt5.QtWebEngineWidgets import (QWebEngineCertificateError as WebEngineCertificateError,
                                          QWebEnginePage as WebEnginePage,
                                          QWebEngineProfile as WebEngineProfile,
                                          QWebEngineView as WebEngineView)
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
        QProxyStyle, \
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

        def __init__(self, resource_files):
            QObject.__init__(self)
            self.player = QMediaPlayer(parent=self)

            self.player.setVolume(100)
            self.playlist = QMediaPlaylist()
            self.player.setPlaylist(self.playlist)
            self.resource_files = resource_files

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
                media_content = QMediaContent(url)
                self.player.setMedia(media_content)
                del url, media_content
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
        """
        Qt5 uses other method than Qt6
        """
        return event.globalPos()


    def get_sort_order_value(sort_order):
        """
        Qt5 has int for Qt.SortOrder but Qt6 has Qt.SortOrder.[Ascending|Descending]Order
        """
        return sort_order


elif QT_FLAVOR == 'PyQt6':
    # PySide/PyQt compatibility
    from PyQt6.QtCore import (pyqtSignal as Signal,
                              pyqtSlot as Slot,
                              PYQT_VERSION_STR as QT_VERSION_STR,
                              QAbstractTableModel,
                              QByteArray,
                              QDateTime,
                              QModelIndex,
                              QObject,
                              QPoint,
                              QSignalMapper,
                              Qt,
                              QThread,
                              QTimer,
                              QUrl,
                              QVariant,
                              QXmlStreamReader)
    from PyQt6.QtGui import (QAction,
                             QBrush,
                             QColor,
                             QCursor,
                             QFont,
                             QFontDatabase,
                             QIcon,
                             QKeySequence,
                             QPainter,
                             QPalette,
                             QPixmap)
    from PyQt6.QtMultimedia import (QAudioOutput,
                                    QMediaDevices,
                                    QMediaPlayer)
    from PyQt6.QtNetwork import (QNetworkCookie,
                                 QNetworkProxy,
                                 QNetworkProxyFactory)
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtSvgWidgets import QSvgWidget
    from PyQt6.QtWebEngineCore import (QWebEngineCertificateError as WebEngineCertificateError,
                                       QWebEnginePage as WebEnginePage,
                                       QWebEngineProfile as WebEngineProfile)
    from PyQt6.QtWebEngineWidgets import QWebEngineView as WebEngineView
    from PyQt6.QtWidgets import (QAbstractItemView,
                                 QApplication,
                                 QColorDialog,
                                 QComboBox,
                                 QDialog,
                                 QFileDialog,
                                 QFontDialog,
                                 QHBoxLayout,
                                 QHeaderView,
                                 QListWidgetItem,
                                 QMenu,
                                 QMenuBar,
                                 QMessageBox,
                                 QLabel,
                                 QProxyStyle,
                                 QPushButton,
                                 QScrollArea,
                                 QSizePolicy,
                                 QSpacerItem,
                                 QToolButton,
                                 QTreeView,
                                 QStyle,
                                 QSystemTrayIcon,
                                 QVBoxLayout,
                                 QWidget)
    from PyQt6 import uic

    # for later decision which differences have to be considered
    QT_FLAVOR = 'PyQt6'


    class MediaPlayer(QObject):
        """
        play media files for notification
        """
        # needed to show error in a thread-safe way
        send_message = Signal(str, str)

        def __init__(self, resource_files):
            QObject.__init__(self)
            # access to media devices
            self.media_devices = QMediaDevices()
            # output needed fpr player
            self.audio_output = QAudioOutput()
            # player gets the output device assigned before playing
            self.player = QMediaPlayer(parent=self)
            self.resource_files = resource_files

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
            """
            play sound on default audio output device, triggered by signal
            """
            try:
                # default audio device
                audio_device = False
                # because devices may change dynamically, get default output device each time before playing
                for audio_device in self.media_devices.audioOutputs():
                    # default device found
                    if audio_device.isDefault():
                        break
                if audio_device:
                    # use audio output device
                    self.audio_output.setDevice(audio_device)
                    # connect player with audio output
                    self.player.setAudioOutput(self.audio_output)
                    # just play sound
                    self.player.play()
            except Exception as error:
                print(error)


    def get_global_position(event):
        """
        Qt5 uses other method than Qt6
        """
        return event.globalPosition()


    def get_sort_order_value(sort_order):
        """
        Qt5 has int for Qt.SortOrder but Qt6 has Qt.SortOrder.[Ascending|Descending]Order
        """
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
#
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
