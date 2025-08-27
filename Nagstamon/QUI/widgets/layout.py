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

from Nagstamon.QUI.qt import QHBoxLayout


class HBoxLayout(QHBoxLayout):
    """
    Custom QHBoxLayout with zero spacing and margins by default.

    This layout is used to create a horizontal box.

    Args:
        spacing (int, optional): Space between child widgets. Defaults to 0.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, spacing=None, parent=None):
        QHBoxLayout.__init__(self, parent)

        if spacing is None:
            self.setSpacing(0)
        else:
            self.setSpacing(spacing)
        # no margin
        self.setContentsMargins(0, 0, 0, 0)
