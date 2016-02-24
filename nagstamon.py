#!/usr/bin/env python3
# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2016 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import sys
import socket

# fix/patch for https://bugs.launchpad.net/ubuntu/+source/nagstamon/+bug/732544
socket.setdefaulttimeout(30)

try:
    if __name__ == "__main__":
        # Initialize global configuration
        from Nagstamon.Config import (conf, RESOURCES)

        from Nagstamon.QUI import (APP, statuswindow, check_version)

        statuswindow.show()
        statuswindow.adjustSize()

        if conf.check_for_new_version == True:
            check_version.check(start_mode = True, parent=statuswindow)

        sys.exit(APP.exec_())


except Exception as err:
    import traceback
    traceback.print_exc(file=sys.stdout)
