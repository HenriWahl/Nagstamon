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
import gc
import time


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
        self.name = "nagstamon"
        self.version = "0.9.7.1"
        self.website = "http://nagstamon.ifw-dresden.de/"
        self.copyright = "©2008-2011 Henri Wahl\nh.wahl@ifw-dresden.de"
        self.comments = "Nagios status monitor for your desktop"
        
        # get resources directory from current directory - only if not being set before by pkg_resources
        if self.Resources == "":
            if os.path.exists(os.path.normcase(os.getcwd() + os.sep + "Nagstamon" + os.sep + "resources")):
                self.Resources = os.path.normcase(os.getcwd() + os.sep + "Nagstamon" + os.sep + "resources")
            else:
                self.Resources = os.path.normcase(os.getcwd() + os.sep + "resources")
                           

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
        self.CreateOutputVisuals()

        # set size of popup-window
        self.popwin.Resize()
    
        # flag which is set True if already notifying
        self.Notifying = False
        
        # flag if settings dialog is already open to omit various open settings dialogs after systray icon context menu click
        self.SettingsDialogOpen = False       
        # flag if about box is shown
        self.AboutDialogOpen = False
        
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

            
    def CreateOutputVisuals(self):
        """
            create output visuals
        """
        # decide if the platform can handle SVG if not (MacOSX or Windows) use PNG
        if platform.system() == "Darwin" or platform.system() == "Windows":
            self.BitmapSuffix = ".png"
        else:
            self.BitmapSuffix = ".svg"
            
        # set app icon for all app windows
        gtk.window_set_default_icon_from_file(self.Resources + os.sep + "nagstamon" + self.BitmapSuffix)
        
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
        self.statusbar.SysTray.connect("popup-menu", self.statusbar.MenuPopup, self.statusbar.Menu)

        # if pointer clicks on logo move stautsbar
        self.statusbar.LogoEventbox.connect("button-press-event", self.statusbar.LogoClicked)
        self.statusbar.LogoEventbox.connect("button-release-event", self.statusbar.LogoReleased)
    
        # if pointer hovers or clicks statusbar show details
        self.statusbar.EventBoxLabel.connect("enter-notify-event", self.statusbar.Hovered)
        self.statusbar.EventBoxLabel.connect("button-press-event", self.statusbar.Clicked)

        # Workaround for behavorial differences of GTK in Windows and Linux
        # in Linux it is enough to check for the pointer leaving the whole popwin,
        # in Windows it is not, here every widget on popwin has to be heard
        # the intended effect is that popwin closes when the pointer leaves it
        self.popwin.ButtonRefresh.connect("leave-notify-event", self.popwin.PopDown)
        self.popwin.ButtonSettings.connect("leave-notify-event", self.popwin.PopDown)
        self.popwin.ButtonClose.connect("leave-notify-event", self.popwin.PopDown)
        self.popwin.connect("leave-notify-event", self.popwin.PopDown)

        # close popwin when its close button is pressed
        self.popwin.ButtonClose.connect("clicked", self.popwin.Close)
        # threaded recheck all when refresh is clicked
        self.popwin.ButtonRecheckAll.connect("clicked", self.RecheckAll)
        # threaded refresh status information when refresh is clicked
        self.popwin.ButtonRefresh.connect("clicked", lambda r: Actions.RefreshAllServers(servers=self.servers, output=self, conf=self.conf))
        # open settings dialog when settings is clicked
        self.popwin.ButtonSettings.connect("clicked", lambda s: Settings(servers=self.servers, output=self, conf=self.conf))        
        
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
        
        # walk through all servers, their hosts and their services
        for server in self.servers.values():
            # only refresh monitor server output if enabled and only once every server loop
            if str(self.conf.servers[server.get_name()].enabled) == "True":
                try:
                    # otherwise it must be shown, full of problems
                    self.popwin.ServerVBoxes[server.get_name()].show()
                    self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(False)
                    
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
                        self.popwin.ServerVBoxes[server.get_name()].set_no_show_all(True)
                        self.status_ok = True
                    else:
                        # otherwise it must be shown, full of problems
                        self.popwin.ServerVBoxes[server.get_name()].show()
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
                    
                    # after all data from server has been put into Liststore it should be deleted
                    ###server.nagitems_filtered.clear()
                                
                    # give new ListStore to the view, overwrites the old one automatically - theoretically
                    server.TreeView.set_model(server.ListStore)

                    # restore sorting order from previous refresh
                    self.set_sorting(server.ListStore, server)
                    
                    # status field in server vbox in popwin    
                    self.popwin.UpdateStatus(server)
    
                except:
                    server.Error(sys.exc_info())
                    
        # show and resize popwin
        self.popwin.VBox.hide_all()
        self.popwin.VBox.show_all()
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
            self.popwin.Close()
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
            if server.status_description != "":
                self.status_ok = False   
                self.popwin.showPopwin = True
            
        # try to fix Debian bug #591875: eventually ends up lower in the window stacking order, and can't be raised
        # raising statusbar window with every refresh should do the job        
        if str(self.conf.statusbar_floating) == "True": self.statusbar.StatusBar.window.raise_()
        
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
        handlers_dict = { "button_ok_clicked" : self.Acknowledge }
        self.acknowledge_xml.connect_signals(handlers_dict, server)
        
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
        self.acknowledge_xml.get_object("input_checkbutton_sticky_acknowledgement").set_active(True)
        self.acknowledge_xml.get_object("input_checkbutton_send_notification").set_active(True)
        self.acknowledge_xml.get_object("input_checkbutton_persistent_comment").set_active(True)
        self.acknowledge_xml.get_object("input_checkbutton_acknowledge_all_services").set_active(False)

        # default author + comment
        self.acknowledge_xml.get_object("input_entry_author").set_text(server.username)        
        self.acknowledge_xml.get_object("input_entry_comment").set_text("acknowledged")


        # show dialog
        self.acknowledge_dialog.run()
        self.acknowledge_dialog.destroy()

        
    def Acknowledge(self, widget, server):
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
        handlers_dict = { "button_ok_clicked" : self.Downtime }
        self.downtime_xml.connect_signals(handlers_dict, server)
        
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
            
        # default author + comment
        self.downtime_xml.get_object("input_entry_author").set_text(server.username)        
        self.downtime_xml.get_object("input_entry_comment").set_text("scheduled downtime")
        # start and end time
        self.downtime_xml.get_object("input_entry_start_time").set_text(start_time)
        self.downtime_xml.get_object("input_entry_end_time").set_text(end_time)
        # flexible downtime duration
        self.downtime_xml.get_object("input_spinbutton_duration_hours").set_value(2)
        self.downtime_xml.get_object("input_spinbutton_duration_minutes").set_value(0)
        
        # show dialog
        self.downtime_dialog.run()
        self.downtime_dialog.destroy()


    def Downtime(self, widget, server):
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
                          "button_cancel_clicked": self.SubmitCheckResultCancel}
        self.submitcheckresult_xml.connect_signals(handlers_dict, server)
        
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

        # show dialog
        self.submitcheckresult_dialog.run()
       
        
    def SubmitCheckResultOK(self, widget, server):
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
        
        for s in ["ok", "warning", "critical", "unreachable", "unknown", "down"]:
            if self.submitcheckresult_xml.get_object("input_radiobutton_result_" + s).get_active() == True:
                state = s
                break

        if "check_output" in server.SUBMIT_CHECK_RESULT_ARGS and len(check_output) == 0:
            self.ErrorDialog("Submit check result needs a check output.")
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

        self.AboutDialogOpen = True        
        self.popwin.Close()
        about.run()
        about.destroy()
        self.AboutDialogOpen = False


    def ErrorDialog(self, error):
        """
            versatile error dialog
        """        
        # close popwin to make sure the error dialog will not be covered by popwin
        self.popwin.Close()
        
        dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CANCEL, message_format=str(error))
        # gtk.Dialog.run() does a mini loop to wait
        dialog.run()
        dialog.destroy()

            
    def CheckForNewVersionDialog(self, version_status=None, version=None):
        """
            Show results of Settings.CheckForNewVersion()
        """
        try:
            # close popwin to make sure the error dialog will not be covered by popwin
            self.popwin.Close()
            
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
                if self.popwin.get_properties("visible")[0] == False:
                    if self.Notifying == False:
                        self.Notifying = True
                        # debug
                        if str(self.conf.debug_mode) == "True":                            
                            self.servers.values()[0].Debug(debug="Notification on.")
                        # threaded statusbar flash
                        if str(self.conf.notification_flashing) == "True":
                            self.statusbar.SysTray.set_blinking(True)
                            self.statusbar.Flashing = True
                            flash = Actions.Notification(output=self, sound=status, Resources=self.Resources, conf=self.conf, servers=self.servers)
                            flash.start()   
                        # if wanted play notification sound
                        ###if str(self.conf.notification_sound) == "True":
                        ###    sound = Actions.PlaySound(sound=status, Resources=self.Resources, conf=self.conf, servers=self.servers)
                        ###    sound.start()
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
        
        # due to different GTK versions on different OS with different capabilities those 
        # flags are used instead of for example gtk.Menu.get_visible()
        self.MenuOpen = False
        
        # put Systray icon into statusbar object
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
            

    def _CreateFloatingStatusbar(self):
        """
        create statusbar as floating window
        """
        # TOPLEVEL seems to be more standard compliant
        #self.StatusBar = gtk.Window(gtk.WINDOW_TOPLEVEL)
        # WINDOWS_POPUP works
        self.StatusBar = gtk.Window(gtk.WINDOW_POPUP)
        self.StatusBar.set_decorated(False)
        self.StatusBar.set_keep_above(True)
        self.StatusBar.stick()
        # at http://www.pygtk.org/docs/pygtk/gdk-constants.html#gdk-window-type-hint-constants
        # there are some hint types to experiment with
        if platform.system() == "Windows":
            self.StatusBar.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
        else:
            #self.StatusBar.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DOCK)
            # trying as _HINT_UTILITY in Linux too as it gets a size modify element
            # in GNOME 3
            self.StatusBar.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
        self.StatusBar.set_property("skip-taskbar-hint", True)
        self.StatusBar.set_skip_taskbar_hint(True)
            

    def MenuResponseMonitors(self, widget, menu_entry):
        """
            open responding Nagios status web page
        """
        Actions.OpenNagios(None, self.output.servers[menu_entry], self.output)
        
        
    def MenuResponse(self, widget, menu_entry):
        """
            responses for the context menu for label in statusbar
        """
        if menu_entry == "Refresh": Actions.RefreshAllServers(servers=self.output.servers, output=self.output, conf=self.conf)
        if menu_entry == "Recheck all": self.output.RecheckAll()
        if menu_entry == "Settings...": Settings(servers=self.output.servers, output=self.output, conf=self.conf)
        if menu_entry == "Save position": self.conf.SaveConfig()
        if menu_entry == "About": self.output.AboutDialog()
        if menu_entry == "Exit": 
            self.conf.SaveConfig()
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
                    if self.output.popwin.get_properties("visible")[0] == False:
                        #...show it...
                        self.output.popwin.PopUp()
                    else:
                        #...otherwise close it
                        self.output.popwin.Close()
                # if hovering is set, popwin is open and statusbar gets clicked...
                else:
                    # close popwin for convinience
                    if self.output.popwin.get_properties("visible")[0] == True:
                        self.output.popwin.Close()
            # if right mousebutton is pressed show statusbar menu
            if event.button == 3:
                self.output.popwin.Close()
                self.Moving = False
                self.MenuPopup(widget=self.Menu, event=event)
                #self.Menu.popup(None, None, None, event.button, event.time)
        
        # switch off Notification    
        self.output.NotificationOff()
            

    def LogoClicked(self, widget=None, event=None):
        """
            see what happens if statusbar is clicked
        """
        # check if settings etc. are not already open
        if self.output.SettingsDialogOpen == False and self.output.AboutDialogOpen == False:
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
                self.Menu.popup(None, None, None, event.button, event.time)
        
                
    def LogoReleased(self, widget=None, event=None):
        """
        used when button click on logo is released
        """
        self.output.popwin.setShowable()
        self.Moving = False
                
            
    def SysTrayClicked(self, widget=None, event=None):
        """
            see what happens when icon in systray has been clicked
        """
        # switch notification off
        self.output.NotificationOff()
        # check if settings ar not already open
        if self.output.popwin.IsWanted() == True:
            # if popwin is not shown pop it up
            if self.output.popwin.get_properties("visible")[0] == False:
                self.output.popwin.PopUp()
            else:
                self.output.popwin.Close()


    def Hovered(self, widget=None, event=None):
        """
            see what happens if statusbar is hovered
        """
        # check if settings ar not already open
        if self.output.popwin.IsWanted() == True and\
           str(self.conf.popup_details_hover) == "True":
                self.output.popwin.PopUp()
           

    def MenuPopup(self, widget=None, event=None, time=None, dummy=None):
        """
            context menu for label in statusbar
        """
        
        self.output.popwin.Close()
        
        # no dragging of statusbar anymore if menu pops up
        self.Moving = False

        # check if settings ar not already open
        if self.output.SettingsDialogOpen == False:
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
                    self.MenuOpen = True
            else:
                # right button
                if event.button == 3:
                    widget.popup(None, None, None, event.button, event.time)
                    self.MenuOpen = True
                    
            self.MenuOpen = False
           
                    
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


class Popwin(gtk.Window):
    """
    Popwin object
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        
        # Initialize type popup
        gtk.Window.__init__(self, type=gtk.WINDOW_POPUP)
        # initialize the coordinates of left upper corner of the popwin
        self.popwinx0 = self.popwiny0 = 0

        self.AlMonitorLabel = gtk.Alignment(xalign=0, yalign=0.5)
        self.AlMonitorComboBox = gtk.Alignment(xalign=0, yalign=0.5)
        self.AlMenu = gtk.Alignment(xalign=1.0, yalign=0.5)
        self.VBox = gtk.VBox()
        self.HBoxAllButtons = gtk.HBox()
        self.HBoxNagiosButtons = gtk.HBox()
        self.HBoxMenu = gtk.HBox()
        self.HBoxCombobox = gtk.HBox()
        
        # put a name tag where there buttons had been before
        # image for logo in statusbar
        self.NagstamonLabel = gtk.Image()
        self.NagstamonLabel.set_from_file(self.output.Resources + os.sep + "nagstamon_label.png")     
        self.HBoxNagiosButtons.add(self.NagstamonLabel)
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
        
        # Button Recheck All - HBox is necessary because gtk.Button allows only one child
        self.ButtonRecheckAll_HBox = gtk.HBox()
        self.ButtonRecheckAll_Icon = gtk.Image()
        self.ButtonRecheckAll_Icon.set_from_file(self.output.Resources + os.sep + "recheckall.png")
        self.ButtonRecheckAll_Label = gtk.Label("Recheck all and refresh")
        self.ButtonRecheckAll_HBox.add(self.ButtonRecheckAll_Icon)
        self.ButtonRecheckAll_HBox.add(self.ButtonRecheckAll_Label)
        self.ButtonRecheckAll = gtk.Button()
        self.ButtonRecheckAll.set_relief(gtk.RELIEF_NONE)
        self.ButtonRecheckAll.add(self.ButtonRecheckAll_HBox)
        self.HBoxMenu.add(self.ButtonRecheckAll)        
        
        # Button Refresh - HBox is necessary because gtk.Button allows only one child
        self.ButtonRefresh_HBox = gtk.HBox()
        self.ButtonRefresh_Icon = gtk.Image()
        self.ButtonRefresh_Icon.set_from_file(self.output.Resources + os.sep + "refresh.png")
        self.ButtonRefresh_Label = gtk.Label("Refresh")
        self.ButtonRefresh_HBox.add(self.ButtonRefresh_Icon)
        self.ButtonRefresh_HBox.add(self.ButtonRefresh_Label)
        self.ButtonRefresh = gtk.Button()
        self.ButtonRefresh.set_relief(gtk.RELIEF_NONE)
        self.ButtonRefresh.add(self.ButtonRefresh_HBox)
        self.HBoxMenu.add(self.ButtonRefresh)
        
        # Button Settings - HBox is necessary because gtk.Button allows only one child
        self.ButtonSettings_HBox = gtk.HBox()
        self.ButtonSettings_Icon = gtk.Image()
        self.ButtonSettings_Icon.set_from_file(self.output.Resources + os.sep + "settings.png")
        self.ButtonSettings_Label = gtk.Label("Settings")
        self.ButtonSettings_HBox.add(self.ButtonSettings_Icon)
        self.ButtonSettings_HBox.add(self.ButtonSettings_Label)
        self.ButtonSettings = gtk.Button()
        self.ButtonSettings.set_relief(gtk.RELIEF_NONE)
        self.ButtonSettings.add(self.ButtonSettings_HBox)
        self.HBoxMenu.add(self.ButtonSettings)
        
        # Button Close - HBox is necessary because gtk.Button allows only one child
        self.ButtonClose_HBox = gtk.HBox()
        self.ButtonClose_Icon = gtk.Image()
        self.ButtonClose_Icon.set_from_file(self.output.Resources + os.sep + "close.png")
        self.ButtonClose_HBox.add(self.ButtonClose_Icon)
        self.ButtonClose = gtk.Button()
        self.ButtonClose.set_relief(gtk.RELIEF_NONE)
        self.ButtonClose.add(self.ButtonClose_HBox)
        self.HBoxMenu.add(self.ButtonClose)
     
        # put the HBox full of buttons full of HBoxes into the aligned HBox...
        self.AlMenu.add(self.HBoxMenu)     
        
        # HBoxes en masse...
        self.HBoxAllButtons.add(self.AlMonitorLabel)
        self.HBoxAllButtons.add(self.AlMonitorComboBox)
        self.HBoxAllButtons.add(self.AlMenu)
                
        # for later calculation of the popwin size we need the height of the buttons
        # it is enough to choose one of those buttons because they all have the same dimensions
        # as it seems to be the largest one we choose ComboboxMonitor
        dummy, self.buttonsheight = self.ComboboxMonitor.size_request()
        
        # add all buttons in their hbox to the overall vbox
        self.VBox.add(self.HBoxAllButtons)

        # put this vbox into popwin
        self.add(self.VBox)        
                    
        # create a scrollable area for the treeview in case it is larger than the screen
        # in case there are too many failed services and hosts
        self.ScrolledWindow = gtk.ScrolledWindow()
        self.ScrolledWindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        
        # try putting everything status-related into a scrolled viewport
        self.ScrolledVBox = gtk.VBox()
        self.ScrolledViewport = gtk.Viewport()
        self.ScrolledViewport.add(self.ScrolledVBox)
        self.ScrolledWindow.add(self.ScrolledViewport)   
       
        # put scrolled window aka scrolled treeview into vbox
        self.VBox.add(self.ScrolledWindow)
        
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
            self.ServerVBoxes[server.get_name()].Label.set_markup('<span weight="bold" size="large">' + server.get_name() + '</span>')
            self.ServerVBoxes[server.get_name()].Label.set_alignment(0,0)
             # set no show all to be able to hide label and treeview if it is empty in case of no hassle
            self.ServerVBoxes[server.get_name()].set_no_show_all(True)
            
            # connect buttons with actions
            # open Nagios main page in your favorite web browser when nagios button is clicked
            self.ServerVBoxes[server.get_name()].ButtonMonitor.connect("clicked", Actions.OpenNagios, server, self.output)
            # open Nagios services in your favorite web browser when service button is clicked
            self.ServerVBoxes[server.get_name()].ButtonServices.connect("clicked", Actions.OpenServices, server, self.output)
            # open Nagios hosts in your favorite web browser when hosts button is clicked
            self.ServerVBoxes[server.get_name()].ButtonHosts.connect("clicked", Actions.OpenHosts, server, self.output)
            
            # windows workaround - see above
            # connect Server_EventBox with leave-notify-event to get popwin popping down when leaving it
            self.ServerVBoxes[server.get_name()].Server_EventBox.connect("leave-notify-event", self.PopDown)
            # sorry folks, but this only works at the border of the treeviews 
            self.ServerVBoxes[server.get_name()].TreeView.connect("leave-notify-event", self.PopDown)
            # connect the treeviews of the servers to mouse clicks
            self.ServerVBoxes[server.get_name()].TreeView.connect("button-press-event", self.ServerVBoxes[server.get_name()].TreeviewPopupMenu, self.ServerVBoxes[server.get_name()].TreeView, self.output.servers[server.get_name()])
           
            # add box to the other ones
            self.ScrolledVBox.add(self.ServerVBoxes[server.get_name()])

        # Initialize show_popwin - show it or not, if everything is OK
        # it is not necessary to pop it up
        self.showPopwin = False
               
        
    def PopUp(self, widget=None, event=None):
        """
            pop up popwin
        """
        # when popwin is showable and label is not "UP" popwin will be showed - 
        # otherwise there is no sense in showing an empty popwin
        # for some reason the painting will lag behind popping up popwin if not getting resized twice -
        # seems like a strange workaround
        if self.showPopwin and not self.output.status_ok:
            self.output.statusbar.Moving = False
            # position and resize...
            self.Resize()
            # ...show
            self.show_all()
            # position and resize...
            self.Resize()
            # set combobox to default value
            self.ComboboxMonitor.set_active(0)
            # switch off Notification    
            self.output.NotificationOff()


    def PopDown(self, widget=None, event=None):
        """
            close popwin
            when it should closed it must be checked if the pointer is outside 
            the popwin to prevent it closing when not necessary/desired
        """
        # catch Exception
        try:
            # access to rootwindow to get the pointers coordinates
            rootwin = self.output.statusbar.StatusBar.get_screen().get_root_window()
            # get position of the pointer
            mousex, mousey, foo = rootwin.get_pointer()
            # get position of popwin
            popwinx0, popwiny0 = self.get_position()

            # actualize values for width and height
            self.popwinwidth, self.popwinheight = self.get_size()

            # If pointer is outside popwin close it
            # to support Windows(TM)'s slow and event-loosing behaviour use some margin (10px) to be more tolerant to get popwin closed
            # y-axis dooes not get extra 10 px on top for sake of combobox and x-axis on right side not because of scrollbar -
            # so i wonder if it has any use left...
            if mousex <= popwinx0 + 10 or mousex >= (popwinx0 + self.popwinwidth) or mousey <= popwiny0 or mousey >= (popwiny0 + self.popwinheight) - 10 :
                self.Close()
        except:
            pass
        

    def Close(self, widget=None):
        """
            hide popwin
        """
        self.hide_all()
        # notification off because user had a look to hosts/services recently
        self.output.NotificationOff()        


    def Resize(self):
        """
            resize popwin depending on the amount of information displayed in scrollbox
        """
        try:
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
            if self.get_properties("visible")[0] == False:
                
                # check if icon in systray or statusbar 
                if str(self.conf.icon_in_systray) == "True":

                    # trayicon seems not to have a .get_pointer() method so we use 
                    # its geometry information
                    if platform.system() == "Windows":
                        # otherwise this does not work in windows
                        rootwin = self.output.statusbar.StatusBar.get_screen().get_root_window()
                        mousex, mousey, foo = rootwin.get_pointer()
                        statusbar_mousex, statusbar_mousey = 0, 2
                    else:    
                        mousex, mousey, foo, bar = self.output.statusbar.SysTray.get_geometry()[1]
                        statusbar_mousex, statusbar_mousey = 0, 2
                        
                    # set monitor for later applying the correct monitor geometry
                    self.output.current_monitor = self.output.statusbar.StatusBar.get_screen().get_monitor_at_point(mousex, mousey)

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

            else:
                # use previously saved values for x0 and y0 in case popwin is still/already open
                statusbarx0 = self.output.statusbar.StatusBar.x0
                statusbary0 = self.output.statusbar.StatusBar.y0
                
            # find out the necessary dimensions of popwin - assembled from scroll area and the buttons
            treeviewwidth, treeviewheight = self.ScrolledVBox.size_request()
            
            # get current monitor's settings
            screenx0, screeny0, screenwidth, screenheight = self.output.monitors[self.output.current_monitor]
           
            if treeviewwidth > screenwidth: treeviewwidth = screenwidth
            self.ScrolledWindow.set_size_request(treeviewwidth, treeviewheight)
            
            # care about the height of the buttons
            # self.buttonsheight comes from create_output_visuals()
            self.popwinwidth, self.popwinheight = treeviewwidth, treeviewheight + self.buttonsheight
            # if popwinwidth is to small the buttons inside could be scrambled, so we give
            # it a default minimum width
            if self.popwinwidth < 600: self.popwinwidth = 600
            
            # add some buffer pixels to popwinheight to avoid silly scrollbars
            heightbuffer = 10
            self.popwinheight = self.popwinheight + heightbuffer
            
            # get parameters of statusbar
            # get dimensions
            if str(self.conf.icon_in_systray) == "True":
                statusbarwidth, statusbarheight = 25, 25
            else:    
                statusbarwidth, statusbarheight = self.output.statusbar.StatusBar.get_size()

            # if statusbar/trayicon stays in upper half of screen, popwin pops up UNDER statusbar/trayicon
            if (statusbary0 + statusbarheight) < (screenheight / 2):
                # if popwin is too large it gets cut at lower end of screen
                if (statusbary0 + self.popwinheight + statusbarheight) > screenheight:
                    treeviewheight = screenheight - (statusbary0 + statusbarheight + self.buttonsheight)
                    self.popwinheight = screenheight - statusbarheight - statusbary0
                    self.popwiny0 = statusbary0 + statusbarheight
                # else do not relate to screen dimensions but own widgets ones
                else:
                    self.popwinheight = treeviewheight + self.buttonsheight + heightbuffer
                    self.popwiny0 = statusbary0 + statusbarheight

            # if it stays in lower half of screen, popwin pops up OVER statusbar/trayicon
            else:
                # if popwin is too large it gets cut at 0 
                if (statusbary0 - self.popwinheight) < 0:
                    treeviewheight = statusbary0 - self.buttonsheight - statusbarheight
                    self.popwinheight = statusbary0
                    self.popwiny0 = 0
                # otherwise use own widgets for sizing
                else:
                    self.popwinheight = treeviewheight + self.buttonsheight + heightbuffer
                    self.popwiny0 = statusbary0 - self.popwinheight

            # after having determined dimensions of scrolling area apply them
            self.ScrolledWindow.set_size_request(treeviewwidth, treeviewheight)
            
            # if popwin is too wide cut it down to screen width
            if self.popwinwidth > screenwidth:
                self.popwinwidth = screenwidth
                    
            # decide x position of popwin
            if (statusbarx0) + statusbarwidth / 2 + (self.popwinwidth) / 2 > (screenwidth + screenx0):
                self.popwinx0 = screenwidth - self.popwinwidth + screenx0
            elif (statusbarx0 + statusbarwidth / 2)- self.popwinwidth / 2 < screenx0:
                self.popwinx0 = screenx0
            else:
                self.popwinx0 = statusbarx0 + (screenx0 + statusbarwidth) / 2 - (self.popwinwidth + screenx0) / 2

            # move popwin to its position
            self.move(self.popwinx0, self.popwiny0)
            
            # set size request of popwin
            self.set_size_request(self.popwinwidth, self.popwinheight)
            
            # set size REALLY because otherwise it stays to large
            self.resize(self.popwinwidth, self.popwinheight)
        except:
            pass


    def setShowable(self, widget=None, event=None):
        """
        stub method to set popwin showable after button-release-event after moving statusbar
        """
        self.showPopwin = True
        
    """    
    def TreeviewPopupMenu(self, widget, event, treeview, server):
    """
            #context menu for treeview detailed status items
    """
        # catch exception in case of clicking outside treeview
        try:
            # get path to clicked cell
            path, obj, x, y = treeview.get_path_at_pos(int(event.x), int(event.y))
            # access content of rendered view model via normal python lists
            self.miserable_server = server
            self.miserable_host = treeview.get_model()[path[0]][server.HOST_COLUMN_ID]
            self.miserable_service = treeview.get_model()[path[0]][server.SERVICE_COLUMN_ID]
            # popup the relevant content menu
            if self.miserable_service and server.hosts[self.miserable_host].services[self.miserable_service].is_passive_only():
                self.recheck_item.set_sensitive(False)
            else:
                self.recheck_item.set_sensitive(True)
            self.popupmenu.popup(None, None, None, event.button, event.time)
        except Exception, err:
            print err
        

    def TreeviewPopupMenuResponse(self, widget, remoteservice):
    """
          #  responses to the menu items
          #  binaries get called by subprocess.Popen to beware nagstamon of hanging while
          #  waiting for the called binary exit code
          #  the requested binary and its arguments are given by a list
    """
        
        # closing popwin is innecessary in case of rechecking, otherwise it must be done
        # because the dialog/app window will stay under the popwin   
        if not remoteservice == "Recheck":
            self.Close()  
        
        #debug    
        if str(self.conf.debug_mode) == "True":
            self.miserable_server.Debug(server=self.miserable_server.get_name(), host=self.miserable_host, service=self.miserable_service, debug="Clicked context menu: " + remoteservice)
            
        # choose appropriate service for menu entry
        # it seems to be more responsive especially while rechecking if every service
        # looks for its own for the miserable host's ip if it is needed
        try:
            if remoteservice == "SSH":
                # get host ip to connect to be independent of dns resolver
                #host = self.miserable_server.GetHost(self.miserable_host)[0]
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    # workaround for bug 2080503@sf.net
                    if self.conf.app_ssh_options == "": args = self.conf.app_ssh_bin + " " + host
                    else: args = self.conf.app_ssh_bin + " " + self.conf.app_ssh_options + " " + host
                    sub = subprocess.Popen(args.split(" "))
            elif remoteservice == "RDP":
                # get host ip to connect to be independent of dns resolver               
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    # workaround for bug 2080503@sf.net
                    if self.conf.app_rdp_options == "": args = self.conf.app_rdp_bin + " " + host
                    else: args = self.conf.app_rdp_bin + " " + self.conf.app_rdp_options + " " + host
                    sub = subprocess.Popen(args.split(" "))
            elif remoteservice == "VNC":
                # get host ip to connect to be independent of dns resolver
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    # workaround for bug 2080503@sf.net
                    if self.conf.app_vnc_options == "": args = self.conf.app_vnc_bin + " " + host
                    else: args = self.conf.app_vnc_bin + " " + self.conf.app_vnc_options + " " + host
                    sub = subprocess.Popen(args.split(" "))
            elif remoteservice == "HTTP":
                # get host ip to connect to be independent of dns resolver
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    Actions.TreeViewHTTP(host)
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
            self.PopDown()
                
        except Exception, err:
            self.output.ErrorDialog(err)
    """     

    def ComboboxClicked(self, widget=None):
        """
            open web interface of selected server
        """
        try:
            active = widget.get_active_iter()
            model = widget.get_model()
            Actions.OpenNagios(widget=None, server=self.output.servers[model.get_value(active, 0)], output=self.output)
        except:
            self.output.servers.values()[0].Error(sys.exc_info())
            
    
    def UpdateStatus(self, server):
        """
            Updates status field of a server
        """
        # status field in server vbox in popwin    
        try:
            self.ServerVBoxes[server.get_name()].LabelStatus.set_markup('<span>Status: ' + str(server.status) + ' <span color="darkred">' + str(server.status_description) + '</span></span>')
        except:
            server.Error(sys.exc_info())
            
    
    def IsWanted(self):
        """
        check if no other dialog/menu is shown which would not like to be
        covered by the popup window
        """
        if self.output.SettingsDialogOpen == False and\
           self.output.AboutDialogOpen == False and\
           self.output.statusbar.MenuOpen == False:
            return True
        else:
            return False
    

class ServerVBox(gtk.VBox):
    """
    VBox which contains all infos about one Monitor server: Name, Buttons, Treeview
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
       
        # server related Buttons
        # Button Monitor - HBox is necessary because gtk.Button allows only one child
        self.ButtonMonitor_HBox = gtk.HBox()
        self.ButtonMonitor_Icon = gtk.Image()
        self.ButtonMonitor_Icon.set_from_file(self.output.Resources + os.sep + "nagios.png")
        self.ButtonMonitor_Label = gtk.Label("Monitor")
        self.ButtonMonitor_HBox.add(self.ButtonMonitor_Icon)
        self.ButtonMonitor_HBox.add(self.ButtonMonitor_Label)
        self.ButtonMonitor = gtk.Button()
        self.ButtonMonitor.set_relief(gtk.RELIEF_NONE)
        self.ButtonMonitor.add(self.ButtonMonitor_HBox)

        # Button Services - HBox is necessary because gtk.Button allows only one child
        self.ButtonServices_HBox = gtk.HBox()
        self.ButtonServices_Icon = gtk.Image()
        self.ButtonServices_Icon.set_from_file(self.output.Resources + os.sep + "services.png")
        self.ButtonServices_Label = gtk.Label("Services")
        self.ButtonServices_HBox.add(self.ButtonServices_Icon)
        self.ButtonServices_HBox.add(self.ButtonServices_Label)
        self.ButtonServices = gtk.Button()
        self.ButtonServices.set_relief(gtk.RELIEF_NONE)
        self.ButtonServices.add(self.ButtonServices_HBox)
        
        # Button Hosts - HBox is necessary because gtk.Button allows only one child
        self.ButtonHosts_HBox = gtk.HBox()
        self.ButtonHosts_Icon = gtk.Image()
        self.ButtonHosts_Icon.set_from_file(self.output.Resources + os.sep + "hosts.png")
        self.ButtonHosts_Label = gtk.Label("Hosts")
        self.ButtonHosts_HBox.add(self.ButtonHosts_Icon)
        self.ButtonHosts_HBox.add(self.ButtonHosts_Label)
        self.ButtonHosts = gtk.Button()
        self.ButtonHosts.set_relief(gtk.RELIEF_NONE)
        self.ButtonHosts.add(self.ButtonHosts_HBox)
        
        # Label with status information
        self.LabelStatus = gtk.Label("")
        
        # order the elements
        self.HBox = gtk.HBox(homogeneous=True)
        self.HBoxLeft = gtk.HBox()
        self.HBoxRight = gtk.HBox()
        self.HBoxLeft.add(self.Label)
        # leave some space around the label
        self.Label.set_padding(5, 5)
        self.HBoxLeft.add(self.ButtonMonitor)
        self.HBoxLeft.add(self.ButtonHosts)
        self.HBoxLeft.add(self.ButtonServices)
        self.HBoxLeft.add(gtk.VSeparator())
        self.HBoxLeft.add(self.LabelStatus)
        
        self.AlignmentLeft = gtk.Alignment(xalign=0, xscale=0.05, yalign=0)
        self.AlignmentLeft.add(self.HBoxLeft)
        self.AlignmentRight = gtk.Alignment(xalign=0, xscale=0.0, yalign=0.5)
        self.AlignmentRight.add(self.HBoxRight)
        
        self.HBox.add(self.AlignmentLeft)
        self.HBox.add(self.AlignmentRight)
        
        self.Server_EventBox.add(self.HBox)
        self.add(self.Server_EventBox)            
        
        # context menu for detailed status overview, opens with a mouse click onto a listed item
        self.popupmenu = gtk.Menu()
        # first add connections
        for i in ["Monitor", "SSH", "RDP", "VNC", "HTTP"]:
            menu_item = gtk.MenuItem(i)
            menu_item.connect("activate", self.TreeviewPopupMenuResponse, i)
            self.popupmenu.append(menu_item)
        # add separator to separate between connections and actions
        self.popupmenu.append(gtk.SeparatorMenuItem())
        # after the separatior add actions
        #for i in ["Recheck", "Acknowledge", "Submit check result", "Downtime"]:
        for i in self.server.MENU_ACTIONS:
            menu_item = gtk.MenuItem(i)
            menu_item.connect("activate", self.TreeviewPopupMenuResponse, i)
            if i == "Recheck":
                self.recheck_item = menu_item
            self.popupmenu.append(menu_item)
        self.popupmenu.show_all()
                    
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
            # popup the relevant content menu
            if self.miserable_service and server.hosts[self.miserable_host].services[self.miserable_service].is_passive_only():
                self.recheck_item.hide()
            else:
                self.recheck_item.show()
            self.popupmenu.popup(None, None, None, event.button, event.time)
        except Exception, err:
            print err
        

    def TreeviewPopupMenuResponse(self, widget, remoteservice):
        """
            responses to the menu items
            binaries get called by subprocess.Popen to beware nagstamon of hanging while
            waiting for the called binary exit code
            the requested binary and its arguments are given by a list
        """
        
        # closing popwin is innecessary in case of rechecking, otherwise it must be done
        # because the dialog/app window will stay under the popwin   
        if not remoteservice == "Recheck":
            self.output.popwin.Close()  
        
        #debug    
        if str(self.output.conf.debug_mode) == "True":
            self.miserable_server.Debug(server=self.miserable_server.get_name(), host=self.miserable_host, service=self.miserable_service, debug="Clicked context menu: " + remoteservice)
            
        # choose appropriate service for menu entry
        # it seems to be more responsive especially while rechecking if every service
        # looks for its own for the miserable host's ip if it is needed
        try:
            if remoteservice == "SSH":
                # get host ip to connect to be independent of dns resolver
                #host = self.miserable_server.GetHost(self.miserable_host)[0]
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    # workaround for bug 2080503@sf.net
                    if self.output.conf.app_ssh_options == "": args = self.output.conf.app_ssh_bin + " " + host
                    else: args = self.output.conf.app_ssh_bin + " " + self.output.conf.app_ssh_options + " " + host
                    sub = subprocess.Popen(args.split(" "))
            elif remoteservice == "RDP":
                # get host ip to connect to be independent of dns resolver               
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    # workaround for bug 2080503@sf.net
                    if self.output.conf.app_rdp_options == "": args = self.output.conf.app_rdp_bin + " " + host
                    else: args = self.output.conf.app_rdp_bin + " " + self.output.conf.app_rdp_options + " " + host
                    sub = subprocess.Popen(args.split(" "))
            elif remoteservice == "VNC":
                # get host ip to connect to be independent of dns resolver
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    # workaround for bug 2080503@sf.net
                    if self.output.conf.app_vnc_options == "": args = self.output.conf.app_vnc_bin + " " + host
                    else: args = self.output.conf.app_vnc_bin + " " + self.output.conf.app_vnc_options + " " + host
                    sub = subprocess.Popen(args.split(" "))
            elif remoteservice == "HTTP":
                # get host ip to connect to be independent of dns resolver
                result = self.miserable_server.GetHost(self.miserable_host)
                host, error = result.result, result.error
                if error == "":
                    Actions.TreeViewHTTP(host)
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
            self.output.ErrorDialog(err)
            
        
class Settings(object):
    """
        settings dialog as object, may lead to less mess
    """
    
    def __init__(self, **kwds):
        # add all keywords to object
        for k in kwds: self.__dict__[k] = kwds[k]
        
        # flag settings dialog as opened
        self.output.SettingsDialogOpen = True
        
        # set the gtkbuilder files
        self.builderfile = self.output.Resources + os.sep + "settings_dialog.ui"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builderfile)
        self.dialog = self.builder.get_object("settings_dialog")
        
        # use connect_signals to assign methods to handlers
        handlers_dict = { "button_ok_clicked": self.OK, 
                          "settings_dialog_close": self.Cancel,
                          "button_cancel_clicked": self.Cancel,
                          "button_new_server": lambda n: NewServer(servers=self.servers, output=self.output, settingsdialog=self, conf=self.conf),
                          "button_edit_server": lambda e: EditServer(servers=self.servers, output=self.output, server=self.selected_server, settingsdialog=self, conf=self.conf),
                          "button_delete_server": lambda d: self.DeleteServer(self.selected_server),
                          "button_check_for_new_version_now": self.CheckForNewVersionNow,
                          "checkbutton_enable_notification": self.ToggleNotification,
                          "checkbutton_enable_sound": self.ToggleSoundOptions,
                          "togglebutton_use_custom_sounds": self.ToggleCustomSoundOptions,
                          "checkbutton_re_host_enabled": self.ToggleREHostOptions,
                          "checkbutton_re_service_enabled": self.ToggleREServiceOptions,
                          "button_play_sound": self.PlaySound,
                          "checkbutton_debug_mode": self.ToggleDebugOptions,
                          "checkbutton_debug_to_file": self.ToggleDebugOptions,
                          "button_colors_default": self.ColorsDefault,
                          "button_colors_reset": self.ColorsReset,
                          "color-set": self.ColorsPreview}
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
            self.output.popwin.hide_all()
        except:
            pass
        
        # set title of settings dialog containing version number
        self.dialog.set_title(self.output.name + " " + self.output.version + " settings")
        
        # workaround for gazpacho-made glade-file - dunno why tab labels do not get named as they should be
        notebook = self.builder.get_object("notebook")
        notebook_tabs =  ["Servers", "Display", "Filters", "Executables", "Notification", "Colors"]
        for c in notebook.get_children():
            notebook.set_tab_label_text(c, notebook_tabs.pop(0))
        
        # fill treeview
        self.FillTreeView()
        
        # toggle debug options
        self.ToggleDebugOptions()

        # toggle custom sounds options
        self.ToggleCustomSoundOptions()
        
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
            self.builder.get_object("input_radiobutton_icon_in_systray").hide()
              
        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        self.dialog.destroy()
  
        # flag settings dialog as closed
        self.output.SettingsDialogOpen = False
               
        
    def FillTreeView(self):
        # fill treeview containing servers
        # create a model for treeview where the table headers all are strings
        liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        
        # to sort the monitor servers alphabetically make a sortable list of their names
        server_list = list(self.conf.servers)
        server_list.sort(key=str.lower)

        for server in server_list:            
            iter = liststore.insert_before(None, None)
            liststore.set_value(iter, 0, server)
            if str(self.conf.servers[server].enabled) == "True":
                liststore.set_value(iter, 1, "black")
                liststore.set_value(iter, 2, False)
            else:
                liststore.set_value(iter, 1, "darkgrey")
                liststore.set_value(iter, 2, True)
        # give model to the view
        self.builder.get_object("servers_treeview").set_model(liststore)
        
        # render aka create table view
        renderer_text = gtk.CellRendererText()
        tab_column = gtk.TreeViewColumn("Servers", renderer_text, text=0, foreground=1, strikethrough=2)
        # somehow idiotic, but less effort... try to delete which column ever, to create a new one
        # this will throw an exception at the first time the options dialog is opened because no column exists
        try:
            self.builder.get_object("servers_treeview").remove_column(self.builder.get_object("servers_treeview").get_column(0))
        except:
            pass
        self.builder.get_object("servers_treeview").append_column(tab_column)
        
        # in case there are no servers yet because it runs the first time do a try-except
        try:
            # selected server to edit or delete, defaults to first one of server list
            self.selected_server = server_list[0]
            # select first server entry
            self.builder.get_object("servers_treeview").set_cursor_on_cell((0,))
        except:
            pass
        # connect treeview with mouseclicks
        self.builder.get_object("servers_treeview").connect("button-press-event", self.SelectedServer)


    def SelectedServer(self, widget=None, event=None):
        """
            findout selected server in servers treeview, should NOT return anything because the treeview
            will be displayed buggy if it does
        """
        try:
            # get path to clicked cell
            path, obj, x, y = self.builder.get_object("servers_treeview").get_path_at_pos(int(event.x), int(event.y))
            # access content of rendered view model via normal python lists
            self.selected_server = self.builder.get_object("servers_treeview").get_model()[path[0]][0]
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
                                                    
        # close settings dialog 
        self.dialog.destroy()
        
        # close popwin
        # catch Exception at first run when there cannot exist a popwin
        try:
            self.output.popwin.hide_all()
        except:
            pass            
     
        if int(self.conf.update_interval) == 0:
            self.conf.update_interval = 1
        
        # save settings
        self.conf.SaveConfig()

        # catch exceptions in case of misconfiguration
        try:
            # now it is not the first run anymore
            self.firstrun = False
            self.conf.unconfigured = False
            
            # create output visuals again because they might have changed (systray/free floating status bar)
            self.output.statusbar.StatusBar.destroy()    
            self.output.statusbar.SysTray.set_visible(False)       
            self.output.popwin.destroy()
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
        self.dialog.destroy()
        self.output.popwin.PopDown()
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
                
            
    def DeleteServer(self, server=None):
        """
            delete Server after prompting
        """
        if server:
            dialog = gtk.MessageDialog(parent=None, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK + gtk.BUTTONS_CANCEL, message_format="Really delete server " + server + "?")
            # gtk.Dialog.run() does a mini loop to wait
            # for some reason response is YES, not OK... but it works.
            if dialog.run() == gtk.RESPONSE_YES:
                # delete server configuration entry
                self.conf.servers.pop(server)
                # stop thread
                try:
                    self.servers[server].thread.Stop()
                except:
                    # most probably server has been disabled and that's why there is no thread running
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        self.servers[server].Error(sys.exc_info())
                # delete server from servers dictionary
                self.servers.pop(server)
                # fill settings dialog treeview
                self.FillTreeView()
                
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
            Disable notification sound when not using sound is enabled
        """
        options = self.builder.get_object("hbox_re_host")
        checkbutton = self.builder.get_object("input_checkbutton_re_host_enabled")
        options.set_sensitive(checkbutton.get_active())
        

    def ToggleREServiceOptions(self, widget=None):
        """
            Disable notification sound when not using sound is enabled
        """
        options = self.builder.get_object("hbox_re_service")
        checkbutton = self.builder.get_object("input_checkbutton_re_service_enabled")
        options.set_sensitive(checkbutton.get_active())
        
    
    def PlaySound(self, playbutton=None):
        """
            play sample of selected sound for Nagios Event
        """
        try:
            filechooser = self.builder.get_object("input_filechooser_notification_custom_sound_" + playbutton.name)
            sound = Actions.PlaySound(sound="FILE", file=filechooser.get_filename(), conf=self.conf, servers=self.servers)
            sound.start()
        except:
            pass


class ServerDialogHelper(object):        
    """ Contains common logic for server dialog """
    
    KNOWN_CONTROLS = set()
    
    def on_server_change(self, combobox):
        """ Disables controls as it is set in server class """
        servers = Actions.get_registered_servers()
        active = combobox.get_active_iter()
        model = combobox.get_model()
        if not model:
            return
        server_class = servers[model.get_value(active, 0)]
        self.KNOWN_CONTROLS.update(server_class.DISABLED_CONTROLS)
        for item_id in self.KNOWN_CONTROLS:
            item = self.builder.get_object(item_id)
            if item is not None:
                if item_id in server_class.DISABLED_CONTROLS:
                    item.set_sensitive(False)
                else:
                    item.set_sensitive(True)
            else:
                print 'Invalid widget set for disable in %s: %s' % (server_class.__name__, item_id)
                
            
class NewServer(ServerDialogHelper):
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
        
        # set title of settings dialog 
        self.dialog.set_title("New Server")
        
        # enable server by default
        self.builder.get_object("input_checkbutton_enabled").set_active(True)
        
        # set server type combobox to Nagios as default
        combobox = self.builder.get_object("input_combo_server_type")
        combomodel = gtk.ListStore(gobject.TYPE_STRING)
        cr = gtk.CellRendererText()
        combobox.pack_start(cr, True)
        combobox.set_attributes(cr, text=0)
        for server in Actions.get_registered_server_type_list():
            combomodel.append((server,))
        combobox.set_model(combomodel)
        combobox.set_active(0)
        
        combobox.connect('changed', self.on_server_change)
        self.on_server_change(combobox)
        
        # show password - or not
        self.ToggleSavePassword()
        # show settings options for proxy - or not
        self.ToggleProxy()
        
        # show filled settings dialog and wait thanks to gtk.run()
        self.dialog.run()
        self.dialog.destroy()       
 

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
   
        # check if there is already a server named like the new one
        if new_server.name in self.conf.servers:
            self.output.ErrorDialog("A server named " + new_server.name + " already exists.")
        else:
            # put in new one
            self.conf.servers[new_server.name] = new_server
            # create new server thread
            created_server = Actions.CreateServer(new_server, self.conf, self.output.debug_queue)
            if created_server is not None:
                self.servers[new_server.name] = created_server 
                
                if str(self.conf.servers[new_server.name].enabled) == "True":
                    # start new thread (should go to Actions!)
                    self.servers[new_server.name].thread = Actions.RefreshLoopOneServer(server=self.servers[new_server.name], output=self.output, conf=self.conf)
                    self.servers[new_server.name].thread.start()        
                  
            # fill settings dialog treeview
            self.settingsdialog.FillTreeView()
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
                    

class EditServer(ServerDialogHelper):
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
        
        # in case server has been selected do nothing
        if not self.server == None:
            # set title of settings dialog 
            self.dialog.set_title("Edit Server " + self.server)
            
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
            combobox = self.builder.get_object("input_combo_server_type")
            combomodel = gtk.ListStore(gobject.TYPE_STRING)
            cr = gtk.CellRendererText()
            combobox.pack_start(cr, True)
            combobox.set_attributes(cr, text=0)
            combobox.set_model(combomodel)
            for server in servers:
                combobox.append_text(server)
            combobox.set_active(server_types[self.conf.servers[self.server].type])
            
            combobox.connect('changed', self.on_server_change)
            self.on_server_change(combobox)
                 
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
        
        # check if there is already a server named like the new one
        if new_server.name in self.conf.servers and new_server.name != self.server:
            self.output.ErrorDialog("A server named " + new_server.name + " already exists.")
        else:
            # delete old server configuration entry
            self.conf.servers.pop(self.server)
            try:
                # stop thread
                self.servers[self.server].thread.Stop()
            except Exception, err:
                print err
            # delete server from servers dictionary
            self.servers.pop(self.server)
    
            # put in new one
            self.conf.servers[new_server.name] = new_server
            # create new server thread
            created_server = Actions.CreateServer(new_server, self.conf, self.output.debug_queue)
            if created_server is not None:
                self.servers[new_server.name] = created_server 
                
                if str(self.conf.servers[new_server.name].enabled) == "True":  
                    # start new thread (should go to Actions)
                    self.servers[new_server.name].thread = Actions.RefreshLoopOneServer(server=self.servers[new_server.name], output=self.output, conf=self.conf)
                    self.servers[new_server.name].thread.start()   
            
            # fill settings dialog treeview
            self.settingsdialog.FillTreeView()
            # destroy dialog
            self.dialog.destroy()
            
      
    def Cancel(self, widget):
        """
            settings dialog got cancelled
        """
        self.dialog.destroy()
 

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
            
        
class PasswordDialog:
    """
    used in case password is not stored
    """
    password = None
    escaped = False

    def __init__( self, prompt ):
        dialog = gtk.MessageDialog(
            None,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK,
            None)
        
        # present password dialog in a safe way
        dialog.present()
        dialog.stick()
        dialog.set_keep_above(True)
        dialog.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        
        dialog.set_markup(prompt)
        # on close, we note that the user escaped the dialog
        dialog.connect("close", self.dialog_close)
        # on response, we check if the user confirmed or closed the dialog
        dialog.connect("response", self.dialog_response)
        # the password entry field
        entry = gtk.Entry()
        # password should not be shown
        entry.set_visibility(False)
        entry.connect("activate", self.entry_activate, dialog, gtk.RESPONSE_OK)
        # a horizontal box to put in the input field and a label
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Password:"), False, 5, 5)
        hbox.pack_end(entry)
        # put all together
        dialog.vbox.pack_end(hbox, True, True, 0)
        # and show it
        dialog.show_all()
        dialog.run()
        # only save the password if the user confirmed the entry
        if not self.escaped:
            self.password = entry.get_text()
        dialog.destroy()
        
        
    def entry_activate(self, entry, dialog, response):
        dialog.response(response)

        
    def dialog_close(self, dialog):
        self.escaped = True
        

    def dialog_response(self, dialog, arg):
        if arg != gtk.RESPONSE_OK:
            self.escaped = True
