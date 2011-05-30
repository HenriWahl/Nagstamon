#!/usr/bin/python
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

# try to get resources path if nagstamon got be installed by setup.py
try:
    import pkg_resources
    Resources = pkg_resources.resource_filename("Nagstamon", "resources")
except Exception, err:
    # set resources to "" in case there are no resources available from setup.py
    Resources = ""

# Resources on MacOS X, environment variable _MEIPASS2 comes from pyinstaller packed executable
# - does not really work at the moment
if "_MEIPASS2" in os.environ and sys.platform == "darwin":
    Resources = os.path.dirname(sys.executable) + "/resources"    
    
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

# create servers
for server in conf.servers.values():
    if server.save_password == "False" and server.enabled == "True":
        pwdialog = GUI.PasswordDialog(
            "Password for " + server.username + " on " + server.nagios_url + ": ")
        if pwdialog.password == None:
            sys.exit(1)
        server.password = pwdialog.password
    created_server = Actions.CreateServer(server, conf, debug_queue)
    if created_server is not None:
        servers[server.name] = created_server     
        
# Initiate Output
output = GUI.GUI(conf=conf, servers=servers, Resources=Resources, debug_queue=debug_queue)

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
    conf.SaveConfig()
except Exception, err:
    output.error_dialog(err)
