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

# Global variables used in different modules

from Nagstamon.qui.qt import QFont

from Nagstamon.config import conf
from Nagstamon.qui.dbus import DBus
from Nagstamon.qui.widgets.app import app


# save default font to be able to reset to it
DEFAULT_FONT = app.font()

# take global FONT from conf if it exists
if conf.font != '':
    FONT = QFont()
    FONT.fromString(conf.font)
else:
    FONT = DEFAULT_FONT

# DBus initialization
dbus_connection = DBus()

pass