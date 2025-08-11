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
from time import time

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)
from Nagstamon.qui.constants import COLOR_STATUS_LABEL
from Nagstamon.qui.globals import statuswindow_properties

from Nagstamon.qui.qt import (QLabel,
                              QSizePolicy,
                              Qt,
                              Signal,
                              Slot)


class LabelAllOK(QLabel):
    """
        Label which is shown in fullscreen and windowed mode when all is OK - pretty seldomly
    """

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text='OK', parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_color()

    @Slot()
    def set_color(self):
        self.setStyleSheet(f'''padding-left: 1px;
                               padding-right: 1px;
                               color: {conf.__dict__['color_ok_text']};
                               background-color: {conf.__dict__['color_ok_background']};
                               font-size: 92px;
                               font-weight: bold;
                            ''')


class ClosingLabel(QLabel):
    """
    modified QLabel which might close the status window if left-clicked
    """

    parent_statuswindow = None
    # neede to close status window
    mouse_released = Signal()

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text, parent=parent)

    def mouseReleaseEvent(self, event):
        """
        left click and configured close-if-clicking-somewhere makes status window close
        """
        # update access to status window
        self.parent_statuswindow = self.parentWidget().parentWidget()
        if event.button() == Qt.MouseButton.LeftButton and conf.close_details_clicking_somewhere:
            # if popup window should be closed by clicking do it now
            if statuswindow_properties.is_shown and \
                    not conf.fullscreen and \
                    not conf.windowed:
                statuswindow_properties.is_hiding_timestamp = time()
                self.mouse_released.emit()


class ServerStatusLabel(ClosingLabel):
    """
    label for ServerVBox to show server connection state
    extra class to apply simple slots for changing text or color
    """

    # storage for label text if it needs to be restored
    text_old = ''

    def __init__(self, parent=None):
        QLabel.__init__(self, parent=parent)

    @Slot(str, str)
    def change(self, text, style=''):
        # store old text and stylesheet in case it needs to be reused
        self.text_old = self.text()
        self.stylesheet_old = self.styleSheet()

        # set stylesheet depending on submitted style
        if style in COLOR_STATUS_LABEL:
            if OS == OS_MACOS:
                self.setStyleSheet(f'''background: {COLOR_STATUS_LABEL[style]};
                                       border-radius: 3px;
                                    ''')
            else:
                self.setStyleSheet(f'''background: {COLOR_STATUS_LABEL[style]};
                                       margin-top: 8px;
                                       padding-top: 3px;
                                       margin-bottom: 8px;
                                       padding-bottom: 3px;
                                       border-radius: 4px;
                                       ''')
        elif style == '':
            self.setStyleSheet('')

        # in case of unknown errors try to avoid freaking out status window with too
        # big status label
        if style != 'unknown':
            # set new text with some space
            self.setText(' {0} '.format(text))
            self.setToolTip('')
        else:
            # set new text to first word of text, delegate full text to tooltip
            self.setText(text.split(' ')[0])
            self.setToolTip(text)

    @Slot()
    def reset(self):
        self.setStyleSheet(self.stylesheet_old)
        self.setText('')

    @Slot()
    def restore(self):
        # restore text, used by recheck_all of tablewidget worker
        self.setStyleSheet(self.stylesheet_old)
        self.setText(self.text_old)