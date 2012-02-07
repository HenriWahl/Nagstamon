#!/usr/bin/env python
# encoding: utf-8

# garbage collection
import gc
gc.enable()

import sys
import os
import os.path
import Queue

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

# Initiate Config
# if modules are not available from central python install try the ones in the same directory
from Nagstamon.Config import Config
conf = Config()

# check for old settings when upgrading from a nagstamon version < 0.8 and convert them
conf.Convert_Conf_to_Multiple_Servers()
# convert settings for actions to custom actions for Nagstamon < 0.9.9
conf.Convert_Conf_to_Custom_Actions()

# try to get resources path if nagstamon got be installed by setup.py
Resources = ""
try:
    import pkg_resources
    Resources = pkg_resources.resource_filename("Nagstamon", "resources")
except Exception, err:
    # get resources directory from current directory - only if not being set before by pkg_resources
    if Resources == "":
        if os.path.exists(os.path.normcase(os.getcwd() + os.sep + "Nagstamon" + os.sep + "resources")):
            Resources = os.path.normcase(os.getcwd() + os.sep + "Nagstamon" + os.sep + "resources")
        else:
            Resources = os.path.normcase(os.getcwd() + os.sep + "resources")

# initialize GUI and actions
# if modules are not available from central python install try the ones in the same directory
from Nagstamon import GUI
from Nagstamon import Actions

    
###### MAIN ##############

# necessary gobject thread initialization
gobject.threads_init()

# dictinary for servers
servers = dict()

# queue for debugging
debug_queue = Queue.Queue()

# Open windows etc. seen from GUI - locking each other not to do unwanted stuff if some windows interfere
GUILock = {}

"""
# create servers
for server in conf.servers.values():
    created_server = Actions.CreateServer(server, conf, debug_queue, Resources)
    if created_server is not None:
        servers[server.name] = created_server     
"""

# create servers
for server in conf.servers.values():
    if server.save_password == "False" and server.enabled == "True":
        # the auth dialog will fill the server's username and password with the given values
        GUI.AuthenticationDialog(server=server, Resources=Resources, conf=conf, debug_queue=debug_queue)        
    created_server = Actions.CreateServer(server, conf, debug_queue)
    if created_server is not None:
        servers[server.name] = created_server   

# Initiate Output
output = GUI.GUI(conf=conf, servers=servers, Resources=Resources, debug_queue=debug_queue, GUILock=GUILock)

# show notice if a legacy config file is used from commandline
if conf.legacyconfigfile_notice == True:
    notice = "Hello Nagstamon user!\nSince version 0.9.9 the configuration is stored \
in a config directory. Your config file has been \
converted and will be saved as the following directory:\n\n %s\n\n\
If you used to start Nagstamon with a special configuration file please use this path or \
create a new one for your custom start of Nagstamon." % ((conf.configdir))
    print "\n" + notice + "\n"
    output.Dialog(type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK, message=notice)


# Start debugging loop
debugloop = Actions.DebugLoop(conf=conf, debug_queue=debug_queue, output=output)
debugloop.start()

# start threaded nagios server checking loop
Actions.StartRefreshLoop(servers=servers, conf=conf, output=output)

# if unconfigured nagstamon shows the settings dialog to get settings
if conf.unconfigured == True:
    GUI.Settings(servers=servers, output=output, conf=conf)

# if checking for new version is set check now
if str(conf.check_for_new_version) == "True":
    check = Actions.CheckForNewVersion(servers=servers, output=output, mode="startup")
    check.start()

try:
    # Gtk Main Loop
    gtk.main()
    # save config
    conf.SaveConfig(output=output)
except Exception, err:
    output.error_dialog(err)
