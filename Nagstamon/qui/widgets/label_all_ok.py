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

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)

from Nagstamon.qui.qt import (QLabel,
                              QSizePolicy,
                              Qt,
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
        self.setStyleSheet('''padding-left: 1px;
                              padding-right: 1px;
                              color: %s;
                              background-color: %s;
                              font-size: 92px;
                              font-weight: bold;'''
                           % (conf.__dict__['color_ok_text'],
                              conf.__dict__['color_ok_background']))