#!/usr/bin/env python
# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2015 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

# for python2 and upcomping python3 compatiblity
from __future__ import print_function, absolute_import, unicode_literals

import sys
import os
import os.path
import socket
from PyQt5.QtWidgets import *

# Initialize global configuration
from Nagstamon.Config import conf

from Nagstamon.QUI import QUI

# try to get resources path if nagstamon got be installed by setup.py
Resources = ""
try:
    import pkg_resources
    Resources = pkg_resources.resource_filename("Nagstamon", "resources")
except Exception, err:
    # get resources directory from current directory - only if not being set before by pkg_resources
    # try-excepts necessary for platforms like Windows .EXE
    join = os.path.join
    normcase = os.path.normcase
    paths_to_check = [normcase(join(os.getcwd(), "Nagstamon", "resources")),
            normcase(join(os.getcwd(), "resources"))]
    try:
        # if resources dir is not available in CWD, try the
        # libs dir (site-packages) for the current Python
        from distutils.sysconfig import get_python_lib
        paths_to_check.append(normcase(join(get_python_lib(), "Nagstamon", "resources")))
    except:
        pass

    #if we're still out of luck, maybe this was a user scheme install
    try:
        import site
        site.getusersitepackages() #make sure USER_SITE is set
        paths_to_check.append(normcase(join(site.USER_SITE, "Nagstamon", "resources")))
    except:
        pass

    # add directory nagstamon.py where nagstamon.py resides for cases like 0install without installed pkg-resources
    paths_to_check.append(os.sep.join(sys.argv[0].split(os.sep)[:-1] + ["Nagstamon", "resources"]))

    for path in paths_to_check:
        if os.path.exists(path):
            Resources = path
            break

# dictionary for servers
servers = dict()

# fix/patch for https://bugs.launchpad.net/ubuntu/+source/nagstamon/+bug/732544
socket.setdefaulttimeout(30)

try:
    if __name__ == "__main__":
        app = QApplication(sys.argv)
        sys.exit(app.exec_())
except Exception as err:
    print(err)