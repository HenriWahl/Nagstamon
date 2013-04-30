# encoding: utf-8

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

# module egg.trayicon doesnt exists on Windows
if platform.system() != "Windows" and platform.system() != "Darwin":
    try:
        import egg.trayicon
    except Exception, err:
        print
        print err
        print
        print "Could not load egg.trayicon, so you cannot put nagstamon statusbar into systray."
        print

# needed for actions e.g. triggered by pressed buttons
from Nagstamon import Config
from Nagstamon import Actions
from Nagstamon import Objects
from Nagstamon import Custom # used for initialization of custom components

import subprocess
import sys
import time

import gc

class Sorting(object):
    """ Sorting persistence purpose class
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
        self.version = "0.9.10-devel"
        self.website = "http://nagstamon.ifw-dresden.de/"
        self.copyright = "©2008-2013 Henri Wahl et al.\nh.wahl@ifw-dresden.de"
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
        self.TAB_BG_COLORS = { "UNKNOWN":str(self.conf.color_unknown_background), "CRITICAL":str(self.conf.color_critical_background), "WARNING":str(self.conf.color_warning_background), "DOWN":str(self.conf.color_down_background), "UNREACHABLE":str(self.conf.color_unreachable_background)  }
        self.TAB_FG_COLORS = { "UNKNOWN":str(self.conf.color_unknown_text), "CRITICAL":str(self.conf.color_critical_text), "WARNING":str(self.conf.color_warning_text), "DOWN":str(self.conf.color_down_text), "UNREACHABLE":str(self.conf.color_unreachable_text) }

        # define popwin table liststore types
        self.LISTSTORE_COLUMNS = [gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,\
                                  gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,\
                                  gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,\
                                  gobject.TYPE_STRING,\
                                  gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf,\
                                  gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf]

        # create all GUI widgets
        self._CreateOutputVisuals()

        # set size of popup-window
        self.popwin.Resize()
        if str(self.conf.maximized_window) == "True":
            self.popwin.Window.show_all()
            self.popwin.Window.set_visible(True)
            self.popwin.RefreshMaximizedWindow()

        # flag which is set True if already notifying
        self.Notifying = False

        # saving sorting state between refresh
        self.rows_reordered_handler = {}
        self.last_sorting = {}
        for server in self.servers.values():
            self.last_sorting[server.get_name()] = Sorting([(server.DEFAULT_SORT_COLUMN_ID, gtk.SORT_ASCENDING),
                                                            (server.HOST_COLUMN_ID, gtk.SORT_ASCENDING)],
                                                           len(server.COLUMNS)+1) # stores sorting between table refresh


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


    def _CreateOutputVisuals(self):
        """
            create output visuals
        """
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

            # init MacOSX integration
            import gtk_osxapplication
            osxapp = gtk_osxapplication.OSXApplication()
            # prevent blocking
            osxapp.connect("NSApplicationBlockTermination", gtk.main_quit)
            osxapp.ready()

        # icons for acknowledgement/downtime visualization
        self.STATE_ICONS = dict()
        for icon in ["acknowledged", "downtime", "flapping", "passive"]:
            self.STATE_ICONS[icon] = gtk.gdk.pixbuf_new_from_file_at_size(self.Resources\
                                                                          + os.sep + "nagstamon_" + icon + self.BitmapSuffix,\
                                                                          int(self.fontsize/650), int(self.fontsize/650))

        # Icon in systray and statusbar both get created but
        # only one of them depending on the settings will
        # be shown
        self.statusbar = StatusBar(conf=self.conf, output=self)

        # Popup is a WINDOW_POPUP without border etc.
        self.popwin = Popwin(conf=self.conf, output=self)
        # Windows workaround for faulty behavior in case the statusbar label shrinks -
        # it does not in Windows, maybe a Gtk bug
        # do this only if statusbar is enabled
        if str(self.conf.statusbar_systray) == "True" or str(self.conf.statusbar_systray) == "True":
            x,y = self.statusbar.HBox.size_request()
            self.statusbar.StatusBar.resize(x, y)

        # connect events to actions
        # when talking about "systray" the Windows variant of upper left desktop corner
        # statusbar is meant synonymical
        # if pointer on systray do popup the long-summary-status-window aka popwin
        self.statusbar.SysTray.connect("activate", self.statusbar.SysTrayClicked)
        #self.statusbar.SysTray.connect("popup-menu", self.statusbar.MenuPopup, self.statusbar.Menu)
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
        # display "ERROR" in case of startup connection trouble
        errors = ""

        # walk through all servers,RefreshDisplayStatus their hosts and their services
        for server in self.servers.values():
            # only refresh monitor server output if enabled and only once every server loop
            if str(self.conf.servers[server.get_name()].enabled) == "True" or\
               server.refresh_authentication == True:
                try:
                    # otherwise it must be shown, full of problems
                    self.popwin.ServerVBoxes[server.get_name()].show()
                    self.popwin.ServerVBoxes[server.get_name()].set_visible(True)
                    self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(False)

                    # if needed show auth line:
                    if server.refresh_authentication == True:
                        self.popwin.ServerVBoxes[server.get_name()].HBoxAuth.set_no_show_all(False)
                        self.popwin.ServerVBoxes[server.get_name()].HBoxAuth.show_all()
                        if self.popwin.ServerVBoxes[server.get_name()].AuthEntryUsername.get_text() == "":
                            self.popwin.ServerVBoxes[server.get_name()].AuthEntryUsername.set_text(server.username)
                        if self.popwin.ServerVBoxes[server.get_name()].AuthEntryPassword.get_text() == "":
                            self.popwin.ServerVBoxes[server.get_name()].AuthEntryPassword.set_text(server.password)

                    # use a bunch of filtered nagitems, services and hosts sorted by different
                    # grades of severity

                    # summarize states
                    downs += server.downs
                    unreachables += server.unreachables
                    unknowns += server.unknowns
                    criticals += server.criticals
                    warnings += server.warnings

                    # if there is no trouble...
                    if len(server.nagitems_filtered["hosts"]["DOWN"]) == 0 and \
                       len(server.nagitems_filtered["hosts"]["UNREACHABLE"]) == 0 and \
                       len(server.nagitems_filtered["services"]["CRITICAL"]) == 0 and \
                       len(server.nagitems_filtered["services"]["WARNING"]) == 0 and \
                       len(server.nagitems_filtered["services"]["UNKNOWN"]) == 0 and \
                       server.status_description == "":
                        # ... there is no need to show a label or treeview...
                        self.popwin.ServerVBoxes[server.get_name()].hide()
                        self.popwin.ServerVBoxes[server.get_name()].set_visible(False)
                        self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(True)
                        self.status_ok = True
                    else:
                        # otherwise it must be shown, full of problems
                        self.popwin.ServerVBoxes[server.get_name()].show()
                        self.popwin.ServerVBoxes[server.get_name()].set_visible(True)
                        self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(False)
                        self.status_ok = False

                    # use a liststore for treeview where the table headers all are strings - first empty it
                    # now added with some simple repair after settings dialog has been used
                    # because sometimes after settings changes ListStore and TreeView become NoneType
                    # would be more logical to do this in Actions.CreateServer() but this gives a segfault :-(
                    if not type(server.ListStore) == type(None):
                        server.ListStore.clear()
                    else:
                        server.ListStore = gtk.ListStore(*self.LISTSTORE_COLUMNS)
                    if type(server.TreeView) == type(None):
                        server.TreeView = gtk.TreeView()

                    # apart from status informations there we need two columns which
                    # hold the color information, which is derived from status which
                    # is used as key at the above color dictionaries
                    # Update: new columns added which contain pixbufs of flag indicators if needed
                    for item_type, status_dict in server.nagitems_filtered.iteritems():
                        for status, item_list in status_dict.iteritems():
                            for item in list(item_list):
                                line = list(server.get_columns(item))

                                #print line

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
                                    line.extend([None, None, None, None])

                                # icons for services
                                else:
                                    # if the hosting host of a service has any flags display them too
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

                    # give new ListStore to the view, overwrites the old one automatically - theoretically
                    server.TreeView.set_model(server.ListStore)

                    # restore sorting order from previous refresh
                    self.set_sorting(server.ListStore, server)

                    # status field in server vbox in popwin
                    self.popwin.UpdateStatus(server)

                except:
                    server.Error(sys.exc_info())

        if self.popwin.Window.get_properties("visible")[0] == True and str(self.conf.maximized_window) == "False":
            self.popwin.Resize()

        # everything OK
        if unknowns == 0 and warnings == 0 and criticals == 0 and unreachables == 0 and downs == 0 and self.status_ok is not False:
            self.statusbar.statusbar_labeltext = '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_ok_background) + '" foreground="' + str(self.conf.color_ok_text) + '"> OK </span>'
            self.statusbar.statusbar_labeltext_inverted = self.statusbar.statusbar_labeltext
            self.statusbar.Label.set_markup(self.statusbar.statusbar_labeltext)
            # fix size when loading with network errors
            self.statusbar.Resize()
            # if all is OK there is no need to pop up popwin so set self.showPopwin to False
            self.popwin.showPopwin = False
            self.popwin.PopDown()
            self.status_ok = True

            # set systray icon to green aka OK
            self.statusbar.SysTray.set_from_pixbuf(self.statusbar.SYSTRAY_ICONS["green"])

            # switch notification off
            self.NotificationOff()

        else:
            self.status_ok = False

            # put text for label together
            self.statusbar.statusbar_labeltext = self.statusbar.statusbar_labeltext_inverted = ""

            if downs > 0:
                if str(self.conf.long_display) == "True": downs = str(downs) + " DOWN"
                self.statusbar.statusbar_labeltext = '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_down_background) + '" foreground="' + str(self.conf.color_down_text) + '"> ' + str(downs) + ' </span>'
                self.statusbar.statusbar_labeltext_inverted = '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_down_text) + '" foreground="' + str(self.conf.color_down_background) + '"> ' + str(downs) + ' </span>'
            if unreachables > 0:
                if str(self.conf.long_display) == "True": unreachables = str(unreachables) + " UNREACHABLE"
                self.statusbar.statusbar_labeltext = self.statusbar.statusbar_labeltext + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_unreachable_background) + '" foreground="' + str(self.conf.color_unreachable_text) + '"> ' + str(unreachables) + ' </span>'
                self.statusbar.statusbar_labeltext_inverted = self.statusbar.statusbar_labeltext_inverted + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_unreachable_text) + '" foreground="' + str(self.conf.color_unreachable_background) + '"> ' + str(unreachables) + ' </span>'
            if criticals > 0:
                if str(self.conf.long_display) == "True": criticals = str(criticals) + " CRITICAL"
                self.statusbar.statusbar_labeltext = self.statusbar.statusbar_labeltext + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_critical_background) + '" foreground="' + str(self.conf.color_critical_text) + '"> ' + str(criticals) + ' </span>'
                self.statusbar.statusbar_labeltext_inverted = self.statusbar.statusbar_labeltext_inverted + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_critical_text) + '" foreground="' + str(self.conf.color_critical_background) + '"> ' + str(criticals) + ' </span>'
            if unknowns > 0:
                if str(self.conf.long_display) == "True": unknowns = str(unknowns) + " UNKNOWN"
                self.statusbar.statusbar_labeltext = self.statusbar.statusbar_labeltext + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_unknown_background) + '" foreground="' + str(self.conf.color_unknown_text) + '"> ' + str(unknowns) + ' </span>'
                self.statusbar.statusbar_labeltext_inverted = self.statusbar.statusbar_labeltext_inverted + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_unknown_text) + '" foreground="' + str(self.conf.color_unknown_background) + '"> ' + str(unknowns) + ' </span>'
            if warnings > 0:
                if str(self.conf.long_display) == "True": warnings = str(warnings) + " WARNING"
                self.statusbar.statusbar_labeltext = self.statusbar.statusbar_labeltext + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_warning_background) + '" foreground="' + str(self.conf.color_warning_text) + '"> ' + str(warnings) + ' </span>'
                self.statusbar.statusbar_labeltext_inverted = self.statusbar.statusbar_labeltext_inverted + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_warning_text) + '" foreground="' + str(self.conf.color_warning_background) + '"> ' + str(warnings) + ' </span>'

            # if connections fails at starting do not display OK - Debian bug #617490
            if unknowns == 0 and warnings == 0 and criticals == 0 and unreachables == 0 and downs == 0 and self.status_ok is False:
                if str(self.conf.long_display) == "True":
                    errors = "ERROR"
                else:
                    errors = "ERR"
                self.statusbar.statusbar_labeltext = self.statusbar.statusbar_labeltext + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_error_background) + '" foreground="' + str(self.conf.color_error_text) + '"> ' + str(errors) + ' </span>'
                self.statusbar.statusbar_labeltext_inverted = self.statusbar.statusbar_labeltext_inverted + '<span size="' + str(self.fontsize) + '" background="' + str(self.conf.color_error_text) + '" foreground="' + str(self.conf.color_error_background) + '"> ' + str(errors) + ' </span>'
                color = "error"

            # put text into label in statusbar, only if not already flashing
            if self.statusbar.Flashing == False:
                self.statusbar.Label.set_markup(self.statusbar.statusbar_labeltext)

            # Windows workaround for non-automatically-shrinking desktop statusbar
            if str(self.conf.statusbar_floating) == "True":
                self.statusbar.Resize()

            # choose icon for systray  - the worst case decides the shown color
            if warnings > 0: color = "yellow"
            if unknowns > 0: color = "orange"
            if criticals > 0: color = "red"
            if unreachables > 0: color = "darkred"
            if downs > 0: color = "black"

            self.statusbar.SysTray.set_from_pixbuf(self.statusbar.SYSTRAY_ICONS[color])

            # if there has been any status change notify user
            # first find out which of all servers states is the worst similar to nagstamonObjects.GetStatus()
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
                    self.NotificationOn(status=worst_status)

            # set self.showPopwin to True because there is something to show
            self.popwin.showPopwin = True

        # if only one monitor cannot be reached show popwin to inform about its trouble
        for server in self.servers.values():
            if server.status_description != "" or server.refresh_authentication == True:
                self.status_ok = False
                self.popwin.showPopwin = True

        # close popwin in case everything is ok and green
        if self.status_ok and not self.popwin.showPopwin:
            self.popwin.Close()

        # try to fix vanishing statusbar
        if str(self.conf.icon_in_systray) == "False":
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
            self.acknowledge_xml.get_object("input_label_host").set_text(host)
            self.acknowledge_xml.get_object("label_service").hide()
            self.acknowledge_xml.get_object("input_label_service").hide()
            self.acknowledge_dialog.set_title("Acknowledge host")
        else:
            # set label for acknowledging a service on host
            self.acknowledge_xml.get_object("input_label_host").set_text(host)
            self.acknowledge_xml.get_object("input_label_service").set_text(service)
            self.acknowledge_dialog.set_title("Acknowledge service")

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
        settings=Settings(servers=self.servers, output=self, conf=self.conf, first_page="Defaults")


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
            self.downtime_xml.get_object("input_label_host").set_text(host)
            self.downtime_xml.get_object("label_service").hide()
            self.downtime_xml.get_object("input_label_service").hide()
            self.downtime_dialog.set_title("Downtime for host")
        else:
            # set label for acknowledging a service on host
            self.downtime_xml.get_object("input_label_host").set_text(host)
            self.downtime_xml.get_object("input_label_service").set_text(service)
            self.downtime_dialog.set_title("Downtime for service")

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
        settings=Settings(servers=self.servers, output=self, conf=self.conf, first_page="Defaults")


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
            self.submitcheckresult_xml.get_object("input_label_host").set_text(host)
            self.submitcheckresult_xml.get_object("label_service").hide()
            self.submitcheckresult_xml.get_object("input_label_service").hide()
            self.submitcheckresult_dialog.set_title("Submit check result for host")
            self.submitcheckresult_xml.get_object("label_service").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_ok").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_warning").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_critical").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_unknown").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_up").set_active(True)
        else:
            # set label for submitting results to a service on host
            self.submitcheckresult_xml.get_object("input_label_host").set_text(host)
            self.submitcheckresult_xml.get_object("input_label_service").set_text(service)
            self.submitcheckresult_dialog.set_title("Submit check result for service")
            self.submitcheckresult_xml.get_object("input_radiobutton_result_unreachable").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_up").hide()
            self.submitcheckresult_xml.get_object("input_radiobutton_result_down").hide()
        for i in server.SUBMIT_CHECK_RESULT_ARGS:
            self.submitcheckresult_xml.get_object("label_" + i).show()
            self.submitcheckresult_xml.get_object("input_entry_" + i).show()

        self.submitcheckresult_xml.get_object("input_entry_comment").set_text(self.conf.defaults_submit_check_result_comment)

        # show dialog
        self.submitcheckresult_dialog.run()


    def SubmitCheckResultDefaultSettings(self, foo, bar):
        """
        show settings with tab "defaults" as shortcut from Submit Check Result dialog
        """
        self.submitcheckresult_dialog.destroy()
        settings=Settings(servers=self.servers, output=self, conf=self.conf, first_page="Defaults")


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
        about.set_name(self.name)
        about.set_version(self.version)
        about.set_website(self.website)
        about.set_copyright(self.copyright)
        about.set_comments(self.comments)
        about.set_authors(["Henri Wahl",\
                           " ",\
                           "Thank you very much for code",\
                           "contributions, patches, packaging,",\
                           "testing, hints and ideas:",\
                           " ",\
                           "Antoine Jacoutot",\
                           "Benoît Soenen",\
                           "Carl Chenet",\
                           "Emile Heitor ",\
                           "John Conroy",\
                           "Lars Michelsen",\
                           "M. Cigdem Cebe",\
                           "Mattias Ryrlén",\
                           "Michał Rzeszut",\
                           "Patrick Cernko",\
                           "Pawel Połewicz",\
                           "Robin Sonefors",\
                           "Sandro Tosi",\
                           "Thomas Gelf",\
                           "Tobias Scheerbaum",\
                           "Yannick Charton",\
                           " ",\
                           "...and those I forgot to mention but who helped a lot...",
                           " ",\
                           "Third party software used by Nagstamon",\
                           "under their respective license:",\
                           "BeautifulSoup - http://www.crummy.com/software/BeautifulSoup",\
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
        #self.popwin.Close()
        self.popwin.PopDown()
        about.run()
        # use gobject.idle_add() to be thread safe
        gobject.idle_add(self.DeleteGUILock, str(self.__class__.__name__))
        about.destroy()


    def Dialog(self, type=gtk.MESSAGE_ERROR, message="", buttons=gtk.BUTTONS_CANCEL):
        """
            versatile message dialog
        """
        # close popwin to make sure the error dialog will not be covered by popwin
        #self.popwin.Close()
        self.popwin.PopDown()

        dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=type, buttons=buttons, message_format=str(message))
        # gtk.Dialog.run() does a mini loop to wait
        dialog.run()
        dialog.destroy()


    def CheckForNewVersionDialog(self, version_status=None, version=None):
        """
            Show results of Settings.CheckForNewVersion()
        """
        try:
            # close popwin to make sure the error dialog will not be covered by popwin
            #self.popwin.Close()
            self.popwin.PopDown()

            # if used version is latest version only inform about
            if version_status == "latest":
                dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_INFO, buttons=gtk.BUTTONS_OK, \
                                           message_format="You are already using the\nlatest version of Nagstamon.\n\nLatest version: %s" % (version))
                dialog.run()
                dialog.destroy()
            # if used version is out of date offer downloading latest one
            elif version_status == "out_of_date":
                dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_YES_NO, \
                                           message_format="You are not using the latest version of Nagstamon.\n\nYour version:\t\t%s\nLatest version:\t%s\n\nDo you want to download the latest version?" % (self.version, version))
                response = dialog.run()
                if response == gtk.RESPONSE_YES:
                    Actions.OpenNagstamonDownload(output=self)
                dialog.destroy()
        except:
            self.servers.values()[0].Error(sys.exc_info())


    def NotificationOn(self, status="UP"):
        """
            switch on whichever kind of notification
        """
        try:
            # check if notification for status is wanted
            if not status == "UP" and str(self.conf.__dict__["notify_if_" + status.lower()]) == "True":
                # only notify if popwin not already popped up
                if self.popwin.Window.get_properties("visible")[0] == False:
                    if self.Notifying == False:
                        self.Notifying = True
                        # debug
                        if str(self.conf.debug_mode) == "True":
                            self.servers.values()[0].Debug(debug="Notification on.")
                        # threaded statusbar flash
                        if str(self.conf.notification_flashing) == "True":
                            self.statusbar.SysTray.set_blinking(True)
                            self.statusbar.Flashing = True

                        notify = Actions.Notification(output=self, sound=status, Resources=self.Resources, conf=self.conf, servers=self.servers)
                        notify.start()

                        # if desired pop up status window
                        # sorry but does absolutely not work with windows and systray icon so I prefer to let it be
                        #if str(self.conf.notification_popup) == "True":
                        #    self.popwin.showPopwin = True
                        #    self.popwin.PopUp()
        except:
            self.servers.values()[0].Error(sys.exc_info())


    def NotificationOff(self):
        """
            switch off whichever kind of notification
        """
        if self.Notifying == True:
            self.Notifying = False
            # debug
            if str(self.conf.debug_mode) == "True":
                self.servers.values()[0].Debug(debug="Notification on.")
            self.statusbar.SysTray.set_blinking(False)
            self.statusbar.Flashing = False
            self.statusbar.Label.set_markup(self.statusbar.statusbar_labeltext)
            # resize statusbar to avoid artefact when showing error
            self.statusbar.Resize()


    def RecheckAll(self, widget=None):
        """
        call threaded recheck all action
        """
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


    def DeleteGUILock(self, window_name):
        """
        delete calling window from dictionary of open windows to keep the windows separated
        to be called via gobject.idle_add
        """
        try:
            self.GUILock.pop(window_name)
        except:
            pass


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

        print dummy
        self.conf.SaveConfig(output=self)
        gtk.main_quit()


class StatusBar(object):
    """
        statusbar object with appended systray icon
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        # TrayIcon - appears as status bar in Windows due to non existent egg.trayicon python module
        if platform.system() == "Windows":
            self._CreateFloatingStatusbar()
        else:
            if str(self.conf.statusbar_systray) == "True":
                try:
                    self.StatusBar = egg.trayicon.TrayIcon(self.output.name)
                except:
                    print "python gnome2 extras with egg.trayicon not installed so trayicon cannot be used. Using floating desktop status bar instead."
                    self._CreateFloatingStatusbar()
            else:
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
        if str(self.conf.statusbar_systray) == "True" or str(self.conf.statusbar_floating) == "True":
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

        # adapt label font size to nagstamon logo height because on different platforms
        # default sizes + fonts vary
        try:
            fontsize = 7000
            self.Label.set_markup('<span size="%s"> Loading... </span>' % (fontsize))
            # compare heights, height of logo is the important one
            while self.LogoEventbox.size_request()[1] > self.Label.size_request()[1]:
                self.Label.set_markup('<span size="%s"> Loading... </span>' % (fontsize))
                fontsize += 250
            self.output.fontsize = fontsize
        except:
            # in case of error define fixed fontsize
            self.output.fontsize = 10000

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
        if menu_entry == "Settings...": Settings(servers=self.output.servers, output=self.output, conf=self.conf)
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
        # check if settings a d other dialogs are not already open
        if self.output.popwin.IsWanted() == True:
            # if popwin is not shown pop it up
            if self.output.popwin.Window.get_properties("visible")[0] == False or len(self.output.GUILock) == 0:
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
                if not "Menu" in dir(self):
                    self.StatusBar.window.raise_()
            # on Linux & Co. only raise if popwin is not shown because otherwise
            # the statusbar shadow overlays the popwin on newer desktop environments
            elif self.output.popwin.showPopwin == False:
                self.StatusBar.window.raise_()


class _Window(gtk.Window):
    """
    derived from gtk.Window for modifying .destroy() method, because otherwise Nagstamon stopped running with
    every display mode change
    """
    # when OKing settings destroy() gets called twice and the first time without "settings" mode set
    # so it Nagstamon soon gets gtk.main_quit()
    # destroycount helps against premature exits.
    destroycount = 0


    def destroy(self, widget=None, mode="", conf=None):
        print "\n", mode, str(conf.maximized_window), widget, self.destroycount, "\n"

        if mode != "settings" and str(conf.maximized_window) == "True":
            if platform.system() == "Windows" and self.destroycount > 0:
                self.destroycount = 0
                conf.SaveConfig()
                gtk.main_quit()
                print "windows"
            elif platform.system() != "Windows" and self.destroycount > 0:
                self.destroycount = 0
                print "nonwindows"
                conf.SaveConfig()
                gtk.main_quit()
        time.sleep(1)
        print self.destroycount
        self.destroycount += 1

        gtk.Window.destroy(self)


class Popwin(object):
    """
    Popwin object
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        self.Window = self._CreatePopwin()

        # initialize the coordinates of left upper corner of the popwin and its size
        self.popwinx0 = self.popwiny0 = 0
        self.popwinwidth = self.popwinheight = 0

        self.AlMonitorLabel = gtk.Alignment(xalign=0, yalign=0.5)
        self.AlMonitorComboBox = gtk.Alignment(xalign=0, yalign=0.5)
        self.AlMenu = gtk.Alignment(xalign=1.0, yalign=0.5)
        self.AlVBox = gtk.Alignment(xalign=0.5, yalign=0, xscale=1, yscale=0)

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
        self.NagstamonVersion = gtk.Label("  " + self.output.version)

        self.HBoxNagiosButtons.add(self.NagstamonLabel)
        self.HBoxNagiosButtons.add(self.NagstamonVersion)

        self.AlMonitorLabel.add(self.HBoxNagiosButtons)
        self.ComboboxMonitor = gtk.combo_box_new_text()
        # fill Nagios server combobox with nagios servers
        self.ComboboxMonitor.append_text("Choose monitor...")
        submenu_items = list(self.output.servers)
        submenu_items.sort(key=str.lower)
        for i in submenu_items:
            self.ComboboxMonitor.append_text(i)
        # set first item active
        self.ComboboxMonitor.set_active(0)
        self.HBoxCombobox.add(self.ComboboxMonitor)
        self.AlMonitorComboBox.add(self.HBoxCombobox)

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

        if str(self.output.conf.maximized_window) == "True":
            self.ButtonMenu = ButtonWithIcon(output=self.output, label="", icon="menu.png")
            self.HBoxMenu.add(self.ButtonMenu)
            #self.ButtonMenu.connect("clicked", self.MenuPopUp)
            self.ButtonMenu.connect("button-press-event", self.MenuPopUp)
        else:
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
        self.HBoxAllButtons.add(self.AlMonitorComboBox)
        self.HBoxAllButtons.add(self.AlMenu)

        # threaded recheck all when refresh is clicked
        self.ButtonRecheckAll.connect("clicked", self.output.RecheckAll)
        # threaded refresh status information when refresh is clicked
        self.ButtonRefresh.connect("clicked", lambda r: Actions.RefreshAllServers(servers=self.output.servers, output=self.output, conf=self.conf))
        # open settings dialog when settings is clicked
        self.ButtonSettings.connect("clicked", lambda s: Settings(servers=self.output.servers, output=self.output, conf=self.conf))
        # open settings dialog for filters when filters is clicked
        self.ButtonFilters.connect("clicked", lambda s: Settings(servers=self.output.servers, output=self.output, conf=self.conf, first_page="Filters"))

        # Workaround for behavorial differences of GTK in Windows and Linux
        # in Linux it is enough to check for the pointer leaving the whole popwin,
        # in Windows it is not, here every widget on popwin has to be heard
        # the intended effect is that popwin closes when the pointer leaves it
        self.ButtonRefresh.connect("leave-notify-event", self.LeavePopWin)
        self.ButtonSettings.connect("leave-notify-event", self.LeavePopWin)


        # define colors for detailed status table in dictionaries
        # need to be redefined here for MacOSX because there it is not
        # possible to reinitialize the whole GUI after config changes without a crash
        self.output.TAB_BG_COLORS = { "UNKNOWN":str(self.conf.color_unknown_background), "CRITICAL":str(self.conf.color_critical_background), "WARNING":str(self.conf.color_warning_background), "DOWN":str(self.conf.color_down_background), "UNREACHABLE":str(self.conf.color_unreachable_background)  }
        self.output.TAB_FG_COLORS = { "UNKNOWN":str(self.conf.color_unknown_text), "CRITICAL":str(self.conf.color_critical_text), "WARNING":str(self.conf.color_warning_text), "DOWN":str(self.conf.color_down_text), "UNREACHABLE":str(self.conf.color_unreachable_text) }

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

        # group server infos in VBoxes
        self.ServerVBoxes = dict()

        # to sort the Nagios servers alphabetically make a sortable list of their names
        server_list = list(self.output.servers)
        server_list.sort(key=str.lower)

        # create table with all the displayed info
        for item in server_list:
            # get the servers alphabetically sorted
            server = self.output.servers[item]
            # put all infos into one VBox object
            self.ServerVBoxes[server.get_name()] = ServerVBox(output=self.output, server=server)
            self.ServerVBoxes[server.get_name()].Label.set_markup('<span weight="bold" size="large">' + server.get_username() + "@" + server.get_name() + '</span>')
            self.ServerVBoxes[server.get_name()].Label.set_alignment(0,0)
            # set no show all to be able to hide label and treeview if it is empty in case of no hassle
            self.ServerVBoxes[server.get_name()].set_no_show_all(True)

            # connect buttons with actions
            # open Nagios main page in your favorite web browser when nagios button is clicked
            self.ServerVBoxes[server.get_name()].ButtonMonitor.connect("clicked", server.OpenBrowser, "monitor", self.output)
            # open Nagios services in your favorite web browser when service button is clicked
            self.ServerVBoxes[server.get_name()].ButtonServices.connect("clicked", server.OpenBrowser, "services", self.output)
            # open Nagios hosts in your favorite web browser when hosts button is clicked
            self.ServerVBoxes[server.get_name()].ButtonHosts.connect("clicked", server.OpenBrowser, "hosts", self.output)
            # open Nagios history in your favorite web browser when hosts button is clicked
            self.ServerVBoxes[server.get_name()].ButtonHistory.connect("clicked", server.OpenBrowser, "history", self.output)
            # OK button for monitor credentials refreshment or when "Enter" being pressed in password field
            self.ServerVBoxes[server.get_name()].AuthButtonOK.connect("clicked", self.ServerVBoxes[server.get_name()].AuthOK, server)
            # jump to password entry field if Return has been pressed on username entry field
            self.ServerVBoxes[server.get_name()].AuthEntryUsername.connect("key-release-event", self.ServerVBoxes[server.get_name()].AuthUsername)
            # for some reason signal "editing done" does not work so we need to check if Return has been pressed
            self.ServerVBoxes[server.get_name()].AuthEntryPassword.connect("key-release-event", self.ServerVBoxes[server.get_name()].AuthPassword, server)
            # windows workaround - see above
            # connect Server_EventBox with leave-notify-event to get popwin popping down when leaving it
            self.ServerVBoxes[server.get_name()].Server_EventBox.connect("leave-notify-event", self.PopDown)
            # sorry folks, but this only works at the border of the treeviews
            self.ServerVBoxes[server.get_name()].TreeView.connect("leave-notify-event", self.PopDown)
            # connect the treeviews of the servers to mouse clicks
            self.ServerVBoxes[server.get_name()].TreeView.connect("button-press-event", self.ServerVBoxes[server.get_name()].TreeviewPopupMenu, self.ServerVBoxes[server.get_name()].TreeView, self.output.servers[server.get_name()])

            # add box to the other ones
            self.ScrolledVBox.add(self.ServerVBoxes[server.get_name()])

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

        if str(self.output.conf.maximized_window) == "True":
            # Popup menu instead statusbar menu  for maximized window view
            self.Menu = gtk.Menu()
            for i in ["Save position", "About", "Exit"]:
                if i == "-----":
                    menu_item = gtk.SeparatorMenuItem()
                    self.Menu.append(menu_item)
                else:
                    menu_item = gtk.MenuItem(i)
                    menu_item.connect("activate", self.MenuResponse, i)
                    self.Menu.append(menu_item)

            self.Menu.show_all()


    def _CreatePopwin(self, x0=0, y0=0, width=0, height=0):
        """
            Create popup window
        """

        # Initialize type popup
        if platform.system() == "Darwin":
            #window = gtk.Window(gtk.WINDOW_POPUP)
            window = _Window(gtk.WINDOW_POPUP)
        else:
            #window = gtk.Window(gtk.WINDOW_TOPLEVEL)
            window = _Window(gtk.WINDOW_TOPLEVEL)
            window.set_title(self.output.name + " " + self.output.version)

        if str(self.output.conf.maximized_window) == "False":
            # for not letting statusbar throw a shadow onto popwin in any composition-window-manager this helps to
            # keep a more consistent look - copied from StatusBar... anyway, doesn't work... well, next attempt:
            # Windows will have an entry on taskbar when not using HINT_UTILITY
            if platform.system() == "Windows":
                window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
            else:
                window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_MENU)

            # make a nice popup of the toplevel window
            window.set_decorated(False)
            window.set_keep_above(True)
            # newer Ubuntus place a resize widget onto floating statusbar - please don't!
            window.set_resizable(False)
            window.set_property("skip-taskbar-hint", True)
            window.stick()
            window.set_skip_taskbar_hint(True)
            window.set_size_request(width, height)
            window.move(x0, y0)
            window.connect("leave-notify-event", self.LeavePopWin)
        else:
            window.move(int(self.output.conf.maximized_window_x0), int(self.output.conf.maximized_window_y0))
            # fullscreen does not work at least with GNOME, Windows is OK
            if platform.system() != "Windows":
                window.maximize()
            else:
                window.fullscreen()
            # give conf to custom destroy method so it can find out if maximized window mode is enabled
            window.connect("destroy", window.destroy, "close", self.output.conf)
            window.show_all()
            window.set_visible(True)

        return window


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


    def RefreshMaximizedWindow(self, widget=None, event=None):
        """
        refresh maximized window
        """

        #if platform.system != "Windows":
        # get current monitor's settings
        # screeny0 might be important on more-than-one-monitor-setups where it will not be 0
        x0, y0 = self.Window.get_position()
        w, h = self.Window.get_size()
        screenx0, screeny0, screenwidth, screenheight = self.output.monitors[self.Window.get_screen().get_monitor_at_point(x0,y0)]

        # limit size of scrolled vbox
        vboxwidth, vboxheight = self.ScrolledVBox.size_request()
        if vboxwidth > screenwidth: vboxwidth = screenwidth

        # get dimensions of top button bar
        self.buttonswidth, self.buttonsheight = self.HBoxAllButtons.size_request()

        # later GNOME might need some extra heightbuffer if using dual screen
        if vboxheight > screenheight - self.buttonsheight - self.heightbuffer_external - self.heightbuffer_internal:
            # helpless attempt to get window fitting on screen if not maximized on newer unixoid DEs by doubling
            # external heightbuffer
            # leads to silly grey unused whitespace on GNOME3 dualmonitor, but there is still some information visisble..
            # let's call this a feature no bug
            vboxheight = screenheight - self.buttonsheight - 2*self.heightbuffer_external - self.heightbuffer_internal
        else:
            # avoid silly scrollbar
            vboxheight += self.heightbuffer_internal

        self.ScrolledWindow.set_size_request(-1, vboxheight)

        self.Window.set_size_request(self.buttonswidth, -1)

        self.Window.show_all()
        self.Window.set_visible(True)

        # shrink window
        w, h = self.Window.get_size()
        self.Window.resize(w, 1)

        # to be saved with configuration
        self.output.conf.maximized_window_x0, self.output.conf.maximized_window_y0 = self.Window.get_position()


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

        if str(self.output.conf.maximized_window) == "False":
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
        if str(self.output.conf.maximized_window) == "False":
            # unregister popwin - seems to be called even if popwin is not open so check before unregistering
            if self.output.GUILock.has_key("Popwin"):
                # use gobject.idle_add() to be thread safe
                gobject.idle_add(self.output.DeleteGUILock, self.__class__.__name__)
            #self.Window.hide_all()
            self.Window.set_visible(False)
            # notification off because user had a look to hosts/services recently
            self.output.NotificationOff()


    def Resize(self):
        """
            calculate popwin dimensions depending on the amount of information displayed in scrollbox
            only if popwin is visible
        """
        # the popwin should always pop up near the systray/desktop status bar, therefore we
        # need to find out its position

        # find out dimension of all monitors
        for m in range(self.output.statusbar.StatusBar.get_screen().get_n_monitors()):
            monx0, mony0, monw, monh = self.output.statusbar.StatusBar.get_screen().get_monitor_geometry(m)
            self.output.monitors[m] = (monx0, mony0, monw, monh)

        # get x0 and y0 - workaround for gtk trayicon because self.statusbar as trayicon
        # cannot get its absolute position, so we need to get pointers position relative
        # to root window and to trayicon and subtract them and save the values in the
        # self.statusbar object to avoid jumping popwin in case it is open, the status
        # refreshed and the pointer has moved
        if self.calculate_coordinates == True:
            # check if icon in systray or statusbar
            if str(self.conf.icon_in_systray) == "True":

                # trayicon seems not to have a .get_pointer() method so we use
                # its geometry information
                if platform.system() == "Windows":
                    # otherwise this does not work in windows
                    rootwin = self.output.statusbar.StatusBar.get_screen().get_root_window()
                    mousex, mousey, foo = rootwin.get_pointer()
                    statusbar_mousex, statusbar_mousey = 0, int(self.conf.systray_popup_offset)
                else:
                    mousex, mousey, foo, bar = self.output.statusbar.SysTray.get_geometry()[1]
                    statusbar_mousex, statusbar_mousey = 0, int(self.conf.systray_popup_offset)
                # set monitor for later applying the correct monitor geometry
                self.output.current_monitor = self.output.statusbar.StatusBar.get_screen().get_monitor_at_point(mousex, mousey)

                statusbarx0 = mousex - statusbar_mousex
                statusbary0 = mousey - statusbar_mousey

            else:
                mousex, mousey, foo = self.output.statusbar.StatusBar.get_screen().get_root_window().get_pointer()

                # set monitor for later applying the correct monitor geometry
                self.output.current_monitor = self.output.statusbar.StatusBar.get_screen().get_monitor_at_point(mousex, mousey)

                statusbar_mousex, statusbar_mousey = self.output.statusbar.StatusBar.get_pointer()

                statusbarx0 = mousex - statusbar_mousex
                statusbary0 = mousey - statusbar_mousey

                # save trayicon x0 and y0 in self.statusbar
                self.output.statusbar.StatusBar.x0 = statusbarx0
                self.output.statusbar.StatusBar.y0 = statusbary0

                # set back to False to do recalculation of coordinates as long as popwin is opened
                self.calculate_coordinates = False

        else:
            # use previously saved values for x0 and y0 in case popwin is still/already open
            statusbarx0 = self.output.statusbar.StatusBar.x0
            statusbary0 = self.output.statusbar.StatusBar.y0

        # find out the necessary dimensions of popwin - assembled from scroll area and the buttons
        treeviewwidth, treeviewheight = self.ScrolledVBox.size_request()

        # get current monitor's settings
        # screeny0 might be important on more-than-one-monitor-setups where it will not be 0
        screenx0, screeny0, screenwidth, screenheight = self.output.monitors[self.output.current_monitor]

        # get dimensions of statusbar
        if str(self.conf.icon_in_systray) == "True":
            statusbarwidth, statusbarheight = 25, 25
        else:
            statusbarwidth, statusbarheight = self.output.statusbar.StatusBar.get_size()

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

        # after having determined dimensions of scrolling area apply them
        self.ScrolledWindow.set_size_request(treeviewwidth, treeviewheight)

        # care about the height of the buttons
        self.popwinwidth, self.popwinheight = treeviewwidth, treeviewheight + self.buttonsheight

        # if popwinwidth is to small the buttons inside could be scrambled, so we give
        # it a minimum width from head buttons
        if self.popwinwidth < self.buttonswidth: self.popwinwidth = self.buttonswidth

        # if popwin is too wide cut it down to screen width
        if self.popwinwidth > screenwidth:
            self.popwinwidth = screenwidth

        # if statusbar/trayicon stays in upper half of screen, popwin pops up BELOW statusbar/trayicon
        if (statusbary0 + statusbarheight - screeny0) < (screenheight / 2):
            # if popwin is too large it gets cut at lower end of screen
            if (statusbary0 + self.popwinheight + statusbarheight) > screenheight:
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

        # after having determined dimensions of scrolling area apply them
        self.ScrolledWindow.set_size_request(treeviewwidth, treeviewheight)

        # decide x position of popwin
        if (statusbarx0) + statusbarwidth / 2 + (self.popwinwidth) / 2 > (screenwidth + screenx0):
            self.popwinx0 = screenwidth - self.popwinwidth + screenx0
        elif (statusbarx0 + statusbarwidth / 2)- self.popwinwidth / 2 < screenx0:
            self.popwinx0 = screenx0
        else:
            self.popwinx0 = statusbarx0 + (screenx0 + statusbarwidth) / 2 - (self.popwinwidth + screenx0) / 2

        if str(self.output.conf.maximized_window) == "False":
            # set size request of popwin
            self.Window.set_size_request(self.popwinwidth, self.popwinheight)

            if self.Window.get_properties("visible")[0] == True:
                self.Window.window.move_resize(self.popwinx0, self.popwiny0, self.popwinwidth, self.popwinheight)

                # if popwin is misplaced please correct it here
                if self.Window.get_position() != (self.popwinx0, self.popwiny0):
                    # would be nice if there could be any way to avoid flickering...
                    # but move/resize only works after a hide_all()/showe_all() mantra
                    self.Window.hide_all()
                    self.Window.show_all()
                    self.Window.window.move_resize(self.popwinx0, self.popwiny0, self.popwinwidth, self.popwinheight)

            # statusbar pulls popwin to the top... with silly-windows-workaround(tm) included
            if str(self.conf.icon_in_systray) == "False": self.output.statusbar.Raise()

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
            self.output.servers[model.get_value(active, 0)].OpenBrowser(url_type="monitor")
        except:
            self.output.servers.values()[0].Error(sys.exc_info())


    def UpdateStatus(self, server):
        """
            Updates status field of a server
        """
        # status field in server vbox in popwin
        try:
            # kick out final "\n" for nicer appearance
            self.ServerVBoxes[server.get_name()].LabelStatus.set_markup('<span> Status: ' + str(server.status) + ' <span color="darkred">' + str(server.status_description).rsplit("\n", 1)[0] + '</span></span>')
        except:
            server.Error(sys.exc_info())


    def IsWanted(self):
        """
        check if no other dialog/menu is shown which would not like to be
        covered by the popup window
        """
        if len(self.output.GUILock) == 0 or "Popwin" in self.output.GUILock:
            return True
        else:
            return False


    def GetVisibleServerVBoxes(self):
        """
        return list of visible server VBoxes
        """
        visible_servervboxes = list()
        for servervbox in self.ServerVBoxes.values():
            if servervbox.get_visible() == True:
                visible_servervboxes.append(servervbox)
        return visible_servervboxes


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
        # once again a Windows(TM) workaround
        self.Server_EventBox = gtk.EventBox()

        # create icony buttons
        self.ButtonMonitor = ButtonWithIcon(output=self.output, label="Monitor", icon="nagios.png")
        self.ButtonHosts = ButtonWithIcon(output=self.output, label="Hosts", icon="hosts.png")
        self.ButtonServices = ButtonWithIcon(output=self.output, label="Services", icon="services.png")
        self.ButtonHistory = ButtonWithIcon(output=self.output, label="History", icon="history.png")

        # Label with status information
        self.LabelStatus = gtk.Label("")

        # order the elements
        # now vboxing the elements to add a line in case authentication failed - so the user should auth here again
        self.VBox = gtk.VBox()
        # first line for usual monitor shortlink buttons
        #self.HBox = gtk.HBox(homogeneous=True)
        self.HBox = gtk.HBox()
        self.HBoxLeft = gtk.HBox()
        self.HBoxRight = gtk.HBox()
        self.HBoxLeft.add(self.Label)
        # leave some space around the label
        self.Label.set_padding(5, 5)
        self.HBoxLeft.add(self.ButtonMonitor)
        self.HBoxLeft.add(self.ButtonHosts)
        self.HBoxLeft.add(self.ButtonServices)
        self.HBoxLeft.add(self.ButtonHistory)
        self.HBoxLeft.add(gtk.VSeparator())
        self.HBoxLeft.add(self.LabelStatus)

        self.AlignmentLeft = gtk.Alignment(xalign=0, xscale=0.05, yalign=0)
        self.AlignmentLeft.add(self.HBoxLeft)
        self.AlignmentRight = gtk.Alignment(xalign=0, xscale=0.0, yalign=0.5)
        self.AlignmentRight.add(self.HBoxRight)

        self.HBox.add(self.AlignmentLeft)
        self.HBox.add(self.AlignmentRight)

        self.VBox.add(self.HBox)

        # Auth line
        self.HBoxAuth = gtk.HBox()
        self.AuthLabelUsername = gtk.Label("Username:")
        self.AuthEntryUsername = gtk.Entry()
        self.AuthEntryUsername.set_can_focus(True)
        self.AuthLabelPassword = gtk.Label("Password:")
        self.AuthEntryPassword = gtk.Entry()
        self.AuthEntryPassword.set_visibility(False)
        self.AuthCheckbuttonSave = gtk.CheckButton("Save password")
        self.AuthButtonOK = gtk.Button("OK")

        self.HBoxAuth.add(self.AuthLabelUsername)
        self.HBoxAuth.add(self.AuthEntryUsername)
        self.HBoxAuth.add(self.AuthLabelPassword)
        self.HBoxAuth.add(self.AuthEntryPassword)
        self.HBoxAuth.add(self.AuthCheckbuttonSave)
        self.HBoxAuth.add(self.AuthButtonOK)

        self.AlignmentAuth = gtk.Alignment(xalign=0, xscale=0.05, yalign=0)
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
        # enable grid lines
        if str(self.output.conf.show_grid) == "True":
            self.server.TreeView.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)
        else:
            self.server.TreeView.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_NONE)
        # Liststore
        self.server.ListStore = gtk.ListStore(*self.output.LISTSTORE_COLUMNS)

        # offset to access host and service flag icons separately, stored in grand liststore
        # may grow with more supported flags
        offset_img = {0:0, 1:len(self.output.STATE_ICONS)}

        # offset for alternate column colors could increase readability
        # even and odd columns are calculated by column number
        offset_color = {0:8, 1:9}

        for s, column in enumerate(self.server.COLUMNS):
            tab_column = gtk.TreeViewColumn(column.get_label())
            self.server.TreeView.append_column(tab_column)
            # the first and second column hold hosts and service name which will get acknowledged/downtime flag
            # indicators added
            if s in [0, 1]:
                # pixbuf for little icon
                cell_img_ack = gtk.CellRendererPixbuf()
                cell_img_down = gtk.CellRendererPixbuf()
                cell_img_flap = gtk.CellRendererPixbuf()
                cell_img_pass = gtk.CellRendererPixbuf()
                # host/service name
                cell_txt = gtk.CellRendererText()
                # stuff all renders into one cell
                tab_column.pack_start(cell_txt, False)
                tab_column.pack_start(cell_img_ack, False)
                tab_column.pack_start(cell_img_down, False)
                tab_column.pack_start(cell_img_flap, False)
                tab_column.pack_start(cell_img_pass, False)
                # set text from liststore and flag icons if existing
                # why ever, in Windows(TM) the background looks better if applied separately
                # to be honest, even looks better in Linux
                tab_column.set_attributes(cell_txt, foreground=7, text=s)
                tab_column.add_attribute(cell_txt, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_ack, pixbuf=10+offset_img[s])
                tab_column.add_attribute(cell_img_ack, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_down, pixbuf=11+offset_img[s])
                tab_column.add_attribute(cell_img_down, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_flap, pixbuf=12+offset_img[s])
                tab_column.add_attribute(cell_img_flap, "cell-background", offset_color[s % 2])
                tab_column.set_attributes(cell_img_pass, pixbuf=13+offset_img[s])
                tab_column.add_attribute(cell_img_pass, "cell-background", offset_color[s % 2])
                tab_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
            else:
                # normal way for all other columns
                cell_txt = gtk.CellRendererText()
                tab_column.pack_start(cell_txt, False)
                tab_column.set_attributes(cell_txt, foreground=7, text=s)
                tab_column.add_attribute(cell_txt, "cell-background", offset_color[s % 2 ])
                tab_column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)

            # set customized sorting
            if column.has_customized_sorting():
                self.server.ListStore.set_sort_func(s, column.sort_function, s)

            # make table sortable by clicking on column headers
            tab_column.set_clickable(True)
            #tab_column.set_property('sort-indicator', True) # makes sorting arrows visible
            tab_column.connect('clicked', self.output.on_column_header_click, s, self.server.ListStore, self.server)

        # the whole TreeView memory leaky complex...
        self.TreeView = self.server.TreeView
        self.ListStore = self.server.ListStore

        self.add(self.TreeView)


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

            # add custom actions - this is just a test!
            actions_list=list(self.output.conf.actions)
            actions_list.sort(key=str.lower)
            for a in actions_list:
                # shortcut for next lines
                action = self.output.conf.actions[a]
                if str(action.enabled) == "True":
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
                # recheck is not necessary for passive set checks
                if i == "Recheck" and\
                   self.miserable_service and server.hosts[self.miserable_host].services[self.miserable_service].is_passive_only():
                    pass
                else:
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
                Settings(servers=self.output.servers, output=self.output, conf=self.output.conf, first_page="Actions")
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


class Settings(object):
    """
        settings dialog as object, may lead to less mess
    """

    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # if not given default tab is empty
        if not "first_page" in kwds: self.first_page = ""

        # set the gtkbuilder files
        self.builderfile = self.output.Resources + os.sep + "settings_dialog.ui"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builderfile)
        self.dialog = self.builder.get_object("settings_dialog")

        # use gobject.idle_add() to be thread safe
        gobject.idle_add(self.output.AddGUILock, str(self.__class__.__name__))

        # little feedback store for servers and actions treeviews
        self.selected_server = None
        self.selected_action = None

        # use connect_signals to assign methods to handlers
        handlers_dict = { "button_ok_clicked": self.OK,
                          "settings_dialog_close": self.Cancel,
                          "button_cancel_clicked": self.Cancel,
                          "button_new_server": lambda n: NewServer(servers=self.servers, output=self.output, settingsdialog=self, conf=self.conf),
                          "button_edit_server": lambda e: EditServer(servers=self.servers, output=self.output, server=self.selected_server, settingsdialog=self, conf=self.conf),
                          "button_delete_server": lambda d: self.DeleteServer(self.selected_server, self.conf.servers),
                          "button_check_for_new_version_now": self.CheckForNewVersionNow,
                          "checkbutton_enable_notification": self.ToggleNotification,
                          "checkbutton_enable_sound": self.ToggleSoundOptions,
                          "togglebutton_use_custom_sounds": self.ToggleCustomSoundOptions,
                          "checkbutton_re_host_enabled": self.ToggleREHostOptions,
                          "checkbutton_re_service_enabled": self.ToggleREServiceOptions,
                          "checkbutton_re_status_information_enabled": self.ToggleREStatusInformationOptions,
                          "button_play_sound": self.PlaySound,
                          "checkbutton_debug_mode": self.ToggleDebugOptions,
                          "checkbutton_debug_to_file": self.ToggleDebugOptions,
                          "button_colors_default": self.ColorsDefault,
                          "button_colors_reset": self.ColorsReset,
                          "color-set": self.ColorsPreview,
                          "radiobutton_icon_in_systray_toggled": self.ToggleSystrayPopupOffset,
                          "button_new_action": lambda a: NewAction(output=self.output, settingsdialog=self, conf=self.conf),
                          "button_edit_action": lambda e: EditAction(output=self.output, action=self.selected_action, settingsdialog=self, conf=self.conf),
                          "button_delete_action": lambda d: self.DeleteAction(self.selected_action, self.conf.actions),
                          }
        self.builder.connect_signals(handlers_dict)

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
        notebook = self.builder.get_object("notebook")
        notebook_tabs =  ["Servers", "Display", "Filters", "Actions", "Notification", "Colors", "Defaults"]
        # now this presumably not necessary anymore workaround even gets extended as
        # determine-first-page-mechanism used for acknowledment dialog settings button
        page = 0
        for c in notebook.get_children():
            if notebook_tabs[0] == self.first_page: notebook.set_current_page(page)
            notebook.set_tab_label_text(c, notebook_tabs.pop(0))
            page += 1

        # fill treeviews
        self.FillTreeView("servers_treeview", self.conf.servers, "Servers", "selected_server")
        self.FillTreeView("actions_treeview", self.conf.actions, "Actions", "selected_action")

        # toggle debug options
        self.ToggleDebugOptions()

        # toggle custom sounds options
        self.ToggleCustomSoundOptions()

        # toggle icon in systray popup offset
        self.ToggleSystrayPopupOffset()

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

        # in case nagstamon runs the first time it should display a new server dialog
        if str(self.conf.unconfigured) == "True":
            self.output.statusbar.StatusBar.hide()
            NewServer(servers=self.servers, output=self.output, settingsdialog=self, conf=self.conf)

        # prepare colors and preview them
        self.ColorsReset()

        # disable non useful gui settings
        # statusbar in trayicon is only useful if GNOME egg trayicon is loaded
        if not sys.modules.has_key("egg.trayicon"):
            self.builder.get_object("input_radiobutton_statusbar_systray").hide()
        if platform.system() == "Darwin":
            # MacOS doesn't need any option because there is only floating statusbar possible
            self.builder.get_object("input_radiobutton_icon_in_systray").hide()
            self.builder.get_object("hbox_systray_popup_offset").hide()
            self.builder.get_object("input_radiobutton_statusbar_floating").hide()
            self.builder.get_object("input_radiobutton_maximized_window").hide()
            self.builder.get_object("label_appearance").hide()

        # this should not be necessary, but for some reason the number of hours is 10 in unitialized state... :-(
        spinbutton = self.builder.get_object("input_spinbutton_defaults_downtime_duration_hours")
        spinbutton.set_value(int(self.conf.defaults_downtime_duration_hours))
        spinbutton = self.builder.get_object("input_spinbutton_defaults_downtime_duration_minutes")
        spinbutton.set_value(int(self.conf.defaults_downtime_duration_minutes))

        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()

        # delete global open Windows entry
        # use gobject.idle_add() to be thread safe
        gobject.idle_add(self.output.DeleteGUILock, str(self.__class__.__name__))

        self.dialog.destroy()


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

        # close popwin
        # catch Exception at first run when there cannot exist a popwin
        try:
            self.output.popwin.PopDown()
        except Exception, err:
            print err

        if int(self.conf.update_interval_seconds) <= 0:
            self.conf.update_interval_seconds = 60

        # save settings
        self.conf.SaveConfig(output=self.output)

        # catch exceptions in case of misconfiguration
        try:
            # now it is not the first run anymore
            self.firstrun = False
            self.conf.unconfigured = False
            # create output visuals again because they might have changed (e.g. systray/free floating status bar)
            self.output.statusbar.StatusBar.destroy()
            self.output.statusbar.SysTray.set_visible(False)
            # mode settings tell custom destroy method that no general stop is wanted, just destroy window
            self.output.popwin.Window.destroy(mode="settings", conf=self.output.conf)
            # re-initialize output with new settings
            self.output.__init__()

            # in Windows the statusbar with gtk.gdk.WINDOW_TYPE_HINT_UTILITY places itself somewhere
            # this way it should be disciplined
            self.output.statusbar.StatusBar.move(int(self.conf.position_x), int(self.conf.position_y))

            # start debugging loop if wanted
            if str(self.conf.debug_mode) == "True":
                debugloop = Actions.DebugLoop(conf=self.conf, debug_queue=self.output.debug_queue, output=self.output)
                debugloop.start()

            # force refresh
            Actions.RefreshAllServers(servers=self.servers, output=self.output, conf=self.conf)

        except:
            self.servers.values()[0].Error(sys.exc_info())


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        # when getting cancelled at first run exit immediately because
        # without settings there is not much nagstamon can do
        if self.output.firstrun == True:
            sys.exit()


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
            dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK + gtk.BUTTONS_CANCEL, message_format='Really delete server "' + server + '"?')
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

            dialog.destroy()


    def DeleteAction(self, action=None, actions=None):
        """
            delete action after prompting
        """
        if action:
            dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK + gtk.BUTTONS_CANCEL, message_format='Really delete action "' + action + '"?')
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
                self.check = Actions.CheckForNewVersion(servers=self.servers, output=self.output, mode="normal")
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
        debug_to_file.set_sensitive(debug_mode.get_active())
        debug_file.set_sensitive(debug_to_file.get_active())

        if debug_to_file.state == gtk.STATE_INSENSITIVE:
            debug_file.set_sensitive(False)


    def ToggleNotification(self, widget=None):
        """
            Disable notifications at all
        """
        options = self.builder.get_object("table_notification_options")
        checkbutton = self.builder.get_object("input_checkbutton_notification")
        options.set_sensitive(checkbutton.get_active())


    def ToggleSoundOptions(self, widget=None):
        """
            Disable notification sound when not using sound is enabled
        """
        options = self.builder.get_object("table_notification_options_sound_options")
        checkbutton = self.builder.get_object("input_checkbutton_notification_sound")
        options.set_sensitive(checkbutton.get_active())


    def ToggleCustomSoundOptions(self, widget=None):
        """
            Disable custom notification sound
        """
        options = self.builder.get_object("table_notification_sound_options_custom_sounds_files")
        checkbutton = self.builder.get_object("input_radiobutton_notification_custom_sound")
        options.set_sensitive(checkbutton.get_active())


    def ToggleREHostOptions(self, widget=None):
        """
            Toggle regular expression filter for hosts
        """
        options = self.builder.get_object("hbox_re_host")
        checkbutton = self.builder.get_object("input_checkbutton_re_host_enabled")
        options.set_sensitive(checkbutton.get_active())


    def ToggleREServiceOptions(self, widget=None):
        """
            Toggle regular expression filter for services
        """
        options = self.builder.get_object("hbox_re_service")
        checkbutton = self.builder.get_object("input_checkbutton_re_service_enabled")
        options.set_sensitive(checkbutton.get_active())


    def ToggleREStatusInformationOptions(self, widget=None):
        """
            Disable notification sound when not using sound is enabled
        """
        options = self.builder.get_object("hbox_re_status_information")
        checkbutton = self.builder.get_object("input_checkbutton_re_status_information_enabled")
        options.set_sensitive(checkbutton.get_active())


    def ToggleSystrayPopupOffset(self, widget=None):
        """
            Toggle adjustment for systray-popup-offset (see sf.net bug 3389241)
        """
        options = self.builder.get_object("hbox_systray_popup_offset")
        checkbutton = self.builder.get_object("input_radiobutton_icon_in_systray")
        options.set_sensitive(checkbutton.get_active())


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
        settings of one particuliar new Nagios server
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        # set the gtkbuilder files
        self.builderfile = self.output.Resources + os.sep + "settings_server_dialog.ui"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builderfile)
        self.dialog = self.builder.get_object("settings_server_dialog")

        # assign handlers
        handlers_dict = { "button_ok_clicked" : self.OK,
                          "button_cancel_clicked" : self.Cancel,
                          "settings_dialog_close" : self.Cancel,
                          "toggle_save_password" : self.ToggleSavePassword,
                          "toggle_proxy" : self.ToggleProxy
                          }
        self.builder.connect_signals(handlers_dict)

        # enable server by default
        self.builder.get_object("input_checkbutton_enabled").set_active(True)

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

        # show password - or not
        self.ToggleSavePassword()
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

        # if there is anything to hide hide it
        if len(server.DISABLED_CONTROLS) != 0:
            for item_id in server.DISABLED_CONTROLS:
                item = self.builder.get_object(item_id)
                if item is not None:
                    item.set_visible(False)
        else:
            # in case there is nothing to be hidden enable all possibly hidden items
            for item_id in ["label_monitor_cgi_url", "input_entry_monitor_cgi_url"]:
                item = self.builder.get_object(item_id)
                if item is not None:
                    item.set_visible(True)


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
            # destroy new server dialog
            self.dialog.destroy()


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        if not self.conf.unconfigured == True:
            self.dialog.destroy()
        else:
            sys.exit()


    def ToggleSavePassword(self, widget=None):
        """
            Disable password input box
        """
        checkbutton = self.builder.get_object("input_checkbutton_save_password")
        is_active = checkbutton.get_active()
        item = self.builder.get_object("label_password")
        item.set_sensitive( is_active )
        item = self.builder.get_object("input_entry_password")
        item.set_sensitive( is_active )
        if not is_active:
            item.set_text("")


    def ToggleProxy(self, widget=None):
        """
            Disable proxy options
        """
        checkbutton = self.builder.get_object("input_checkbutton_use_proxy")

        self.ToggleProxyFromOS(checkbutton)
        self.ToggleProxyAddress(checkbutton)


    def ToggleProxyFromOS(self, widget=None):
        """
            toggle proxy from OS when using proxy is enabled
        """
        checkbutton = self.builder.get_object("input_checkbutton_use_proxy_from_os")
        checkbutton.set_sensitive(self.builder.get_object("input_checkbutton_use_proxy").get_active())


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
            item.set_sensitive(state)


class NewServer(GenericServer):
    """
        settings of one particuliar new Nagios server
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        GenericServer.__init__(self, **kwds)

        # set title of settings dialog
        self.dialog.set_title("New server")

        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        self.dialog.destroy()


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

            # show password - or not
            self.ToggleSavePassword()
            # show settings options for proxy - or not
            self.ToggleProxy()

            # show filled settings dialog and wait thanks to gtk.run()
            self.dialog.run()
            self.dialog.destroy()


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
            # destroy dialog
            self.dialog.destroy()


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        self.dialog.destroy()


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

        # assign handlers
        handlers_dict = { "button_ok_clicked" : self.OK,
                          "button_cancel_clicked" : self.Cancel,
                          "settings_dialog_close" : self.Cancel,
                          "checkbutton_re_host_enabled": self.ToggleREHostOptions,
                          "checkbutton_re_service_enabled": self.ToggleREServiceOptions,
                          "checkbutton_re_status_information_enabled": self.ToggleREStatusInformationOptions,
                          "button_help_string_clicked": self.ToggleActionStringHelp,
                          "button_help_type_clicked": self.ToggleActionTypeHelp,
                          }
        self.builder.connect_signals(handlers_dict)

        # enable action by default
        self.builder.get_object("input_checkbutton_enabled").set_active(True)

        # fill combobox with options
        combobox = self.builder.get_object("input_combo_action_type")
        combomodel = gtk.ListStore(gobject.TYPE_STRING)
        cr = gtk.CellRendererText()
        combobox.pack_start(cr, True)
        combobox.set_attributes(cr, text=0)
        for action_type in ["Browser", "Command", "URL"]:
            combomodel.append((action_type,))
        combobox.set_model(combomodel)
        combobox.set_active(0)

        # if uninitialized action (e.g. new one) is used don't access actions dictionary
        if self.action == "":
            # ...but use a dummy object with default settings
            action = Config.Action()
        else:
            action = self.conf.actions[self.action]
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

        # disable help labels for actions
        self.ToggleActionStringHelp()
        self.ToggleActionTypeHelp()


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
        combobox = self.builder.get_object("input_combo_action_type")
        active = combobox.get_active_iter()
        model = combobox.get_model()
        new_action.type = model.get_value(active, 0).lower()

        # check if there is already an action named like the new one
        if new_action.name in self.conf.actions:
            self.output.Dialog(message='An action named "' + new_action.name + '" already exists.')
        else:
            # put in new one
            self.conf.actions[new_action.name] = new_action

            # fill settings dialog treeview
            self.settingsdialog.FillTreeView("actions_treeview", self.conf.actions, "Actions", "selected_action")
            # destroy new action dialog
            self.dialog.destroy()


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        self.dialog.destroy()


    def ToggleREHostOptions(self, widget=None):
        """
            Toggle regular expression filter for hosts
        """
        options = self.builder.get_object("hbox_re_host")
        checkbutton = self.builder.get_object("input_checkbutton_re_host_enabled")
        options.set_sensitive(checkbutton.get_active())


    def ToggleREServiceOptions(self, widget=None):
        """
            Toggle regular expression filter for services
        """
        options = self.builder.get_object("hbox_re_service")
        checkbutton = self.builder.get_object("input_checkbutton_re_service_enabled")
        options.set_sensitive(checkbutton.get_active())


    def ToggleREStatusInformationOptions(self, widget=None):
        """
            Disable notification sound when not using sound is enabled
        """
        options = self.builder.get_object("hbox_re_status_information")
        checkbutton = self.builder.get_object("input_checkbutton_re_status_information_enabled")
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

        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        self.dialog.destroy()


class EditAction(GenericAction):
    """
        generic settings of one particuliar new action server
    """
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]

        GenericAction.__init__(self, **kwds)

        # set title of settings dialog
        self.dialog.set_title("Edit action " + self.action)

        # adjust combobox to used action type
        self.combobox = self.builder.get_object("input_combo_action_type")
        self.combobox.set_active({"browser":0, "command":1, "url":2}[self.conf.actions[self.action].type])

        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        self.dialog.destroy()


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
        combobox = self.builder.get_object("input_combo_action_type")
        active = combobox.get_active_iter()
        model = combobox.get_model()
        new_action.type = model.get_value(active, 0).lower()

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
            self.dialog.destroy()


    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        self.dialog.destroy()


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
                          "button_disable_clicked" : self.Disable
                          }

        self.builder.connect_signals(handlers_dict)

        self.label_monitor = self.builder.get_object("label_monitor")
        self.entry_username = self.builder.get_object("input_entry_username")
        self.entry_password = self.builder.get_object("input_entry_password")

        self.dialog.set_title("Nagstamon authentication for " + self.server.name)
        self.label_monitor.set_text("Please give the correct credentials for "+ self.server.name + ":")
        self.entry_username.set_text(str(self.server.username))
        self.entry_password.set_text(str(self.server.password))

        # omitting .show_all() leads to crash under Linux - why?
        self.dialog.show_all()
        self.dialog.run()
        self.dialog.destroy()


    def OK(self, widget):
        self.server.username = self.entry_username.get_text()
        self.server.password = self.entry_password.get_text()
        toggle_save_password = self.builder.get_object("input_checkbutton_save_password")

        if toggle_save_password.get_active() == True:
            # store authentication information in config
            self.conf.servers[self.server.name].username = self.server.username
            self.conf.servers[self.server.name].password = self.server.password
            self.conf.servers[self.server.name].save_password = True
            self.conf.SaveConfig(output=self.output)


    def Disable(self, widget):
        # the old settings
        self.conf.servers[self.server.name].enabled = False


    def Exit(self, widget):
        gtk.main_quit()
        sys.exit()


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
        hbox = gtk.HBox()
        icon = gtk.Image()
        icon.set_from_file(self.output.Resources + os.sep + self.icon)
        hbox.add(icon)

        if self.label != "":
            label = gtk.Label(" " + self.label)
            hbox.add(label)

        self.set_relief(gtk.RELIEF_NONE)
        self.add(hbox)

