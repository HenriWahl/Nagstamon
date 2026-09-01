#!/usr/bin/env python3
# encoding: utf-8

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

import importlib.util
import os
import sys
import socket

# make sure to inject truststore into ssl very early
if importlib.util.find_spec('truststore') is not None:
    import truststore
    truststore.inject_into_ssl()

# fix/patch for https://bugs.launchpad.net/ubuntu/+source/nagstamon/+bug/732544
socket.setdefaulttimeout(30)

try:
    if __name__ == '__main__':
        from Nagstamon.config import (conf,
                                      debug_queue,
                                      OS,
                                      OS_WINDOWS)

        from Nagstamon.helpers import (is_translated_by_rosetta,
                                       lock_config_folder)

        # Acquire the lock
        if not lock_config_folder(conf.configdir):
            print('An instance is already running this config ({})'.format(conf.configdir))
            sys.exit(1)

        # an Intel build started on Apple Silicon works, but slower and with subtle Qt
        # differences - saying so saves everybody from debugging the wrong download
        if is_translated_by_rosetta():
            message = 'Running the Intel build translated by Rosetta - ' \
                      'please use the ARM build for Apple Silicon Macs.'
            print(message)
            debug_queue.append(message)

        # get GUI
        from Nagstamon.qui import (app,
                                   check_version,
                                   statuswindow)
        from Nagstamon.qui.helpers import check_servers

        # ask for help if no servers are configured
        check_servers.check()

        # show and resize the status window
        statuswindow.show()
        if not conf.fullscreen:
            statuswindow.adjustSize()

        if conf.check_for_new_version is True:
            check_version.check(start_mode=True, parent=statuswindow)

        exit_code = app.exec()

        # leave without the Python and Qt teardown: a worker thread which is stuck in a
        # request running into the socket timeout cannot be stopped in time, and destroying
        # its QThread while it is still running makes Qt call qFatal() - see
        # https://github.com/HenriWahl/Nagstamon/issues/1055
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)

except Exception as err:
    import traceback
    traceback.print_exc(file=sys.stdout)
