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

from Nagstamon.config import conf
from Nagstamon.qui.constants import HEADERS_HEADERS
from Nagstamon.qui.globals import font_icons
from Nagstamon.qui.qt import (QAbstractTableModel,
                              Qt,
                              QVariant,
                              Signal,
                              Slot)


class Model(QAbstractTableModel):
    """
    model for storing status data to be presented in Treeview-table
    """

    model_data_array_filled = Signal()

    # list of lists for storage of status data
    data_array = list()

    # cache row and column count
    row_count = 0
    column_count = len(HEADERS_HEADERS)

    # tell treeview if flags columns should be hidden or not
    hosts_flags_column_needed = Signal(bool)
    services_flags_column_needed = Signal(bool)

    def __init__(self, server, parent=None):
        QAbstractTableModel.__init__(self, parent=parent)
        self.server = server

    def rowCount(self, parent):
        """
        overridden method to get number of rows
        """
        return self.row_count

    def columnCount(self, parent):
        """
        overridden method to get number of columns
        """
        return self.column_count

    def headerData(self, column, orientation, role):
        """
        overridden method to get headers of columns
        """
        if role == Qt.ItemDataRole.DisplayRole:
            return HEADERS_HEADERS[column]
        return None

    @Slot(list, dict)
    # @Slot(list)
    def fill_data_array(self, data_array, info):
        """
        fill data_array for model
        """
        # tell treeview that model is about to change - necessary because
        # otherwise new number of rows would not be applied
        self.beginResetModel()

        # first empty the data storage
        del self.data_array[:]

        # use delivered data array
        self.data_array = data_array

        # cache row_count
        self.row_count = len(self.data_array)

        # tell treeview if flags columns are needed
        self.hosts_flags_column_needed.emit(info['hosts_flags_column_needed'])
        self.services_flags_column_needed.emit(info['services_flags_column_needed'])

        # new model applied
        self.endResetModel()

        self.model_data_array_filled.emit()

    def data(self, index, role):
        """
        overridden method for data delivery for treeview
        """
        if role == Qt.ItemDataRole.DisplayRole:
            return self.data_array[index.row()][index.column()]

        elif role == Qt.ItemDataRole.ForegroundRole:
            return self.data_array[index.row()][10]

        elif role == Qt.ItemDataRole.BackgroundRole:
            return self.data_array[index.row()][11]

        elif role == Qt.ItemDataRole.FontRole:
            if index.column() == 1:
                return font_icons
            elif index.column() == 3:
                return font_icons
            else:
                return QVariant
        # provide icons via Qt.UserRole
        elif role == Qt.ItemDataRole.UserRole:
            # depending on host or service column return host or service icon list
            return self.data_array[index.row()][7 + index.column()]

        elif role == Qt.ItemDataRole.ToolTipRole:
            # only if tooltips are wanted show them, combining host + service + status_info
            if conf.show_tooltips:
                return (f'<div style=white-space:pre;margin:3px;>'
                        f'<b>{self.data_array[index.row()][0]}: {self.data_array[index.row()][2]}</b>'
                        f'</div>'
                        f'{self.data_array[index.row()][8]}')
            else:
                return QVariant
        return None