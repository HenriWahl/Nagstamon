# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2014 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

try:
    import pygtk
    pygtk.require("2.0")
except Exception, err:
    print
    print err
    print
    print "Could not load pygtk, maybe you need to install python gtk."
    print
    import sys
    sys.exit()

import gtk
import gobject
import os
import platform
import sys
import copy

# testing pynotify support
try:
    import pynotify
    pynotify.init("Nagstamon")
except:
    pass

# testing Ubuntu AppIndicator support
try:
    import appindicator
except:
    pass

# needed for actions e.g. triggered by pressed buttons
from Nagstamon import Config
from Nagstamon import Actions
from Nagstamon import Custom


class Sorting(object):
    """
    Sorting persistence purpose class
    Stores tuple pairs in form of:
    (<column_id>, <gtk.SORT_ASCENDING|gtk.SORT_DESCENDING)
    """
    def __init__(self, sorting_tuple_list=[], max_remember=8):
        self.sorting_tuple_list = sorting_tuple_list
        self.max_remember = max_remember

    def iteritems(self):
        for item in reversed(self.sorting_tuple_list):
            yield item

    def add(self, id, order):
        length = len(self.sorting_tuple_list)
        if length > 0:
            if length >= self.max_remember:
                self.sorting_tuple_list.pop()
            if id == self.sorting_tuple_list[0][0]:
                self.sorting_tuple_list.remove(self.sorting_tuple_list[0])
        self.sorting_tuple_list.insert(0, (id, order))


class GUI(object):
    """
        class which organizes the GUI
    """

    def __init__(self, **kwds):
        """
            some fundamental preliminaries
        """
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # Meta
        self.name = "Nagstamon"
        self.version = "1.0.3"
        self.website = "https://nagstamon.ifw-dresden.de/"
        self.copyright = "©2008-2016 Henri Wahl et al.\nh.wahl@ifw-dresden.de"
        self.comments = "Nagios status monitor for your desktop"

        # initialize overall status flag
        self.status_ok = True

        # if run first it is impossible to refresh the display with
        # non-existent settings so there has to be extra treatment
        # at the second run nagstamon will be configured and so no first run
        if self.conf.unconfigured:
            self.firstrun = True
        else:
            self.firstrun = False

        # font size, later adjusted by StatusBar
        self.fontsize = 10000

        # store information about monitors
        self.monitors = dict()
        self.current_monitor = 0

        # define colors for detailed status table in dictionaries
        self.TAB_BG_COLORS = { 
                          "UNKNOWN":str(self.conf.color_unknown_background), 
						  "INFORMATION": str(self.conf.color_information_background), 
						  "AVERAGE": str(self.conf.color_average_background), 
						  "HIGH": str(self.conf.color_high_background), 
						  "CRITICAL":str(self.conf.color_critical_background), 
						  "WARNING":str(self.conf.color_warning_background), 
						  "DOWN":str(self.conf.color_down_background), 
						  "UNREACHABLE":str(self.conf.color_unreachable_background)  }
        self.TAB_FG_COLORS = { 
                          "UNKNOWN":str(self.conf.color_unknown_text), 
						  "INFORMATION": str(self.conf.color_information_text), 
						  "AVERAGE": str(self.conf.color_average_text), 
						  "HIGH": str(self.conf.color_high_text), 
						  "CRITICAL":str(self.conf.color_critical_text), 
						  "WARNING":str(self.conf.color_warning_text), 
						  "DOWN":str(self.conf.color_down_text), 
						  "UNREACHABLE":str(self.conf.color_unreachable_text) }

        # define popwin table liststore types
        self.LISTSTORE_COLUMNS = [gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,\
                                  gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,\
                                  gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,\
                                  gobject.TYPE_STRING, gobject.TYPE_STRING,\
                                  gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf,\
                                  gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf,\
                                  gtk.gdk.Pixbuf, gtk.gdk.Pixbuf]

        # decide if the platform can handle SVG if not use PNG
        if platform.system() in ["Darwin", "Windows"]:
            self.BitmapSuffix = ".png"
        else:
            self.BitmapSuffix = ".svg"

        # set app icon for all app windows
        
        gtk.window_set_default_icon_from_file(self.Resources + os.sep + "nagstamon" + self.BitmapSuffix)

        if platform.system() == "Darwin":
            # MacOSX gets instable with default theme "Clearlooks" so use custom one with theme "Murrine"
            gtk.rc_parse_string('gtk-theme-name = "Murrine"')
            # workaround for ugly Fonts on Maverick
            if platform.release() > "12":
                gtk.rc_parse_string('style "font" {font_name = "Lucida Grande"} widget_class "*" style "font"')

            # init MacOSX integration
            import gtk_osxapplication
            osxapp = gtk_osxapplication.OSXApplication()
            # prevent blocking
            osxapp.connect("NSApplicationBlockTermination", gtk.main_quit)
            osxapp.ready()

        # icons for acknowledgement/downtime visualization
        self.STATE_ICONS = dict()
        for icon in ["fresh", "acknowledged", "downtime", "flapping", "passive"]:
            self.STATE_ICONS[icon] = gtk.gdk.pixbuf_new_from_file_at_size(self.Resources\
                                                                          + os.sep + "nagstamon_" + icon + self.BitmapSuffix,\
                                                                          int(self.fontsize/650), int(self.fontsize/650))

        # Icon in systray and statusbar both get created but
        # only one of them depending on the settings will
        # be shown
        self.statusbar = StatusBar(conf=self.conf, output=self)

        # Popup is a WINDOW_POPUP without border etc.
        self.popwin = Popwin(conf=self.conf, output=self)

        # find out dimension of all monitors
        for m in range(self.statusbar.StatusBar.get_screen().get_n_monitors()):
            monx0, mony0, monw, monh = self.statusbar.StatusBar.get_screen().get_monitor_geometry(m)
            self.monitors[m] = (monx0, mony0, monw, monh)

        # testing Ubuntu AppIndicator
        if sys.modules.has_key("appindicator"):
            self.appindicator = AppIndicator(conf=self.conf, output=self)

        # check if statusbar is inside display boundaries
        # give 5 pixels tolerance to x0 and y0
        # modify x0 and y0 to fit into display
        statusbar_x0, statusbar_y0 = self.statusbar.StatusBar.get_position()
        m = self.statusbar.StatusBar.get_screen().get_monitor_at_point(statusbar_x0, statusbar_y0)
        # get max dimensions of current display
        x0, y0, x_max, y_max = self._get_display_dimensions(m)
        if not (x0-5 <= int(self.conf.position_x)):
            self.conf.position_x = x0 + 30
        if not int(self.conf.position_x) <= x_max:
            self.conf.position_x = x_max - 50
        if not (y0-5 <= int(self.conf.position_y)):
            self.conf.position_y = y0 + 30
        if not int(self.conf.position_y) <= y_max:
            self.conf.position_y = y_max - 50
        self.statusbar.StatusBar.move(int(self.conf.position_x), int(self.conf.position_y))

        if str(self.conf.fullscreen) == "True":
            self.popwin.Window.show_all()
            self.popwin.Window.set_visible(True)
            self.popwin.RefreshFullscreen()
        else:
            self.popwin.Resize()

        # connect events to actions
        # when talking about "systray" the Windows variant of upper left desktop corner
        # statusbar is meant synonymical
        # if pointer on systray do popup the long-summary-status-window aka popwin
        self.statusbar.SysTray.connect("activate", self.statusbar.SysTrayClicked)
        self.statusbar.SysTray.connect("popup-menu", self.statusbar.MenuPopup)

        # if pointer clicks on logo move stautsbar
        self.statusbar.LogoEventbox.connect("button-press-event", self.statusbar.LogoClicked)
        self.statusbar.LogoEventbox.connect("button-release-event", self.statusbar.LogoReleased)

        # if pointer hovers or clicks statusbar show details
        self.statusbar.EventBoxLabel.connect("enter-notify-event", self.statusbar.Hovered)
        self.statusbar.EventBoxLabel.connect("button-press-event", self.statusbar.Clicked)

        # server combobox
        self.popwin.ComboboxMonitor.connect("changed", self.popwin.ComboboxClicked)

        # attempt to place and resize statusbar where it belongs to in Windows - workaround
        self.statusbar.StatusBar.move(int(self.conf.position_x), int(self.conf.position_y))
        self.statusbar.Resize()

        # flag which is set True if already notifying
        self.Notifying = False

        # last worst state for notification
        self.last_worst_status = "UP"

        # defining sorting defaults in first render
        self.COLUMNS_IDS_MAP = {"Host": 0,\
                          "Service": 1,\
                          "Status": 2,\
                          "Last Check": 3,\
                          "Duration": 4,\
                          "Attempt": 5,\
                          "Status Information": 6}

        # reverse mapping of column names and IDs for settings dialog
        self.IDS_COLUMNS_MAP = dict((id, column) for column, id in self.COLUMNS_IDS_MAP.iteritems())

        # use configured default sorting order
        if str(self.conf.default_sort_order) == "Ascending":
            self.startup_sort_order = gtk.SORT_ASCENDING
        else:
            self.startup_sort_order = gtk.SORT_DESCENDING

        self.startup_sort_field = self.COLUMNS_IDS_MAP[self.conf.default_sort_field]

        self.rows_reordered_handler = {}
        self.last_sorting = {}
        for server in self.servers.values():
            self.last_sorting[server.get_name()] = Sorting([(self.startup_sort_field, self.startup_sort_order ),
                                                            (server.HOST_COLUMN_ID, gtk.SORT_ASCENDING)],
                                                           len(server.COLUMNS)+1) # stores sorting between table refresh

        # store once created dialogs here to minimize memory usage
        self.Dialogs = {}

        # history of events to track status changes for notifications
        # events that came in
        self.events_current = {}
        # events that had been already displayed in popwin and need no extra mark
        self.events_history = {}
        # events to be given to custom notification, maybe to desktop notification too
        self.events_notification = {}


    def _get_display_dimensions(self, monitor):
        """
        get x0 y0 xmax and ymax of a distinct monitor, usefull to put statusbar inside the fence
        """
        # start with values of first display
        x0, y0, x_max, y_max = self.monitors[0]
        # only calculate some dimensions when multiple displays are used
        if len(self.monitors) > 1:
            # run through all displays
            for m in range(1, monitor+1):
                # if 2 displays have some coordinates in common they belong to each other
                if self.monitors[m-1][2] == self.monitors[m][0]:
                    x0 += self.monitors[m][0]
                    x_max += self.monitors[m][2]
                else:
                    x0 = self.monitors[m][0]
                    x_max = self.monitors[m][2] + self.monitors[m][0]
                if self.monitors[m-1][3] == self.monitors[m][1]:
                    y0 += self.monitors[m][1]
                    y_max += self.monitors[m][3]
                else:
                    y0 = self.monitors[m][1]
                    y_max = self.monitors[m][3] + self.monitors[m][1]

        return x0, y0, x_max, y_max


    def get_last_sorting(self, server):
        return self.last_sorting[server.get_name()]


    def get_rows_reordered_handler(self, server):
        return self.rows_reordered_handler.get(server.get_name())


    def set_rows_reordered_handler(self, server, handler):
        self.rows_reordered_handler[server.get_name()] = handler


    def set_sorting(self, liststore, server):
        """ Restores sorting after refresh """
        for id, order in self.get_last_sorting(server).iteritems():
            liststore.set_sort_column_id(id, order)
            # this makes sorting arrows visible according to
            # sort order after refresh
            column = self.popwin.ServerVBoxes[server.get_name()].TreeView.get_column(id)
            if column is not None:
                column.set_property('sort-order', order)


    def on_column_header_click(self, model, id, liststore, server):
        """ Sets current sorting according to column id """

        # makes column headers sortable by first time click (hack)
        order = model.get_sort_order()
        liststore.set_sort_column_id(id, order)

        rows_reordered_handler = self.get_rows_reordered_handler(server)
        if rows_reordered_handler is not None:
            liststore.disconnect(rows_reordered_handler)
            new_rows_reordered_handler = liststore.connect_after('rows-reordered', self.on_sorting_order_change, id, model, server)
            self.set_rows_reordered_handler(server, new_rows_reordered_handler)
        else:
            new_rows_reordered_handler = liststore.connect_after('rows-reordered', self.on_sorting_order_change, id, model, server, False)
            self.set_rows_reordered_handler(server, new_rows_reordered_handler)
            self.on_sorting_order_change(liststore, None, None, None, id, model, server)
        model.set_sort_column_id(id)


    def on_sorting_order_change(self, liststore, path, iter, new_order, id, model, server, do_action=True):
        """ Saves current sorting change in object property """
        if do_action:
            order = model.get_sort_order()
            last_sorting = self.get_last_sorting(server)
            last_sorting.add(id, order)


    def RefreshDisplayStatus(self):
        """
            load current nagios status and refresh trayicon and detailed treeview
            add only services which are not on maintained or acknowledged hosts
            this way applying the nagios filter more comfortably because in
            nagios one had to schedule/acknowledge every single service
        """
        # refresh statusbar
        # flag for overall status, needed by popwin.popup to decide if popup in case all is OK
        self.status_ok = False

        # set handler to None for do not disconnecting it after display refresh
        self.rows_reordered_handler = {}

        # local counters for summarize all miserable hosts
        downs = 0
        unreachables = 0
        unknowns = 0
        criticals = 0
        warnings = 0

        informations = 0
        averages = 0
        highs = 0
        # display "ERROR" in case of startup connection trouble
        errors = ""

        # walk through all servers, RefreshDisplayStatus their hosts and their services
        for server in self.servers.values():
            # only refresh monitor server output if enabled and only once every server loop
            if str(self.conf.servers[server.get_name()].enabled) == "True" or\
               server.refresh_authentication == True:
                try:
                    # otherwise it must be shown, full of problems
                    self.popwin.ServerVBoxes[server.get_name()].show()
                    self.popwin.ServerVBoxes[server.get_name()].set_visible(True)
                    self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(False)
                    # if needed show auth line
                    # Centreon autologin could be set in Settings dialog
                    if server.refresh_authentication == True and str(server.use_autologin) == "False":
                        self.popwin.ServerVBoxes[server.get_name()].HBoxAuth.set_no_show_all(False)
                        self.popwin.ServerVBoxes[server.get_name()].HBoxAuth.show_all()
                        if self.popwin.ServerVBoxes[server.get_name()].AuthEntryUsername.get_text() == "":
                            self.popwin.ServerVBoxes[server.get_name()].AuthEntryUsername.set_text(server.username)
                        if self.popwin.ServerVBoxes[server.get_name()].AuthEntryPassword.get_text() == "":
                            self.popwin.ServerVBoxes[server.get_name()].AuthEntryPassword.set_text(server.password)
                    else:
                        # no re-authentication necessary
                        self.popwin.ServerVBoxes[server.get_name()].HBoxAuth.hide_all()
                        self.popwin.ServerVBoxes[server.get_name()].HBoxAuth.set_no_show_all(True)

                    # use a bunch of filtered nagitems, services and hosts sorted by different
                    # grades of severity

                    # summarize states
                    downs += server.downs
                    unreachables += server.unreachables
                    unknowns += server.unknowns
                    criticals += server.criticals
                    warnings += server.warnings
                    informations += server.informations
                    averages += server.averages
                    highs += server.highs
                    # if there is no trouble...
                    if len(server.nagitems_filtered["hosts"]["DOWN"]) == 0 and \
                       len(server.nagitems_filtered["hosts"]["UNREACHABLE"]) == 0 and \
                       len(server.nagitems_filtered["services"]["CRITICAL"]) == 0 and \
                       len(server.nagitems_filtered["services"]["WARNING"]) == 0 and \
                       len(server.nagitems_filtered["services"]["UNKNOWN"]) == 0 and \
                       len(server.nagitems_filtered["services"]["INFORMATION"]) == 0 and \
                       len(server.nagitems_filtered["services"]["AVERAGE"]) == 0 and \
                       len(server.nagitems_filtered["services"]["HIGH"]) == 0 and \
                       server.status_description == "":
                        # ... there is no need to show a label or treeview...
                        self.popwin.ServerVBoxes[server.get_name()].hide()
                        self.popwin.ServerVBoxes[server.get_name()].set_visible(False)
                        self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(True)
                        self.status_ok = True
                    else:
                        # otherwise it must be shown, full of problems
                        self.popwin.ServerVBoxes[server.get_name()].set_visible(True)
                        self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(False)
                        self.popwin.ServerVBoxes[server.get_name()].show_all()
                        self.status_ok = False

                    # calculate freshness of hosts
                    # first reset all events
                    self.events_current.clear()

                    # run through all servers and hosts and services
                    for s in self.servers.values():
                        for host in s.hosts.values():
                            if not host.status == "UP":
                                # only if host is not filtered out add it to current events
                                # the boolean is meaningless for current events
                                if host.visible:
                                    self.events_current[host.get_hash()] = True
                            for service in host.services.values():
                                # same for services of host
                                if service.visible:
                                    self.events_current[service.get_hash()] = True

                    # check if some cached event still is relevant - kick it out if not
                    for event in self.events_history.keys():
                        if not event in self.events_current.keys():
                            self.events_history.pop(event)
                            self.events_notification.pop(event)

                    # if some current event is not yet in event cache add it and mark it as fresh (=True)
                    for event in self.events_current.keys():
                        if not event in self.events_history.keys() and str(self.conf.highlight_new_events) == "True":
                            self.events_history[event] = True
                            self.events_notification[event] = True

                    # use a liststore for treeview where the table headers all are strings - first empty it
                    # now added with some simple repair after settings dialog has been used
                    # because sometimes after settings changes ListStore and TreeView become NoneType
                    # would be more logical to do this in Actions.CreateServer() but this gives a segfault :-(
                    if not type(server.ListStore) == type(None):
                        server.ListStore.clear()
                    else:
                        server.ListStore = gtk.ListStore(*self.LISTSTORE_COLUMNS)
                    if type(server.TreeView) == type(None):
                        # if treeview got lost recycle the one in servervbox
                        server.TreeView = self.popwin.ServerVBoxes[server.get_name()].TreeView

                    # apart from status informations there we need two columns which
                    # hold the color information, which is derived from status which
                    # is used as key at the above color dictionaries
                    # Update: new columns added which contain pixbufs of flag indicators if needed
                    for item_type, status_dict in server.nagitems_filtered.iteritems():
                        for status, item_list in status_dict.iteritems():
                            for single_item in list(item_list):
                                # use copy to fight memory leak
                                item = copy.deepcopy(single_item)

                                line = list(server.get_columns(item))

                                line.append("%s: %s\n%s" %((line[0], line[1], line[6])))

                                line.append(self.TAB_FG_COLORS[item.status])
                                line.append(self.TAB_BG_COLORS[item.status])

                                # add a slightly changed version of bg_color for better recognition in treeview
                                color = gtk.gdk.color_parse(self.TAB_BG_COLORS[item.status])
                                color = gtk.gdk.Color(red = self._GetAlternateColor(color.red),\
                                                      green = self._GetAlternateColor(color.green),\
                                                      blue = self._GetAlternateColor(color.blue),\
                                                      pixel = color.pixel)
                                line.append(color.to_string())

                                # icons for hosts
                                if item.is_host():
                                    if item.get_hash() in self.events_history and self.events_history[item.get_hash()] == True:
                                        line.append(self.STATE_ICONS["fresh"])
                                    else:
                                        line.append(None)

                                    if item.is_acknowledged():
                                        line.append(self.STATE_ICONS["acknowledged"])
                                    else:
                                        line.append(None)

                                    if item.is_in_scheduled_downtime():
                                        line.append(self.STATE_ICONS["downtime"])
                                    else:
                                        line.append(None)

                                    if item.is_flapping():
                                        line.append(self.STATE_ICONS["flapping"])
                                    else:
                                        line.append(None)

                                    if item.is_passive_only():
                                        line.append(self.STATE_ICONS["passive"])
                                    else:
                                        line.append(None)

                                    # fill line with dummmy values because there will
                                    # be none for services if this is a host
                                    line.extend([None, None, None, None, None])

                                # icons for services
                                else:
                                    # if the hosting host of a service has any flags display them too
                                    # a fresh service's host does not need a freshness icon
                                    line.append(None)

                                    if server.hosts[item.host].is_acknowledged():
                                        line.append(self.STATE_ICONS["acknowledged"])
                                    else:
                                        line.append(None)

                                    if server.hosts[item.host].is_in_scheduled_downtime():
                                        line.append(self.STATE_ICONS["downtime"])
                                    else:
                                        line.append(None)

                                    if server.hosts[item.host].is_flapping():
                                        line.append(self.STATE_ICONS["flapping"])
                                    else:
                                        line.append(None)

                                    if server.hosts[item.host].is_passive_only():
                                        line.append(self.STATE_ICONS["passive"])
                                    else:
                                        line.append(None)

                                    # now the service...
                                    if item.get_hash() in self.events_history and self.events_history[item.get_hash()] == True:
                                        line.append(self.STATE_ICONS["fresh"])
                                    else:
                                        line.append(None)

                                    if item.is_acknowledged():
                                        line.append(self.STATE_ICONS["acknowledged"])
                                    else:
                                        line.append(None)

                                    if item.is_in_scheduled_downtime():
                                        line.append(self.STATE_ICONS["downtime"])
                                    else:
                                        line.append(None)

                                    if item.is_flapping():
                                        line.append(self.STATE_ICONS["flapping"])
                                    else:
                                        line.append(None)

                                    if item.is_passive_only():
                                        line.append(self.STATE_ICONS["passive"])
                                    else:
                                        line.append(None)

                                server.ListStore.append(line)

                                del item, line

                    # give new ListStore to the view, overwrites the old one automatically - theoretically
                    server.TreeView.set_model(server.ListStore)

                    # restore sorting order from previous refresh
                    self.set_sorting(server.ListStore, server)

                    # status field in server vbox in popwin
                    self.popwin.UpdateStatus(server)

                except:
                    import traceback
                    traceback.print_exc(file=sys.stdout)
                    server.Error(sys.exc_info())

        if str(self.conf.fullscreen) == "False":
            self.popwin.Resize()
        else:
            # set every active vbox to window with to avoid too small ugly treeviewa
            for server in self.servers.values():
                if str(self.conf.servers[server.get_name()].enabled) == "True":
                    self.popwin.ServerVBoxes[server.get_name()].set_size_request(self.popwin.Window.get_size()[1], -1)
            pass

        # everything OK

        if unknowns == 0 and warnings == 0 and criticals == 0 and unreachables == 0 and informations == 0 and averages == 0 and highs == 0 and downs == 0 and self.status_ok is not False:
            self.statusbar.statusbar_labeltext = '<span size="%s" background="%s" foreground="%s"> OK </span>' % (str(self.fontsize), str(self.conf.color_ok_background), str(self.conf.color_ok_text))
            self.statusbar.statusbar_labeltext_inverted = self.statusbar.statusbar_labeltext
            self.statusbar.Label.set_markup(self.statusbar.statusbar_labeltext)
            # fix size when loading with network errors
            self.statusbar.Resize()
            # if all is OK there is no need to pop up popwin so set self.showPopwin to False
            self.popwin.showPopwin = False
            self.popwin.PopDown()
            self.status_ok = True

            # set systray icon to green aka OK
            if str(self.conf.icon_in_systray) == "True":
                self.statusbar.SysTray.set_from_pixbuf(self.statusbar.SYSTRAY_ICONS["green"])

            if str(self.conf.appindicator) == "True" and sys.modules.has_key("appindicator"):
                # greenify status icon
                self.appindicator.Indicator.set_attention_icon(self.Resources + os.sep + "nagstamon_green" + self.BitmapSuffix)
                self.appindicator.Indicator.set_status(appindicator.STATUS_ATTENTION)
                # disable all unneeded menu entries
                self.appindicator.Menu_OK.hide()
                self.appindicator.Menu_WARNING.hide()
                self.appindicator.Menu_UNKNOWN.hide()
                self.appindicator.Menu_CRITICAL.hide()
                self.appindicator.Menu_UNREACHABLE.hide()
                self.appindicator.Menu_DOWN.hide()

            # switch notification off
            self.NotificationOff()

        else:
            self.status_ok = False

            # put text for label together
            self.statusbar.statusbar_labeltext = self.statusbar.statusbar_labeltext_inverted = ""

            if downs > 0:
                if str(self.conf.long_display) == "True": downs = str(downs) + " DOWN"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_down_background), str(self.conf.color_down_text), str(downs))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_down_text), str(self.conf.color_down_background), str(downs))
            if unreachables > 0:
                if str(self.conf.long_display) == "True": unreachables = str(unreachables) + " UNREACHABLE"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_unreachable_background), str(self.conf.color_unreachable_text), str(unreachables))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_unreachable_text), str(self.conf.color_unreachable_background), str(unreachables))
            if criticals > 0:
                if str(self.conf.long_display) == "True": criticals = str(criticals) + " CRITICAL"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_critical_background), str(self.conf.color_critical_text), str(criticals))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_critical_text), str(self.conf.color_critical_background), str(criticals))
            if unknowns > 0:
                if str(self.conf.long_display) == "True": unknowns = str(unknowns) + " UNKNOWN"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_unknown_background), str(self.conf.color_unknown_text), str(unknowns))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_unknown_text), str(self.conf.color_unknown_background), str(unknowns))
            if warnings > 0:
                if str(self.conf.long_display) == "True": warnings = str(warnings) + " WARNING"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_warning_background), str(self.conf.color_warning_text), str(warnings))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_warning_text), str(self.conf.color_warning_background), str(warnings))
            if informations > 0:
                if str(self.conf.long_display) == "True": informations = str(informations) + " INFORMATION"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_unknown_background), str(self.conf.color_unknown_text), str(informations))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_unknown_text), str(self.conf.color_unknown_background), str(informations))
            if averages > 0:
                if str(self.conf.long_display) == "True": averages = str(averages) + " AVERAGE"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_average_background), str(self.conf.color_average_text), str(averages))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_average_text), str(self.conf.color_average_background), str(averages))
            if highs > 0:
                if str(self.conf.long_display) == "True": highs = str(highs) + " HIGH"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_high_background), str(self.conf.color_high_text), str(highs))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_high_text), str(self.conf.color_high_background), str(highs))

            # if connections fails at starting do not display OK - Debian bug #617490
            if unknowns == 0 and informations == 0 and averages  ==0 and highs == 0 and warnings == 0 and criticals == 0 and unreachables == 0 and downs == 0 and self.status_ok is False:
                if str(self.conf.long_display) == "True":
                    errors = "ERROR"
                else:
                    errors = "ERR"
                self.statusbar.statusbar_labeltext += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_error_background), str(self.conf.color_error_text), str(errors))
                self.statusbar.statusbar_labeltext_inverted += '<span size="%s" background="%s" foreground="%s"> %s </span>' % (str(self.fontsize), str(self.conf.color_error_text), str(self.conf.color_error_background), str(errors))
                color = "error"

            if str(self.conf.appindicator) == "True" and sys.modules.has_key("appindicator"):
                # set new icon
                self.appindicator.Indicator.set_attention_icon(self.Resources + os.sep + "nagstamon_error" + self.BitmapSuffix)
                self.appindicator.Indicator.set_status(appindicator.STATUS_ATTENTION)

            # put text into label in statusbar, only if not already flashing
            if self.statusbar.Flashing == False:
                self.statusbar.Label.set_markup(self.statusbar.statusbar_labeltext)

            # Windows workaround for non-automatically-shrinking desktop statusbar
            if str(self.conf.statusbar_floating) == "True":
                self.statusbar.Resize()

            # choose icon for systray  - the worst case decides the shown color
            if warnings > 0: color = "yellow"
            if unknowns > 0: color = "orange"
            if unknowns > 0: color = "yellow"
            if criticals > 0: color = "red"
            if unreachables > 0: color = "darkred"
            if downs > 0: color = "black"

            if str(self.conf.icon_in_systray) == "True":
                self.statusbar.SysTray.set_from_pixbuf(self.statusbar.SYSTRAY_ICONS[color])

            if str(self.conf.appindicator) == "True" and sys.modules.has_key("appindicator"):
                # enable/disable menu entries depending on existence of problems
                if warnings > 0:
                    self.appindicator.Menu_WARNING.set_label(str(warnings) + " WARNING")
                    self.appindicator.Menu_WARNING.show()
                else:
                    self.appindicator.Menu_WARNING.hide()
                if unknowns > 0:
                    self.appindicator.Menu_UNKNOWN.set_label(str(unknowns) + " UNKNOWN")
                    self.appindicator.Menu_UNKNOWN.show()
                else:
                    self.appindicator.Menu_UNKNOWN.hide()
                if informations > 0:
                    self.appindicator.Menu_INFORMATION.set_label(str(informations) + " INFORMATION")
                    self.appindicator.Menu_INFORMATION.show()
                else:
                    self.appindicator.Menu_INFORMATION.hide()
                if averages > 0:
                    self.appindicator.Menu_AVERAGE.set_label(str(averages) + " AVERAGE")
                    self.appindicator.Menu_AVERAGE.show()
                else:
                    self.appindicator.Menu_AVERAGE.hide()
                if highs > 0:
                    self.appindicator.Menu_HIGH.set_label(str(highs) + " HIGH")
                    self.appindicator.Menu_HIGH.show()
                else:
                    self.appindicator.Menu_HIGH.hide()
                if criticals > 0:
                    self.appindicator.Menu_CRITICAL.set_label(str(criticals) + " CRITICAL")
                    self.appindicator.Menu_CRITICAL.show()
                else:
                    self.appindicator.Menu_CRITICAL.hide()
                if unreachables > 0:
                    self.appindicator.Menu_UNREACHABLE.set_label(str(unreachables) + " UNREACHABLE")
                    self.appindicator.Menu_UNREACHABLE.show()
                else:
                    self.appindicator.Menu_UNREACHABLE.hide()
                if downs > 0:
                    self.appindicator.Menu_DOWN.set_label(str(downs) + " DOWNS")
                    self.appindicator.Menu_DOWN.show()
                else:
                    self.appindicator.Menu_DOWN.hide()

                # show nenu entry to acknowledge the notification
                self.appindicator.Menu_OK.show()

                # set new icon
                self.appindicator.Indicator.set_attention_icon(self.Resources + os.sep + "nagstamon_" + color + self.BitmapSuffix)
                self.appindicator.Indicator.set_status(appindicator.STATUS_ATTENTION)

            # if there has been any status change notify user
            # first find out which of all servers states is the worst
            worst = 0
            worst_status = "UP"

            """
            the last worse state should be saved here and taken for
            comparison to decide if keep warning if the respective
            (and not yet existing) option is set
            """
            for server in self.servers.values():
                if not server.WorstStatus == "UP":
                    # switch server status back because it has been recognized
                    if server.States.index(server.WorstStatus) > worst:
                        worst_status = server.WorstStatus
                    # reset status of the server for only processing it once
                    server.WorstStatus = "UP"
                if not worst_status == "UP" and str(self.conf.notification) == "True":
                    self.NotificationOn(status=worst_status, ducuw=(downs, unreachables, criticals, unknowns, warnings))
                    # store latst worst status for decide if there has to be notification action
                    # when all is OK some lines later
                    self.last_worst_status = worst_status

            # set self.showPopwin to True because there is something to show
            self.popwin.showPopwin = True

        # id all gets OK and an notifikation actions is defined run it
        if self.status_ok and self.last_worst_status != "UP":
            if str(self.conf.notification_action_ok) == "True":
               Actions.RunNotificationAction(str(self.conf.notification_action_ok_string))
            self.last_worst_status = "UP"

        # if failures have gone and nobody took notice switch notification off again
        if len([k for k,v in self.events_history.items() if v == True]) == 0 and self.Notifying == True:
            self.NotificationOff()

        # if only one monitor cannot be reached show popwin to inform about its trouble
        for server in self.servers.values():
            if server.status_description != "" or server.refresh_authentication == True:
                self.status_ok = False
                self.popwin.showPopwin = True

        # close popwin in case everything is ok and green
        if self.status_ok and not self.popwin.showPopwin:
            self.popwin.Close()

        # try to fix vanishing statusbar
        if str(self.conf.statusbar_floating) == "True":
            self.statusbar.Raise()

        # return False to get removed as gobject idle source
        return False


    def AcknowledgeDialogShow(self, server, host, service=None):
        """
            create and show acknowledge_dialog from gtkbuilder file
        """

        # set the gtkbuilder file
        self.builderfile = self.Resources + os.sep + "acknowledge_dialog.ui"
        self.acknowledge_xml = gtk.Builder()
        self.acknowledge_xml.add_from_file(self.builderfile)
        self.acknowledge_dialog = self.acknowledge_xml.get_object("acknowledge_dialog")
        # do not lose dialog behind other windows
        self.acknowledge_dialog.set_keep_above(True)

        # connect with action
        # only OK needs to be connected - if this action gets canceled nothing happens
        # use connect_signals to assign methods to handlers
        handlers_dict = { "button_ok_clicked": self.Acknowledge,
                          "button_acknowledge_settings_clicked": self.AcknowledgeDefaultSettings }
        self.acknowledge_xml.connect_signals(handlers_dict, server)

        # did not get it to work with glade so comments will be fired up this way when pressing return
        self.acknowledge_xml.get_object("input_entry_author").connect("key-release-event", self._FocusJump, self.acknowledge_xml, "input_entry_comment")
        self.acknowledge_xml.get_object("input_entry_comment").connect("key-release-event", self.AcknowledgeCommentReturn, server)

        # if service is "" it must be a host
        if service == "":
            # set label for acknowledging a host
            self.acknowledge_dialog.set_title("Acknowledge host")
            self.acknowledge_xml.get_object("input_label_description").set_markup("Host <b>%s</b>" % (host))
        else:
            # set label for acknowledging a service on host
            self.acknowledge_dialog.set_title("Acknowledge service")
            self.acknowledge_xml.get_object("input_label_description").set_markup("Service <b>%s</b> on host <b>%s</b>" % (service, host))

        # host and service labels are hidden to transport info to OK method
        self.acknowledge_xml.get_object("input_label_host").set_text(host)
        self.acknowledge_xml.get_object("input_label_host").hide()
        self.acknowledge_xml.get_object("input_label_service").set_text(service)
        self.acknowledge_xml.get_object("input_label_service").hide()

        # default flags of Nagios acknowledgement
        self.acknowledge_xml.get_object("input_checkbutton_sticky_acknowledgement").set_active(eval(str(self.conf.defaults_acknowledge_sticky)))
        self.acknowledge_xml.get_object("input_checkbutton_send_notification").set_active(eval(str(self.conf.defaults_acknowledge_send_notification)))
        self.acknowledge_xml.get_object("input_checkbutton_persistent_comment").set_active(eval(str(self.conf.defaults_acknowledge_persistent_comment)))
        self.acknowledge_xml.get_object("input_checkbutton_acknowledge_all_services").set_active(eval(str(self.conf.defaults_acknowledge_all_services)))

        # default author + comment
        self.acknowledge_xml.get_object("input_entry_author").set_text(server.username)
        self.acknowledge_xml.get_object("input_entry_comment").set_text(self.conf.defaults_acknowledge_comment)
        self.acknowledge_xml.get_object("input_entry_comment").grab_focus()

        # show dialog
        self.acknowledge_dialog.run()
        self.acknowledge_dialog.destroy()


    def AcknowledgeDefaultSettings(self, foo, bar):
        """
        show settings with tab "defaults" as shortcut from Acknowledge dialog
        """
        self.acknowledge_dialog.destroy()
        self.GetDialog(dialog="Settings", servers=self.servers, output=self, conf=self.conf, first_page="Defaults")


    def AcknowledgeCommentReturn(self, widget, event, server):
        """
        if Return key has been pressed in comment entry field interprete this as OK button being pressed
        """
        # KP_Enter seems to be the code for return key of numeric key block
        if gtk.gdk.keyval_name(event.keyval) in ["Return", "KP_Enter"]:
            self.Acknowledge(server=server)
            self.acknowledge_dialog.destroy()


    def Acknowledge(self, widget=None, server=None):
        """
            acknowledge miserable host/service
        """
        # various parameters for the CGI request
        host = self.acknowledge_xml.get_object("input_label_host").get_text()
        service = self.acknowledge_xml.get_object("input_label_service").get_text()
        author = self.acknowledge_xml.get_object("input_entry_author").get_text()
        comment = self.acknowledge_xml.get_object("input_entry_comment").get_text()
        acknowledge_all_services = self.acknowledge_xml.get_object("input_checkbutton_acknowledge_all_services").get_active()
        sticky = self.acknowledge_xml.get_object("input_checkbutton_sticky_acknowledgement").get_active()
        notify = self.acknowledge_xml.get_object("input_checkbutton_send_notification").get_active()
        persistent = self.acknowledge_xml.get_object("input_checkbutton_persistent_comment").get_active()

        # create a list of all service of selected host to acknowledge them all
        all_services = list()
        if acknowledge_all_services == True:
            for i in server.nagitems_filtered["services"].values():
                for s in i:
                    if s.host == host:
                        all_services.append(s.name)

        # let thread execute POST request
        acknowledge = Actions.Acknowledge(server=server, host=host,\
                                          service=service, author=author, comment=comment, acknowledge_all_services=acknowledge_all_services,\
                                          all_services=all_services, sticky=sticky, notify=notify, persistent=persistent)
        acknowledge.start()


    def DowntimeDialogShow(self, server, host, service=None):
        """
            create and show downtime_dialog from gtkbuilder file
        """
        # set the gtkbuilder file
        self.builderfile = self.Resources + os.sep + "downtime_dialog.ui"
        self.downtime_xml = gtk.Builder()
        self.downtime_xml.add_from_file(self.builderfile)
        self.downtime_dialog = self.downtime_xml.get_object("downtime_dialog")
        # do not lose dialog behind other windows
        self.downtime_dialog.set_keep_above(True)

        # connect with action
        # only OK needs to be connected - if this action gets canceled nothing happens
        # use connect_signals to assign methods to handlers
        handlers_dict = { "button_ok_clicked" : self.Downtime,
                          "button_downtime_settings_clicked" : self.DowntimeDefaultSettings }
        self.downtime_xml.connect_signals(handlers_dict, server)

        # focus jump chain - used to connect input fields in downtime dialog and access them via return key
        chain = ["input_entry_start_time",
                 "input_entry_end_time",
                 "input_entry_author",
                 "input_entry_comment"]
        for i in range(len(chain)-1):
            self.downtime_xml.get_object(chain[i]).connect("key-release-event", self._FocusJump, self.downtime_xml, chain[i+1])

        # if return key enterd in comment field see this as OK button pressed
        self.downtime_xml.get_object("input_entry_comment").connect("key-release-event", self.DowntimeCommentReturn, server)

        # if service is None it must be a host
        if service == "":
            # set label for acknowledging a host
            self.downtime_dialog.set_title("Downtime for host")
            self.downtime_xml.get_object("input_label_description").set_markup("Host <b>%s</b>" % (host))
        else:
            # set label for acknowledging a service on host
            self.downtime_dialog.set_title("Downtime for service")
            self.downtime_xml.get_object("input_label_description").set_markup("Service <b>%s</b> on host <b>%s</b>" % (service, host))

        # host and service labels are hidden to transport info to OK method
        self.downtime_xml.get_object("input_label_host").set_text(host)
        self.downtime_xml.get_object("input_label_host").hide()
        self.downtime_xml.get_object("input_label_service").set_text(service)
        self.downtime_xml.get_object("input_label_service").hide()

        # get start_time and end_time externally from Actions.Downtime_get_start_end() for not mixing GUI and actions too much
        start_time, end_time = Actions.Downtime_get_start_end(server=server, host=host)

        self.downtime_xml.get_object("input_radiobutton_type_fixed").set_active(eval(str(self.conf.defaults_downtime_type_fixed)))
        self.downtime_xml.get_object("input_radiobutton_type_flexible").set_active(eval(str(self.conf.defaults_downtime_type_flexible)))

        # default author + comment
        self.downtime_xml.get_object("input_entry_author").set_text(server.username)
        self.downtime_xml.get_object("input_entry_comment").set_text(self.conf.defaults_downtime_comment)
        self.downtime_xml.get_object("input_entry_comment").grab_focus()

        # start and end time
        self.downtime_xml.get_object("input_entry_start_time").set_text(start_time)
        self.downtime_xml.get_object("input_entry_end_time").set_text(end_time)

        # flexible downtime duration
        self.downtime_xml.get_object("input_spinbutton_duration_hours").set_value(int(self.conf.defaults_downtime_duration_hours))
        self.downtime_xml.get_object("input_spinbutton_duration_minutes").set_value(int(self.conf.defaults_downtime_duration_minutes))

        # show dialog
        self.downtime_dialog.run()
        self.downtime_dialog.destroy()


    def DowntimeDefaultSettings(self, foo, bar):
        """
        show settings with tab "defaults" as shortcut from Downtime dialog
        """
        self.downtime_dialog.destroy()
        self.GetDialog(dialog="Settings", servers=self.servers, output=self, conf=self.conf, first_page="Defaults")


    def DowntimeCommentReturn(self, widget, event, server):
        """
        if Return key has been pressed in comment entry field interprete this as OK button being pressed
        """
        # KP_Enter seems to be the code for return key of numeric key block
        if gtk.gdk.keyval_name(event.keyval) in ["Return", "KP_Enter"]:
            self.Downtime(server=server)
            self.downtime_dialog.destroy()


    def Downtime(self, widget=None, server=None):
        """
            schedule downtime for miserable host/service
        """
        # various parameters for the CGI request
        host = self.downtime_xml.get_object("input_label_host").get_text()
        service = self.downtime_xml.get_object("input_label_service").get_text()
        author = self.downtime_xml.get_object("input_entry_author").get_text()
        comment = self.downtime_xml.get_object("input_entry_comment").get_text()

        # start and end time
        start_time = self.downtime_xml.get_object("input_entry_start_time").get_text()
        end_time = self.downtime_xml.get_object("input_entry_end_time").get_text()
        # type of downtime - fixed or flexible
        if self.downtime_xml.get_object("input_radiobutton_type_fixed").get_active() == True: fixed = 1
        else: fixed = 0
        # duration of downtime if flexible
        hours = self.downtime_xml.get_object("input_spinbutton_duration_hours").get_value()
        minutes = self.downtime_xml.get_object("input_spinbutton_duration_minutes").get_value()

        # execute POST request with cgi_data, in this case threaded
        downtime = Actions.Downtime(server=server, host=host, service=service, author=author, comment=comment, fixed=fixed, start_time=start_time, end_time=end_time, hours=int(hours), minutes=int(minutes))
        downtime.start()


    def SubmitCheckResultDialogShow(self, server, host, service=None):
        """
            create and show acknowledge_dialog from gtkbuilder file
        """

        # set the gtkbuilder file
        self.builderfile = self.Resources + os.sep + "submit_check_result_dialog.ui"
        self.submitcheckresult_xml = gtk.Builder()
        self.submitcheckresult_xml.add_from_file(self.builderfile)
        self.submitcheckresult_dialog = self.submitcheckresult_xml.get_object("submit_check_result_dialog")
        # do not lose dialog behind other windows
        self.submitcheckresult_dialog.set_keep_above(True)

        # connect with action
        # only OK needs to be connected - if this action gets canceled nothing happens
        # use connect_signals to assign methods to handlers
        handlers_dict = { "button_ok_clicked" : self.SubmitCheckResultOK,\
                          "button_cancel_clicked": self.SubmitCheckResultCancel,\
                          "button_submit_check_result_settings_clicked" : self.SubmitCheckResultDefaultSettings}
        self.submitcheckresult_xml.connect_signals(handlers_dict, server)

        # focus jump chain - used to connect input fields in submit check result dialog and access them via return key
        # server.SUBMIT_CHECK_RESULT_ARGS contains the valid arguments for this server type so we might use it here too
        chain = server.SUBMIT_CHECK_RESULT_ARGS
        for i in range(len(chain)-1):
            self.submitcheckresult_xml.get_object("input_entry_" + chain[i]).connect("key-release-event", self._FocusJump, self.submitcheckresult_xml, "input_entry_" + chain[i+1])

        # if return key entered in lastfield see this as OK button pressed
        self.submitcheckresult_xml.get_object("input_entry_" + chain[-1]).connect("key-release-event", self.SubmitCheckResultCommentReturn, server)

        # if service is "" it must be a host
        if service == "":
            # set label for submitting results to an host
            self.submitcheckresult_dialog.set_title("Submit check result for host")
            self.submitcheckresult_xml.get_object("input_label_description").set_markup("Host <b>%s</b>" % (host))
            self.submitcheckresult_xml.get_object("input_radiobutton_result_ok").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_warning").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_critical").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_unknown").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_up").set_active(True)
        else:
            # set label for submitting results to a service on host
            self.submitcheckresult_dialog.set_title("Submit check result for service")
            self.submitcheckresult_xml.get_object("input_label_description").set_markup("Service <b>%s</b> on host <b>%s</b>" % (service, host))
            self.submitcheckresult_xml.get_object("input_radiobutton_result_unreachable").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_up").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_down").hide()
        for i in server.SUBMIT_CHECK_RESULT_ARGS:
            self.submitcheckresult_xml.get_object("label_" + i).show()
            self.submitcheckresult_xml.get_object("input_entry_" + i).show()

        # host and service labels are hidden to transport info to OK method
        self.submitcheckresult_xml.get_object("input_label_host").set_text(host)
        self.submitcheckresult_xml.get_object("input_label_host").hide()
        self.submitcheckresult_xml.get_object("input_label_service").set_text(service)
        self.submitcheckresult_xml.get_object("input_label_service").hide()

        self.submitcheckresult_xml.get_object("input_entry_comment").set_text(self.conf.defaults_submit_check_result_comment)

        # show dialog
        self.submitcheckresult_dialog.run()


    def SubmitCheckResultDefaultSettings(self, foo, bar):
        """
            show settings with tab "defaults" as shortcut from Submit Check Result dialog
        """
        self.submitcheckresult_dialog.destroy()
        self.GetDialog(dialog="Settings", servers=self.servers, output=self, conf=self.conf, first_page="Defaults")


    def SubmitCheckResultOK(self, widget=None, server=None):
        """
            submit check result
        """
        # various parameters for the CGI request
        host = self.submitcheckresult_xml.get_object("input_label_host").get_text()
        service = self.submitcheckresult_xml.get_object("input_label_service").get_text()
        comment = self.submitcheckresult_xml.get_object("input_entry_comment").get_text()
        check_output = self.submitcheckresult_xml.get_object("input_entry_check_output").get_text()
        performance_data = self.submitcheckresult_xml.get_object("input_entry_performance_data").get_text()

        # dummy default state
        state = "ok"

        for s in ["ok", "up", "warning", "critical", "unreachable", "unknown", "down"]:
            if self.submitcheckresult_xml.get_object("input_radiobutton_result_" + s).get_active() == True:
                state = s
                break

        if "check_output" in server.SUBMIT_CHECK_RESULT_ARGS and len(check_output) == 0:
            self.Dialog(message="Submit check result needs a check output.")
        else:
            # let thread execute POST request
            submit_check_result = Actions.SubmitCheckResult(server=server, host=host,\
                                                            service=service, comment=comment, check_output=check_output,\
                                                            performance_data=performance_data, state=state)
            submit_check_result.start()
            # only close dialog if input was correct
            self.submitcheckresult_dialog.destroy()


    def SubmitCheckResultCancel(self, widget, server):
        self.submitcheckresult_dialog.destroy()


    def SubmitCheckResultCommentReturn(self, widget, event, server):
        """
            if Return key has been pressed in comment entry field interprete this as OK button being pressed
        """
        # KP_Enter seems to be the code for return key of numeric key block
        if gtk.gdk.keyval_name(event.keyval) in ["Return", "KP_Enter"]:
            self.SubmitCheckResultOK(server=server)
            self.submitcheckresult_dialog.destroy()


    def AboutDialog(self):
        """
            about nagstamon
        """
        about = gtk.AboutDialog()
        about.set_keep_above(True)
        about.set_name(self.name)
        about.set_version(self.version)
        about.set_website(self.website)
        about.set_copyright(self.copyright)
        about.set_comments(self.comments)
        about.set_authors(["Henri Wahl",
                           " ",
                           "Thank you very much for code",
                           "contributions, patches, packaging,",
                           "testing, hints and ideas:",
                           " ",
                           "Andreas Ericsson",
                           "Antoine Jacoutot",
                           "Anton Löfgren",
                           "Arnaud Gomes",
                           "Benoît Soenen",
                           "Carl Chenet",
                           "Carl Helmertz",
                           "Davide Cecchetto",
                           "Emile Heitor ",
                           "John Conroy",
                           "Lars Michelsen",
                           "M. Cigdem Cebe",
                           "Martin Campbell",
                           "Mattias Ryrlén",
                           "Michał Rzeszut",
                           "Nikita Klimov",
                           "Patrick Cernko",
                           "Pawel Połewicz",
                           "Robin Sonefors",
                           "Salvatore LaMendola",
                           "Sandro Tosi",
                           "Sven Nierlein",
                           "Thomas Gelf",
                           "Tobias Scheerbaum",
                           "Wouter Schoot",
                           "Yannick Charton",
                           " ",
                           "...and those I forgot to mention but who helped a lot...",
                           " ",
                           "Third party software used by Nagstamon",
                           "under their respective license:",
                           "BeautifulSoup - http://www.crummy.com/software/BeautifulSoup",
                           "Pyinstaller - http://www.pyinstaller.org"])
        # read LICENSE file
        license = ""
        try:
            # try to find license file in resource directory
            f = open(self.Resources + os.sep + "LICENSE", "r")
            s = f.readlines()
            f.close()
            for line in s:
                license += line
        except:
            license = "Nagstamon is licensed under GPL 2.0.\nYou should have got a LICENSE file distributed with nagstamon.\nGet it at http://www.gnu.org/licenses/gpl-2.0.txt."
        about.set_license(license)

        # use gobject.idle_add() to be thread safe
        gobject.idle_add(self.AddGUILock, str(self.__class__.__name__))
        self.popwin.Close()
        about.run()
        # use gobject.idle_add() to be thread safe
        gobject.idle_add(self.DeleteGUILock, str(self.__class__.__name__))
        about.destroy()


    def Dialog(self, type=gtk.MESSAGE_ERROR, message="", buttons=gtk.BUTTONS_CANCEL):
        """
            versatile message dialog
        """
        # close popwin to make sure the error dialog will not be covered by popwin
        self.popwin.PopDown()
        self.dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=type, buttons=buttons, message_format=str(message))
        # gtk.Dialog.run() does a mini loop to wait
        self.dialog.run()
        self.dialog.destroy()


    def CheckForNewVersionDialog(self, version_status=None, version=None):
        """
            Show results of Settings.CheckForNewVersion()
        """
        try:
            # close popwin to make sure the error dialog will not be covered by popwin
            self.popwin.PopDown()

            # if used version is latest version only inform about
            if version_status == "latest":
                self.dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_INFO, buttons=gtk.BUTTONS_OK, \
                                           message_format="You are already using the\nlatest version of Nagstamon.\n\nLatest version: %s" % (version))
                # keep message dialog in front
                self.dialog.set_keep_above(True)
                self.dialog.present()

                self.dialog.run()
                self.dialog.destroy()
            # if used version is out of date offer downloading latest one
            elif version_status == "out_of_date":
                self.dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_YES_NO, \
                                           message_format="You are not using the latest version of Nagstamon.\n\nYour version:\t\t%s\nLatest version:\t%s\n\nDo you want to download the latest version?" % (self.version, version))
                # keep message dialog in front
                self.dialog.set_keep_above(True)
                self.dialog.present()

                response = self.dialog.run()
                if response == gtk.RESPONSE_YES:
                    Actions.OpenNagstamonDownload(output=self)
                self.dialog.destroy()
        except:
            self.servers.values()[0].Error(sys.exc_info())

        # return False to get removed as gobject idle source
        return False


    def NotificationOn(self, status="UP", ducuw=None):
        """
            switch on whichever kind of notification
            ducuw = downs, unreachables, criticals, unknowns, warnings
        """
        try:
            # check if notification for status is wanted
            if not status == "UP" and str(self.conf.__dict__["notify_if_" + status.lower()]) == "True":
                # only notify if popwin not already popped up
                if (self.popwin.Window.get_properties("visible")[0] == False and\
                    str(self.conf.fullscreen) == "False")\
                    or\
                    (self.popwin.Window.get_properties("visible")[0] == True and\
                     str(self.conf.fullscreen) == "True"):
                    if self.Notifying == False:
                        self.Notifying = True
                        # debug
                        if str(self.conf.debug_mode) == "True":
                            self.servers.values()[0].Debug(debug="Notification on.")
                        # threaded statusbar flash
                        if str(self.conf.notification_flashing) == "True":
                            if  str(self.conf.icon_in_systray) == "True":
                                self.statusbar.SysTray.set_blinking(True)
                            elif  str(self.conf.statusbar_floating) == "True":
                                self.statusbar.Flashing = True
                            elif str(self.conf.appindicator) == "True":
                                self.appindicator.Flashing = True

                        # flashing notification
                        notify = Actions.Notification(output=self, sound=status, Resources=self.Resources, conf=self.conf, servers=self.servers)
                        notify.start()

                        # just playing with libnotify
                        if str(self.conf.notification_desktop) == "True":
                            trouble = ""
                            if ducuw[0] > 0 : trouble += ducuw[0] + " "
                            if ducuw[1] > 0 : trouble += ducuw[1] + " "
                            if ducuw[2] > 0 : trouble += ducuw[2] + " "
                            if ducuw[3] > 0 : trouble += ducuw[3] + " "
                            if ducuw[4] > 0 : trouble += ducuw[4]
                            self.notify_bubble = pynotify.Notification ("Nagstamon", trouble, self.Resources + os.sep + "nagstamon" +self.BitmapSuffix)
                            # only offer button for popup window when floating statusbar is used
                            if str(self.conf.statusbar_floating) == "True":
                                self.notify_bubble.add_action("action", "Open popup window", self.popwin.PopUp)
                            self.notify_bubble.show()

                        # Notification actions
                        if str(self.conf.notification_actions) == "True":
                            if str(self.conf.notification_action_warning) == "True" and status == "WARNING":
                                Actions.RunNotificationAction(str(self.conf.notification_action_warning_string))
                            if str(self.conf.notification_action_critical) == "True" and status == "CRITICAL":
                                Actions.RunNotificationAction(str(self.conf.notification_action_critical_string))
                            if str(self.conf.notification_action_down) == "True" and status == "DOWN":
                                Actions.RunNotificationAction(str(self.conf.notification_action_down_string))

                        # if desired pop up status window
                        # sorry but does absolutely not work with windows and systray icon so I prefer to let it be
                        #if str(self.conf.notification_popup) == "True":
                        #    self.popwin.showPopwin = True
                        #    self.popwin.PopUp()

                # Custom event notification
                if str(self.conf.notification_actions) == "True" and str(self.conf.notification_custom_action) == "True":
                    events = ""
                    # if no single notifications should be used (default) put all events into one string, separated by separator
                    if str(self.conf.notification_custom_action_single) == "False":
                        # list comprehension only considers events which are new, ergo True
                        events = self.conf.notification_custom_action_separator.join([k for k,v in self.events_notification.items() if v == True])
                        # clear already notified events setting them to False
                        for event in [k for k,v in self.events_notification.items() if v == True]: self.events_notification[event] = False
                    else:
                        for event in [k for k,v in self.events_notification.items() if v == True]:
                            custom_action_string = self.conf.notification_custom_action_string.replace("$EVENTS$", event)
                            Actions.RunNotificationAction(custom_action_string)
                            # clear already notified events setting them to False
                            self.events_notification[event] = False
                    # if events got filled display them now
                    if events != "":
                        # in case a single action per event has to be executed
                        custom_action_string = self.conf.notification_custom_action_string.replace("$EVENT$", "$EVENTS$")
                        # insert real event(s)
                        custom_action_string = custom_action_string.replace("$EVENTS$", events)
                        Actions.RunNotificationAction(custom_action_string)
                else:
                    # set all events to False to ignore them in the future
                    for event in self.events_notification: self.events_notification[event] = False

        except:
            self.servers.values()[0].Error(sys.exc_info())


    def NotificationOff(self, widget=None):
        """
            switch off whichever kind of notification
        """
        if self.Notifying == True:
            self.Notifying = False
            # debug
            if str(self.conf.debug_mode) == "True":
                self.servers.values()[0].Debug(debug="Notification off.")
            if  str(self.conf.icon_in_systray) == "True":
                self.statusbar.SysTray.set_blinking(False)
            elif  str(self.conf.statusbar_floating) == "True":
                self.statusbar.Flashing = False
                self.statusbar.Label.set_markup(self.statusbar.statusbar_labeltext)
                # resize statusbar to avoid artefact when showing error
                self.statusbar.Resize()
            elif str(self.conf.appindicator) == "True" and sys.modules.has_key("appindicator"):
                self.appindicator.Flashing = False
                self.appindicator.Indicator.set_status(appindicator.STATUS_ATTENTION)


    def RecheckAll(self, widget=None):
        """
            call threaded recheck all action
        """
        # first delete all freshness flags
        self.UnfreshEventHistory()
        # run threads for rechecking
        recheckall = Actions.RecheckAll(servers=self.servers, output=self, conf=self.conf)
        recheckall.start()


    def _GetAlternateColor(self, color, diff=2048):
        """
            helper for treeview table colors to get a slightly different color
        """
        if color > (65535 - diff):
            color = color - diff
        else:
            color = color + diff
        return color


    def AddGUILock(self, widget_name, widget=None):
        """
            add calling window to dictionary of open windows to keep the windows separated
            to be called via gobject.idle_add
        """
        self.GUILock[widget_name] = widget

        # return False to get removed as gobject idle source
        return False


    def DeleteGUILock(self, window_name):
        """
        delete calling window from dictionary of open windows to keep the windows separated
        to be called via gobject.idle_add
        """
        try:
            self.GUILock.pop(window_name)
        except:
            #import traceback
            #traceback.print_exc(file=sys.stdout)
            pass

        # return False to get removed as gobject idle source
        return False


    def _FocusJump(self, widget=None, event=None, builder=None, next_widget=None):
        """
        if Return key has been pressed in entry field jump to given widget
        """
        if gtk.gdk.keyval_name(event.keyval) in ["Return", "KP_Enter"]:
            builder.get_object(next_widget).grab_focus()


    def Exit(self, dummy):
        """
            exit....
        """
        self.conf.SaveConfig(output=self)
        gtk.main_quit()


    def GetDialog(self, **kwds):
        """
            Manage dialogs et al. so they would not have been re-created with every access
            Hoping to decrease memory usage this way
        """
        for k in kwds: self.__dict__[k] = kwds[k]

        # create dialogs if not yet existing
        if not self.dialog in self.Dialogs:
            if self.dialog == "Settings":
                gobject.idle_add(self.output.AddGUILock, "Settings")
                self.Dialogs["Settings"] = Settings(servers=self.servers, output=self.output, conf=self.conf, first_page=self.first_page)
                self.Dialogs["Settings"].show()

            elif self.dialog == "NewServer":
                gobject.idle_add(self.output.AddGUILock, "NewServer")
                self.Dialogs["NewServer"] = NewServer(servers=self.servers, output=self.output, settingsdialog=self.settingsdialog, conf=self.conf)
                self.Dialogs["NewServer"].show()

            elif self.dialog == "EditServer":
                gobject.idle_add(self.output.AddGUILock, "EditServer")
                self.Dialogs["EditServer"] = EditServer(servers=self.servers, output=self.output, settingsdialog=self.settingsdialog, conf=self.conf, server=self.selected_server)
                self.Dialogs["EditServer"].show()

            elif self.dialog == "CopyServer":
                gobject.idle_add(self.output.AddGUILock, "CopyServer")
                self.Dialogs["CopyServer"] = CopyServer(servers=self.servers, output=self.output, settingsdialog=self.settingsdialog, conf=self.conf, server=self.selected_server)
                self.Dialogs["CopyServer"].show()

            elif self.dialog == "NewAction":
                gobject.idle_add(self.output.AddGUILock, "NewAction")
                self.Dialogs["NewAction"] = NewAction(output=self.output, settingsdialog=self.settingsdialog, conf=self.conf)
                self.Dialogs["NewAction"].show()

            elif self.dialog == "EditAction":
                gobject.idle_add(self.output.AddGUILock, "EditAction")
                self.Dialogs["EditAction"] = EditAction(output=self.output, settingsdialog=self.settingsdialog, conf=self.conf, action=self.selected_action)
                self.Dialogs["EditAction"].show()
            elif self.dialog == "CopyAction":
                gobject.idle_add(self.output.AddGUILock, "CopyAction")
                self.Dialogs["CopyAction"] = CopyAction(output=self.output, settingsdialog=self.settingsdialog, conf=self.conf, action=self.selected_action)
                self.Dialogs["CopyAction"].show()
        else:
            # when being reused some dialogs need some extra values
            if self.dialog in ["Settings", "NewServer", "EditServer", "CopyServer", "NewAction", "EditAction", "CopyAction"]:
                self.output.popwin.Close()
                gobject.idle_add(self.output.AddGUILock, self.dialog)
                if self.dialog == "Settings":
                    self.Dialogs["Settings"].first_page = self.first_page
                if self.dialog == "EditServer":
                    self.Dialogs["EditServer"].server = self.selected_server
                if self.dialog == "CopyServer":
                    self.Dialogs["CopyServer"].server = self.selected_server
                if self.dialog == "EditAction":
                    self.Dialogs["EditAction"].action = self.selected_action
                if self.dialog == "CopyAction":
                    self.Dialogs["CopyAction"].action = self.selected_action
                self.Dialogs[self.dialog].initialize()
                self.Dialogs[self.dialog].show()


    def UnfreshEventHistory(self):
        # set all flagged-as-fresh-events to un-fresh
        for event in self.events_history.keys():
            self.events_history[event] = False


    def ApplyServerModifications(self):
        """
        used by every dialog that modifies server settings
        """
        # kick out deleted or renamed servers,
        # create new ones for new, renamed or re-enabled ones
        for server in self.servers.values():
            if not server.get_name() in self.popwin.ServerVBoxes:
                self.popwin.ServerVBoxes[server.get_name()] = self.popwin.CreateServerVBox(server.get_name(), self)
                if str(self.conf.servers[server.get_name()].enabled)== "True":
                    self.popwin.ServerVBoxes[server.get_name()].set_visible(True)
                    self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(False)
                    self.popwin.ServerVBoxes[server.get_name()].show_all()
                    #self.output.popwin.ServerVBoxes[server.get_name()].Label.set_markup('<span weight="bold" size="large">%s@%s</span>' % (server.get_username(), server.get_name()))
                    # refresh servervboxes
                    self.popwin.ServerVBoxes[server.get_name()].initialize(server)
                    # add box to the other ones
                    self.popwin.ScrolledVBox.add(self.popwin.ServerVBoxes[server.get_name()])
                    # add server sorting
                    self.last_sorting[server.get_name()] = Sorting([(self.startup_sort_field,\
                                                                  self.startup_sort_order ),\
                                                                  (server.HOST_COLUMN_ID, gtk.SORT_ASCENDING)],\
                                                                  len(server.COLUMNS)+1)
        # delete not-current-anymore servers (disabled or renamed)
        for server in self.popwin.ServerVBoxes.keys():
            if not server in self.servers:
                self.popwin.ServerVBoxes[server].hide_all()
                self.popwin.ServerVBoxes[server].destroy()
                self.popwin.ServerVBoxes.pop(server)

        # reorder server VBoxes in case some names changed
        # to sort the monitor servers alphabetically make a sortable list of their names
        server_list = []
        for server in self.conf.servers:
            if str(self.conf.servers[server].enabled) == "True":
                server_list.append(server)
            else:
                # destroy disabled server vboxes if they exist
                if server in self.popwin.ServerVBoxes:
                    self.popwin.ServerVBoxes[server].destroy()
                    self.popwin.ServerVBoxes.pop(server)
        server_list.sort(key=str.lower)

        # sort server vboxes
        for server in server_list:
            # refresh servervboxes
            self.popwin.ServerVBoxes[server].initialize(self.servers[server])
            self.popwin.ScrolledVBox.reorder_child(self.popwin.ServerVBoxes[server], server_list.index(server))

        # refresh servers combobox in popwin
        # first remove all entries
        for i in range(1, len(self.popwin.ComboboxMonitor.get_model())):
            # "Go to monitor..." is the first entry so do not delete item index 0
            self.popwin.ComboboxMonitor.remove_text(1)

        # sort server names for list
        server_list = list()
        for server in self.conf.servers.keys():
            server_list.append(server)
        server_list.sort(key=str.lower)
        # add all servers in sorted order
        for server in server_list:
            self.popwin.ComboboxMonitor.append_text(server)

        # brutal renewal of popup menu for of statusbar because servers might have been added
        self.output.statusbar.Menu.destroy()
        self.output.statusbar._CreateMenu()
        if self.conf.appindicator == True:
            # otherwise Ubuntu loses its Nagstamon submenu
            self.output.appindicator.Menu_Nagstamon.set_submenu(self.output.statusbar.Menu)


        # force refresh
        Actions.RefreshAllServers(servers=self.servers, output=self, conf=self.conf)


class StatusBar(object):
    """
        statusbar object with appended systray icon
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        self._CreateFloatingStatusbar()

        # image for logo in statusbar
        self.nagstamonLogo = gtk.Image()
        self.nagstamonLogo.set_from_file(self.output.Resources + os.sep + "nagstamon_small" + self.output.BitmapSuffix)

        # icons for systray
        self.SYSTRAY_ICONS = dict()
        for color in ["green", "yellow", "red", "darkred", "orange", "black","error"]:
            self.SYSTRAY_ICONS[color] = gtk.gdk.pixbuf_new_from_file(self.output.Resources + os.sep + "nagstamon_" + color + self.output.BitmapSuffix)

        # 2 versions of label text for notification
        self.statusbar_labeltext = ""
        self.statusbar_labeltext_inverted = ""
        self.Flashing = False

        # Label for display
        self.Label = gtk.Label()

        # statusbar hbox container for logo and status label
        self.HBox = gtk.HBox()

        # Use EventBox because Label cannot get events
        self.LogoEventbox = gtk.EventBox()
        self.LogoEventbox.add(self.nagstamonLogo)
        self.EventBoxLabel = gtk.EventBox()
        self.EventBoxLabel.add(self.Label)
        self.HBox.add(self.LogoEventbox)
        self.HBox.add(self.EventBoxLabel)
        self.StatusBar.add(self.HBox)
        # trying a workaround for windows gtk 2.22 not letting statusbar being dragged around
        self.Moving = False

        # if statusbar is enabled...
        self.StatusBar.move(int(self.conf.position_x), int(self.conf.position_y))
        if str(self.conf.statusbar_floating) == "True":
        # ...move statusbar in case it is floating to its last saved position and show it
            self.StatusBar.show_all()
        else:
            self.StatusBar.hide_all()

        # put Systray icon into statusbar object
        # on MacOSX use only dummy
        if platform.system() == "Darwin":
            self.SysTray = DummyStatusIcon()
        else:
            self.SysTray = gtk.StatusIcon()
        self.SysTray.set_from_file(self.output.Resources + os.sep + "nagstamon" + self.output.BitmapSuffix)

        # if systray icon should be shown show it
        if str(self.conf.icon_in_systray) == "False": self.SysTray.set_visible(False)
        else: self.SysTray.set_visible(True)

        # flag to lock statusbar error messages not to provoke a pango crash
        self.isShowingError = False

        self.CalculateFontSize()

        # Popup menu for statusbar
        self._CreateMenu()


    def _CreateMenu(self):
        """
        create statusbar menu, to be used by statusbar initialization and after Settings changes
        """
        # Popup menu for statusbar
        self.Menu = gtk.Menu()
        for i in ["Refresh", "Recheck all", "-----", "Monitors", "-----", "Settings...", "Save position", "About", "Exit"]:
            if i == "-----":
                menu_item = gtk.SeparatorMenuItem()
                self.Menu.append(menu_item)
            else:
                if i == "Monitors":
                    monitor_items = list(self.output.servers)
                    monitor_items.sort(key=str.lower)
                    for m in monitor_items:
                        menu_item = gtk.MenuItem(m)
                        menu_item.connect("activate", self.MenuResponseMonitors, m)
                        self.Menu.append(menu_item)
                else:
                    menu_item = gtk.MenuItem(i)
                    menu_item.connect("activate", self.MenuResponse, i)
                    self.Menu.append(menu_item)

        self.Menu.show_all()


    def CalculateFontSize(self):
        """
            adapt label font size to nagstamon logo height because on different platforms
            default sizes + fonts vary
        """
        try:
            fontsize = 7000
            self.Label.set_markup('<span size="%s"> Loading... </span>' % (fontsize))
            # compare heights, height of logo is the important one
            while self.LogoEventbox.size_request()[1] > self.Label.size_request()[1]:
                self.Label.set_markup('<span size="%s"> Loading... </span>' % (fontsize))
                fontsize += 250
            # take away some pixels to fit into status bar
            self.output.fontsize = fontsize - 250
        except:
            # in case of error define fixed fontsize
            self.output.fontsize = 10000


    def _CreateFloatingStatusbar(self):
        """
            create statusbar as floating window
        """
        # TOPLEVEL seems to be more standard compliant
        if platform.system() == "Windows" or platform.system() == "Darwin":
            self.StatusBar = gtk.Window(gtk.WINDOW_POPUP)
        else:
            self.StatusBar = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.StatusBar.set_decorated(False)
        self.StatusBar.set_keep_above(True)
        # newer Ubuntus place a resize widget onto floating statusbar - please don't!
        self.StatusBar.set_resizable(False)
        self.StatusBar.stick()
        # at http://www.pygtk.org/docs/pygtk/gdk-constants.html#gdk-window-type-hint-constants
        # there are some hint types to experiment with
        # see https://github.com/HenriWahl/Nagstamon/issues/51
        if platform.system() == "Windows":
            self.StatusBar.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
        else:
            self.StatusBar.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_MENU)
        self.StatusBar.set_property("skip-taskbar-hint", True)
        self.StatusBar.set_skip_taskbar_hint(True)


    def MenuPopup(self, widget=None, event=None, time=None, dummy=None):
        """
            context menu for label in statusbar
        """
        self.output.popwin.Close()

        # no dragging of statusbar anymore if menu pops up
        self.Moving = False

        # check if settings are not already open
        if not "Settings" in self.output.GUILock:
            # for some reason StatusIcon delivers another event (type int) than
            # egg.trayicon (type object) so it must be checked which one has
            # been calling
            # to make it even worse there are different integer types given back
            # in Windows and Unix
            if isinstance(event, int) or isinstance(event, long):
                # right button
                if event == 3:
                    # 'time' is important (wherever it comes from) for Linux/Gtk to let
                    # the popup be shown even after releasing the mouse button
                    self.Menu.popup(None, None, None, event, time)
            else:
                # right button
                if event.button == 3:
                    self.Menu.popup(None, None, None, event.button, event.time)

            # silly Windows(TM) workaround to keep menu above taskbar
            if not platform.system() == "Darwin":
                self.Menu.window.set_keep_above(True)


    def MenuResponseMonitors(self, widget, menu_entry):
        """
            open responding Nagios status web page
        """
        self.output.servers[menu_entry].OpenBrowser(url_type="monitor")


    def MenuResponse(self, widget, menu_entry):
        """
            responses for the context menu for label in statusbar
        """
        if menu_entry == "Refresh": Actions.RefreshAllServers(servers=self.output.servers, output=self.output, conf=self.conf)
        if menu_entry == "Recheck all": self.output.RecheckAll()
        if menu_entry == "Settings...": self.output.GetDialog(dialog="Settings", servers=self.output.servers, output=self.output, conf=self.conf, first_page="Servers")
        if menu_entry == "Save position": self.conf.SaveConfig(output=self.output)
        if menu_entry == "About": self.output.AboutDialog()
        if menu_entry == "Exit":
            self.conf.SaveConfig(output=self.output)
            gtk.main_quit()


    def Clicked(self, widget=None, event=None):
        """
            see what happens if statusbar is clicked
        """
        # check if settings etc. are not already open
        if self.output.popwin.IsWanted() == True:
            # if left mousebutton is pressed
            if event.button == 1:
                # if popping up on click is true...
                if str(self.conf.popup_details_clicking) == "True":
                    #... and summary popup not shown yet...
                    if self.output.popwin.Window.get_properties("visible")[0] == False:
                        #...show it...
                        self.output.popwin.PopUp()
                    else:
                        #...otherwise close it
                        self.output.popwin.Close()
                # if hovering is set, popwin is open and statusbar gets clicked...
                else:
                    # close popwin for convinience
                    if self.output.popwin.Window.get_properties("visible")[0] == True:
                        self.output.popwin.Close()
            # if right mousebutton is pressed show statusbar menu
            if event.button == 3:
                #self.output.popwin.Close()
                self.Moving = False
                self.MenuPopup(widget=self.Menu, event=event)

        # switch off Notification
        self.output.NotificationOff()


    def LogoClicked(self, widget=None, event=None):
        """
            see what happens if statusbar is clicked
        """
        # check if settings etc. are not already open - an open popwin will be closed anyway
        if len(self.output.GUILock) == 0 or self.output.GUILock.has_key("Popwin"):
            # get position of statusbar
            self.StatusBar.x = event.x
            self.StatusBar.y = event.y
            # if left mousebutton is pressed
            if event.button == 1:
                self.output.popwin.Close()

                self.Moving = True
                move = Actions.MoveStatusbar(output=self.output)
                move.start()

            # if right mousebutton is pressed show statusbar menu
            if event.button == 3:
                self.output.popwin.Close()
                self.Moving = False
                self.MenuPopup(widget=self.Menu, event=event)


    def LogoReleased(self, widget=None, event=None):
        """
        used when button click on logo is released
        """
        self.output.popwin.setShowable()
        self.Moving = False
        # to avoid wrong placed popwin in macosx
        gobject.idle_add(self.output.RefreshDisplayStatus)


    def SysTrayClicked(self, widget=None, event=None):
        """
            see what happens when icon in systray has been clicked
        """

        # workaround for continuous popup menu
        try:
            self.Menu.popdown()
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

        # switch notification off
        self.output.NotificationOff()
        # check if settings and other dialogs are not already open
        if self.output.popwin.IsWanted() == True:
            # if popwin is not shown pop it up
            if self.output.popwin.Window.get_properties("visible")[0] == False or len(self.output.GUILock) == 0:
                # workaround for Windows loyal popwin bug
                # https://github.com/HenriWahl/Nagstamon/issues/63
                if self.output.popwin.mousex == self.output.popwin.mousey == 0:
                    rootwin = self.StatusBar.get_screen().get_root_window()
                    self.output.popwin.mousex, self.output.popwin.mousey, foo = rootwin.get_pointer()
                self.output.popwin.PopUp()
            else:
                self.output.popwin.Close()


    def Hovered(self, widget=None, event=None):
        """
            see what happens if statusbar is hovered
        """
        # check if any dialogs are not already open and pointer does not come
        # directly from popwin - to avoid flicker and artefact
        if self.output.popwin.IsWanted() == True and\
           str(self.conf.popup_details_hover) == "True" and\
           self.output.popwin.pointer_left_popwin == False:
            self.output.popwin.PopUp()


    def Move(self, widget=None, event=None):
        """
            moving statusbar
        """
        # access to rootwindow to get the pointers coordinates
        rootwin = self.StatusBar.get_screen().get_root_window()
        # get position of the pointer
        mousex, mousey, foo = rootwin.get_pointer()
        self.conf.position_x = int(mousex - self.StatusBar.x)
        self.conf.position_y = int(mousey - self.StatusBar.y)
        self.StatusBar.move(self.conf.position_x, self.conf.position_y)

        # return False to get removed as gobject idle source
        return False


    def ShowErrorMessage(self, message):
        """
            Shows error message in statusbar
        """
        try:
            # set flag to locked
            self.isShowingError = True
            self.Label.set_markup('<span size="%s"> %s </span>' % (self.output.fontsize, message))
            # Windows workaround for non-shrinking desktop statusbar
            self.Resize()
            # change systray icon to error
            self.SysTray.set_from_pixbuf(self.SYSTRAY_ICONS["error"])
            # Windows workaround for non-shrinking desktop statusbar
            self.Resize()
        except:
            self.servers.values()[0].Error(sys.exc_info())

        # return False to get removed as gobject idle source
        return False


    def Flash(self):
        """
            Flashing notification, triggered by threaded RefreshLoop
        """
        # replace statusbar label text with its inverted version
        if self.Label.get_label() == self.statusbar_labeltext:
            self.Label.set_markup(self.statusbar_labeltext_inverted)
        else:
            self.Label.set_markup(self.statusbar_labeltext)

        # Windows workaround for non-automatically-shrinking desktop statusbar
        if str(self.conf.statusbar_floating) == "True":
            try:
                self.Resize()
            except:
                self.servers.values()[0].Error(sys.exc_info())

        # return False to get removed as gobject idle source
        return False


    def Resize(self):
        """
            Resize/fix statusbar
        """
        try:
            x,y = self.Label.size_request()
            self.StatusBar.resize(x, y)
        except:
            self.StatusBar.resize(1, 1)


    def Raise(self):
        """
        try to fix Debian bug #591875: eventually ends up lower in the window stacking order, and can't be raised
        raising statusbar window with every refresh should do the job
        also do NOT raise if statusbar menu is open because otherwise it will be overlapped
        """
        if str(self.conf.statusbar_floating) == "True":
            # always raise on Windows plus
            # workaround for statusbar-that-overlaps-popup-menu (oh my god)
            if platform.system() == "Windows":
                if not self.Menu.get_properties("visible")[0]:
                    self.StatusBar.window.raise_()
            # on Linux & Co. only raise if popwin is not shown because otherwise
            # the statusbar shadow overlays the popwin on newer desktop environments
            elif self.output.popwin.showPopwin == False:
                self.StatusBar.window.raise_()


class Popwin(object):
    """
    Popwin object
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        # Initialize type popup
        if platform.system() == "Darwin":
            self.Window = gtk.Window(gtk.WINDOW_POPUP)
        else:
            self.Window = gtk.Window(gtk.WINDOW_TOPLEVEL)
            self.Window.set_title(self.output.name + " " + self.output.version)

        # notice leaving cursor
        self.Window.connect("leave-notify-event", self.LeavePopWin)

        # initialize the coordinates of left upper corner of the popwin and its size
        self.popwinx0 = self.popwiny0 = 0
        self.popwinwidth = self.popwinheight = 0

        self.AlMonitorLabel = gtk.Alignment(xalign=0, yalign=0.5)
        self.AlMonitorComboBox = gtk.Alignment(xalign=0, yalign=0.5)
        self.AlMenu = gtk.Alignment(xalign=1.0, yalign=0.5)
        self.AlVBox = gtk.Alignment(xalign=0, yalign=0, xscale=0, yscale=0)

        self.VBox = gtk.VBox()
        self.HBoxAllButtons = gtk.HBox()
        self.HBoxNagiosButtons = gtk.HBox()
        self.HBoxMenu = gtk.HBox()
        self.HBoxCombobox = gtk.HBox()

        # put a name tag where there buttons had been before
        # image for logo in statusbar
        # use pixbuf to keep transparency which itself should keep some padding if popup is oversized
        self.NagstamonLabel = gtk.Image()
        self.NagstamonLabel_Pixbuf = gtk.gdk.pixbuf_new_from_file(self.output.Resources + os.sep + "nagstamon_label.png")
        self.NagstamonLabel.set_from_pixbuf(self.NagstamonLabel_Pixbuf)
        self.NagstamonVersion = gtk.Label()
        self.NagstamonVersion.set_markup("<b>%s</b>  " % (self.output.version))

        self.HBoxNagiosButtons.add(self.NagstamonLabel)
        self.HBoxNagiosButtons.add(self.NagstamonVersion)

        self.AlMonitorLabel.add(self.HBoxNagiosButtons)
        self.ComboboxMonitor = gtk.combo_box_new_text()
        # fill Nagios server combobox with nagios servers
        self.ComboboxMonitor.append_text("Go to monitor...")
        submenu_items = list(self.output.servers)
        submenu_items.sort(key=str.lower)
        for i in submenu_items:
            self.ComboboxMonitor.append_text(i)

        # set first item active
        self.ComboboxMonitor.set_active(0)

        # add conmbobox to right-side menu
        self.AlMonitorComboBox.add(self.ComboboxMonitor)
        self.HBoxCombobox.add(self.AlMonitorComboBox)
        self.HBoxMenu.add(self.HBoxCombobox)

        # general buttons
        self.ButtonFilters = ButtonWithIcon(output=self.output, label="Filters", icon="settings.png")
        self.ButtonRecheckAll = ButtonWithIcon(output=self.output, label="Recheck all", icon="recheckall.png")
        self.ButtonRefresh = ButtonWithIcon(output=self.output, label="Refresh", icon="refresh.png")
        self.ButtonSettings = ButtonWithIcon(output=self.output, label="Settings", icon="settings.png")
        self.HBoxMenu.add(self.ButtonFilters)
        self.HBoxMenu.add(self.ButtonRecheckAll)
        self.HBoxMenu.add(self.ButtonRefresh)
        self.HBoxMenu.add(self.ButtonSettings)

        # nice separator
        self.HBoxMenu.add(gtk.VSeparator())
        self.ButtonMenu = ButtonWithIcon(output=self.output, label="", icon="menu.png")
        self.HBoxMenu.add(self.ButtonMenu)
        self.ButtonMenu.connect("button-press-event", self.MenuPopUp)
        self.ButtonClose = ButtonWithIcon(output=self.output, label="", icon="close.png")
        self.HBoxMenu.add(self.ButtonClose)
        # close popwin when its close button is pressed
        self.ButtonClose.connect("clicked", self.Close)
        self.ButtonClose.connect("leave-notify-event", self.LeavePopWin)
        # for whatever reason in Windows the Filters button grabs initial focus
        # so the close button should grab it for cosmetical reasons
        self.ButtonClose.grab_focus()

        # put the HBox full of buttons full of HBoxes into the aligned HBox...
        self.AlMenu.add(self.HBoxMenu)

        # HBoxes en masse...
        self.HBoxAllButtons.add(self.AlMonitorLabel)
        #self.HBoxAllButtons.add(self.AlMonitorComboBox)
        self.HBoxAllButtons.add(self.AlMenu)

        # threaded recheck all when refresh is clicked
        self.ButtonRecheckAll.connect("clicked", self.output.RecheckAll)
        # threaded refresh status information when refresh is clicked
        self.ButtonRefresh.connect("clicked", lambda r: Actions.RefreshAllServers(servers=self.output.servers, output=self.output, conf=self.conf))
        # open settings dialog when settings is clicked
        self.ButtonSettings.connect("clicked", lambda s: self.output.GetDialog(dialog="Settings", servers=self.output.servers, output=self.output, conf=self.conf, first_page="Servers"))

        # open settings dialog for filters when filters is clicked
        self.ButtonFilters.connect("clicked", lambda s: self.output.GetDialog(dialog="Settings", servers=self.output.servers, output=self.output, conf=self.conf, first_page="Filters"))

        # Workaround for behavorial differences of GTK in Windows and Linux
        # in Linux it is enough to check for the pointer leaving the whole popwin,
        # in Windows it is not, here every widget on popwin has to be heard
        # the intended effect is that popwin closes when the pointer leaves it
        self.ButtonRefresh.connect("leave-notify-event", self.LeavePopWin)
        self.ButtonSettings.connect("leave-notify-event", self.LeavePopWin)

        # define colors for detailed status table in dictionaries
        # need to be redefined here for MacOSX because there it is not
        # possible to reinitialize the whole GUI after config changes without a crash
        #self.output.TAB_BG_COLORS = { "UNKNOWN":str(self.conf.color_unknown_background), "INFORMATION": str(self.conf.color_information_background), "CRITICAL":str(self.conf.color_critical_background), "WARNING":str(self.conf.color_warning_background), "DOWN":str(self.conf.color_down_background), "UNREACHABLE":str(self.conf.color_unreachable_background)  }
        #self.output.TAB_FG_COLORS = { "UNKNOWN":str(self.conf.color_unknown_text), "INFORMATION": str(self.conf.color_information_text), "CRITICAL":str(self.conf.color_critical_text), "WARNING":str(self.conf.color_warning_text), "DOWN":str(self.conf.color_down_text), "UNREACHABLE":str(self.conf.color_unreachable_text) }
        self.TAB_BG_COLORS = { 
                          "UNKNOWN":str(self.conf.color_unknown_background), 
						  "INFORMATION": str(self.conf.color_information_background), 
						  "AVERAGE": str(self.conf.color_average_background), 
						  "HIGH": str(self.conf.color_high_background), 
						  "CRITICAL":str(self.conf.color_critical_background), 
						  "WARNING":str(self.conf.color_warning_background), 
						  "DOWN":str(self.conf.color_down_background), 
						  "UNREACHABLE":str(self.conf.color_unreachable_background)  }
        self.TAB_FG_COLORS = { 
                          "UNKNOWN":str(self.conf.color_unknown_text), 
						  "INFORMATION": str(self.conf.color_information_text), 
						  "AVERAGE": str(self.conf.color_average_text), 
						  "HIGH": str(self.conf.color_high_text), 
						  "CRITICAL":str(self.conf.color_critical_text), 
						  "WARNING":str(self.conf.color_warning_text), 
						  "DOWN":str(self.conf.color_down_text), 
						  "UNREACHABLE":str(self.conf.color_unreachable_text) }

        # create a scrollable area for the treeview in case it is larger than the screen
        # in case there are too many failed services and hosts
        self.ScrolledWindow = gtk.ScrolledWindow()
        self.ScrolledWindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)

        # try putting everything status-related into a scrolled viewport
        self.ScrolledVBox = gtk.VBox()
        #self.ScrolledWindow.add_with_viewport(self.ScrolledVBox)
        self.ScrolledViewport = gtk.Viewport()
        self.ScrolledViewport.add(self.ScrolledVBox)
        self.ScrolledWindow.add(self.ScrolledViewport)

        # menu in upper right corner for fullscreen mode
        self.Menu = gtk.Menu()
        for i in ["About", "Exit"]:
            if i == "-----":
                menu_item = gtk.SeparatorMenuItem()
                self.Menu.append(menu_item)
            else:
                menu_item = gtk.MenuItem(i)
                menu_item.connect("activate", self.MenuResponse, i)
                self.Menu.append(menu_item)
        self.Menu.show_all()

        # group server infos in VBoxes
        self.ServerVBoxes = dict()

        # to sort the Nagios servers alphabetically make a sortable list of their names
        server_list = list(self.output.servers)
        server_list.sort(key=str.lower)

        # create table with all the displayed info
        for server in server_list:
            # only if server is enabled
            if str(self.conf.servers[server].enabled) == "True":
                self.ServerVBoxes[server] = self.CreateServerVBox(server, self.output)
                # add box to the other ones
                self.ScrolledVBox.add(self.ServerVBoxes[server])

        # add all buttons in their hbox to the overall vbox
        self.VBox.add(self.HBoxAllButtons)

        # put scrolled window aka scrolled treeview into vbox
        self.VBox.add(self.ScrolledWindow)

        # put this vbox into popwin
        self.AlVBox.add(self.VBox)
        self.Window.add(self.AlVBox)

        # Initialize show_popwin - show it or not, if everything is OK
        # it is not necessary to pop it up
        self.showPopwin = False

        # measure against artefactional popwin
        self.pointer_left_popwin = False

        # flag for deciding if coordinates of statusbar need to be reinvestigated,
        # only necessary after popping up
        self.calculate_coordinates = True

        # add some buffer pixels to popwinheight to avoid silly scrollbars
        self.heightbuffer_internal = 10
        if platform.system() != "Windows" and self.Window.get_screen().get_n_monitors() > 1:
            self.heightbuffer_external = 30
        else:
            self.heightbuffer_external = 0

        # switch between fullscreen and popup mode
        self.SwitchMode()

        # helpers for Windows jumping popwin bug
        # https://github.com/HenriWahl/Nagstamon/issues/63
        self.mousex = 0
        self.mousey = 0


    def SwitchMode(self):
        """
            switch between fullscreen and popup window mode
        """

        try:
            if str(self.output.conf.fullscreen) == "False":
                # for not letting statusbar throw a shadow onto popwin in any composition-window-manager this helps to
                # keep a more consistent look - copied from StatusBar... anyway, doesn't work... well, next attempt:
                # Windows will have an entry on taskbar when not using HINT_UTILITY
                ###self.Window.set_visible(False)
                if platform.system() == "Windows":
                    self.Window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
                else:
                    self.Window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_MENU)
                # make a nice popup of the toplevel window
                self.Window.set_decorated(False)
                self.Window.set_keep_above(True)
                self.Window.unfullscreen()
                # newer Ubuntus place a resize widget onto floating statusbar - please don't!
                self.Window.set_resizable(False)
                self.Window.set_property("skip-taskbar-hint", True)
                self.Window.stick()
                self.Window.set_skip_taskbar_hint(True)

                # change Close/Menu button in popup-mode
                self.ButtonClose.set_no_show_all(True)
                self.ButtonClose.show()
            else:
                # find out dimension of all monitors
                if len(self.output.monitors) == 0:
                    for m in range(self.Window.get_screen().get_n_monitors()):
                        monx0, mony0, monw, monh = self.Window.get_screen().get_monitor_geometry(m)
                        self.output.monitors[m] = (monx0, mony0, monw, monh)
                self.Window.set_visible(False)
                self.Window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_NORMAL)
                self.Window.set_visible(True)
                x0, y0, width, height = self.output.monitors[int(self.output.conf.fullscreen_display)]
                self.Window.move(x0, y0)
                self.Window.set_decorated(True)
                self.Window.set_keep_above(False)
                self.Window.set_resizable(True)
                self.Window.set_property("skip-taskbar-hint", False)
                self.Window.set_skip_taskbar_hint(False)
                self.Window.unstick()
                self.Window.fullscreen()

                # change Close/Menu button in fullscreen-mode
                self.ButtonClose.set_no_show_all(True)
                self.ButtonClose.hide()

                self.Window.show_all()

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

        # dummy return
        return True


    def CreateServerVBox(self, server_name=None, output=None):
        """
        creates one VBox for one server
        """
        # get the servers alphabetically sorted
        server = self.output.servers[server_name]
        # put all infos into one VBox object
        servervbox = ServerVBox(output=self.output, server=server)
        #servervbox.Label.set_markup('<span weight="bold" size="large">%s@%s</span>' % (server.get_username(), server.get_name()))
        # initialize servervbox
        servervbox.initialize(server)
        # set no show all to be able to hide label and treeview if it is empty in case of no hassle
        servervbox.set_no_show_all(True)

        # connect buttons with actions
        # open Nagios main page in your favorite web browser when nagios button is clicked
        servervbox.ButtonMonitor.connect("clicked", server.OpenBrowser, "monitor", self.output)
        # open Nagios services in your favorite web browser when service button is clicked
        servervbox.ButtonServices.connect("clicked", server.OpenBrowser, "services", self.output)
        # open Nagios hosts in your favorite web browser when hosts button is clicked
        servervbox.ButtonHosts.connect("clicked", server.OpenBrowser, "hosts", self.output)
        # open Nagios history in your favorite web browser when hosts button is clicked
        servervbox.ButtonHistory.connect("clicked", server.OpenBrowser, "history", self.output)
        # OK button for monitor credentials refreshment or when "Enter" being pressed in password field
        servervbox.AuthButtonOK.connect("clicked", servervbox.AuthOK, server)
        # jump to password entry field if Return has been pressed on username entry field
        servervbox.AuthEntryUsername.connect("key-release-event", servervbox.AuthUsername)
        # for some reason signal "editing done" does not work so we need to check if Return has been pressed
        servervbox.AuthEntryPassword.connect("key-release-event", servervbox.AuthPassword, server)
        # windows workaround - see above
        # connect Server_EventBox with leave-notify-event to get popwin popping down when leaving it
        servervbox.Server_EventBox.connect("leave-notify-event", self.PopDown)
        # sorry folks, but this only works at the border of the treeviews
        servervbox.TreeView.connect("leave-notify-event", self.PopDown)
        # connect the treeviews of the servers to mouse clicks
        servervbox.TreeView.connect("button-press-event", servervbox.TreeviewPopupMenu, servervbox.TreeView, self.output.servers[server.get_name()])

        """
        # at the moment this feature does not work yet
        # Check_MK special feature: easily switch between private and overall view
        if server.type == "Check_MK Multisite":
            servervbox.HBoxCheckMK.set_no_show_all(False)
            servervbox.HBoxCheckMK.show_all()
            servervbox.CheckButtonCheckMKVisibility.set_active(bool(self.conf.only_my_issues))
            servervbox.CheckButtonCheckMKVisibility.connect("clicked", server.ToggleVisibility)
        else:
            servervbox.HBoxCheckMK.set_no_show_all(True)
            servervbox.HBoxCheckMK.hide_all()
        """

        return servervbox


    def PopUp(self, widget=None, event=None):
        """
            pop up popwin
        """
        # when popwin is showable and label is not "UP" popwin will be showed -
        # otherwise there is no sense in showing an empty popwin
        # for some reason the painting will lag behind popping up popwin if not getting resized twice -
        # seems like a strange workaround
        if self.showPopwin and not self.output.status_ok and self.output.conf.GetNumberOfEnabledMonitors() > 0:
            if len(self.output.GUILock) == 0 or self.output.GUILock.has_key("Popwin"):
                self.output.statusbar.Moving = False

                self.Window.show_all()
                self.Window.set_visible(True)

                # position and resize...
                self.calculate_coordinates = True
                self.Resize()

                # set combobox to default value
                self.ComboboxMonitor.set_active(0)
                # switch off Notification
                self.output.NotificationOff()
                # register as open window
                # use gobject.idle_add() to be thread safe
                gobject.idle_add(self.output.AddGUILock, str(self.__class__.__name__))

        # position and resize...
        self.calculate_coordinates = True
        self.Resize()


    def RefreshFullscreen(self, widget=None, event=None):
        """
        refresh fullscreen window
        """
        # get current monitor's settings
        screenx0, screeny0, screenwidth, screenheight = self.output.monitors[int(self.conf.fullscreen_display)]

        # limit size of scrolled vbox
        vboxwidth, vboxheight = self.ScrolledVBox.size_request()

        # VBox should be as wide as the screen
        # https://github.com/HenriWahl/Nagstamon/issues/100
        vboxwidth = screenwidth

        # get dimensions of top button bar
        self.buttonswidth, self.buttonsheight = self.HBoxAllButtons.size_request()

        # later GNOME might need some extra heightbuffer if using dual screen
        if vboxheight > screenheight - self.buttonsheight- self.heightbuffer_internal:
            # helpless attempt to get window fitting on screen if not maximized on newer unixoid DEs by doubling
            # external heightbuffer
            # leads to silly grey unused whitespace on GNOME3 dualmonitor, but there is still some information visisble..
            # let's call this a feature no bug
            vboxheight = screenheight - self.buttonsheight - self.heightbuffer_internal
        else:
            # avoid silly scrollbar
            vboxheight += self.heightbuffer_internal

        #self.ScrolledWindow.set_size_request(-1, vboxheight)
        self.ScrolledWindow.set_size_request(vboxwidth, vboxheight)
        # even if fullscreen this is necessary
        self.Window.set_size_request(self.buttonswidth, -1)
        self.Window.show_all()
        self.Window.set_visible(True)

        # return False to get removed as gobject idle source
        return False


    def LeavePopWin(self, widget=None, event=None):
        """
        when pointer leaves popwin the pointer_left_popwin flag has to be set to avoid
        popwin artefacts when hovering over statusbar
        """
        self.pointer_left_popwin = True
        self.PopDown(widget, event)
        # after a shortdelay set pointer_left_popwin back to false, in the meantime
        # there will be no extra flickering popwin coming from hovered statusbar
        gobject.timeout_add(250, self.SetPointerLeftPopwinFalse)


    def SetPointerLeftPopwinFalse(self):
        """
        function to be called by gobject.
        """
        self.pointer_left_popwin = False
        return False


    def PopDown(self, widget=None, event=None):
        """
            close popwin
            when it should closed it must be checked if the pointer is outside
            the popwin to prevent it closing when not necessary/desired
        """

        if str(self.output.conf.fullscreen) == "False":
            # catch Exception
            try:
                # access to rootwindow to get the pointers coordinates
                rootwin = self.output.statusbar.StatusBar.get_screen().get_root_window()
                # get position of the pointer
                mousex, mousey, foo = rootwin.get_pointer()
                # get position of popwin
                popwinx0, popwiny0 = self.Window.get_position()

                # actualize values for width and height
                self.popwinwidth, self.popwinheight = self.Window.get_size()

                # If pointer is outside popwin close it
                # to support Windows(TM)'s slow and event-loosing behaviour use some margin (10px) to be more tolerant to get popwin closed
                # y-axis dooes not get extra 10 px on top for sake of combobox and x-axis on right side not because of scrollbar -
                # so I wonder if it has any use left...
                if str(self.conf.close_details_hover) == "True":
                    if mousex <= popwinx0 + 10 or mousex >= (popwinx0 + self.popwinwidth) or mousey <= popwiny0 or mousey >= (popwiny0 + self.popwinheight) - 10 :
                        self.Close()

            except:
                import traceback
                traceback.print_exc(file=sys.stdout)


    def Close(self, widget=None):
        """
            hide popwin
        """
        if str(self.output.conf.fullscreen) == "False":
            # unregister popwin - seems to be called even if popwin is not open so check before unregistering
            if self.output.GUILock.has_key("Popwin"):
                # use gobject.idle_add() to be thread safe
                gobject.idle_add(self.output.DeleteGUILock, self.__class__.__name__)

            # reset mousex and mousey coordinates for Windows popwin workaround
            self.mousex, self.mousey = 0, 0

            self.Window.set_visible(False)
            # notification off because user had a look to hosts/services recently
            self.output.NotificationOff()

            # set all flagged-as-fresh-events to un-fresh
            self.output.UnfreshEventHistory()


    def Resize(self):
        """
            calculate popwin dimensions depending on the amount of information displayed in scrollbox
            only if popwin is visible
        """
        # the popwin should always pop up near the systray/desktop status bar, therefore we
        # need to find out its position
        # get dimensions of statusbar
        if str(self.conf.icon_in_systray) == "True":
            statusbarwidth, statusbarheight = 25, 25
        else:
            statusbarwidth, statusbarheight = self.output.statusbar.StatusBar.get_size()
            # to avoid jumping popwin when statusbar changes dimensions set width fixed
            statusbarwidth = 320

        if self.calculate_coordinates == True and str(self.conf.appindicator) == "False":
            # check if icon in systray or statusbar
            if str(self.conf.icon_in_systray) == "True":
                # trayicon seems not to have a .get_pointer() method so we use
                # its geometry information
                """
                if platform.system() == "Windows":
                    # otherwise this does not work in windows
                    #if self.mousex == self.mousey == 0:
                    #    rootwin = self.output.statusbar.StatusBar.get_screen().get_root_window()
                    #    self.mousex, self.mousey, foo = rootwin.get_pointer()
                    mousex, mousey = self.mousex, self.mousey
                    statusbar_mousex, statusbar_mousey = 0, int(self.conf.systray_popup_offset)
                else:
                    mousex, mousey, foo, bar = self.output.statusbar.SysTray.get_geometry()[1]
                    statusbar_mousex, statusbar_mousey = 0, int(self.conf.systray_popup_offset)
                """
                # regardless of the platform the fix for https://github.com/HenriWahl/Nagstamon/issues/63
                # to use self.mousex and self.mousey makes things easier
                mousex, mousey = self.mousex, self.mousey
                statusbar_mousex, statusbar_mousey = 0, int(self.conf.systray_popup_offset)

                # set monitor for later applying the correct monitor geometry
                self.output.current_monitor = self.output.statusbar.StatusBar.get_screen().get_monitor_at_point(mousex, mousey)
                statusbarx0 = mousex - statusbar_mousex
                statusbary0 = mousey - statusbar_mousey
            else:
                statusbarx0, statusbary0 = self.output.statusbar.StatusBar.get_position()
                # set monitor for later applying the correct monitor geometry
                self.output.current_monitor = self.output.statusbar.StatusBar.get_screen().get_monitor_at_point(\
                                              statusbarx0+statusbarwidth/2, statusbary0+statusbarheight/2)
                # save trayicon x0 and y0 in self.statusbar
                self.output.statusbar.StatusBar.x0 = statusbarx0
                self.output.statusbar.StatusBar.y0 = statusbary0

                # set back to False to do no recalculation of coordinates as long as popwin is opened
                self.calculate_coordinates = False
        else:
            if str(self.conf.appindicator) == "True":
                rootwin = self.output.appindicator.Menu_Nagstamon.get_screen().get_root_window()
                mousex, mousey, foo = rootwin.get_pointer()
                # set monitor for later applying the correct monitor geometry
                self.output.current_monitor = self.output.appindicator.Menu_Nagstamon.get_screen().get_monitor_at_point(mousex, mousey)
                # maybe more confusing but for not having rewrite too much code the statusbar*0 variables
                # are reused here
                self.popwinx0, dummy, screenwidth, dummy = self.output.monitors[self.output.current_monitor]
                # putting the "statusbar" into the farest right edge of the screen to get the popwin into that corner
                self.popwinx0 = screenwidth + self.popwinx0
            else:
                # use previously saved values for x0 and y0 in case popwin is still/already open
                statusbarx0 = self.output.statusbar.StatusBar.x0
                statusbary0 = self.output.statusbar.StatusBar.y0

        # get current monitor's settings
        # screeny0 might be important on more-than-one-monitor-setups where it will not be 0
        screenx0, screeny0, screenwidth, screenheight = self.output.monitors[self.output.current_monitor]

        # limit size of treeview
        treeviewwidth, treeviewheight = self.ScrolledVBox.size_request()

        if treeviewwidth > screenwidth: treeviewwidth = screenwidth

        # get dimensions of top button bar
        self.buttonswidth, self.buttonsheight = self.HBoxAllButtons.size_request()

        # later GNOME might need some extra heightbuffer if using dual screen
        if treeviewheight > screenheight - self.buttonsheight - statusbarheight - self.heightbuffer_external:
            treeviewheight = screenheight - self.buttonsheight - statusbarheight - self.heightbuffer_external
        else:
            # avoid silly scrollbar
            treeviewheight += self.heightbuffer_internal

        #### after having determined dimensions of scrolling area apply them
        ###self.ScrolledWindow.set_size_request(treeviewwidth, treeviewheight)

        # care about the height of the buttons
        self.popwinwidth, self.popwinheight = treeviewwidth, treeviewheight + self.buttonsheight

        # if popwinwidth is to small the buttons inside could be scrambled, so we give
        # it a minimum width from head buttons
        if self.popwinwidth < self.buttonswidth: self.popwinwidth = self.buttonswidth

        # if popwin is too wide cut it down to screen width - in case of AppIndicator use keep some space for ugly Ubuntu dock
        if str(self.conf.appindicator) == "True":
            if self.popwinwidth > screenwidth - 100:
                self.popwinwidth = screenwidth - 100
            # fixed x0 coordinate
            self.popwinx0 = screenwidth - self.popwinwidth + screenx0
            # make room for menu bar of Ubuntu
            if self.popwinheight >= screenheight - 25:
                treeviewheight += -25
                self.popwinheight = screenheight - 25
            # place popup unfer menu bar in Ubuntu
            self.popwiny0 = screeny0 + 25
        else:
            if self.popwinwidth > screenwidth:
                self.popwinwidth = screenwidth

            # if statusbar/trayicon stays in upper half of screen, popwin pops up BELOW statusbar/trayicon
            # take into account different y0 on multiple monitors, otherwise the popwin might be scretched somehow
            if (statusbary0 - self.output.monitors[self.output.current_monitor][1] + statusbarheight - screeny0) < (screenheight / 2):
                # if popwin is too large it gets cut at lower end of screen
                # take into account different y0 on multiple monitors, otherwise the popwin might be scretched somehow
                if (statusbary0 - self.output.monitors[self.output.current_monitor][1] +\
                    self.popwinheight + statusbarheight) > screenheight:
                    treeviewheight = screenheight - (statusbary0 + statusbarheight + self.buttonsheight) + screeny0
                    self.popwinheight = screenheight - statusbarheight - statusbary0 + screeny0
                    self.popwiny0 = statusbary0 + statusbarheight
                # else do not relate to screen dimensions but own widgets ones
                else:
                    self.popwinheight = treeviewheight + self.buttonsheight
                    self.popwiny0 = statusbary0 + statusbarheight

            # if it stays in lower half of screen, popwin pops up ABOVE statusbar/trayicon
            else:
                # if popwin is too large it gets cut at 0
                if (statusbary0 - self.popwinheight - self.heightbuffer_external) <= screeny0:
                    treeviewheight = statusbary0 - self.buttonsheight - statusbarheight - screeny0 - self.heightbuffer_internal
                    self.popwinheight = statusbary0 - screeny0 - self.heightbuffer_external
                    self.popwiny0 = screeny0 + self.heightbuffer_external
                # otherwise use own widgets for sizing
                else:
                    self.popwinheight = treeviewheight + self.buttonsheight
                    self.popwiny0 = statusbary0 - self.popwinheight

            # decide x position of popwin
            if (statusbarx0) + statusbarwidth / 2 + (self.popwinwidth) / 2 > (screenwidth + screenx0):
                self.popwinx0 = screenwidth - self.popwinwidth + screenx0
            elif (statusbarx0 + statusbarwidth / 2)- self.popwinwidth / 2 < screenx0:
                self.popwinx0 = screenx0
            else:
                self.popwinx0 = statusbarx0 + (screenx0 + statusbarwidth) / 2 - (self.popwinwidth + screenx0) / 2

        # after having determined dimensions of scrolling area apply them
        self.ScrolledWindow.set_size_request(treeviewwidth, treeviewheight)

        # set size request of popwin
        self.Window.set_size_request(self.popwinwidth, self.popwinheight)

        if self.Window.get_properties("visible")[0] == True:
            # avoid resizing artefacts when popwin keeps opened introduced in 0.9.10
            real_winwidth, real_winheight = self.Window.get_size()
            real_scrolledwinwidth, real_scrolledwinheight = self.ScrolledWindow.get_size_request()
            if real_scrolledwinheight + self.buttonsheight < real_winheight and not (self.popwinheight == treeviewheight + self.buttonsheight):
                self.Window.hide_all()
                self.Window.show_all()
            self.Window.window.move_resize(self.popwinx0, self.popwiny0, self.popwinwidth, self.popwinheight)

            # if popwin is misplaced please correct it here
            if self.Window.get_position() != (self.popwinx0, self.popwiny0):
                # would be nice if there could be any way to avoid flickering...
                # but move/resize only works after a hide_all()/show_all() mantra
                self.Window.hide_all()
                self.Window.show_all()
                self.Window.window.move_resize(self.popwinx0, self.popwiny0, self.popwinwidth, self.popwinheight)

        # statusbar pulls popwin to the top... with silly-windows-workaround(tm) included
        if str(self.conf.statusbar_floating) == "True": self.output.statusbar.Raise()

        return self.popwinx0, self.popwiny0, self.popwinwidth, self.popwinheight


    def setShowable(self, widget=None, event=None):
        """
        stub method to set popwin showable after button-release-event after moving statusbar
        """
        self.showPopwin = True


    def ComboboxClicked(self, widget=None):
        """
            open web interface of selected server
        """
        try:
            active = widget.get_active_iter()
            model = widget.get_model()
            self.output.servers[model.get_value(active, 0)].OpenBrowser(url_type="monitor", output=self.output)
        except:
            self.output.servers.values()[0].Error(sys.exc_info())


    def UpdateStatus(self, server):
        """
            Updates status field of a server
        """
        # status field in server vbox in popwin
        try:
            # kick out final "\n" for nicer appearance
            self.ServerVBoxes[server.get_name()].LabelStatus.set_markup('<span> Status: %s <span color="darkred">%s</span></span>' % (str(server.status), str(server.status_description).rsplit("\n", 1)[0]))
        except:
            server.Error(sys.exc_info())

        # return False to get removed as gobject idle source
        return False


    def IsWanted(self):
        """
        check if no other dialog/menu is shown which would not like to be
        covered by the popup window
        """
        if len(self.output.GUILock) == 0 or "Popwin" in self.output.GUILock:
            return True
        else:
            return False


    def MenuPopUp(self, widget=None, event=None):
        """
        popup menu for maximized overview window - instead of statusbar menu
        """
        self.Menu.popup(None, None, None, event.button, event.time)


    def MenuResponse(self, widget, menu_entry):
        """
            responses for the context menu for menu button in maximized popup status window
        """
        if menu_entry == "Save position": self.conf.SaveConfig(output=self.output)
        if menu_entry == "About": self.output.AboutDialog()
        if menu_entry == "Exit": self.output.Exit(True)


class ServerVBox(gtk.VBox):
    """
    VBox which contains all infos about one monitor server: Name, Buttons, Treeview
    """
    def __init__(self, **kwds):
            # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        # initalize VBox
        gtk.VBox.__init__(self)

        # elements of server info VBox
        self.Label = gtk.Label()
        self.Label.set_alignment(0,0)

        # once again a Windows(TM) workaround
        self.Server_EventBox = gtk.EventBox()

        # create icony buttons
        self.ButtonMonitor = ButtonWithIcon(output=self.output, label="Monitor", icon="nagios.png")
        self.ButtonHosts = ButtonWithIcon(output=self.output, label="Hosts", icon="hosts.png")
        self.ButtonServices = ButtonWithIcon(output=self.output, label="Services", icon="services.png")
        self.ButtonHistory = ButtonWithIcon(output=self.output, label="History", icon="history.png")

        """
        # not yet working
        # Check_MK stuff
        self.CheckButtonCheckMKVisibility = gtk.CheckButton("Only my issues")
        """

        # Label with status information
        self.LabelStatus = gtk.Label("")

        # order the elements
        # now vboxing the elements to add a line in case authentication failed - so the user should auth here again
        self.VBox = gtk.VBox()
        # first line for usual monitor shortlink buttons
        self.HBox = gtk.HBox()
        self.HBoxLeft = gtk.HBox()
        self.HBoxCheckMK = gtk.HBox()
        self.HBoxRight = gtk.HBox()
        self.HBoxLeft.add(self.Label)
        # leave some space around the label
        self.Label.set_padding(5, 5)
        self.HBoxLeft.add(self.ButtonMonitor)
        self.HBoxLeft.add(self.ButtonHosts)
        self.HBoxLeft.add(self.ButtonServices)
        self.HBoxLeft.add(self.ButtonHistory)

        """
        # see above
        # Check_MK stuff
        self.HBoxCheckMK.add(gtk.VSeparator())
        self.HBoxCheckMK.add(self.CheckButtonCheckMKVisibility)
        self.HBoxLeft.add(self.HBoxCheckMK)
        """

        # Status info
        self.HBoxLeft.add(gtk.VSeparator())
        self.HBoxLeft.add(self.LabelStatus)

        self.AlignmentLeft = gtk.Alignment(xalign=0, xscale=0.0, yalign=0)
        self.AlignmentLeft.add(self.HBoxLeft)
        self.AlignmentRight = gtk.Alignment(xalign=0, xscale=0.0, yalign=0.5)
        self.AlignmentRight.add(self.HBoxRight)

        self.HBox.add(self.AlignmentLeft)
        self.HBox.add(self.AlignmentRight)

        self.VBox.add(self.HBox)

        # Auth line
        self.HBoxAuth = gtk.HBox()
        self.AuthLabelUsername = gtk.Label(" Username: ")
        self.AuthEntryUsername = gtk.Entry()
        self.AuthEntryUsername.set_can_focus(True)
        self.AuthLabelPassword = gtk.Label(" Password: ")
        self.AuthEntryPassword = gtk.Entry()
        self.AuthEntryPassword.set_visibility(False)
        self.AuthCheckbuttonSave = gtk.CheckButton("Save password ")
        self.AuthButtonOK = gtk.Button("   OK   ")

        self.HBoxAuth.add(self.AuthLabelUsername)
        self.HBoxAuth.add(self.AuthEntryUsername)
        self.HBoxAuth.add(self.AuthLabelPassword)
        self.HBoxAuth.add(self.AuthEntryPassword)
        self.HBoxAuth.add(self.AuthCheckbuttonSave)
        self.HBoxAuth.add(self.AuthButtonOK)

        self.AlignmentAuth = gtk.Alignment(xalign=0, xscale=0.0, yalign=0)
        self.AlignmentAuth.add(self.HBoxAuth)

        self.VBox.add(self.AlignmentAuth)

        # start with hidden auth as default
        self.HBoxAuth.set_no_show_all(True)
        self.HBoxAuth.hide_all()

        self.Server_EventBox.add(self.VBox)
        self.add(self.Server_EventBox)

        # new TreeView handling, not generating new items with every refresh cycle
        self.server.TreeView = gtk.TreeView()
        # enable hover effect
        self.server.TreeView.set_hover_selection(True)

        """
        # tooltips or not
        if str(self.output.conf.show_tooltips) == "True":
            self.server.TreeView.set_has_tooltip(True)
            self.server.TreeView.set_tooltip_column(7)
        else:
            self.server.TreeView.set_has_tooltip(False)

        # enable grid lines
        if str(self.output.conf.show_grid) == "True":
            self.server.TreeView.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)
        else:
            self.server.TreeView.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_NONE)
        """

        # Liststore
        self.server.ListStore = gtk.ListStore(*self.output.LISTSTORE_COLUMNS)

        # offset to access host and service flag icons separately, stored in grand liststore
        # may grow with more supported flags
        offset_img = {0:0, 1:len(self.output.STATE_ICONS)}

        # offset for alternate column colors could increase readability
        # even and odd columns are calculated by column number
        offset_color = {0:9, 1:10}

        for s, column in enumerate(self.server.COLUMNS):
            tab_column = gtk.TreeViewColumn(column.get_label())
            self.server.TreeView.append_column(tab_column)
            # the first and second column hold hosts and service name which will get acknowledged/downtime flag
            # indicators added
            if s in [0, 1]:
                # pixbuf for little icon
                cell_img_fresh = gtk.CellRendererPixbuf()
                cell_img_ack = gtk.CellRendererPixbuf()
                cell_img_down = gtk.CellRendererPixbuf()
                cell_img_flap = gtk.CellRendererPixbuf()
                cell_img_pass = gtk.CellRendererPixbuf()
                # host/service name
                cell_txt = gtk.CellRendererText()
                # stuff all renderers into one cell
                tab_column.pack_start(cell_txt, False)
                tab_column.pack_start(cell_img_fresh, False)
                tab_column.pack_start(cell_img_ack, False)
                tab_column.pack_start(cell_img_down, False)
                tab_column.pack_start(cell_img_flap, False)
                tab_column.pack_start(cell_img_pass, False)
                # set text from liststore and flag icons if existing
                # why ever, in Windows(TM) the background looks better if applied separately
                # to be honest, even looks better in Linux
                tab_column.set_attributes(cell_txt, foreground=8, text=s)
                tab_column.add_attribute(cell_txt, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_fresh, pixbuf=11+offset_img[s])
                tab_column.add_attribute(cell_img_fresh, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_ack, pixbuf=12+offset_img[s])
                tab_column.add_attribute(cell_img_ack, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_down, pixbuf=13+offset_img[s])
                tab_column.add_attribute(cell_img_down, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_flap, pixbuf=14+offset_img[s])
                tab_column.add_attribute(cell_img_flap, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_pass, pixbuf=15+offset_img[s])
                tab_column.add_attribute(cell_img_pass, "cell-background", offset_color[s % 2])
                tab_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
            else:
                # normal way for all other columns
                cell_txt = gtk.CellRendererText()
                tab_column.pack_start(cell_txt, False)
                tab_column.set_attributes(cell_txt, foreground=8, text=s)
                tab_column.add_attribute(cell_txt, "cell-background", offset_color[s % 2 ])
                tab_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)

            # set customized sorting
            if column.has_customized_sorting():
                self.server.ListStore.set_sort_func(s, column.sort_function, s)

            # make table sortable by clicking on column headers
            tab_column.set_clickable(True)
            tab_column.connect('clicked', self.output.on_column_header_click, s, self.server.ListStore, self.server)

        # the whole TreeView memory leaky complex...
        self.TreeView = self.server.TreeView
        self.ListStore = self.server.ListStore

        self.add(self.TreeView)


    def initialize(self, server):
        """
        set settings, to be used by __init__ and after changed settings in Settings dialog
        """
        # user@server info label
        self.Label.set_markup('<span weight="bold" size="large">%s@%s</span>' % (server.get_username(), server.get_name()))
        # tooltips or not
        if str(self.output.conf.show_tooltips) == "True":
            self.server.TreeView.set_tooltip_column(7)
        else:
            self.server.TreeView.set_tooltip_column(-1)
        # enable grid lines
        if str(self.output.conf.show_grid) == "True":
            self.server.TreeView.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)
        else:
            self.server.TreeView.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_NONE)


    def TreeviewPopupMenu(self, widget, event, treeview, server):
        """
            context menu for treeview detailed status items
        """
        # catch exception in case of clicking outside treeview
        try:
            # get path to clicked cell
            path, obj, x, y = treeview.get_path_at_pos(int(event.x), int(event.y))
            # access content of rendered view model via normal python lists
            self.miserable_server = server
            self.miserable_host = treeview.get_model()[path[0]][server.HOST_COLUMN_ID]
            self.miserable_service = treeview.get_model()[path[0]][server.SERVICE_COLUMN_ID]
            self.miserable_status_info = treeview.get_model()[path[0]][server.STATUS_INFO_COLUMN_ID]
            # context menu for detailed status overview, opens with a mouse click onto a listed item
            self.popupmenu = gtk.Menu()

            # add custom actions
            actions_list=list(self.output.conf.actions)
            actions_list.sort(key=str.lower)
            for a in actions_list:
                # shortcut for next lines
                action = self.output.conf.actions[a]
                if str(action.enabled) == "True" and action.monitor_type in ["", self.server.TYPE] :
                    # menu item visibility flag
                    item_visible = False
                    # check if clicked line is a service or host
                    # if it is check if the action is targeted on hosts or services
                    if self.miserable_service:
                        if str(action.filter_target_service) == "True":
                            # only check if there is some to check
                            if str(action.re_host_enabled) == "True":
                                if Actions.IsFoundByRE(self.miserable_host,\
                                                       action.re_host_pattern,\
                                                       action.re_host_reverse):
                                    item_visible = True
                            # dito
                            if str(action.re_service_enabled) == "True":
                                if Actions.IsFoundByRE(self.miserable_service,\
                                                       action.re_service_pattern,\
                                                       action.re_service_reverse):
                                    item_visible = True
                            # dito
                            if str(action.re_status_information_enabled) == "True":
                                if Actions.IsFoundByRE(self.miserable_service,\
                                                       action.re_status_information_pattern,\
                                                       action.re_status_information_reverse):
                                    item_visible = True
                            # fallback if no regexp is selected
                            if str(action.re_host_enabled) == str(action.re_service_enabled) == str(action.re_status_information_enabled) == "False":
                                item_visible = True

                    else:
                        # hosts should only care about host specific actions, no services
                        if str(action.filter_target_host) == "True":
                            if str(action.re_host_enabled) == "True":
                                if Actions.IsFoundByRE(self.miserable_host,\
                                                       action.re_host_pattern,\
                                                       action.re_host_reverse):
                                    item_visible = True
                            else:
                                # a non specific action will be displayed per default
                                item_visible = True
                else:
                    item_visible = False

                # populate context menu with service actions
                if item_visible == True:
                    menu_item = gtk.MenuItem(a)
                    menu_item.connect("activate", self.TreeviewPopupMenuResponse, a)
                    self.popupmenu.append(menu_item)

                del action, item_visible

            # add "Edit actions..." menu entry
            menu_item = gtk.MenuItem("Edit actions...")
            menu_item.connect("activate", self.TreeviewPopupMenuResponse, "Edit actions...")
            self.popupmenu.append(menu_item)

            # add separator to separate between connections and actions
            self.popupmenu.append(gtk.SeparatorMenuItem())

            # after the separator add actions
            # available default menu actions are monitor server dependent
            for i in self.server.MENU_ACTIONS:
                # sometimes menu does not open due to "Recheck" so catch that exception
                try:
                    # recheck is not necessary for passive set checks
                    if i == "Recheck" and self.miserable_service\
                            and server.hosts[self.miserable_host].services[self.miserable_service].is_passive_only():
                            pass
                    else:
                        menu_item = gtk.MenuItem(i)
                        menu_item.connect("activate", self.TreeviewPopupMenuResponse, i)
                        self.popupmenu.append(menu_item)
                except:
                    menu_item = gtk.MenuItem(i)
                    menu_item.connect("activate", self.TreeviewPopupMenuResponse, i)
                    self.popupmenu.append(menu_item)

            self.popupmenu.show_all()
            self.popupmenu.popup(None, None, None, event.button, event.time)
            # silly Windows(TM) workaround to keep menu above popwin
            self.popupmenu.window.set_keep_above(True)

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)


    def TreeviewPopupMenuResponse(self, widget, remoteservice):
        """
            responses to the menu items
            commands get called by subprocess.Popen to beware nagstamon of hanging while
            waiting for the called command exit code
            the requested command and its arguments are given by a list
        """

        # closing popwin is innecessary in case of rechecking, otherwise it must be done
        # because the dialog/app window will stay under the popwin
        if remoteservice in ["Acknowledge", "Monitor", "Downtime", "Submit check result", "Edit actions..."]:
            self.output.popwin.Close()

        #debug
        if str(self.output.conf.debug_mode) == "True":
            self.miserable_server.Debug(server=self.miserable_server.get_name(),\
                                        host=self.miserable_host,\
                                        service=self.miserable_service,\
                                        debug="Clicked context menu: " + remoteservice)

        # choose appropriate service for menu entry
        # it seems to be more responsive especially while rechecking if every service
        # looks for its own for the miserable host's ip if it is needed
        try:
            # custom actions
            if remoteservice in self.output.conf.actions:
                # let the thread do the work
                action = Actions.Action(action=self.output.conf.actions[remoteservice],\
                                        conf=self.output.conf,\
                                        server=self.miserable_server,\
                                        host=self.miserable_host,\
                                        service=self.miserable_service,\
                                        status_info=self.miserable_status_info)

                # if action wants a closed powin it should be closed
                if str(self.output.conf.actions[remoteservice].close_popwin) == "True":
                    self.output.popwin.Close()

                # Action!
                action.start()

            elif remoteservice == "Edit actions...":
                # open actions settings
                self.output.GetDialog(dialog="Settings", servers=self.output.servers, output=self.output, conf=self.output.conf, first_page="Actions")
            elif remoteservice == "Monitor":
                # let Actions.TreeViewNagios do the work to open a webbrowser with nagios informations
                Actions.TreeViewNagios(self.miserable_server, self.miserable_host, self.miserable_service)
            elif remoteservice == "Recheck":
                # start new rechecking thread
                recheck = Actions.Recheck(server=self.miserable_server, host=self.miserable_host, service=self.miserable_service)
                recheck.start()
            elif remoteservice == "Acknowledge":
                self.output.AcknowledgeDialogShow(server=self.miserable_server, host=self.miserable_host, service=self.miserable_service)
            elif remoteservice == "Submit check result":
                self.output.SubmitCheckResultDialogShow(server=self.miserable_server, host=self.miserable_host, service=self.miserable_service)
            elif remoteservice == "Downtime":
                self.output.DowntimeDialogShow(server=self.miserable_server, host=self.miserable_host, service=self.miserable_service)
            # close popwin
            self.output.popwin.PopDown()

        except Exception, err:
            self.output.Dialog(message=err)


    def AuthOK(self, widget, server):
        """
        use given auth informations
        """
        server.username, server.password = self.AuthEntryUsername.get_text(), self.AuthEntryPassword.get_text()
        server.refresh_authentication = False

        if self.AuthCheckbuttonSave.get_active() == True:
            # store authentication information in config
            server.conf.servers[server.get_name()].username = server.username
            server.conf.servers[server.get_name()].password = server.password
            server.conf.servers[server.get_name()].save_password = True
            server.conf.SaveConfig(server=server)

        self.HBoxAuth.hide_all()
        self.HBoxAuth.set_no_show_all(True)

        # refresh server label
        self.Label.set_markup('<span weight="bold" size="large">%s@%s</span>' % (server.get_username(), server.get_name()))

        server.status = "Trying to reauthenticate..."
        server.status_description = ""
        self.output.popwin.UpdateStatus(server)
        self.output.popwin.Resize()


    def AuthUsername(self, widget, event):
        """
        if Return key has been pressed in password entry field interprete this as OK button being pressed
        """
        if gtk.gdk.keyval_name(event.keyval) in ["Return", "KP_Enter"]:
            self.AuthEntryPassword.grab_focus()


    def AuthPassword(self, widget, event, server):
        """
        if Return key has been pressed in password entry field interprete this as OK button being pressed
        """
        if gtk.gdk.keyval_name(event.keyval) in ["Return", "KP_Enter"]:
            self.AuthOK(widget, server)


class AppIndicator(object):
    """
        Ubuntu AppIndicator management class
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        self.Indicator = appindicator.Indicator("Nagstamon", self.output.Resources + os.sep + "nagstamon_appindicator" +\
                                                self.output.BitmapSuffix, appindicator.CATEGORY_APPLICATION_STATUS)
        # define all items on AppIndicator menu, which might be switched on and off depending of their relevance
        self.Menu = gtk.Menu()
        # Nagstamon Submenu
        self.Menu_Nagstamon = gtk.MenuItem("Nagstamon")
        self.Menu_Nagstamon.set_submenu(self.output.statusbar.Menu)
        self.Menu_Separator = gtk.SeparatorMenuItem()
        # Status menu items
        self.Menu_DOWN = gtk.MenuItem("")
        self.Menu_DOWN.connect("activate", self.output.popwin.PopUp)
        self.Menu_UNREACHABLE = gtk.MenuItem("")
        self.Menu_UNREACHABLE.connect("activate", self.output.popwin.PopUp)
        self.Menu_CRITICAL = gtk.MenuItem("")
        self.Menu_CRITICAL.connect("activate", self.output.popwin.PopUp)
        self.Menu_UNKNOWN = gtk.MenuItem("")
        self.Menu_UNKNOWN.connect("activate", self.output.popwin.PopUp)
        self.Menu_INFORMATION = gtk.MenuItem("")
        self.Menu_INFORMATION.connect("activate", self.output.popwin.PopUp)
        self.Menu_AVERAGE = gtk.MenuItem("")
        self.Menu_AVERAGE.connect("activate", self.output.popwin.PopUp)
        self.Menu_HIGH = gtk.MenuItem("")
        self.Menu_HIGH.connect("activate", self.output.popwin.PopUp)
        self.Menu_WARNING = gtk.MenuItem("")
        self.Menu_WARNING.connect("activate", self.output.popwin.PopUp)
        # show detail popup, same effect as clicking one f the above
        self.Menu_ShowDetails = gtk.MenuItem("Show details...")
        self.Menu_ShowDetails.connect("activate", self.output.popwin.PopUp)
        self.Menu_OK = gtk.MenuItem("OK")
        self.Menu_OK.connect("activate", self.OK)

        self.Menu.append(self.Menu_Nagstamon)
        self.Menu.append(self.Menu_Separator)
        self.Menu.append(self.Menu_DOWN)
        self.Menu.append(self.Menu_UNREACHABLE)
        self.Menu.append(self.Menu_CRITICAL)
        self.Menu.append(self.Menu_UNKNOWN)
        self.Menu.append(self.Menu_INFORMATION)		
        self.Menu.append(self.Menu_AVERAGE)		
        self.Menu.append(self.Menu_HIGH)		
        self.Menu.append(self.Menu_WARNING)
        self.Menu.append(self.Menu_ShowDetails)
        self.Menu.append(self.Menu_OK)

        self.Menu_Nagstamon.show()
        self.Menu_Separator.show()
        self.Menu_ShowDetails.show()
        self.Menu.show()
        self.Indicator.set_menu(self.Menu)

        # display AppIndicator only if configured
        if str(self.conf.appindicator) == "True":
            self.Indicator.set_status(appindicator.STATUS_ACTIVE)
        else:
            self.Indicator.set_status(appindicator.STATUS_PASSIVE)

        # flash flag evaluated in notification thread
        self.Flashing = False


    def Flash(self):
        """
            Flash in case of reason to do so
        """
        if self.Indicator.get_status() == appindicator.STATUS_ATTENTION:
            self.Indicator.set_status(appindicator.STATUS_ACTIVE)
        else:
            self.Indicator.set_status(appindicator.STATUS_ATTENTION)

        # return False to get removed as gobject idle source
        return False


    def OK(self, dummy=None):
        """
            action for OK menu entry, to be triggered if notification is acknowledged
        """
        self.Menu_OK.hide()
        self.output.NotificationOff()
        self.Indicator.set_status(appindicator.STATUS_ATTENTION)
        self.output.popwin.Close()


class Settings(object):
    """
        settings dialog as object, may lead to less mess
    """

    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # if not given default tab is empty
        if not "first_page" in kwds: self.first_page = "Servers"

        # set the gtkbuilder files
        self.builderfile = self.output.Resources + os.sep + "settings_dialog.ui"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builderfile)
        self.dialog = self.builder.get_object("settings_dialog")

        # little feedback store for servers and actions treeviews
        self.selected_server = None
        self.selected_action = None

        # use connect_signals to assign methods to handlers
        handlers_dict = { "button_ok_clicked": self.OK,
                          "settings_dialog_close": self.Cancel,
                          "button_cancel_clicked": self.Cancel,
                          "button_new_server": lambda n: self.output.GetDialog(dialog="NewServer", servers=self.servers, output=self.output, settingsdialog=self, conf=self.conf),
                          "button_edit_server": lambda e: self.output.GetDialog(dialog="EditServer", servers=self.servers, output=self.output, selected_server=self.selected_server, settingsdialog=self, conf=self.conf),
                          "button_copy_server": lambda e: self.output.GetDialog(dialog="CopyServer", servers=self.servers, output=self.output, selected_server=self.selected_server, settingsdialog=self, conf=self.conf),
                          "button_delete_server": lambda d: self.DeleteServer(self.selected_server, self.conf.servers),
                          "button_check_for_new_version_now": self.CheckForNewVersionNow,
                          "checkbutton_enable_notification": self.ToggleNotification,
                          "checkbutton_enable_sound": self.ToggleSoundOptions,
                          "togglebutton_use_custom_sounds": self.ToggleCustomSoundOptions,
                          "checkbutton_re_host_enabled": self.ToggleREHostOptions,
                          "checkbutton_re_service_enabled": self.ToggleREServiceOptions,
                          "checkbutton_re_status_information_enabled": self.ToggleREStatusInformationOptions,
                          "checkbutton_re_criticality_enabled": self.ToggleRECriticalityOptions,
                          "button_play_sound": self.PlaySound,
                          "checkbutton_debug_mode": self.ToggleDebugOptions,
                          "checkbutton_debug_to_file": self.ToggleDebugOptions,
                          "button_colors_default": self.ColorsDefault,
                          "button_colors_reset": self.ColorsReset,
                          "color-set": self.ColorsPreview,
                          "radiobutton_icon_in_systray_toggled": self.ToggleSystrayPopupOffset,
                          "radiobutton_fullscreen_toggled": self.ToggleFullscreenDisplay,
                          "notification_actions": self.ToggleNotificationActions,
                          "notification_custom_action": self.ToggleNotificationCustomAction,
                          "notification_action_warning": self.ToggleNotificationActionWarning,
                          "notification_action_critical": self.ToggleNotificationActionCritical,
                          "notification_action_down": self.ToggleNotificationActionDown,
                          "notification_action_ok": self.ToggleNotificationActionOk,
                          "button_help_notification_actions_clicked": self.ToggleNotificationActionsHelp,
                          "button_help_notification_custom_actions_clicked": self.ToggleNotificationCustomActionsHelp,
                          "button_new_action": lambda a: self.output.GetDialog(dialog="NewAction", output=self.output, settingsdialog=self, conf=self.conf),
                          "button_edit_action": lambda e: self.output.GetDialog(dialog="EditAction", output=self.output, selected_action=self.selected_action, settingsdialog=self, conf=self.conf),
                          "button_copy_action": lambda e: self.output.GetDialog(dialog="CopyAction", output=self.output, selected_action=self.selected_action, settingsdialog=self, conf=self.conf),
                          "button_delete_action": lambda d: self.DeleteAction(self.selected_action, self.conf.actions),
                          }
        self.builder.connect_signals(handlers_dict)

        # keystore option has to be set/unset before it gets overwritten by the following loops
        self.conf.keyring_available = self.conf.KeyringAvailable()
        self.ToggleSystemKeyring()

        keys = self.conf.__dict__.keys()
        # walk through all relevant input types to fill dialog with existing settings
        for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_", "input_spinbutton_", "input_filechooser_"]:
            for key in keys:
                j = self.builder.get_object(i + key)
                if not j:
                    continue
                # some hazard, every widget has other methods to fill it with desired content
                # so we try them all, one of them should work

                # help gtk.filechooser on windows
                if str(self.conf.__dict__[key]) == "None":
                    self.conf.__dict__[key] = None
                try:
                    # filechooser
                    j.set_filename(self.conf.__dict__[key])
                except:
                    pass
                try:
                    j.set_text(self.conf.__dict__[key])
                except:
                    pass
                try:
                    if str(self.conf.__dict__[key]) == "True":
                        j.set_active(True)
                    if str(self.conf.__dict__[key]) == "False":
                        j.set_active(False)
                except:
                    pass
                try:
                    j.set_value(int(self.conf.__dict__[key]))
                except:
                    pass

        # hide open popwin in try/except clause because at first start there
        # cannot be a popwin object
        try:
            self.output.popwin.Close()
        except:
            pass

        # set title of settings dialog containing version number
        self.dialog.set_title(self.output.name + " " + self.output.version + " settings")

        # workaround for gazpacho-made glade-file - dunno why tab labels do not get named as they should be
        self.notebook = self.builder.get_object("notebook")
        notebook_tabs =  ["Servers", "Display", "Filters", "Actions", "Notifications", "Colors", "Defaults"]
        # now this presumably not necessary anymore workaround even gets extended as
        # determine-first-page-mechanism used for acknowledment dialog settings button
        page = 0
        for c in self.notebook.get_children():
            if notebook_tabs[0] == self.first_page: self.notebook.set_current_page(page)
            self.notebook.set_tab_label_text(c, notebook_tabs.pop(0))
            page += 1

        # fill treeviews
        self.FillTreeView("servers_treeview", self.conf.servers, "Servers", "selected_server")
        self.FillTreeView("actions_treeview", self.conf.actions, "Actions", "selected_action")

        # set filters fore sound filechoosers
        filters = dict()
        # WAV files work on every platform
        filters["wav"] = gtk.FileFilter()
        filters["wav"].set_name("WAV files")
        filters["wav"].add_pattern("*.wav")
        filters["wav"].add_pattern("*.WAV")

        # OGG files are only usable on unixoid OSes:
        if not platform.system() == "Windows":
            filters["ogg"] = gtk.FileFilter()
            filters["ogg"].set_name("OGG files")
            filters["ogg"].add_pattern("*.ogg")
            filters["ogg"].add_pattern("*.OGG")

        for f in ["warning", "critical", "down"]:
            filechooser = self.builder.get_object("input_filechooser_notification_custom_sound_" + f)
            for f in filters: filechooser.add_filter(filters[f])
            # for some reason does not show wanted effect
            filechooser.set_filter(filters["wav"])

        # commit e1946ea33fefac6271d44eb44c05dd2c3ff5bfe9 from pull request by foscarini@github
        # offering sort order for status popup
        # default sort column field
        self.combo_default_sort_field = self.builder.get_object("input_combo_default_sort_field")
        combomodel_default_sort_field = gtk.ListStore(gobject.TYPE_STRING)
        crsf = gtk.CellRendererText()
        self.combo_default_sort_field.pack_start(crsf, True)
        self.combo_default_sort_field.set_attributes(crsf, text=0)
        for i in range(6):
            combomodel_default_sort_field.append((self.output.IDS_COLUMNS_MAP[i],))
        self.combo_default_sort_field.set_model(combomodel_default_sort_field)
        self.combo_default_sort_field.set_active(self.output.COLUMNS_IDS_MAP[self.conf.default_sort_field])

        # default column sort order combobox
        self.combo_default_sort_order = self.builder.get_object("input_combo_default_sort_order")
        combomodel_default_sort_order = gtk.ListStore(gobject.TYPE_STRING)
        crso = gtk.CellRendererText()
        self.combo_default_sort_order.pack_start(crso, True)
        self.combo_default_sort_order.set_attributes(crso, text=0)
        combomodel_default_sort_order.append(("Ascending" ,))
        combomodel_default_sort_order.append(("Descending",))
        self.combo_default_sort_order.set_model(combomodel_default_sort_order)
        self.combo_default_sort_order.set_active({"Ascending": 0, "Descending": 1}[self.conf.default_sort_order])

        # fill fullscreen display combobox
        self.combo_fullscreen_display = self.builder.get_object("input_combo_fullscreen_display")
        combomodel_fullscreen_display = gtk.ListStore(gobject.TYPE_STRING)
        crfsd = gtk.CellRendererText()
        self.combo_fullscreen_display.pack_start(crfsd, True)
        self.combo_fullscreen_display.set_attributes(crfsd, text=0)
        for i in self.output.monitors:
            combomodel_fullscreen_display.append((str(i)))
        self.combo_fullscreen_display.set_model(combomodel_fullscreen_display)
        self.combo_fullscreen_display.set_active(int(self.conf.fullscreen_display))

        # in case nagstamon runs the first time it should display a new server dialog
        if str(self.conf.unconfigured) == "True":
            self.output.statusbar.StatusBar.hide()
            self.output.GetDialog(dialog="NewServer", servers=self.servers, output=self.output, settingsdialog=self, conf=self.conf)
            # save settings
            self.conf.SaveConfig(output=self.output)

        # prepare colors and preview them
        self.ColorsReset()

        # disable non useful gui settings
        if platform.system() == "Darwin":
            # MacOS doesn't need any option because there is only floating statusbar possible
            self.builder.get_object("input_radiobutton_icon_in_systray").hide()
            self.builder.get_object("hbox_systray_popup_offset").hide()
            self.builder.get_object("input_radiobutton_statusbar_floating").hide()
            self.builder.get_object("label_appearance").hide()
            self.builder.get_object("input_radiobutton_fullscreen").hide()
            self.builder.get_object("input_combo_fullscreen_display").hide()
            self.builder.get_object("label_fullscreen_display").hide()
            self.builder.get_object("input_checkbutton_notification_desktop").hide()
            self.builder.get_object("input_radiobutton_appindicator").hide()

        # as of now there is no notification in Windows so disable it
        if platform.system() == "Windows":
            self.builder.get_object("input_checkbutton_notification_desktop").hide()
            self.builder.get_object("input_radiobutton_appindicator").hide()

        # libnotify-based desktop notification probably only available on Linux
        if not sys.modules.has_key("pynotify"):
            self.builder.get_object("input_checkbutton_notification_desktop").hide()
        # appindicator option is not needed on non-Ubuntuesque systems
        if not sys.modules.has_key("appindicator"):
            self.builder.get_object("input_radiobutton_appindicator").hide()

        # this should not be necessary, but for some reason the number of hours is 10 in unitialized state... :-(
        spinbutton = self.builder.get_object("input_spinbutton_defaults_downtime_duration_hours")
        spinbutton.set_value(int(self.conf.defaults_downtime_duration_hours))
        spinbutton = self.builder.get_object("input_spinbutton_defaults_downtime_duration_minutes")
        spinbutton.set_value(int(self.conf.defaults_downtime_duration_minutes))

        # store fullscreen state to avoif innecessary popwin flickering
        self.saved_fullscreen_state = str(self.conf.fullscreen)

        # initialize state of some GUI elements
        self.initialize()


    def show(self):
        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        # delete global open Windows entry
        gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
        self.dialog.hide()


    def initialize(self):
        """
        initialize some stuff at every call of this dialog
        """
        # set first page of notebook tabs - meanwhile for some historic reason
        self.notebook.set_current_page(["Servers", "Display", "Filters", "Actions",\
                                        "Notification", "Colors", "Defaults"].index(self.first_page))

        # store fullscreen state to avoid innecessary popwin flickering
        self.saved_fullscreen_state = str(self.conf.fullscreen)

        # toggle regexp options
        self.ToggleREHostOptions()
        self.ToggleREServiceOptions()
        self.ToggleREStatusInformationOptions()

        # care about Centreon criticality filter
        self.ToggleRECriticalityFilter()
        self.ToggleRECriticalityOptions()

        # toggle debug options
        self.ToggleDebugOptions()

        # toggle sounds options
        self.ToggleSoundOptions()
        self.ToggleCustomSoundOptions()

        # toggle icon in systray popup offset
        self.ToggleSystrayPopupOffset()

        # toggle fullscreen display selection combobox
        self.ToggleFullscreenDisplay()

        # toggle notification action options
        self.ToggleNotificationActions()
        self.ToggleNotificationActionWarning()
        self.ToggleNotificationActionCritical()
        self.ToggleNotificationActionDown()
        self.ToggleNotificationActionOk()
        self.ToggleSystemKeyring()


    def FillTreeView(self, treeview_widget, items, column_string, selected_item):
        """
        fill treeview containing items - has been for servers only before
        treeview_widget - string from gtk builder
        items - dictionary containing the to-be-listed items
        column_string - certain column name
        selected_item - property which stores the selected item
        """

        # create a model for treeview where the table headers all are strings
        liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)

        # to sort the monitor servers alphabetically make a sortable list of their names
        item_list = list(items)
        item_list.sort(key=str.lower)

        for item in item_list:
            iter = liststore.insert_before(None, None)
            liststore.set_value(iter, 0, item)
            if str(items[item].enabled) == "True":
                liststore.set_value(iter, 1, "black")
                liststore.set_value(iter, 2, False)
            else:
                liststore.set_value(iter, 1, "darkgrey")
                liststore.set_value(iter, 2, True)
        # give model to the view
        self.builder.get_object(treeview_widget).set_model(liststore)

        # render aka create table view
        renderer_text = gtk.CellRendererText()
        tab_column = gtk.TreeViewColumn(column_string, renderer_text, text=0, foreground=1, strikethrough=2)
        # somehow idiotic, but less effort... try to delete which column ever, to create a new one
        # this will throw an exception at the first time the options dialog is opened because no column exists
        try:
            self.builder.get_object(treeview_widget).remove_column(self.builder.get_object(treeview_widget).get_column(0))
        except:
            pass
        self.builder.get_object(treeview_widget).append_column(tab_column)

        # in case there are no items yet because it runs the first time do a try-except
        try:
            # selected server to edit or delete, defaults to first one of server list
            self.__dict__[selected_item] = item_list[0]
            # select first entry
            self.builder.get_object(treeview_widget).set_cursor_on_cell((0,))
        except:
            pass
        # connect treeview with mouseclicks
        self.builder.get_object(treeview_widget).connect("button-press-event", self.SelectedTreeviewItem, treeview_widget, selected_item)


    def SelectedTreeviewItem(self, widget, event, treeview_widget, selected_item):
        """
            findout selected item in treeview, should NOT return anything because the treeview
            will be displayed buggy if it does
        """
        try:
            # get path to clicked cell
            path, obj, x, y = self.builder.get_object(treeview_widget).get_path_at_pos(int(event.x), int(event.y))
            # access content of rendered view model via normal python lists and put
            # it into Settings dictionary
            self.__dict__[selected_item] = self.builder.get_object(treeview_widget).get_model()[path[0]][0]
        except:
            pass


    def OK(self, widget):
        """
            when dialog gets closed the content of its widgets gets put into the appropriate
            values of the config object
            after this the config file gets saved.
        """
        keys = self.conf.__dict__.keys()
        for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_", "input_spinbutton_", "input_filechooser_"]:
            for key in keys:
                j = self.builder.get_object(i + key)
                if not j:
                    continue
                # some hazard, every widget has other methods to get its content
                # so we try them all, one of them should work
                try:
                    self.conf.__dict__[key] = j.get_text()
                except:
                    try:
                        self.conf.__dict__[key] = j.get_active()
                    except:
                        try:
                            self.conf.__dict__[key] = int(j.get_value())
                        except:
                            try:
                                # filechooser
                                self.conf.__dict__[key] = j.get_filename()
                            except:
                                pass

        # evaluate and apply colors
        for state in ["ok", "warning", "critical", "unknown", "unreachable", "down", "error"]:
            self.conf.__dict__["color_" + state + "_text"] = self.builder.get_object("input_colorbutton_" + state + "_text").get_color().to_string()
            self.conf.__dict__["color_" + state + "_background"] = self.builder.get_object("input_colorbutton_" + state + "_background").get_color().to_string()
            # add new color information to color dictionaries for cells to render
            self.output.TAB_FG_COLORS[state.upper()] = self.builder.get_object("input_colorbutton_" + state + "_text").get_color().to_string()
            self.output.TAB_BG_COLORS[state.upper()] = self.builder.get_object("input_colorbutton_" + state + "_background").get_color().to_string()

        # evaluate comboboxes
        self.conf.default_sort_field = self.combo_default_sort_field.get_active_text()
        self.conf.default_sort_order = self.combo_default_sort_order.get_active_text()
        self.conf.fullscreen_display = self.combo_fullscreen_display.get_active_text()

        # close popwin
        # catch Exception at first run when there cannot exist a popwin
        try:
            # only useful if not on first run
            if self.output.firstrun == False and self.conf.unconfigured == False:
                self.output.popwin.PopDown()
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

        if int(self.conf.update_interval_seconds) <= 0:
            self.conf.update_interval_seconds = 60

        # save settings
        self.conf.SaveConfig(output=self.output)

        # catch exceptions in case of misconfiguration
        try:
            # now it is not the first run anymore
            self.output.firstrun = False
            self.conf.unconfigured = False

            gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
            self.dialog.hide()

            if str(self.conf.statusbar_floating) == "True":
                self.output.statusbar.StatusBar.show_all()
                self.output.statusbar.CalculateFontSize()
            else:
                self.output.statusbar.StatusBar.hide_all()

            if str(self.conf.icon_in_systray) == "True":
                self.output.statusbar.SysTray.set_visible(True)
            else:
                self.output.statusbar.SysTray.set_visible(False)

            # only if appindicator module exists
            if sys.modules.has_key("appindicator"):
                if str(self.conf.appindicator) == "True":
                    self.output.appindicator.OK()
                else:
                    self.output.appindicator.Indicator.set_status(appindicator.STATUS_PASSIVE)

            # in Windows the statusbar with gtk.gdk.WINDOW_TYPE_HINT_UTILITY places itself somewhere
            # this way it should be disciplined
            self.output.statusbar.StatusBar.move(int(self.conf.position_x), int(self.conf.position_y))

            # popwin treatment
            # only change popwin if fullscreen mode is changed
            if self.saved_fullscreen_state != str(self.conf.fullscreen):
                self.output.popwin.SwitchMode()

            # apply settings for modified servers
            self.output.ApplyServerModifications()

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            self.servers.values()[0].Error(sys.exc_info())


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        # when getting cancelled at first run exit immediately because
        # without settings there is not much nagstamon can do
        if self.output.firstrun == True:
            sys.exit()
        else:
            gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
            self.dialog.hide()


    def ColorsPreview(self, widget=None):
        """
        preview for status information colors
        """
        for state in ["ok", "warning", "critical", "unknown", "unreachable", "down", "error"]:
            text = self.builder.get_object("input_colorbutton_" + state + "_text").get_color().to_string()
            background = self.builder.get_object("input_colorbutton_" + state + "_background").get_color().to_string()
            label = self.builder.get_object("label_color_" + state)
            label.set_markup('<span foreground="%s" background="%s"> %s: </span>' %\
                             (text, background, state.upper()))


    def ColorsDefault(self, widget=None):
        """
        reset default colors
        """
        # text and background colors of all states get set to defaults
        for state in ["ok", "warning", "critical", "unknown", "unreachable", "down", "error"]:
            self.builder.get_object("input_colorbutton_" + state + "_text").set_color(gtk.gdk.color_parse(self.conf.__dict__["default_color_" + state + "_text"]))
            self.builder.get_object("input_colorbutton_" + state + "_background").set_color(gtk.gdk.color_parse(self.conf.__dict__["default_color_" + state + "_background"]))

        # renew preview
        self.ColorsPreview()


    def ColorsReset(self, widget=None):
        """
        reset to previous colors
        """
        # text and background colors of all states get set to defaults
        for state in ["ok", "warning", "critical", "unknown", "unreachable", "down", "error"]:
            self.builder.get_object("input_colorbutton_" + state + "_text").set_color(gtk.gdk.color_parse(self.conf.__dict__["color_" + state + "_text"]))
            self.builder.get_object("input_colorbutton_" + state + "_background").set_color(gtk.gdk.color_parse(self.conf.__dict__["color_" + state + "_background"]))

        # renew preview
        self.ColorsPreview()


    def DeleteServer(self, server=None, servers=None):
        """
            delete Server after prompting
        """
        if server:
            dialog = gtk.MessageDialog(parent=self.dialog, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK + gtk.BUTTONS_CANCEL, message_format='Really delete server "' + server + '"?')
            # gtk.Dialog.run() does a mini loop to wait
            # for some reason response is YES, not OK... but it works.
            if dialog.run() == gtk.RESPONSE_YES:
                # delete server configuration entry
                self.conf.servers.pop(server)
                # stop thread
                try:
                    if self.servers[server].thread:
                        self.servers[server].thread.Stop()
                except:
                    # most probably server has been disabled and that's why there is no thread running
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        self.servers[server].Error(sys.exc_info())
                # delete server from servers dictionary
                self.servers.pop(server)
                # fill settings dialog treeview
                self.FillTreeView("servers_treeview", servers, "Servers", "selected_server")

                # renew appearances of servers
                self.output.ApplyServerModifications()

            dialog.destroy()


    def DeleteAction(self, action=None, actions=None):
        """
            delete action after prompting
        """
        if action:
            dialog = gtk.MessageDialog(parent=self.dialog, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK + gtk.BUTTONS_CANCEL, message_format='Really delete action "' + action + '"?')
            # gtk.Dialog.run() does a mini loop to wait
            # for some reason response is YES, not OK... but it works.
            if dialog.run() == gtk.RESPONSE_YES:
                # delete actions configuration entry
                self.conf.actions.pop(action)
                # fill settings dialog treeview
                self.FillTreeView("actions_treeview", actions, "Actions", "selected_action")

            dialog.destroy()


    def CheckForNewVersionNow(self, widget=None):
        """
            Check for new version of nagstamon - use connection data of configured servers
        """
        # check if there is already a checking thread
        for s in self.servers.values():
            if s.CheckingForNewVersion == True:
                # if there is already one server used for checking break
                break
            else:
                # start thread which checks for updates
                self.check = Actions.CheckForNewVersion(servers=self.servers, output=self.output, mode="normal", parent=self)
                self.check.start()
                # if one of the servers is not used to check for new version this is enough
                break


    def ToggleDebugOptions(self, widget=None):
        """
        allow to use a file for debug output
        """
        debug_to_file = self.builder.get_object("input_checkbutton_debug_to_file")
        debug_file = self.builder.get_object("input_entry_debug_file")
        debug_mode = self.builder.get_object("input_checkbutton_debug_mode")

        if debug_to_file.state == gtk.STATE_INSENSITIVE:
            debug_file.set_sensitive(False)

        if not debug_mode.get_active():
            debug_to_file.hide()
            debug_to_file.set_sensitive(debug_mode.get_active())
            debug_file.hide()
            debug_file.set_sensitive(debug_to_file.get_active())
        else:
            debug_to_file.show()
            debug_to_file.set_sensitive(debug_mode.get_active())
            debug_file.show()
            debug_file.set_sensitive(debug_to_file.get_active())


    def ToggleNotification(self, widget=None):
        """
            Disable notifications at all
        """
        options = self.builder.get_object("table_notification_options")
        checkbutton = self.builder.get_object("input_checkbutton_notification")
        #options.set_sensitive(checkbutton.get_active())
        if not checkbutton.get_active():
            options.hide()
        else:
            options.show()


    def ToggleSoundOptions(self, widget=None):
        """
            Disable notification sound when not using sound is enabled
        """
        options = self.builder.get_object("table_notification_options_sound_options")
        checkbutton = self.builder.get_object("input_checkbutton_notification_sound")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()
        options.set_sensitive(checkbutton.get_active())
        # in case custom options are shown but not selected (due to .show_all())
        self.ToggleCustomSoundOptions()


    def ToggleCustomSoundOptions(self, widget=None):
        """
            Disable custom notification sound
        """
        options = self.builder.get_object("table_notification_sound_options_custom_sounds_files")
        checkbutton = self.builder.get_object("input_radiobutton_notification_custom_sound")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()


    def ToggleREHostOptions(self, widget=None):
        """
            Toggle regular expression filter for hosts
        """
        options = self.builder.get_object("hbox_re_host")
        checkbutton = self.builder.get_object("input_checkbutton_re_host_enabled")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()
        options.set_sensitive(checkbutton.get_active())


    def ToggleREServiceOptions(self, widget=None):
        """
            Toggle regular expression filter for services
        """
        options = self.builder.get_object("hbox_re_service")
        checkbutton = self.builder.get_object("input_checkbutton_re_service_enabled")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()
        options.set_sensitive(checkbutton.get_active())


    def ToggleREStatusInformationOptions(self, widget=None):
        """
            Toggle regular expression filter for status
        """
        options = self.builder.get_object("hbox_re_status_information")
        checkbutton = self.builder.get_object("input_checkbutton_re_status_information_enabled")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()
        options.set_sensitive(checkbutton.get_active())


    def ToggleRECriticalityOptions(self, widget=None):
        """
            Toggle regular expression filter for criticality
        """
        options = self.builder.get_object("hbox_re_criticality")
        checkbutton = self.builder.get_object("input_checkbutton_re_criticality_enabled")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()


    def ToggleRECriticalityFilter(self):
        """
            1. Always hide criticality options
            2. Check if type of any enabled server is Centreon.
            3. If true, show the criticality filter options
        """
        self.builder.get_object("hbox_re_criticality").hide()
        self.builder.get_object("input_checkbutton_re_criticality_enabled").hide()
        for server in self.conf.servers:
            if (str(self.conf.servers[server].enabled) == "True") and (str(self.conf.servers[server].type) == "Centreon"):
                self.builder.get_object("input_checkbutton_re_criticality_enabled").show()


    def ToggleSystrayPopupOffset(self, widget=None):
        """
            Toggle adjustment for systray-popup-offset (see sf.net bug 3389241)
        """
        options = self.builder.get_object("hbox_systray_popup_offset")
        checkbutton = self.builder.get_object("input_radiobutton_icon_in_systray")

        #options.set_sensitive(checkbutton.get_active())
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()


    def ToggleFullscreenDisplay(self, widget=None):
        """
            Toggle adjustment for fullscreen display choice
        """
        options = self.builder.get_object("hbox_fullscreen_display")
        checkbutton = self.builder.get_object("input_radiobutton_fullscreen")

        #options.set_sensitive(checkbutton.get_active())
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()


    def ToggleNotificationActions(self, widget=None):
        """
            Toggle extra notifications per level
        """
        options = self.builder.get_object("vbox_notification_actions")
        checkbutton = self.builder.get_object("input_checkbutton_notification_actions")
        if not checkbutton.get_active():
            options.hide()
        else:
            options.show()
        self.ToggleNotificationCustomAction()


    def ToggleNotificationCustomAction(self, widget=None):
        """
            Toggle generic custom notification
        """
        options = self.builder.get_object("table_notification_custom_action")
        checkbutton = self.builder.get_object("input_checkbutton_notification_custom_action")
        if not checkbutton.get_active():
            options.hide()
        else:
            options.show()


    def ToggleNotificationActionWarning(self, widget=None):
        """
            Toggle notification action for WARNING
        """
        options = self.builder.get_object("input_entry_notification_action_warning_string")
        checkbutton = self.builder.get_object("input_checkbutton_notification_action_warning")
        if not checkbutton.get_active():
            options.hide()
            checkbutton.set_label("WARNING")
        else:
            options.show()
            checkbutton.set_label("WARNING:")


    def ToggleNotificationActionCritical(self, widget=None):
        """
            Toggle notification action for CRITICAL
        """
        options = self.builder.get_object("input_entry_notification_action_critical_string")
        checkbutton = self.builder.get_object("input_checkbutton_notification_action_critical")
        if not checkbutton.get_active():
            options.hide()
            checkbutton.set_label("CRITICAL")
        else:
            options.show()
            checkbutton.set_label("CRITICAL:")


    def ToggleNotificationActionDown(self, widget=None):
        """
            Toggle notification action for DOWN
        """
        options = self.builder.get_object("input_entry_notification_action_down_string")
        checkbutton = self.builder.get_object("input_checkbutton_notification_action_down")
        if not checkbutton.get_active():
            options.hide()
            checkbutton.set_label("DOWN")
        else:
            options.show()
            checkbutton.set_label("DOWN:")


    def ToggleNotificationActionOk(self, widget=None):
        """
            Toggle notification action for OK
        """
        options = self.builder.get_object("input_entry_notification_action_ok_string")
        checkbutton = self.builder.get_object("input_checkbutton_notification_action_ok")
        if not checkbutton.get_active():
            options.hide()
            checkbutton.set_label("OK")
        else:
            options.show()
            checkbutton.set_label("OK:")


    def ToggleNotificationActionsHelp(self, widget=None):
        """
            Toggle help label for action string
        """
        help = self.builder.get_object("label_help_notification_actions_description")
        help.set_visible(not help.get_visible())


    def ToggleNotificationCustomActionsHelp(self, widget=None):
        """
            Toggle help label for action string
        """
        help = self.builder.get_object("label_help_notification_custom_actions_description")
        help.set_visible(not help.get_visible())


    def ToggleSystemKeyring(self, widget=None):
        """
        check on non-OSX/Windows systems if keyring and secretstorage modules are available and disable
        keyring checkbox if not
        """
        checkbutton = self.builder.get_object("input_checkbutton_use_system_keyring")
        if not platform.system() in ["Darwin", "Windows"]:
            if self.conf.keyring_available:
                checkbutton.set_visible(True)
            else:
                checkbutton.set_visible(False)
                # disable keyring in general
                #self.conf.use_system_keyring = False
        # it's OK on Darwin and Windows
        else:
            checkbutton.set_visible(True)


    def PlaySound(self, playbutton=None):
        """
            play sample of selected sound for Nagios Event
        """
        try:
            filechooser = self.builder.get_object("input_filechooser_notification_custom_sound_" + gtk.Buildable.get_name(playbutton))
            sound = Actions.PlaySound(sound="FILE", file=filechooser.get_filename(), conf=self.conf, servers=self.servers)
            sound.start()
        except Exception, err:
            import traceback
            traceback.print_exc(file=sys.stdout)


class GenericServer(object):
    """
        settings of one particular new Nagios server
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # set the gtkbuilder files
        self.builderfile = self.output.Resources + os.sep + "settings_server_dialog.ui"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builderfile)
        self.dialog = self.builder.get_object("settings_server_dialog")
        # try to avoid shy dialog on MacOSX
        self.dialog.set_transient_for(self.settingsdialog.dialog)

        # assign handlers
        handlers_dict = { "button_ok_clicked" : self.OK,
                          "button_cancel_clicked" : self.Cancel,
                          "settings_dialog_close" : self.Cancel,
                          "toggle_save_password" : self.ToggleSavePassword,
                          "toggle_autologin_key" : self.ToggleAutoLoginKey,
                          "toggle_proxy" : self.ToggleProxy
                          }
        self.builder.connect_signals(handlers_dict)

        # set server type combobox to Nagios as default
        self.combobox = self.builder.get_object("input_combo_server_type")
        combomodel = gtk.ListStore(gobject.TYPE_STRING)
        cr = gtk.CellRendererText()
        self.combobox.pack_start(cr, True)
        self.combobox.set_attributes(cr, text=0)
        for server in Actions.get_registered_server_type_list():
            combomodel.append((server,))
        self.combobox.set_model(combomodel)
        self.combobox.set_active(0)

        self.combobox.connect('changed', self.on_server_type_change)
        # initialize server type dependent dialog outfit
        self.on_server_type_change(self.combobox)

        # set specific defaults or server settings
        self.initialize()


    def show(self):
        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
        self.dialog.hide()


    def initialize(self):
        """
        set server settings to default values
        """

        if self.server == "":
            # new server
            # enable server by default
            self.builder.get_object("input_checkbutton_enabled").set_active(True)
            # disable autologin by default
            self.ToggleAutoLoginKey()
            # save password by default
            self.builder.get_object("input_checkbutton_save_password").set_active(True)
            # disable proxy by default
            self.builder.get_object("input_checkbutton_use_proxy").set_active(False)

            # set first monitor type as default
            self.combobox.set_active(0)

            # default monitor server addresses
            self.builder.get_object("input_entry_monitor_url").set_text("https://monitor-server")
            self.builder.get_object("input_entry_monitor_cgi_url").set_text("https://monitor-server/monitor/cgi-bin")
            # default user and password
            self.builder.get_object("input_entry_username").set_text("user")
            self.builder.get_object("input_entry_password").set_text("password")
            # default proxy settings
            self.builder.get_object("input_entry_proxy_address").set_text("http://proxy:port/")
            self.builder.get_object("input_entry_proxy_username").set_text("proxyuser")
            self.builder.get_object("input_entry_proxy_password").set_text("proxypassword")
        else:
            # edit or copy a server
            keys = self.conf.servers[self.server].__dict__.keys()
            # walk through all relevant input types to fill dialog with existing settings
            for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_", "input_spinbutton_"]:
                for key in keys:
                    j = self.builder.get_object(i + key)
                    if not j:
                        continue
                    # some hazard, every widget has other methods to fill it with desired content
                    # so we try them all, one of them should work
                    try:
                        j.set_text(self.conf.servers[self.server].__dict__[key])
                    except:
                        pass
                    try:
                        if str(self.conf.servers[self.server].__dict__[key]) == "True":
                            j.set_active(True)
                        if str(self.conf.servers[self.server].__dict__[key]) == "False":
                            j.set_active(False)
                    except:
                        pass
                    try:
                        j.set_value(int(self.conf.servers[self.server].__dict__[key]))
                    except:
                        pass

            # set server type combobox which cannot be set by above hazard method
            servers = Actions.get_registered_server_type_list()
            server_types = dict([(x[1], x[0]) for x in enumerate(servers)])

            # set server type
            self.combobox.set_active(server_types[self.conf.servers[self.server].type])

        # show password - or not
        #self.ToggleSavePassword()
        # show settings options for proxy - or not
        self.ToggleProxy()


    def on_server_type_change(self, combobox):
        """
        Disables controls as it is set in server class
        from former ServerDialogHelper class which contained common logic for server dialog
        might be of interest in case server type is changed and dialog content should be
        adjusted to reflect different labels/entry fields
        """
        active = combobox.get_active_iter()
        model = combobox.get_model()
        if not model:
            return
        server = Actions.get_registered_servers()[model.get_value(active, 0)]

        # make everything visible
        for item_id in ["label_monitor_cgi_url",
                        "input_entry_monitor_cgi_url",
                        "input_checkbutton_use_autologin",
                        "label_autologin_key",
                        "input_entry_autologin_key",
                        "input_checkbutton_use_display_name_host",
                        "input_checkbutton_use_display_name_service"]:
            item = self.builder.get_object(item_id)
            if item is not None:
                item.set_visible(True)

        # so we can hide what may be hidden
        if len(server.DISABLED_CONTROLS) != 0:
            for item_id in server.DISABLED_CONTROLS:
                item = self.builder.get_object(item_id)
                if item is not None:
                    item.set_visible(False)


    def OK(self, widget):
        """
            New server configured
        """
        # put changed data into new server, which will get into the servers dictionary after the old
        # one has been deleted
        new_server = Config.Server()

        keys = new_server.__dict__.keys()
        for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_", "input_spinbutton_", "input_filechooser_"]:
            for key in keys:
                j = self.builder.get_object(i + key)
                if not j:
                    continue
                # some hazard, every widget has other methods to get its content
                # so we try them all, one of them should work
                try:
                    new_server.__dict__[key] = j.get_text()
                except:
                    pass
                try:
                    new_server.__dict__[key] = j.get_active()
                except:
                    pass
                try:
                    new_server.__dict__[key] = int(j.get_value())
                except:
                    pass

        # set server type combobox which cannot be set by above hazard method
        combobox = self.builder.get_object("input_combo_server_type")
        active = combobox.get_active_iter()
        model = combobox.get_model()
        new_server.__dict__["type"] = model.get_value(active, 0)

        # workaround for cgi-url not needed by certain monitor types
        server = Actions.get_registered_servers()[new_server.type]
        if "input_entry_monitor_cgi_url" in server.DISABLED_CONTROLS:
            new_server.monitor_cgi_url = new_server.monitor_url

        # URLs should not end with / - clean it
        new_server.monitor_url = new_server.monitor_url.rstrip("/")
        new_server.monitor_cgi_url = new_server.monitor_cgi_url.rstrip("/")

        # check if there is already a server named like the new one
        if new_server.name in self.conf.servers:
            self.output.Dialog(message='A server named "' + new_server.name + '" already exists.')
        else:
            # put in new one
            self.conf.servers[new_server.name] = new_server
            # create new server thread
            created_server = Actions.CreateServer(new_server, self.conf, self.output.debug_queue, self.output.Resources)
            if created_server is not None:
                self.servers[new_server.name] = created_server

                if str(self.conf.servers[new_server.name].enabled) == "True":
                    # start new thread (should go to Actions!)
                    self.servers[new_server.name].thread = Actions.RefreshLoopOneServer(server=self.servers[new_server.name], output=self.output, conf=self.conf)
                    self.servers[new_server.name].thread.start()

            # fill settings dialog treeview
            self.settingsdialog.FillTreeView("servers_treeview", self.conf.servers, "Servers", "selected_server")

            # care about Centreon criticality filter
            self.settingsdialog.ToggleRECriticalityFilter()

            # apply settings for modified servers
            self.output.ApplyServerModifications()

            # destroy new server dialog
            gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
            self.dialog.hide()


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        if not self.conf.unconfigured == True:
            gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
            self.dialog.hide()
        else:
            sys.exit()


    def ToggleSavePassword(self, widget=None):
        """
            Disable password input box
        """
        checkbutton = self.builder.get_object("input_checkbutton_save_password")
        is_active = checkbutton.get_active()
        item = self.builder.get_object("label_password")
        item.set_sensitive(is_active)
        item = self.builder.get_object("input_entry_password")
        item.set_sensitive(is_active)
        ###if not is_active:
        ###    item.set_text("")


    def ToggleAutoLoginKey(self, widget=None):
        """
            Disable autologin key input box
        """
        use_autologin = self.builder.get_object("input_checkbutton_use_autologin")
        is_active = use_autologin.get_active()
        item = self.builder.get_object("label_autologin_key")
        item.set_sensitive( is_active )
        item = self.builder.get_object("input_entry_autologin_key")
        item.set_sensitive( is_active )
        ###if not is_active:
        ###    item.set_text("")

	    #disable save password
        item = self.builder.get_object("input_checkbutton_save_password")
        item.set_active( False )
        item.set_sensitive( not is_active )
        item = self.builder.get_object("label_password")
        item.set_sensitive( not is_active )
        item = self.builder.get_object("input_entry_password")
        item.set_sensitive( not is_active )
        item.set_text("")


    def ToggleProxy(self, widget=None):
        """
            Disable proxy options
        """
        checkbutton = self.builder.get_object("input_checkbutton_use_proxy")
        self.ToggleProxyFromOS(checkbutton.get_active())
        self.ToggleProxyAddress(checkbutton.get_active())


    def ToggleProxyFromOS(self, widget=None):
        """
            toggle proxy from OS when using proxy is enabled
        """
        checkbutton = self.builder.get_object("input_checkbutton_use_proxy_from_os")
        #checkbutton.set_sensitive(self.builder.get_object("input_checkbutton_use_proxy").get_active())
        if self.builder.get_object("input_checkbutton_use_proxy").get_active():
            self.builder.get_object("input_checkbutton_use_proxy_from_os").show()
        else:
            self.builder.get_object("input_checkbutton_use_proxy_from_os").hide()


    def ToggleProxyAddress(self, widget=None):
        """
            toggle proxy address options when not using proxy is enabled
        """
        use_proxy = self.builder.get_object("input_checkbutton_use_proxy")
        use_proxy_from_os = self.builder.get_object("input_checkbutton_use_proxy_from_os")
        # depending on checkbox state address fields wil be active
        if use_proxy.get_active() == True:
            # always the opposite of os proxy selection
            state = not use_proxy_from_os.get_active()
        else:
            state = False

        for n in ("label_proxy_address",
                  "input_entry_proxy_address",
                  "label_proxy_username",
                  "input_entry_proxy_username",
                  "label_proxy_password",
                  "input_entry_proxy_password"):
            item = self.builder.get_object(n)
            if state:
                item.show()
            else:
                item.hide()

class NewServer(GenericServer):
    """
        settings of one particuliar new Nagios server
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # create new dummy server
        self.server = ""

        GenericServer.__init__(self, **kwds)

        # set title of settings dialog
        self.dialog.set_title("New server")


class EditServer(GenericServer):
    """
        settings of one particuliar Nagios server
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        GenericServer.__init__(self, **kwds)

        # in case server has been selected do nothing
        if not self.server == None:
            # set title of settings dialog
            self.dialog.set_title("Edit server " + self.server)

            keys = self.conf.servers[self.server].__dict__.keys()
            # walk through all relevant input types to fill dialog with existing settings
            for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_", "input_spinbutton_"]:
                for key in keys:
                    j = self.builder.get_object(i + key)
                    if not j:
                        continue
                    # some hazard, every widget has other methods to fill it with desired content
                    # so we try them all, one of them should work
                    try:
                        j.set_text(self.conf.servers[self.server].__dict__[key])
                    except:
                        pass
                    try:
                        if str(self.conf.servers[self.server].__dict__[key]) == "True":
                            j.set_active(True)
                        if str(self.conf.servers[self.server].__dict__[key]) == "False":
                            j.set_active(False)
                    except:
                        pass
                    try:
                        j.set_value(int(self.conf.servers[self.server].__dict__[key]))
                    except:
                        pass

            # set server type combobox which cannot be set by above hazard method
            servers = Actions.get_registered_server_type_list()
            server_types = dict([(x[1], x[0]) for x in enumerate(servers)])

            self.combobox.set_active(server_types[self.conf.servers[self.server].type])


    def initialize(self):
        """
        fill dialog with server settings
        """

        GenericServer.initialize(self)

        # set title of settings dialog
        self.dialog.set_title("Edit server " + self.server)


    def OK(self, widget):
        """
            settings dialog got OK-ed
        """
        # put changed data into new server, which will get into the servers dictionary after the old
        # one has been deleted
        new_server = Config.Server()

        keys = new_server.__dict__.keys()
        for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_", "input_spinbutton_", "input_filechooser_"]:
            for key in keys:
                j = self.builder.get_object(i + key)
                if not j:
                    continue
                # some hazard, every widget has other methods to get its content
                # so we try them all, one of them should work
                try:
                    new_server.__dict__[key] = j.get_text()
                except:
                    pass
                try:
                    new_server.__dict__[key] = j.get_active()
                except:
                    pass
                try:
                    new_server.__dict__[key] = int(j.get_value())
                except:
                    pass

        # set server type combobox which cannot be set by above hazard method
        combobox = self.builder.get_object("input_combo_server_type")
        active = combobox.get_active_iter()
        model = combobox.get_model()
        new_server.__dict__["type"] = model.get_value(active, 0)

        # workaround for cgi-url not needed by certain monitor types
        server = Actions.get_registered_servers()[new_server.type]
        if "input_entry_monitor_cgi_url" in server.DISABLED_CONTROLS:
            new_server.monitor_cgi_url = new_server.monitor_url

        # URLs should not end with / - clean it
        new_server.monitor_url = new_server.monitor_url.rstrip("/")
        new_server.monitor_cgi_url = new_server.monitor_cgi_url.rstrip("/")

        # check if there is already a server named like the new one
        if new_server.name in self.conf.servers and new_server.name != self.server:
            self.output.Dialog(message="A server named " + new_server.name + " already exists.")
        else:
            # delete old server configuration entry
            self.conf.servers.pop(self.server)
            try:
                # stop thread - only if it is yet initialized as such
                if self.servers[self.server].thread:
                    self.servers[self.server].thread.Stop()
            except:
                import traceback
                traceback.print_exc(file=sys.stdout)
            # delete server from servers dictionary
            self.servers.pop(self.server)

            # put in new one
            self.conf.servers[new_server.name] = new_server
            # create new server thread
            created_server = Actions.CreateServer(new_server, self.conf, self.output.debug_queue, self.output.Resources)
            if created_server is not None:
                self.servers[new_server.name] = created_server
                if str(self.conf.servers[new_server.name].enabled) == "True":
                    # start new thread (should go to Actions)
                    self.servers[new_server.name].thread = Actions.RefreshLoopOneServer(server=self.servers[new_server.name], output=self.output, conf=self.conf)
                    self.servers[new_server.name].thread.start()

            # fill settings dialog treeview
            self.settingsdialog.FillTreeView("servers_treeview", self.conf.servers, "Servers", "selected_server")

            # care about Centreon criticality filter
            self.settingsdialog.ToggleRECriticalityFilter()

            # apply settings for modified servers
            self.output.ApplyServerModifications()

            # hide dialog
            gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
            self.dialog.hide()


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
        self.dialog.hide()



class CopyServer(GenericServer):
    """
        copy a server
    """
    def initialize(self):
        # get existing properties from action like it was edited
        GenericServer.initialize(self)

        # set title of settings dialog
        self.dialog.set_title("Copy server " + self.server)

        # modify name if action to indicate copy
        self.entry_name = self.builder.get_object("input_entry_name")
        self.entry_name.set_text("Copy of %s" % (self.entry_name.get_text()))


class GenericAction(object):
    """
        settings of one particuliar action
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # set the gtkbuilder files
        self.builderfile = self.output.Resources + os.sep + "settings_action_dialog.ui"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builderfile)
        self.dialog = self.builder.get_object("settings_action_dialog")
        # try to avoid shy dialog on MacOSX
        self.dialog.set_transient_for(self.settingsdialog.dialog)

        # assign handlers
        handlers_dict = { "button_ok_clicked" : self.OK,
                          "button_cancel_clicked" : self.Cancel,
                          "settings_dialog_close" : self.Cancel,
                          "checkbutton_re_host_enabled": self.ToggleREHostOptions,
                          "checkbutton_re_service_enabled": self.ToggleREServiceOptions,
                          "checkbutton_re_status_information_enabled": self.ToggleREStatusInformationOptions,
                          "checkbutton_re_criticality_enabled": self.ToggleRECriticalityOptions,
                          "button_help_string_clicked": self.ToggleActionStringHelp,
                          "button_help_type_clicked": self.ToggleActionTypeHelp,
                          }
        self.builder.connect_signals(handlers_dict)

        # fill combobox for action type with options
        self.combobox_action_type = self.builder.get_object("input_combo_action_type")
        self.combomodel_action_type = gtk.ListStore(gobject.TYPE_STRING)
        cr = gtk.CellRendererText()
        self.combobox_action_type.pack_start(cr, True)
        self.combobox_action_type.set_attributes(cr, text=0)
        for action_type in ["Browser", "Command", "URL"]:
            self.combomodel_action_type.append((action_type,))
        self.combobox_action_type.set_model(self.combomodel_action_type)

        # fill combobox for monitor type with options
        self.combobox_monitor_type = self.builder.get_object("input_combo_monitor_type")
        self.combomodel_monitor_type = gtk.ListStore(gobject.TYPE_STRING)
        cr = gtk.CellRendererText()
        self.combobox_monitor_type.pack_start(cr, True)
        self.combobox_monitor_type.set_attributes(cr, text=0)
        self.monitor_types = sorted(Actions.get_registered_server_type_list())
        # as default setting - would be "" in config file
        self.monitor_types.insert(0, "All monitor servers")
        # transform monitor types list to a dictionary with numbered values to handle combobox index later
        self.monitor_types = dict(zip(self.monitor_types, range(len(self.monitor_types))))
        for monitor_type in sorted(self.monitor_types.keys()):
            self.combomodel_monitor_type.append((monitor_type,))
        self.combobox_monitor_type.set_model(self.combomodel_monitor_type)

        # if action applies to all monitors which is "" as default in config file its index is like "All monitor servers"
        self.monitor_types[""] = 0

        self.initialize()


    def show(self):
        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
        self.dialog.hide()


    def initialize(self):
        """
        set defaults for action
        """
        # if uninitialized action (e.g. new one) is used don't access actions dictionary
        if self.action == "":
            # ...but use a dummy object with default settings
            action = Config.Action()
            # enable action by default
            self.builder.get_object("input_checkbutton_enabled").set_active(True)
            # action type combobox should be set to default
            self.combobox_action_type = self.builder.get_object("input_combo_action_type")
            self.combobox_action_type.set_active(0)
            # monitor type combobox should be set to default
            self.combobox_monitor_type = self.builder.get_object("input_combo_monitor_type")
            self.combobox_monitor_type.set_active(0)
        else:
            action = self.conf.actions[self.action]
            # adjust combobox to used action type
            self.combobox_action_type = self.builder.get_object("input_combo_action_type")
            self.combobox_action_type.set_active({"browser":0, "command":1, "url":2}[self.conf.actions[self.action].type])
            self.combobox_action_type = self.builder.get_object("input_combo_monitor_type")
            self.combobox_action_type.set_active(self.monitor_types[self.conf.actions[self.action].monitor_type])

        keys = action.__dict__.keys()
        # walk through all relevant input types to fill dialog with existing settings
        for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_"]:
            for key in keys:
                j = self.builder.get_object(i + key)

                if not j:
                    continue
                # some hazard, every widget has other methods to fill it with desired content
                # so we try them all, one of them should work
                try:
                    j.set_text(action.__dict__[key])
                except:
                    pass
                try:
                    if str(action.__dict__[key]) == "True":
                        j.set_active(True)
                    if str(action.__dict__[key]) == "False":
                        j.set_active(False)
                except:
                    pass
                try:
                    j.set_value(int(self.conf.__dict__[key]))
                except:
                    pass

        # disable help per default
        self.builder.get_object("label_help_string_description").set_visible(False)
        self.builder.get_object("label_help_type_description").set_visible(False)

        # toggle some GUI elements
        self.ToggleREHostOptions()
        self.ToggleREServiceOptions()
        self.ToggleREStatusInformationOptions()
        self.ToggleRECriticalityOptions()


    def OK(self, widget):
        """
            New action configured pr existing one edited
        """
        # put changed data into new server, which will get into the servers dictionary after the old
        # one has been deleted
        new_action = Config.Action()

        keys = new_action.__dict__.keys()
        for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_"]:
            for key in keys:
                j = self.builder.get_object(i + key)
                if not j:
                    continue
                # some hazard, every widget has other methods to get its content
                # so we try them all, one of them should work
                try:
                    new_action.__dict__[key] = j.get_text()
                except:
                    try:
                        new_action.__dict__[key] = j.get_active()
                    except:
                        try:
                            new_action.__dict__[key] = int(j.get_value())
                        except:
                            pass

        # set action type combobox which cannot be set by above hazard method
        self.combobox_action_type = self.builder.get_object("input_combo_action_type")
        active = self.combobox_action_type.get_active_iter()
        self.combomodel_action_type = self.combobox_action_type.get_model()
        new_action.type = self.combomodel_action_type .get_value(active, 0).lower()

        # set monitor type combobox which cannot be set by above hazard method
        self.combobox_monitor_type = self.builder.get_object("input_combo_monitor_type")
        active = self.combobox_monitor_type.get_active_iter()
        self.combomodel_monitor_type = self.combobox_monitor_type.get_model()
        new_action.monitor_type = self.combomodel_monitor_type.get_value(active, 0)

        # if action applies to all monitor types its monitor_type should be ""
        # because it is "All monitor servers" in Combobox
        if not new_action.monitor_type in Actions.get_registered_server_type_list():
            new_action.monitor_type = ""

        # check if there is already an action named like the new one
        if new_action.name in self.conf.actions:
            self.output.Dialog(message='An action named "' + new_action.name + '" already exists.')
        else:
            # put in new one
            self.conf.actions[new_action.name] = new_action

            # fill settings dialog treeview
            self.settingsdialog.FillTreeView("actions_treeview", self.conf.actions, "Actions", "selected_action")
            # destroy new action dialog
            gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
            self.dialog.hide()


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
        self.dialog.hide()


    def ToggleREHostOptions(self, widget=None):
        """
            Toggle regular expression filter for hosts
        """
        options = self.builder.get_object("hbox_re_host")
        checkbutton = self.builder.get_object("input_checkbutton_re_host_enabled")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()
        options.set_sensitive(checkbutton.get_active())


    def ToggleREServiceOptions(self, widget=None):
        """
            Toggle regular expression filter for services
        """
        options = self.builder.get_object("hbox_re_service")
        checkbutton = self.builder.get_object("input_checkbutton_re_service_enabled")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()
        options.set_sensitive(checkbutton.get_active())


    def ToggleREStatusInformationOptions(self, widget=None):
        """
            Toggle regular expression filter for status
        """
        options = self.builder.get_object("hbox_re_status_information")
        checkbutton = self.builder.get_object("input_checkbutton_re_status_information_enabled")
        if not checkbutton.get_active():
            options.hide_all()
        else:
            options.show_all()
        options.set_sensitive(checkbutton.get_active())


    def ToggleRECriticalityOptions(self, widget=None):
        """
            Toggle regular expression filter for criticality
        """
        options = self.builder.get_object("hbox_re_criticality")
        checkbutton = self.builder.get_object("input_checkbutton_re_criticality_enabled")
        if not checkbutton == None:
            if not checkbutton.get_active():
                options.hide_all()
            else:
                options.show_all()
            options.set_sensitive(checkbutton.get_active())


    def ToggleActionStringHelp(self, widget=None):
        """
            Toggle help label for action string
        """
        help = self.builder.get_object("label_help_string_description")
        help.set_visible(not help.get_visible())


    def ToggleActionTypeHelp(self, widget=None):
        """
            Toggle help label for action type
        """
        help = self.builder.get_object("label_help_type_description")
        help.set_visible(not help.get_visible())


class NewAction(GenericAction):
    """
        generic settings of one particuliar new action server
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # create new dummy action
        self.action = ""

        GenericAction.__init__(self, **kwds)

        # set title of settings dialog
        self.dialog.set_title("New action")


class EditAction(GenericAction):
    """
        generic settings of one particuliar new action server
    """
    def initialize(self):
        """
            extra initialization needed for every call
        """
        GenericAction.initialize(self)

        # set title of settings dialog
        self.dialog.set_title("Edit action " + self.action)


    def OK(self, widget):
        """
            New action configured pr existing one edited
        """
        # put changed data into new server, which will get into the servers dictionary after the old
        # one has been deleted
        new_action = Config.Action()

        keys = new_action.__dict__.keys()
        for i in ["input_entry_", "input_checkbutton_", "input_radiobutton_"]:
            for key in keys:
                j = self.builder.get_object(i + key)
                if not j:
                    continue
                # some hazard, every widget has other methods to get its content
                # so we try them all, one of them should work
                try:
                    new_action.__dict__[key] = j.get_text()
                except:
                    try:
                        new_action.__dict__[key] = j.get_active()
                    except:
                        try:
                            new_action.__dict__[key] = int(j.get_value())
                        except:
                            pass

        # set server type combobox which cannot be set by above hazard method
        self.combobox_action_type = self.builder.get_object("input_combo_action_type")
        active = self.combobox_action_type.get_active_iter()
        model = self.combobox_action_type.get_model()
        new_action.type = model.get_value(active, 0).lower()

        # set monitor type combobox which cannot be set by above hazard method
        self.combobox_monitor_type = self.builder.get_object("input_combo_monitor_type")
        active = self.combobox_monitor_type.get_active_iter()
        self.combomodel_monitor_type = self.combobox_monitor_type.get_model()
        new_action.monitor_type = self.combomodel_monitor_type.get_value(active, 0)

        # if action applies to all monitor types its monitor_type should be ""
        # because it is "All monitor servers" in Combobox
        if not new_action.monitor_type in Actions.get_registered_server_type_list():
            new_action.monitor_type = ""

        # check if there is already an action named like the new one
        if new_action.name in self.conf.actions and new_action.name != self.action:
            self.output.Dialog(message='An action named "' + new_action.name + '" already exists.')
        else:
            # delete old one
            self.conf.actions.pop(self.action)
            # put in new one
            self.conf.actions[new_action.name] = new_action
            # fill settings dialog treeview
            self.settingsdialog.FillTreeView("actions_treeview", self.conf.actions, "Actions", "selected_action")
            # destroy new action dialog
            gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))
            self.dialog.hide()


class CopyAction(GenericAction):
    """
        copies an existing action
    """
    def initialize(self):
        """
        extra initialization needed for every call
        """
        # get existing properties from action like it was edited
        GenericAction.initialize(self)

        # set title of settings dialog
        self.dialog.set_title("Copy action " + self.action)

        # modify name if action to indicate copy
        self.entry_name = self.builder.get_object("input_entry_name")
        self.entry_name.set_text("Copy of %s" % (self.entry_name.get_text()))


class AuthenticationDialog:
    """
    used in case password should not be stored
    "server" is here a Config.Server() instance given from nagstamon.py at startup, not a GenericServer()!
    """

    def __init__(self, **kwds):
        # the usual...
        for k in kwds: self.__dict__[k] = kwds[k]

        # set the gtkbuilder files
        self.builderfile = self.Resources + os.sep + "authentication_dialog.ui"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builderfile)
        self.dialog = self.builder.get_object("authentication_dialog")

        # assign handlers
        handlers_dict = { "button_ok_clicked" : self.OK,
                          "button_exit_clicked" : self.Exit,
                          "toggle_autologin_key_auth" : self.ToggleAutoLoginKeyAuth,
                          "button_disable_clicked" : self.Disable
                          }

        self.builder.connect_signals(handlers_dict)

        self.label_monitor = self.builder.get_object("label_monitor")
        self.entry_username = self.builder.get_object("input_entry_username")
        self.entry_password = self.builder.get_object("input_entry_password")
        self.entry_autologin_key = self.builder.get_object("input_entry_autologin_key")

        self.dialog.set_title("Nagstamon authentication for " + self.server.name)
        self.label_monitor.set_text("Please give the correct credentials for "+ self.server.name + ":")
        self.entry_username.set_text(str(self.server.username))
        self.entry_password.set_text(str(self.server.password))
        self.entry_autologin_key.set_text(str(self.server.autologin_key))

        self.ToggleAutoLoginKeyAuth()

        # omitting .show_all() leads to crash under Linux - why?
        self.dialog.show_all()

        # any monitor that is not Centreon does not need autologin entry
        if not self.server.type == "Centreon":
            self.entry_autologin_key.set_visible(False)
            self.builder.get_object("input_checkbutton_use_autologin").set_visible(False)
            self.builder.get_object("label_autologin_key").set_visible(False)
            self.builder.get_object("input_entry_autologin_key").set_visible(False)

        self.dialog.run()
        self.dialog.destroy()


    def OK(self, widget):
        self.server.username = self.entry_username.get_text()
        self.server.password = self.entry_password.get_text()
        self.server.autologin_key = self.entry_autologin_key.get_text()
        toggle_save_password = self.builder.get_object("input_checkbutton_save_password")
        toggle_use_autologin = self.builder.get_object("input_checkbutton_use_autologin")

        if toggle_save_password.get_active() == True:
            # store authentication information in config
            self.conf.servers[self.server.name].username = self.server.username
            self.conf.servers[self.server.name].password = self.server.password
            self.conf.servers[self.server.name].save_password = True
            self.conf.SaveConfig()

        if toggle_use_autologin.get_active() == True:
            # store autologin information in config
            self.conf.servers[self.server.name].username = self.server.username
            self.conf.servers[self.server.name].password = ""
            self.conf.servers[self.server.name].save_password = False
            self.conf.servers[self.server.name].autologin_key = self.server.autologin_key
            self.conf.servers[self.server.name].use_autologin = True
            self.conf.SaveConfig()


    def Disable(self, widget):
        # the old settings
        self.conf.servers[self.server.name].enabled = False


    def Exit(self, widget):
        sys.exit()


    def ToggleAutoLoginKeyAuth(self, widget=None):
        """
            Disable autologin key input box
        """
        use_autologin = self.builder.get_object("input_checkbutton_use_autologin")
        is_active = use_autologin.get_active()
        item = self.builder.get_object("label_autologin_key")
        item.set_sensitive( is_active )
        item = self.builder.get_object("input_entry_autologin_key")
        item.set_sensitive( is_active )
        if not is_active:
            item.set_text("")

	    #disable save password
        item = self.builder.get_object("input_checkbutton_save_password")
        item.set_active( False )
        item.set_sensitive( not is_active )
        item = self.builder.get_object("label_password")
        item.set_sensitive( not is_active )
        item = self.builder.get_object("input_entry_password")
        item.set_sensitive( not is_active )
        item.set_text("")


class DummyStatusIcon(object):
    """
    trayicon for MacOSX - only purpose is not showing trayicon because making it work
    as on Windows or Linux seems to need too much efford
    """
    def __init__(self):
        pass

    def set_from_file(self, *args, **kwds):
        pass

    def set_visible(self, *args, **kwds):
        pass

    def get_geometry(self, *args, **kwds):
        pass

    def connect(self, *args, **kwds):
        pass

    def set_from_pixbuf(self, *args, **kwds):
        pass

    def set_blinking(self, *args, **kwds):
        pass


class ButtonWithIcon(gtk.Button):
    """
    Button with an icon - reduces code
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        gtk.Button.__init__(self)

        # HBox is necessary because gtk.Button allows only one child
        self.HBox = gtk.HBox()
        self.Icon = gtk.Image()
        self.Icon.set_from_file(self.output.Resources + os.sep + self.icon)
        self.HBox.add(self.Icon)

        if self.label != "":
            self.Label = gtk.Label(" " + self.label)
            self.HBox.add(self.Label)

        self.set_relief(gtk.RELIEF_NONE)
        self.add(self.HBox)

    def show(self):
        """
        'normal' .show() does not show HBox and Icon
        """
        gtk.Button.show(self)
        self.HBox.show()
        self.Icon.show()
        if self.__dict__.has_key("Label"):
            self.Label.show()


    def hide(self):
        """
        'normal' .hide() does not hide HBox and Icon
        """
        gtk.Button.hide(self)
        self.HBox.hide()
        self.Icon.hide()
        if self.__dict__.has_key("Label"):
            self.Label.hide()
