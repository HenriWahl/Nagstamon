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

from platform import release
from os import sep
from sys import argv

from Nagstamon.config import (OS,
                              OS_WINDOWS,
                              RESOURCES)
from Nagstamon.qui.qt import (Qt,
                              QApplication,
                              QFontDatabase,
                              QT_VERSION_MAJOR)
from Nagstamon.qui.widgets.buttons import StandardDialogIconsProxyStyle

# since Qt6 HighDPI-awareness is default behaviour
if QT_VERSION_MAJOR < 6:
    # enable HighDPI-awareness to avoid https://github.com/HenriWahl/Nagstamon/issues/618
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    except AttributeError:
        pass
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


# global application instance
app = QApplication(argv)

# set style for tooltips globally - to sad not all properties can be set here
app.setStyleSheet('''QToolTip { margin: 3px;
                                }''')

# proxy style helps to remove ugly icons in Linux Fusion style
app.setStyle(StandardDialogIconsProxyStyle())

# as long as Windows 11 + Qt6 looks that ugly it's better to choose another app style
# might be mitigated with sometimes, so commented out now
if OS == OS_WINDOWS and release() >= '11':
    app.setStyle('fusion')

# add nagstamon.ttf with icons to fonts
QFontDatabase.addApplicationFont(f'{RESOURCES}{sep}nagstamon.ttf')