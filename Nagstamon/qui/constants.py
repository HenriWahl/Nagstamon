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

# Constants for Qt

from collections import OrderedDict
from os import sep
from platform import system

from Nagstamon.config import (AppInfo,
                              RESOURCES)
from Nagstamon.qui.qt import (QIcon,
                              Qt)

# fixed shortened and lowered color names for cells, also used by statusbar label snippets
COLORS = OrderedDict([('DOWN', 'color_down_'),
                      ('UNREACHABLE', 'color_unreachable_'),
                      ('DISASTER', 'color_disaster_'),
                      ('CRITICAL', 'color_critical_'),
                      ('HIGH', 'color_high_'),
                      ('AVERAGE', 'color_average_'),
                      ('WARNING', 'color_warning_'),
                      ('INFORMATION', 'color_information_'),
                      ('UNKNOWN', 'color_unknown_')])

# states to be used in statusbar if the long version is used
COLOR_STATE_NAMES = {'DOWN': {True: 'DOWN', False: ''},
                     'UNREACHABLE': {True: 'UNREACHABLE', False: ''},
                     'DISASTER': {True: 'DISASTER', False: ''},
                     'CRITICAL': {True: 'CRITICAL', False: ''},
                     'HIGH': {True: 'HIGH', False: ''},
                     'AVERAGE': {True: 'AVERAGE', False: ''},
                     'WARNING': {True: 'WARNING', False: ''},
                     'INFORMATION': {True: 'INFORMATION', False: ''},
                     'UNKNOWN': {True: 'UNKNOWN', False: ''}}

# colors for server status label in ServerVBox
COLOR_STATUS_LABEL = {'critical': 'lightsalmon',
                      'error': 'orange',
                      'unknown': 'gray'}

# headers for tablewidgets
HEADERS = OrderedDict([('host', {'header': 'Host',
                                 'column': 0}),
                       ('host_flags', {'header': '',
                                       'column': 0}),
                       ('service', {'header': 'Service',
                                    'column': 2}),
                       ('service_flags', {'header': '',
                                          'column': 2}),
                       ('status', {'header': 'Status',
                                   'column': 4}),
                       ('last_check', {'header': 'Last Check',
                                       'column': 5}),
                       ('duration', {'header': 'Duration',
                                     'column': 6}),
                       ('attempt', {'header': 'Attempt',
                                    'column': 7}),
                       ('status_information', {'header': 'Status Information',
                                               'column': 8}),
                       ('dummy_column', {'header': '',
                                         'column': 8})])

# various headers-key-columns variations needed in different parts
HEADERS_HEADERS = list()
for item in HEADERS.values():
    HEADERS_HEADERS.append(item['header'])

HEADERS_HEADERS_COLUMNS = dict()
for item in HEADERS.values():
    HEADERS_HEADERS_COLUMNS[item['header']] = item['column']

HEADERS_HEADERS_KEYS = dict()
for item in HEADERS.keys():
    HEADERS_HEADERS_KEYS[HEADERS[item]['header']] = item

HEADERS_KEYS_COLUMNS = dict()
for item in HEADERS.keys():
    HEADERS_KEYS_COLUMNS[item] = HEADERS[item]['column']

HEADERS_KEYS_HEADERS = dict()
for item in HEADERS.keys():
    HEADERS_KEYS_HEADERS[item] = HEADERS[item]['header']

# sorting order for tablewidgets
SORT_ORDER = {'descending': 1, 'ascending': 0, 0: Qt.SortOrder.DescendingOrder, 1: Qt.SortOrder.AscendingOrder}

# bend columns 1 and 3 to 0 and 2 to avoid sorting the extra flag icons of hosts and services
SORT_COLUMNS_INDEX = {0: 0,
                      1: 0,
                      2: 2,
                      3: 2,
                      4: 4,
                      5: 5,
                      6: 6,
                      7: 7,
                      8: 8,
                      9: 8}

# space used in LayoutBoxes - increased for modern look
SPACE = 15

# Flags for statusbar - experiment with Qt.ToolTip for Windows because
# statusbar permanently seems to vanish at some users desktops
# see https://github.com/HenriWahl/Nagstamon/issues/222
WINDOW_FLAGS = Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool

# icon for dialogs
ICON = QIcon(f'{RESOURCES}{sep}nagstamon.ico')
