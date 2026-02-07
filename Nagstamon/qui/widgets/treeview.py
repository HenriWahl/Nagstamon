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
from copy import deepcopy
from datetime import datetime
from subprocess import Popen
from sys import stdout
from traceback import print_exc
from urllib.parse import quote

from Nagstamon.config import conf
from Nagstamon.helpers import (is_found_by_re,
                               STATES,
                               SORT_COLUMNS_FUNCTIONS,
                               urlify,
                               webbrowser_open)
from Nagstamon.qui.constants import (COLORS,
                                     HEADERS,
                                     SORT_COLUMNS_INDEX,
                                     SORT_ORDER)
from Nagstamon.qui.dialogs.weblogin import DialogWebLogin
from Nagstamon.qui.globals import (clipboard,
                                   font,
                                   qbrushes,
                                   statuswindow_properties)
from Nagstamon.qui.qt import (get_sort_order_value,
                              QAbstractItemView,
                              QAction,
                              QColor,
                              QHeaderView,
                              QKeySequence,
                              QMenu,
                              QObject,
                              QSignalMapper,
                              QSizePolicy,
                              Qt,
                              QThread,
                              QTimer,
                              QTreeView,
                              Signal,
                              Slot)
from Nagstamon.qui.widgets.app import app
from Nagstamon.qui.widgets.menu import MenuAtCursor
from Nagstamon.qui.widgets.model import Model
from Nagstamon.servers import SERVER_TYPES, servers


class TreeView(QTreeView):
    """
    attempt to get a less resource-hungry table/tree
    """

    # tell global window that it should be resized
    ready_to_resize = Signal()

    # sent by refresh() for statusbar
    refreshed = Signal()

    # tell worker to get status after a recheck has been solicited
    recheck = Signal(dict)

    # tell notification that status of server has changed
    status_changed = Signal(str, str, str)

    # action to be executed by worker
    # 2 values: action and host/service info
    request_action = Signal(dict, dict)

    # tell worker it should sort columns after someone pressed the column header
    sort_data_array_for_columns = Signal(int, int, bool)

    # mouse clicked on cell
    mouse_released = Signal()

    # action menu option was selected
    action_menu_clicked = Signal()

    # action to edit actions in settings dialog
    action_edit_triggered = Signal(int)

    # action acknowledge triggered, needs to be initialized and shown
    action_acknowledge_triggered_initialize = Signal(object, list, list)
    action_acknowledge_triggered_show = Signal()

    # action downtime triggered, needs to be initialized and shown
    action_downtime_triggered_initialize = Signal(object, list, list)
    action_downtime_triggered_show = Signal()

    # action submit check result triggered, needs to be initialized and shown
    action_submit_triggered_initialize = Signal(object, str, str)
    action_submit_triggered_show = Signal()

    def __init__(self, columncount, rowcount, sort_column, sort_order, server, parent=None):
        QTreeView.__init__(self, parent=parent)

        self.parent_statuswindow = self.parentWidget()

        self.sort_column = sort_column
        self.sort_order = sort_order
        self.server = server

        # no handling of selection by treeview
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # disable space on the left side
        self.setRootIsDecorated(False)
        self.setIndentation(0)

        self.setUniformRowHeights(True)

        # no scrollbars at tables because they will be scrollable by the global vertical scrollbar
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAutoScroll(False)
        self.setSortingEnabled(True)

        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        self.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSortIndicatorShown(True)
        self.header().setStretchLastSection(True)

        self.header().setSortIndicator(sort_column, SORT_ORDER[self.sort_order])

        # small method needed to tell worker which column and sort order to use
        self.header().sortIndicatorChanged.connect(self.sort_columns)

        # Set object name for QSS styling - styling is now centralized in modern_theme.qss
        self.setObjectName('TreeView')

        # set application font
        self.set_font()

        # change font if it has been changed by settings
        self.parent_statuswindow.injected_dialogs.settings.changed.connect(self.set_font)

        # create brushes if colors have been changed
        self.parent_statuswindow.injected_dialogs.settings.changed.connect(self.create_brushes)

        # create brushes for treeview
        self.create_brushes()

        # action context menu
        self.action_menu = MenuAtCursor(parent=self)
        # signalmapper for getting triggered actions
        self.signalmapper_action_menu = QSignalMapper()
        # connect menu to responder
        self.signalmapper_action_menu.mappedString[str].connect(self.action_menu_custom_response)

        # clipboard actions
        self.clipboard_menu = QMenu('Copy to clipboard', self)

        self.clipboard_action_host = QAction('Host', self)
        self.clipboard_action_host.triggered.connect(self.action_clipboard_action_host)
        self.clipboard_menu.addAction(self.clipboard_action_host)

        self.clipboard_action_service = QAction('Service', self)
        self.clipboard_action_service.triggered.connect(self.action_clipboard_action_service)
        self.clipboard_menu.addAction(self.clipboard_action_service)

        self.clipboard_action_statusinformation = QAction('Status information', self)
        self.clipboard_action_statusinformation.triggered.connect(self.action_clipboard_action_statusinformation)
        self.clipboard_menu.addAction(self.clipboard_action_statusinformation)

        self.clipboard_action_all = QAction('All information', self)
        self.clipboard_action_all.triggered.connect(self.action_clipboard_action_all)
        self.clipboard_menu.addAction(self.clipboard_action_all)

        self.setModel(Model(server=self.server, parent=self))
        self.model().model_data_array_filled.connect(self.adjust_table)
        self.model().hosts_flags_column_needed.connect(self.show_hosts_flags_column)
        self.model().services_flags_column_needed.connect(self.show_services_flags_column)

        # a thread + worker is necessary to get new monitor server data in the background and
        # to refresh the table cell by cell after new data is available
        self.worker_thread = QThread(parent=self)
        self.worker = self.Worker(server=server, sort_column=self.sort_column, sort_order=self.sort_order, status_window=self.parent_statuswindow)
        self.worker.moveToThread(self.worker_thread)

        # if worker got new status data from monitor server get_status
        # the treeview model has to be updated
        self.worker.worker_data_array_filled.connect(self.model().fill_data_array)

        # fill array again if data has been sorted after a header column click
        self.worker.data_array_sorted.connect(self.model().fill_data_array)

        # tell worker to sort data_array depending on sort_column and sort_order
        self.sort_data_array_for_columns.connect(self.worker.sort_data_array)

        # if worker got new status data from monitor server get_status the table should be refreshed
        self.worker.new_status.connect(self.refresh)

        # quit thread if worker has finished
        self.worker.finish.connect(self.finish_worker_thread)

        # get status if started
        self.worker_thread.started.connect(self.worker.get_status)
        # start with priority 0 = lowest
        self.worker_thread.start()

        # connect signal for acknowledge
        self.parent_statuswindow.injected_dialogs.acknowledge.acknowledge.connect(self.worker.acknowledge)

        # connect signal to get start end time for downtime from worker
        self.parent_statuswindow.injected_dialogs.downtime.get_start_end.connect(self.worker.get_start_end)
        self.worker.set_start_end.connect(self.parent_statuswindow.injected_dialogs.downtime.set_start_end)

        # connect signal for downtime
        self.parent_statuswindow.injected_dialogs.downtime.downtime.connect(self.worker.downtime)

        # connect signal for submit check result
        self.parent_statuswindow.injected_dialogs.submit.submit.connect(self.worker.submit)

        # connect signal for recheck action
        self.recheck.connect(self.worker.recheck)

        # execute action by worker
        self.request_action.connect(self.worker.execute_action)

        # hide status window if mouse was clicked ant it is configured to do so
        self.mouse_released.connect(self.parent_statuswindow.hide_window)

        # option of action menu was selected
        self.action_menu_clicked.connect(self.parent_statuswindow.hide_window)

        # edit actions in settings dialog in tab #3
        self.action_edit_triggered.connect(self.parent_statuswindow.injected_dialogs.settings.show)

        # intialize and open acknowledge dialog
        self.action_acknowledge_triggered_initialize.connect(self.parent_statuswindow.injected_dialogs.acknowledge.initialize)
        self.action_acknowledge_triggered_show.connect(self.parent_statuswindow.injected_dialogs.acknowledge.show)

        # intialize and open downtime dialog
        self.action_downtime_triggered_initialize.connect(self.parent_statuswindow.injected_dialogs.downtime.initialize)
        self.action_downtime_triggered_show.connect(self.parent_statuswindow.injected_dialogs.downtime.show)

        # intialize and open submit check result dialog
        self.action_submit_triggered_initialize.connect(self.parent_statuswindow.injected_dialogs.submit.initialize)
        self.action_submit_triggered_show.connect(self.parent_statuswindow.injected_dialogs.submit.show)

    @Slot()
    def set_font(self):
        """
        change font if it has been changed by settings
        """
        self.setFont(font)

    @Slot()
    def create_brushes(self):
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
                qbrushes[0][COLORS[state] + role] = QColor(conf.__dict__[COLORS[state] + role])
                # if the background is too dark to be litten split it into RGB values
                # and increase them separately
                # light/darkness spans from 0 to 255 - 30 is just a guess
                if role == 'background' and conf.show_grid:
                    if qbrushes[0][COLORS[state] + role].lightness() < 30:
                        r, g, b, a = (qbrushes[0][COLORS[state] + role].getRgb())
                        r += 30
                        g += 30
                        b += 30
                        qbrushes[1][COLORS[state] + role] = QColor(r, g, b).lighter(intensity)
                    else:
                        # otherwise just make it a little bit darker
                        qbrushes[1][COLORS[state] + role] = QColor(conf.__dict__[COLORS[state] +
                                                                                 role]).darker(intensity)
                else:
                    # only make the background darker; the text should stay as it is
                    qbrushes[1][COLORS[state] + role] = qbrushes[0][COLORS[state] + role]

    @Slot(bool)
    def show_hosts_flags_column(self, value):
        """
        show hosts flags column if needed
        'value' is True if there is a need so it has to be converted
        """
        self.setColumnHidden(1, not value)

    @Slot(bool)
    def show_services_flags_column(self, value):
        """
        show service flags column if needed
        'value' is True if there is a need so it has to be converted
        """
        self.setColumnHidden(3, not value)

    def get_real_height(self):
        """
        calculate real table height as there is no method included
        """
        height = 0

        # only count if there is anything to display - there is no use of the headers only
        if self.model().rowCount(self) > 0:
            # height summary starts with headers' height
            # apparently height works better/without scrollbar if some pixels are added
            height = self.header().sizeHint().height() + 2

            # maybe simply take nagitems_filtered_count?
            height += self.indexRowSizeHint(self.model().index(0, 0)) * self.model().rowCount(self)

        return height

    def get_real_width(self):
        width = 0
        # avoid the last dummy column to be counted
        for column in range(len(HEADERS) - 1):
            width += self.columnWidth(column)
        return width

    @Slot()
    def adjust_table(self):
        """
        adjust table dimensions after filling it
        """
        # force table to its maximal height, calculated by .get_real_height()
        self.setMinimumHeight(self.get_real_height())
        self.setMaximumHeight(self.get_real_height())
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        # after setting table whole window can be repainted
        self.ready_to_resize.emit()

    def count_selected_rows(self):
        """
        find out if rows are selected and return their number
        """
        rows = []
        for index in self.selectedIndexes():
            if index.row() not in rows:
                rows.append(index.row())
        return len(rows)

    def mouseReleaseEvent(self, event):
        """
        forward clicked cell info from event
        """
        # special treatment if window should be closed when left-clicking somewhere
        # it is important to check if CTRL or SHIFT key is presses while clicking to select lines
        modifiers = event.modifiers()
        if conf.close_details_clicking_somewhere:
            if event.button() == Qt.MouseButton.LeftButton:
                # count selected rows - if more than 1 do not close popwin
                if modifiers or self.count_selected_rows() > 1:
                    super(TreeView, self).mouseReleaseEvent(event)
                else:
                    self.mouse_released.emit()
                return
            elif event.button() == Qt.MouseButton.RightButton:
                self.cell_clicked()
                return
        elif not modifiers or \
                event.button() == Qt.MouseButton.RightButton:
            self.cell_clicked()
            return
        else:
            super(TreeView, self).mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """
        avoid scrollable single treeview in Linux and GNOME3 by simply do nothing when getting a wheel event
        """
        event.ignore()

    def keyPressEvent(self, event):
        """
        Use to handle copy from keyboard
        """
        if event.matches(QKeySequence.StandardKey.Copy):
            self.action_clipboard_action_all()
            return
        super(TreeView, self).keyPressEvent(event)

    @Slot()
    def cell_clicked(self):
        """
        Windows reacts differently to clicks into table cells than Linux and MacOSX
        Therefore the .available flag is necessary
        """
        # empty the menu
        self.action_menu.clear()

        # clear signal mappings
        self.signalmapper_action_menu.removeMappings(self.signalmapper_action_menu)

        # add custom actions
        actions_list = list(conf.actions)
        actions_list.sort(key=str.lower)

        # How many rows do we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        # dummy definition to avoid crash if no actions are enabled - asked for some lines later
        miserable_service = None

        # Add custom actions if all selected rows want them, one per one
        for a in actions_list:
            # shortcut for next lines
            action = conf.actions[a]

            # check if current monitor server type is in action
            # second check for server type is legacy-compatible with older settings
            if action.enabled is True and (action.monitor_type in ['', self.server.TYPE] or
                                           action.monitor_type not in SERVER_TYPES):

                # menu item visibility flag
                item_visible = None

                for lrow in list_rows:
                    # temporary menu item visibility flag to collect all visibility info
                    item_visible_temporary = False
                    # take data from model data_array
                    miserable_host = self.model().data_array[lrow][0]
                    miserable_service = self.model().data_array[lrow][2]
                    miserable_duration = self.model().data_array[lrow][6]
                    miserable_attempt = self.model().data_array[lrow][7]
                    miserable_status_information = self.model().data_array[lrow][8]
                    # check if clicked line is a service or host
                    # it is checked if the action is targeted on hosts or services
                    if miserable_service:
                        if action.filter_target_service is True:
                            # only check if there is some to check
                            if action.re_host_enabled is True:
                                if is_found_by_re(miserable_host,
                                                  action.re_host_pattern,
                                                  action.re_host_reverse):
                                    item_visible_temporary = True
                            # dito
                            if action.re_service_enabled is True:
                                if is_found_by_re(miserable_service,
                                                  action.re_service_pattern,
                                                  action.re_service_reverse):
                                    item_visible_temporary = True
                            # dito
                            if action.re_status_information_enabled is True:
                                if is_found_by_re(miserable_status_information,
                                                  action.re_status_information_pattern,
                                                  action.re_status_information_reverse):
                                    item_visible_temporary = True
                            # dito
                            if action.re_duration_enabled is True:
                                if is_found_by_re(miserable_duration,
                                                  action.re_duration_pattern,
                                                  action.re_duration_reverse):
                                    item_visible_temporary = True

                            # dito
                            if action.re_attempt_enabled is True:
                                if is_found_by_re(miserable_attempt,
                                                  action.re_attempt_pattern,
                                                  action.re_attempt_reverse):
                                    item_visible_temporary = True

                            # dito - how is this supposed to work?
                            if action.re_groups_enabled is True:
                                if is_found_by_re(miserable_service,
                                                  action.re_groups_pattern,
                                                  action.re_groups_reverse):
                                    item_visible_temporary = True

                            # fallback if no regexp is selected
                            if action.re_host_enabled == action.re_service_enabled == \
                                    action.re_status_information_enabled == action.re_duration_enabled == \
                                    action.re_attempt_enabled == action.re_groups_enabled is False:
                                item_visible_temporary = True

                    else:
                        # hosts should only care about host specific actions, no services
                        if action.filter_target_host is True:
                            if action.re_host_enabled is True:
                                if is_found_by_re(miserable_host,
                                                  action.re_host_pattern,
                                                  action.re_host_reverse):
                                    item_visible_temporary = True
                            else:
                                # a non-specific action will be displayed per default
                                item_visible_temporary = True

                    # when item_visible has never been set it shall be false
                    # also if at least one row leads to not-showing the item it will be false
                    if item_visible_temporary and item_visible is None:
                        item_visible = True
                    if not item_visible_temporary:
                        item_visible = False

            else:
                item_visible = False

            # populate context menu with service actions
            if item_visible:
                # create action
                action_menuentry = QAction(a, self)
                # add action
                self.action_menu.addAction(action_menuentry)
                # action to signalmapper
                self.signalmapper_action_menu.setMapping(action_menuentry, a)
                action_menuentry.triggered.connect(self.signalmapper_action_menu.map)

            del action, item_visible

        # create and add default actions
        action_edit_actions = QAction('Edit actions...', self)
        action_edit_actions.triggered.connect(self.action_edit_actions)
        self.action_menu.addAction(action_edit_actions)

        # put actions into menu after separator
        self.action_menu.addSeparator()
        if 'Monitor' in self.server.MENU_ACTIONS and len(list_rows) == 1:
            action_monitor = QAction('Monitor', self)
            action_monitor.triggered.connect(self.action_monitor)
            self.action_menu.addAction(action_monitor)

        if 'Recheck' in self.server.MENU_ACTIONS:
            action_recheck = QAction('Recheck', self)
            action_recheck.triggered.connect(self.action_recheck)
            self.action_menu.addAction(action_recheck)

        if 'Acknowledge' in self.server.MENU_ACTIONS:
            action_acknowledge = QAction('Acknowledge', self)
            action_acknowledge.triggered.connect(self.action_acknowledge)
            self.action_menu.addAction(action_acknowledge)

        if 'Downtime' in self.server.MENU_ACTIONS:
            action_downtime = QAction('Downtime', self)
            action_downtime.triggered.connect(self.action_downtime)
            self.action_menu.addAction(action_downtime)

        # special menu entry for Checkmk Multisite for archiving events
        if self.server.type == 'Checkmk Multisite' and len(list_rows) == 1:
            if miserable_service == 'Events':
                action_archive_event = QAction('Archive event', self)
                action_archive_event.triggered.connect(self.action_archive_event)
                self.action_menu.addAction(action_archive_event)

        # not all servers allow to submit fake check results
        if 'Submit check result' in self.server.MENU_ACTIONS and len(list_rows) == 1:
            action_submit = QAction('Submit check result', self)
            action_submit.triggered.connect(self.action_submit)
            self.action_menu.addAction(action_submit)

        # experimental clipboard submenu
        self.action_menu.addMenu(self.clipboard_menu)

        # show menu
        self.action_menu.show_at_cursor()

    @Slot(str)
    def action_menu_custom_response(self, action):
        # How many rows do we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            miserable_host = self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole)
            miserable_service = self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole)
            miserable_status_info = self.model().data(self.model().createIndex(lrow, 8), Qt.ItemDataRole.DisplayRole)

            # get data to send to action
            server = self.server.get_name()
            address = self.server.get_host(miserable_host).result
            monitor = self.server.monitor_url
            monitor_cgi = self.server.monitor_cgi_url
            username = self.server.username
            password = self.server.password
            comment_ack = conf.defaults_acknowledge_comment
            comment_down = conf.defaults_downtime_comment
            comment_submit = conf.defaults_submit_check_result_comment

            # send dict with action info and dict with host/service info
            self.request_action.emit(conf.actions[action].__dict__,
                                     {'server': server,
                                      'host': miserable_host,
                                      'service': miserable_service,
                                      'status-info': miserable_status_info,
                                      'address': address,
                                      'monitor': monitor,
                                      'monitor-cgi': monitor_cgi,
                                      'username': username,
                                      'password': password,
                                      'comment-ack': comment_ack,
                                      'comment-down': comment_down,
                                      'comment-submit': comment_submit
                                      }
                                     )

            # if action wants a closed status window it should be closed now
            if conf.actions[action].close_popwin and not conf.fullscreen and not conf.windowed:
                self.action_menu_clicked.emit()

        # clean up
        del list_rows

    @Slot()
    def action_response_decorator(method):
        """
        decorate repeatedly called stuff
        """

        def decoration_function(self):
            # run decorated method
            method(self)
            # default actions need closed statuswindow to display own dialogs
            if not conf.fullscreen and not conf.windowed and \
                    not method.__name__ == 'action_recheck' and \
                    not method.__name__ == 'action_archive_event':
                self.action_menu_clicked.emit()

        return decoration_function

    @action_response_decorator
    def action_edit_actions(self):
        # buttons in toparee
        if not conf.fullscreen and not conf.windowed:
            self.action_menu_clicked.emit()
        # open actions tab (#3) of settings dialog
        self.action_edit_triggered.emit(3)

    @action_response_decorator
    def action_monitor(self):
        # only on 1 row
        indexes = self.selectedIndexes()
        if len(indexes) > 0:
            index = indexes[0]
            miserable_host = self.model().data(self.model().createIndex(index.row(), 0), Qt.ItemDataRole.DisplayRole)
            miserable_service = self.model().data(self.model().createIndex(index.row(), 2), Qt.ItemDataRole.DisplayRole)

            # open host/service monitor in browser
            self.server.open_monitor(miserable_host, miserable_service)

    @action_response_decorator
    def action_recheck(self):
        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            miserable_host = self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole)
            miserable_service = self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole)

            # send signal to worker recheck slot
            self.recheck.emit({'host': miserable_host,
                               'service': miserable_service})

    @action_response_decorator
    def action_acknowledge(self):
        list_host = []
        list_service = []

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        # running worker method is left to OK button of dialog
        self.action_acknowledge_triggered_initialize.emit(self.server, list_host, list_service)
        self.action_acknowledge_triggered_show.emit()

    @action_response_decorator
    def action_downtime(self):
        list_host = []
        list_service = []

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        # running worker method is left to OK button of dialog
        self.action_downtime_triggered_initialize.emit(self.server, list_host, list_service)
        self.action_downtime_triggered_show.emit()

    @action_response_decorator
    def action_archive_event(self):
        """
        archive events in Checkmk Multisite Event Console
        """

        # fill action and info dict for thread-safe action request
        action = {
            'string': '$MONITOR$/view.py?_transid=$TRANSID$&_do_actions=yes&_do_confirm=Yes!&output_format=python&view_name=ec_events_of_monhost&host=$HOST$&_mkeventd_comment=archived&_mkeventd_acknowledge=on&_mkeventd_state=2&_delete_event=Archive Event&event_first_from=&event_first_until=&event_last_from=&event_last_until=',
            'type': 'url', 'recheck': True}

        list_host = []
        list_service = []
        list_status = []

        # How many rows we have
        list_rows = []
        indexes = self.selectedIndexes()
        for index in indexes:
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))
            list_status.append(self.model().data(self.model().createIndex(lrow, 8), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_host)):
            host = list_host[line_number]
            service = list_service[line_number]
            status = list_status[line_number]

            info = {'server': self.server.get_name(),
                    'host': host,
                    'service': service,
                    'status-info': status,
                    'address': self.server.get_host(host).result,
                    'monitor': self.server.monitor_url,
                    'monitor-cgi': self.server.monitor_cgi_url,
                    'username': self.server.username,
                    'password': self.server.password,
                    'comment-ack': conf.defaults_acknowledge_comment,
                    'comment-down': conf.defaults_downtime_comment,
                    'comment-submit': conf.defaults_submit_check_result_comment
                    }

            # tell worker to do the action
            self.request_action.emit(action, info)

        # clean up
        del index, indexes, list_rows, list_host, list_service, list_status

    @action_response_decorator
    def action_submit(self):
        # only on 1 row
        indexes = self.selectedIndexes()
        index = indexes[0]
        miserable_host = self.model().data(self.model().createIndex(index.row(), 0), Qt.ItemDataRole.DisplayRole)
        miserable_service = self.model().data(self.model().createIndex(index.row(), 2), Qt.ItemDataRole.DisplayRole)

        # running worker method is left to OK button of dialog
        self.action_submit_triggered_initialize.emit(self.server, miserable_host, miserable_service)
        self.action_submit_triggered_show.emit()

    @Slot()
    def action_clipboard_action_host(self):
        """
        copy host name to clipboard
        """
        list_host = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_host)):
            text = text + list_host[line_number]
            if line_number + 1 < len(list_host):
                text += '\n'

        clipboard.setText(text)

    @Slot()
    def action_clipboard_action_service(self):
        """
        copy service name to clipboard
        """
        list_service = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_service)):
            text = text + list_service[line_number]
            if line_number + 1 < len(list_service):
                text += '\n'

        clipboard.setText(text)

    @Slot()
    def action_clipboard_action_statusinformation(self):
        """
        copy status information to clipboard
        """
        list_status = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_status.append(self.model().data(self.model().createIndex(lrow, 8), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_status)):
            text = text + list_status[line_number]
            if line_number + 1 < len(list_status):
                text += '\n'

        clipboard.setText(text)

    @Slot()
    def action_clipboard_action_all(self):
        """
        copy all information to clipboard
        """
        list_host = []
        list_service = []
        text = ''

        # How many rows we have
        list_rows = []
        for index in self.selectedIndexes():
            if index.row() not in list_rows:
                list_rows.append(index.row())

        for lrow in list_rows:
            list_host.append(self.model().data(self.model().createIndex(lrow, 0), Qt.ItemDataRole.DisplayRole))
            list_service.append(self.model().data(self.model().createIndex(lrow, 2), Qt.ItemDataRole.DisplayRole))

        for line_number in range(len(list_host)):
            host = list_host[line_number]
            service = list_service[line_number]

            # item to access all properties of host/service object
            # defaults to host
            item = self.server.hosts[host]
            text += f'Host: {host}\n'
            # if it is a service switch to service object
            if service != '':
                if item.services.get(service):
                    item = item.services[service]
                    text += f'Service: {service}\n'
                # finally solve https://github.com/HenriWahl/Nagstamon/issues/1024
                elif self.server.TYPE == 'Zabbix':
                    for service_item in item.services.values():
                        if service_item.name == service:
                            item = service_item
                            text += f'Service: {service}\n'
                            break

            # the other properties belong to both hosts and services
            text += 'Status: {0}\n'.format(item.status)
            text += 'Last check: {0}\n'.format(item.last_check)
            text += 'Duration: {0}\n'.format(item.duration)
            text += 'Attempt: {0}\n'.format(item.attempt)
            text += 'Status information: {0}\n'.format(item.status_information)
            if line_number + 1 < len(list_host):
                text += '\n'

        # copy text to clipboard
        clipboard.setText(text)

    @Slot()
    def refresh(self):
        """
        refresh status display
        """
        # avoid race condition when waiting for password dialog
        if self.parent_statuswindow is not None:
            # do nothing if window is moving to avoid lagging movement
            if not statuswindow_properties.moving:
                # tell statusbar it should update
                self.refreshed.emit()

                # check if status changed and notification is necessary
                # send signal because there are unseen events
                # status has changed if there are unseen events in the list OR (current status is up AND has been changed since last time)
                if (self.server.get_events_history_count() > 0) or \
                        ((self.server.worst_status_current == 'UP') and (
                                self.server.worst_status_current != self.server.worst_status_last)):
                    self.status_changed.emit(self.server.name, self.server.worst_status_diff,
                                             self.server.worst_status_current)

    @Slot(int, Qt.SortOrder)
    def sort_columns(self, sort_column, sort_order):
        """
        forward sorting task to worker
        """
        # better int() the Qt.* values because they partly seem to be
        # intransmissible
        # get_sort_order_value() cures the differences between Qt5 and Qt6
        self.sort_data_array_for_columns.emit(int(sort_column), int(get_sort_order_value(sort_order)), True)

    @Slot()
    def finish_worker_thread(self):
        """
        attempt to shut down thread cleanly
        """
        # tell thread to quit
        self.worker_thread.quit()
        # wait until thread is really stopped
        self.worker_thread.wait()

    class Worker(QObject):
        """
        attempt to run a server status update thread - only needed by table so it is defined here inside table
        """

        # send signal if monitor server has new status data
        new_status = Signal()
        get_status_successful = Signal(str)

        # send signal if next cell can be filled
        next_cell = Signal(int, int, str, str, str, list, str)

        # send signal if all cells are filled and table can be adjusted
        table_ready = Signal()

        # send signal if ready to stop
        finish = Signal()

        # send start and end of downtime
        set_start_end = Signal(str, str)

        # try to stop thread by evaluating this flag
        running = True

        # signal to be sent to slot "change" of ServerStatusLabel
        change_label_status = Signal(str, str)

        # signal to be sent to slot "restore" of ServerStatusLabel
        restore_label_status = Signal()

        # send notification a stop message if problems vanished without being noticed
        problems_vanished = Signal()

        # flag to keep recheck_all from being started more than once
        rechecking_all = False

        # signals to control error message in statusbar
        show_error = Signal(str)
        hide_error = Signal()

        # signal to request authentication
        authentication_needed = Signal()

        # sent to treeview with new data_array
        worker_data_array_filled = Signal(list, dict)

        # sendt to treeview if data has been sorted by click on column header
        data_array_sorted = Signal(list, dict)

        # keep track of last sorting column and order to pre-sort by it
        # start with sorting by host
        last_sort_column_cached = 0
        last_sort_column_real = 0
        last_sort_order = 0

        # keep track of action menu being shown or not to avoid refresh while selecting multiple items
        # action_menu_shown = False

        def __init__(self, parent=None, server=None, sort_column=0, sort_order=0, status_window=None):
            QObject.__init__(self)
            self.server = server
            # needed for update interval
            self.timer = QTimer(self)
            self.server.init_config()

            self.sort_column = sort_column
            self.sort_order = sort_order

            self.parent_statuswindow = status_window

            self.get_status_successful.connect(self.parent_statuswindow.injected_dialogs.weblogin.close_browser)

        @Slot()
        def get_status(self):
            """
            check every second if thread still has to run
            if interval time is reached get status
            """
            # if counter is at least update interval get status or the weblogin dialog triggered this
            if self.server.thread_counter >= conf.update_interval_seconds or \
                type(self.sender()) is DialogWebLogin:
                # only if no multiple selection is done at the moment and no context action menu is open
                if not app.keyboardModifiers() and app.activePopupWidget() is None:
                    # reflect status retrieval attempt on server vbox label
                    self.change_label_status.emit('Refreshing...', '')

                    status = self.server.get_status()

                    # all is OK if no error info came back
                    if self.server.status_description == '' and \
                            self.server.status_code < 400 and \
                            not self.server.refresh_authentication and \
                            not self.server.tls_error:
                        # show last update time
                        self.change_label_status.emit(f"Last updated at {datetime.now().strftime('%X')}", '')

                        self.get_status_successful.emit(self.server.name)

                        # reset server error flag, needed for error label in statusbar
                        self.server.has_error = False

                        # tell statusbar there is no error
                        self.hide_error.emit()
                    else:
                        # try to display some more user-friendly error description
                        if self.server.status_code == 404:
                            self.change_label_status.emit('Monitor URL not valid', 'critical')
                        elif status.error.startswith('requests.exceptions.ConnectTimeout'):
                            self.change_label_status.emit('Connection timeout', 'error')
                        elif status.error.startswith('requests.exceptions.ConnectionError'):
                            self.change_label_status.emit('Connection error', 'error')
                        elif status.error.startswith('requests.exceptions.ReadTimeout'):
                            self.change_label_status.emit('Connection timeout', 'error')
                        elif status.error.startswith('requests.exceptions.ProxyError'):
                            self.change_label_status.emit('Proxy error', 'error')
                        elif status.error.startswith('requests.exceptions.MaxRetryError'):
                            self.change_label_status.emit('Max retry error', 'error')
                        elif self.server.tls_error:
                            self.change_label_status.emit('SSL/TLS problem', 'critical')
                        elif self.server.status_code in self.server.STATUS_CODES_NO_AUTH or \
                                self.server.refresh_authentication:
                            self.change_label_status.emit('Authentication problem', 'critical')
                            self.authentication_needed.emit()
                        elif self.server.status_code == 503:
                            self.change_label_status.emit('Service unavailable', 'error')
                        else:
                            # kick out line breaks to avoid broken status window
                            if self.server.status_description == '':
                                self.server.status_description = 'Unknown error'
                            self.change_label_status.emit(self.server.status_description.replace('\n', ''), 'error')

                        # set server error flag, needed for error label in statusbar
                        self.server.has_error = True

                        # tell statusbar there is some error to display
                        self.show_error.emit('ERROR')

                    # reset counter for this thread
                    self.server.thread_counter = 0

                    # if failures have gone and nobody took notice switch notification off again
                    if len([k for k, v in self.server.events_history.items() if v is True]) == 0 and \
                            self.parent_statuswindow and \
                            statuswindow_properties.is_notifying is True and \
                            statuswindow_properties.notifying_server == self.server.name:
                        # tell notification that unnoticed problems are gone
                        self.problems_vanished.emit()

                    # stuff data into array and sort it
                    self.fill_data_array(self.sort_column, self.sort_order)

                    # tell news about new status available
                    self.new_status.emit()

            # increase thread counter
            self.server.thread_counter += 1

            # if running flag is still set call myself after 1 second
            if self.running:
                self.timer.singleShot(1000, self.get_status)
            else:
                # tell treeview to finish worker_thread
                self.finish.emit()

        @Slot(int, int)
        def fill_data_array(self, sort_column, sort_order):
            """
            let worker do the dirty job of filling the array
            """

            # data_array to be evaluated in data() of model
            # first 9 items per row come from current status information
            self.data_array = list()

            # dictionary containing extra info about data_array
            self.info = {'hosts_flags_column_needed': False,
                         'services_flags_column_needed': False, }

            # only refresh table if there is no popup opened
            if not app.activePopupWidget():
                # avoid race condition when waiting for password dialog
                if len(qbrushes[0]) > 0:
                    # cruising the whole nagitems structure
                    for category in ('hosts', 'services'):
                        for state in self.server.nagitems_filtered[category].values():
                            for item in state:
                                self.data_array.append(list(item.get_columns(HEADERS)))

                                # hash for freshness comparison
                                hash = item.get_hash()

                                if item.is_host():
                                    if hash in self.server.events_history and \
                                            self.server.events_history[hash] is True:
                                        # second item in last data_array line is host flags
                                        self.data_array[-1][1] += 'N'
                                else:
                                    if hash in self.server.events_history and \
                                            self.server.events_history[hash] is True:
                                        # fourth item in last data_array line is service flags
                                        self.data_array[-1][3] += 'N'
                                # add text color as QBrush from status
                                self.data_array[-1].append(
                                    qbrushes[len(self.data_array) % 2][COLORS[item.status] + 'text'])
                                # add background color as QBrush from status
                                self.data_array[-1].append(
                                    qbrushes[len(self.data_array) % 2][COLORS[item.status] + 'background'])
                                # add text color name for sorting data
                                self.data_array[-1].append(COLORS[item.status] + 'text')
                                # add background color name for sorting data
                                self.data_array[-1].append(COLORS[item.status] + 'background')

                                # check if hosts and services flags should be shown
                                if self.data_array[-1][1] != '':
                                    self.info['hosts_flags_column_needed'] = True
                                if self.data_array[-1][3] != '':
                                    self.info['services_flags_column_needed'] = True

                                self.data_array[-1].append('X')

                # sort data before it gets transmitted to treeview model
                self.sort_data_array(self.sort_column, self.sort_order, False)

                # give sorted data to model
                self.worker_data_array_filled.emit(self.data_array, self.info)

        @Slot(int, int, bool)
        def sort_data_array(self, sort_column, sort_order, header_clicked=False):
            """
            sort list of lists in data_array depending on sort criteria
            used from fill_data_array() and when clicked on table headers
            """
            # store current sort_column and sort_data for next sort actions
            self.sort_column = sort_column
            self.sort_order = sort_order

            # to keep GTK Treeview sort behaviour first by hosts
            first_sort = sorted(self.data_array,
                                key=lambda row: SORT_COLUMNS_FUNCTIONS[self.last_sort_column_real](
                                    row[SORT_COLUMNS_INDEX[self.last_sort_column_real]]),
                                reverse=self.last_sort_order)

            # use SORT_COLUMNS from Helpers to sort column accordingly
            self.data_array = sorted(first_sort,
                                     key=lambda row: SORT_COLUMNS_FUNCTIONS[self.sort_column](
                                         row[SORT_COLUMNS_INDEX[self.sort_column]]),
                                     reverse=self.sort_order)

            # fix alternating colors
            for count, row in enumerate(self.data_array):
                # change text color of sorted rows
                row[10] = qbrushes[count % 2][row[12]]
                # change background color of sorted rows
                row[11] = qbrushes[count % 2][row[13]]

            # if header was clicked tell model to use new data_array
            if header_clicked:
                self.data_array_sorted.emit(self.data_array, self.info)

            # store last sorting column for next sorting only if header was clicked
            if header_clicked:
                # last sorting column needs to be cached to avoid losing it
                # effective last column is self.last_sort_column_real
                if self.last_sort_column_cached != self.sort_column:
                    self.last_sort_column_real = self.last_sort_column_cached
                    self.last_sort_order = self.sort_order

                self.last_sort_column_cached = self.sort_column

        @Slot(dict)
        def acknowledge(self, info_dict):
            """
            slot waiting for 'acknowledge' signal from ok button from acknowledge dialog
            all information about target server, host, service and flags is contained
            in dictionary 'info_dict'
            """
            # because all monitors are connected to this slot we must check which one sent the signal,
            # otherwise there are several calls and not only one as wanted
            if self.server == info_dict['server']:
                # pass dictionary to server's acknowledge machinery
                self.server.set_acknowledge(info_dict)

        @Slot(dict)
        def downtime(self, info_dict):
            """
            slot waiting for 'downtime' signal from ok button from downtime dialog
            all information about target server, host, service and flags is contained
            in dictionary 'info_dict'
            """
            # because all monitors are connected to this slot we must check which one sent the signal,
            # otherwise there are several calls and not only one as wanted
            if self.server == info_dict['server']:
                # pass dictionary to server's downtime machinery
                self.server.set_downtime(info_dict)

        @Slot(dict)
        def submit(self, info_dict):
            """
            slot waiting for 'submit' signal from ok button from submit dialog
            all information about target server, host, service and flags is contained
            in dictionary 'info_dict'
            """
            # because all monitors are connected to this slot we must check which one sent the signal,
            # otherwise there are several calls and not only one as wanted
            if self.server == info_dict['server']:
                # pass dictionary to server's downtime machinery
                self.server.set_submit_check_result(info_dict)

        @Slot(dict)
        def recheck(self, info_dict):
            """
            Slot to start server recheck method, getting signal from TableWidget context menu
            """
            if conf.debug_mode:
                # host
                if info_dict['service'] == '':
                    self.server.debug(server=self.server.name, debug='Rechecking host {0}'.format(info_dict['host']))
                else:
                    self.server.debug(server=self.server.name,
                                      debug='Rechecking service {0} on host {1}'.format(info_dict['service'],
                                                                                        info_dict['host']))

            # call server recheck method
            self.server.set_recheck(info_dict)

        @Slot()
        def recheck_all(self):
            """
            call server.set_recheck for every single host/service
            """
            # only if no already rechecking
            if self.rechecking_all is False:
                # block rechecking
                self.rechecking_all = True
                # change label of server vbox
                self.change_label_status.emit('Rechecking all...', '')
                if conf.debug_mode:
                    self.server.debug(server=self.server.name, debug='Start rechecking all')
                # special treatment for Checkmk Multisite because there is only one URL call necessary
                if self.server.type != 'Checkmk Multisite':
                    # make a copy to preserve hosts/service to recheck - just in case something changes meanwhile
                    nagitems_filtered = deepcopy(self.server.nagitems_filtered)
                    for status in nagitems_filtered['hosts'].items():
                        for host in status[1]:
                            if conf.debug_mode:
                                self.server.debug(server=self.server.name,
                                                  debug='Rechecking host {0}'.format(host.name))
                            # call server recheck method
                            self.server.set_recheck({'host': host.name, 'service': ''})
                    for status in nagitems_filtered['services'].items():
                        for service in status[1]:
                            if conf.debug_mode:
                                self.server.debug(server=self.server.name,
                                                  debug='Rechecking service {0} on host {1}'.format(
                                                      service.get_service_name(),
                                                      service.host))
                            # call server recheck method
                            self.server.set_recheck({'host': service.host, 'service': service.name})
                    del nagitems_filtered, status
                else:
                    # Checkmk Multisite does it its own way
                    self.server.recheck_all()
                # release rechecking lock
                self.rechecking_all = False
                # restore server status label
                self.restore_label_status.emit()
            else:
                if conf.debug_mode:
                    self.server.debug(server=self.server.name, debug='Already rechecking all')

        @Slot(str, str)
        def get_start_end(self, server_name, host):
            """
            Investigates start and end time of a downtime asynchronously
            """
            # because every server listens to this signal the name has to be filtered
            if server_name == self.server.name:
                start, end = self.server.get_start_end(host)
                # send start/end time to slot
                self.set_start_end.emit(start, end)

        @Slot(dict, dict)
        def execute_action(self, action, info):
            """
            runs action, may it be custom or included like the Checkmk Multisite actions
            """
            # first replace placeholder variables in string with actual values
            #
            # Possible values for variables:
            # $HOST$             - host as in monitor
            # $SERVICE$          - service as in monitor
            # $MONITOR$          - monitor address - not yet clear what exactly for
            # $MONITOR-CGI$      - monitor CGI address - not yet clear what exactly for
            # $ADDRESS$          - address of host, investigated by Server.GetHost()
            # $STATUS-INFO$      - status information
            # $USERNAME$         - username on monitor
            # $PASSWORD$         - username's password on monitor - whatever for
            # $COMMENT-ACK$      - default acknowledge comment
            # $COMMENT-DOWN$     - default downtime comment
            # $COMMENT-SUBMIT$   - default submit check result comment

            try:
                # used for POST request
                if 'cgi_data' in action:
                    cgi_data = action['cgi_data']
                else:
                    cgi_data = ''

                # mapping of variables and values
                mapping = {'$HOST$': info['host'],
                           '$SERVICE$': info['service'],
                           '$ADDRESS$': info['address'],
                           '$MONITOR$': info['monitor'],
                           '$MONITOR-CGI$': info['monitor-cgi'],
                           '$STATUS-INFO$': info['status-info'],
                           '$USERNAME$': info['username'],
                           '$PASSWORD$': info['password'],
                           '$COMMENT-ACK$': info['comment-ack'],
                           '$COMMENT-DOWN$': info['comment-down'],
                           '$COMMENT-SUBMIT$': info['comment-submit']}

                # take string form action
                string = action['string']

                # mapping mapping
                for i in mapping:
                    # mapping with urllib.quote
                    string = string.replace("$" + i + "$", quote(mapping[i]))
                    # normal mapping
                    string = string.replace(i, mapping[i])

                # see what action to take
                if action['type'] == 'browser':
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: BROWSER ' + string)
                    webbrowser_open(string)
                elif action['type'] == 'command':
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: COMMAND ' + string)
                    Popen(string, shell=True)
                elif action['type'] == 'url':
                    # Checkmk uses transids - if this occurs in URL its very likely that a Checkmk-URL is called
                    if '$TRANSID$' in string:
                        transid = servers[info['server']]._get_transid(info['host'], info['service'])
                        string = string.replace('$TRANSID$', transid).replace(' ', '+')
                    else:
                        # make string ready for URL
                        string = urlify(string)
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: URL in background ' + string)
                    servers[info['server']].fetch_url(string)
                # used for example by Op5Monitor.py
                elif action['type'] == 'url-post':
                    # make string ready for URL
                    string = urlify(string)
                    # debug
                    if conf.debug_mode is True:
                        self.server.debug(server=self.server.name, host=info['host'], service=info['service'],
                                          debug='ACTION: URL-POST in background ' + string)
                    servers[info['server']].fetch_url(string, cgi_data=cgi_data, multipart=True)

                if action['recheck']:
                    self.recheck(info)

            except Exception:
                print_exc(file=stdout)

        @Slot()
        def unfresh_event_history(self):
            # set all flagged-as-fresh-events to un-fresh
            for event in self.server.events_history.keys():
                self.server.events_history[event] = False
