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

from Nagstamon.Config import (OS,
                              OS_MACOS)


# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)


def hide_macos_dock_icon(hide=False):
    """
    small helper to make dock icon visible or not in macOS
    inspired by https://stackoverflow.com/questions/6796028/start-a-gui-process-in-mac-os-x-without-dock-icon
    """
    if hide:
        NSApp.setActivationPolicy_(NSApplicationPresentationHideDock)
    else:
        NSApp.setActivationPolicy_(NSApplicationPresentationDefault)

