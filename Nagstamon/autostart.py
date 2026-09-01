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

"""
Start Nagstamon at login on macOS.

Windows gets its autostart entry from the installer and Linux from the .desktop file,
but macOS users had to add Nagstamon to their login items by hand.

A LaunchAgent is used instead of SMAppService because it needs no additional PyObjC
dependency, works for a Nagstamon started from source as well, and is a single file which
can be removed again without a trace. It still shows up in the login items of the system
settings.
"""

import plistlib
import sys
from pathlib import Path

from Nagstamon.config import (conf,
                              OS,
                              OS_MACOS)

LAUNCH_AGENT_LABEL = 'de.nagstamon'
LAUNCH_AGENTS_DIR = Path.home() / 'Library' / 'LaunchAgents'
LAUNCH_AGENT_FILE = LAUNCH_AGENTS_DIR / f'{LAUNCH_AGENT_LABEL}.plist'


def get_application_bundle():
    """
    Path of the .app bundle Nagstamon runs from, or None if it does not run from one
    """
    if not getattr(sys, 'frozen', False):
        return None
    # sys.executable is <bundle>.app/Contents/MacOS/Nagstamon
    for parent in Path(sys.executable).parents:
        if parent.suffix == '.app':
            return parent
    return None


def is_available():
    """
    Autostart can only be offered on macOS and only for an application bundle - there is
    nothing sensible to point a login item at when running from source
    """
    return OS == OS_MACOS and get_application_bundle() is not None


def is_enabled():
    """
    Tell if the LaunchAgent is in place
    """
    return OS == OS_MACOS and LAUNCH_AGENT_FILE.is_file()


def enable():
    """
    Write the LaunchAgent which starts Nagstamon at login

    The configuration directory is passed on so an instance started at login uses the same
    configuration as the one the setting was made in.
    """
    bundle = get_application_bundle()
    if bundle is None:
        return False

    # 'open' is used instead of the bundled executable to let Launch Services start the
    # application the same way a user would
    agent = {'Label': LAUNCH_AGENT_LABEL,
             'ProgramArguments': ['/usr/bin/open',
                                  '-a', str(bundle),
                                  '--args', conf.configdir],
             'RunAtLoad': True}

    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    with LAUNCH_AGENT_FILE.open('wb') as file:
        plistlib.dump(agent, file)
    return True


def disable():
    """
    Remove the LaunchAgent again
    """
    LAUNCH_AGENT_FILE.unlink(missing_ok=True)
    return True


def apply(enabled):
    """
    Bring the LaunchAgent in line with the given setting
    """
    if not is_available():
        return False
    if enabled:
        return enable()
    return disable()
