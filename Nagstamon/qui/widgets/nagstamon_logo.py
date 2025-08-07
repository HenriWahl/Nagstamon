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

from Nagstamon.qui.qt import (QSvgWidget,
                              QSizePolicy,
                              Signal)
from Nagstamon.qui.widgets.draggables import DraggableWidget


class NagstamonLogo(QSvgWidget, DraggableWidget):
    """
    SVG based logo, used for statusbar and top area logos
    """
    # yell if statusbar is moved
    window_moved = Signal()

    # needed for popup after hover
    mouse_entered = Signal()

    # needed for popup after click
    mouse_pressed = Signal()
    mouse_released_for_show = Signal()

    def __init__(self, file, width=None, height=None, parent=None):
        QSvgWidget.__init__(self, parent=parent)
        # either filepath or QByteArray for top area logo
        self.load(file)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # size needed for small Nagstamon logo in statusbar
        if width is not None and height is not None:
            self.setMinimumSize(width, height)
            self.setMaximumSize(width, height)

    def adjust_size(self, height=None, width=None):
        if width is not None and height is not None:
            self.setMinimumSize(width, height)
            self.setMaximumSize(width, height)
