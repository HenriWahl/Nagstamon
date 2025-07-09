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

from Nagstamon.qui.qt import (QMenu, \
                              QCursor,
                              QPoint,
                              Signal,
                              Slot)


class MenuAtCursor(QMenu):
    """
    Displays the menu at the current mouse pointer position.

    Signals:
        is_shown (bool): Emitted with True when the menu is shown, and with False when it is closed.

    Args:
        parent (QWidget, optional): The parent widget of the menu.

    Methods:
        show_at_cursor(): Shows the menu at the current mouse pointer position and emits is_shown signals.
    """
    # flag to avoid too fast popping up menus
    # available = True

    is_shown = Signal(bool)

    def __init__(self, parent=None):
        QMenu.__init__(self, parent=parent)

    @Slot()
    def show_at_cursor(self):
        """
        Pop up at mouse pointer position, lock itself to avoid constantly popping menus on Windows
        """
        # get cursor coordinates and decrease them to show menu under mouse pointer
        x = QCursor.pos().x() - 10
        y = QCursor.pos().y() - 10
        # tell the world that the menu will be shown
        self.is_shown.emit(True)
        # show menu
        self.exec(QPoint(x, y))
        # tell world that menu will be closed
        self.is_shown.emit(False)
        del (x, y)
