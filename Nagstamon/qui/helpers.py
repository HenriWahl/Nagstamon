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

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)
from Nagstamon.helpers import STATES
from Nagstamon.qui.constants import (COLORS,
                                     QBRUSHES)
from Nagstamon.qui.qt import (QColor,
                              QObject,
                              Signal,
                              Slot)
from Nagstamon.Servers import servers

# make icon status in macOS dock accessible via NSApp, used by set_macos_dock_icon_visible()
if OS == OS_MACOS:
    from AppKit import (NSApp,
                        NSApplicationPresentationDefault,
                        NSApplicationPresentationHideDock)


class CheckServers(QObject):
    """
    check if there are any servers configured and enabled
    """
    # signal to emit if no server is configured or enabled
    checked = Signal(str)

    @Slot()
    def check(self):
        """
        check if there are any servers configured and enabled
        """
        # no server is configured
        if len(servers) == 0:
            # emit signal that no server is configured
            self.checked.emit('no_server')
        # no server is enabled
        elif len([x for x in conf.servers.values() if x.enabled is True]) == 0:
            # emit signal that no server is enabled
            self.checked.emit('no_server_enabled')


def hide_macos_dock_icon(hide=False):
    """
    small helper to make dock icon visible or not in macOS
    inspired by https://stackoverflow.com/questions/6796028/start-a-gui-process-in-mac-os-x-without-dock-icon
    """
    if hide:
        NSApp.setActivationPolicy_(NSApplicationPresentationHideDock)
    else:
        NSApp.setActivationPolicy_(NSApplicationPresentationDefault)


def create_brushes():
    """
        fill static brushes with current colors for treeview
    """
    # if not customized, use default intensity
    if conf.grid_use_custom_intensity:
        intensity = 100 + conf.grid_alternation_intensity
    else:
        intensity = 115

    # every state has 2 labels in both alteration levels 0 and 1
    for state in STATES[1:]:
        for role in ('text', 'background'):
            QBRUSHES[0][COLORS[state] + role] = QColor(conf.__dict__[COLORS[state] + role])
            # if the background is too dark to be litten split it into RGB values
            # and increase them separately
            # light/darkness spans from 0 to 255 - 30 is just a guess
            if role == 'background' and conf.show_grid:
                if QBRUSHES[0][COLORS[state] + role].lightness() < 30:
                    r, g, b, a = (QBRUSHES[0][COLORS[state] + role].getRgb())
                    r += 30
                    g += 30
                    b += 30
                    QBRUSHES[1][COLORS[state] + role] = QColor(r, g, b).lighter(intensity)
                else:
                    # otherwise just make it a little bit darker
                    QBRUSHES[1][COLORS[state] + role] = QColor(conf.__dict__[COLORS[state] +
                                                                             role]).darker(intensity)
            else:
                # only make the background darker; the text should stay as it is
                QBRUSHES[1][COLORS[state] + role] = QBRUSHES[0][COLORS[state] + role]

# to be used in nagstamon.py and qui/widgets/dialogs/settings.py
check_servers = CheckServers()
