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
from time import time

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)
from Nagstamon.qui.constants import COLOR_STATUS_LABEL
from Nagstamon.qui.globals import (font,
                                   statuswindow_properties)

from Nagstamon.qui.qt import (QLabel,
                              QSizePolicy,
                              Qt,
                              Signal,
                              Slot)


class LabelAllOK(QLabel):
    """
    label which is shown in fullscreen and windowed mode when all is OK - pretty seldomly
    """

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text='OK', parent=parent)
        self.setObjectName('LabelAllOK')  # For QSS styling
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(font)
        self.set_color()

    @Slot()
    def set_color(self):
        # Apply user-configurable colors (these must remain dynamic)
        # Note: inline styles must include QSS properties to avoid losing them
        self.setStyleSheet(f'''color: {conf.__dict__['color_ok_text']};
                               background-color: {conf.__dict__['color_ok_background']};
                               padding-left: 4px;
                               padding-right: 4px;
                               font-size: 92px;
                               font-weight: bold;
                            ''')


class ClosingLabel(QLabel):
    """
    modified QLabel which might close the status window if left-clicked
    """
    # neede to close status window
    mouse_released = Signal()

    def __init__(self, text='', parent=None):
        QLabel.__init__(self, text, parent=parent)
        self.parent_statuswindow = None

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

    def __init__(self, parent=None):
        QLabel.__init__(self, parent=parent)
        self.setObjectName('ServerStatusLabel')  # For QSS styling
        # storage for label text if it needs to be restored
        self.text_old = ''
        self.stylesheet_old = None

    @Slot(str, str)
    def change(self, text, style=''):
        # store old text and stylesheet in case it needs to be reused
        self.text_old = self.text()
        self.stylesheet_old = self.styleSheet()

        # set stylesheet depending on submitted style
        # Dynamic colors must remain inline as they're user-configurable
        # Note: inline styles must include QSS properties to avoid losing them
        if style in COLOR_STATUS_LABEL:
            self.setStyleSheet(f'''background: {COLOR_STATUS_LABEL[style]};
                                   border-radius: 6px;
                                   padding: 4px 8px;''')
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