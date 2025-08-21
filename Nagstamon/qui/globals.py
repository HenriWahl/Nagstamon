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

from dataclasses import dataclass

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS,
                              RESOURCES)
from Nagstamon.helpers import FilesDict
from Nagstamon.qui.dbus import DBus
from Nagstamon.qui.qt import QFont
from Nagstamon.qui.widgets.app import app


# save default font to be able to reset to it
font_default = app.font()

# take global font from conf if it exists
if conf.font != '':
    font = QFont()
    font.fromString(conf.font)
else:
    font = font_default

# always stay in normal weight without any italic
font_icons = QFont('Nagstamon', font.pointSize() + 2, QFont.Weight.Normal, False)

# DBus initialization
dbus_connection = DBus()

# check ECP authentication support availability
try:
    from requests_ecp import HTTPECPAuth
    ecp_available = True
except ImportError:
    ecp_available = False

# flag to keep track of Kerberos availability
kerberos_available = False
if OS == OS_MACOS:
    # requests_gssapi is newer but not available everywhere
    try:
        # extra imports needed to get it compiled on macOS
        import numbers
        import gssapi.raw.cython_converters
        from requests_gssapi import HTTPSPNEGOAuth as HTTPSKerberos
        kerberos_available = True
    except ImportError as error:
        print(error)
else:
    # requests_gssapi is newer but not available everywhere
    try:
        # requests_gssapi needs installation of KfW - Kerberos for Windows
        # requests_kerberoes doesn't
        from requests_kerberos import HTTPKerberosAuth as HTTPSKerberos
        kerberos_available = True
    except ImportError as error:
        print(error)


@dataclass
class StatusWindowProperties:
    """
    storing statuswindow related variables globally available for several classes
    """
    icon_x: int = 0
    icon_y: int = 0
    is_shown: bool = False
    is_shown_timestamp: float = 0.0
    is_hiding_timestamp: float = 0.0
    moving: bool = False
    relative_x: int = 0
    relative_y: int = 0
    status_ok: bool = True
    top: bool = False
    # flag about current notification state
    is_notifying: bool = False
    # current worst state worth a notification
    worst_notification_status: str = 'UP'
    notifying_server: str = ''
    debug_loop_looping = False

# shared status window properties
statuswindow_properties = StatusWindowProperties()

# access to clipboard
clipboard = app.clipboard()

# QBrushes made of QColors for treeview model data() method
# 2 flavours for alternating backgrounds
# filled by create_brushes()
qbrushes = {0: {}, 1: {}}

# store default sounds as buffers to avoid https://github.com/HenriWahl/Nagstamon/issues/578
# meanwhile used as backup copy in case they had been deleted by macOS
# https://github.com/HenriWahl/Nagstamon/issues/578
resource_files = FilesDict(RESOURCES)