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

import os
import sys
###import psutil
###import getpass
import socket

# fix/patch for https://bugs.launchpad.net/ubuntu/+source/nagstamon/+bug/732544
socket.setdefaulttimeout(30)


try:
    if __name__ == '__main__':
        # Initialize global configuration
        from Nagstamon.Config import (conf,
                                      RESOURCES)

        from Nagstamon.Helpers import lock_config_folder

        # Acquire the lock
        if not lock_config_folder(conf.configdir):
            print('An instance is already running this config ({})'.format(conf.configdir))
            sys.exit(1)

        # get GUI
        from Nagstamon.QUI import (APP,
                                   statuswindow,
                                   check_version,
                                   check_servers,
                                   dialogs)
        # get server information
        from Nagstamon.Servers import (servers,
                                       get_enabled_servers)

        # ask for help if no servers are configured
        check_servers()

        # show and resize status window
        statuswindow.show()
        statuswindow.adjustSize()

        if conf.check_for_new_version == True:
            check_version.check(start_mode = True, parent=statuswindow)

        sys.exit(APP.exec_())


except Exception as err:
    import traceback
    traceback.print_exc(file=sys.stdout)
