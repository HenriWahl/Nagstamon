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

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)
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

# check ECP authentication support availability
try:
    from requests_ecp import HTTPECPAuth
    ECP_AVAILABLE = True
except ImportError:
    ECP_AVAILABLE = False

# flag to keep track of Kerberos availability
KERBEROS_AVAILABLE = False
if OS == OS_MACOS:
    # requests_gssapi is newer but not available everywhere
    try:
        # extra imports needed to get it compiled on macOS
        import numbers
        import gssapi.raw.cython_converters
        from requests_gssapi import HTTPSPNEGOAuth as HTTPSKerberos
        KERBEROS_AVAILABLE = True
    except ImportError as error:
        print(error)
else:
    # requests_gssapi is newer but not available everywhere
    try:
        # requests_gssapi needs installation of KfW - Kerberos for Windows
        # requests_kerberoes doesn't
        from requests_kerberos import HTTPKerberosAuth as HTTPSKerberos
        KERBEROS_AVAILABLE = True
    except ImportError as error:
        print(error)