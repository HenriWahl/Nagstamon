# encoding: utf-8

import threading
import gobject
import time
import datetime
import urllib
import webbrowser
import commands
import re
import sys
import traceback
import gtk

# if running on windows import winsound
import platform
if platform.system() == "Windows":
    import winsound

# Garbage collection
import gc

# import for MultipartPostHandler.py which is needed for Opsview downtime form
import urllib2
import mimetools, mimetypes
import os, stat

from Nagstamon import Objects
from Nagstamon.Objects import Result
    
#from Nagstamon import GUI
import GUI

# import md5 for centreon url autologin encoding
try:
    #from python 2.5 md5 is in hashlib
    from hashlib import md5
except:
    # older pythons use md5 lib
    from md5 import md5

# flag which indicates if already rechecking all
RecheckingAll = False


def StartRefreshLoop(servers=None, output=None, conf=None):
    """
    the everlasting refresh cycle - starts refresh cycle for every server as thread
    """

    for server in servers.values():
        if str(conf.servers[server.get_name()].enabled) == "True":
            server.thread = RefreshLoopOneServer(server=server, output=output, conf=conf)
            server.thread.start()


class RefreshLoopOneServer(threading.Thread):
    """
    one thread for one server per loop
    """
    # kind of a stop please flag, if set to True run() should run no more
    stopped = False
    # Check flag, if set and thread recognizes do a refresh, set to True at the beginning
    doRefresh = True
    
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        # include threading mechanism
        threading.Thread.__init__(self, name=self.server.get_name())
        self.setDaemon(1)

    def Stop(self):
        # simply sets the stopped flag to True to let the above while stop this thread when checking next
        self.stopped = True
        
    def Refresh(self):
        # simply sets the stopped flag to True to let the above while stop this thread when checking next
        self.doRefresh = True        
        
    def run(self):  
        """
        loop until end of eternity or until server is stopped
        """
              
        while self.stopped == False:          
            # check if we have to leave update interval sleep
            if self.server.count > int(self.conf.update_interval)*60: self.doRefresh = True       
            # self.doRefresh could also been changed by RefreshAllServers()
            if self.doRefresh == True:              
                # reset server count
                self.server.count = 0
                # check if server is already checked
                if self.server.isChecking == False:              
                    # set server status for status field in popwin
                    self.server.status = "Refreshing"
                    gobject.idle_add(self.output.popwin.UpdateStatus, self.server)
                    # get current status
                    server_status = self.server.GetStatus()
                    # GTK/Pango does not like tag brackets < and >, so clean them out from description
                    server_status.error = server_status.error.replace("<", "").replace(">", "").replace("\n", " ")
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        self.server.Debug(server=self.server.get_name(), debug="server return values: " + server_status.result + " " + server_status.error)
                    if server_status.error != "":
                        # set server status for status field in popwin 
                        self.server.status = "ERROR"
                        # give server status description for future usage    
                        self.server.status_description = str(server_status.error)
                        gobject.idle_add(self.output.popwin.UpdateStatus, self.server)
                        # tell gobject to care about GUI stuff - refresh display status
                        # use a flag to prevent all threads at once to write to statusbar label in case
                        # of lost network connectivity - this leads to a mysterious pango crash
                        if self.output.statusbar.isShowingError == False:
                            gobject.idle_add(self.output.RefreshDisplayStatus)
                            # wait a moment
                            time.sleep(5)
                            # change statusbar to the following error message
                            # show error message in statusbar
                            # shorter error message - see https://sourceforge.net/tracker/?func=detail&aid=3017044&group_id=236865&atid=1101373
                            gobject.idle_add(self.output.statusbar.ShowErrorMessage, {"True":"ERROR", "False":"ERR"}[str(self.conf.long_display)])
                            # wait some seconds
                            time.sleep(5) 
                            # set statusbar error message status back
                            self.output.statusbar.isShowingError = False                           
                        # wait a moment
                        time.sleep(10)
                    else:
                        # set server status for status field in popwin
                        self.server.status = "Connected"
                        # tell gobject to care about GUI stuff - refresh display status
                        gobject.idle_add(self.output.RefreshDisplayStatus)
                        # wait for the doRefresh flag to be True, if it is, do a refresh
                        if self.doRefresh == True:
                            if str(self.conf.debug_mode) == "True":
                                #print self.server.get_name(), ":", "Refreshing output - server is already checking:", self.server.isChecking                                        
                                self.server.Debug(server=self.server.get_name(), debug="Refreshing output - server is already checking: " + str(self.server.isChecking))
                            # reset refresh flag
                            self.doRefresh = False
                            # call Hook() for extra action
                            self.server.Hook()
            else:
                # sleep and count
                time.sleep(3)
                self.server.count += 3
                # call Hook() for extra action
                self.server.Hook()

                    
def RefreshAllServers(servers=None, output=None, conf=None):
    """
    one refreshing action, starts threads, one per polled server
    """    
    for server in servers.values():        
        # check if server is already checked
        if server.isChecking == False and str(conf.servers[server.get_name()].enabled) == "True":
            #debug
            if str(conf.debug_mode) == "True":
                #print "Checking server:", server.get_name()
                server.Debug(server=server.get_name(), debug="Checking server...")
    
            server.thread.Refresh()

            # set server status for status field in popwin
            server.status = "Refreshing"
            gobject.idle_add(output.popwin.UpdateStatus, server)
    
    
class DebugLoop(threading.Thread):    
    """
    run and empty debug_queue into debug log file
    """
    # stop flag
    stopped = False
    
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        
        # check if DebugLoop is already looping - if it does do not run another one
        for t in threading.enumerate():
            if t.getName() == "DebugLoop": 
                # loop gets stopped as soon as it starts - maybe waste
                self.stopped = True

        # initiate Loop
        try:
            threading.Thread.__init__(self, name="DebugLoop")
            self.setDaemon(1)
        except Exception, err:
            print err
        
        # open debug file if needed
        if str(self.conf.debug_to_file) == "True" and self.stopped == False:
            try:
                self.debug_file = open(self.conf.debug_file, "w")
            except Exception, err:
                # if path to file does not exist tell user
                self.output.ErrorDialog(err) 
        
        
    def run(self):       
        # as long as debugging is wanted do it
        while self.stopped == False and str(self.conf.debug_mode) == "True":
            # .get() waits until there is something to get - needs timeout in case no debug messages fly in
            debug_string = ""
            
            try:
                debug_string = self.debug_queue.get(True, 1)
                print debug_string
                if str(self.conf.debug_to_file) == "True" and self.__dict__.has_key("debug_file") and debug_string != "":
                    self.debug_file.write(debug_string + "\n")
            except:
                pass

            # if no debugging is needed anymore stop it
            if str(self.conf.debug_mode) == "False": self.stopped = True
            
            
    def Stop(self):
        # simply sets the stopped flag to True to let the above while stop this thread when checking next
        self.stopped = True

            
class Recheck(threading.Thread):
    """
    recheck a clicked service/host
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self, name=self.server.get_name() + "-Recheck")
        self.setDaemon(1)
        

    def run(self):
        try:
            self.server.set_recheck(self)
        except:
            self.server.Error(sys.exc_info())
               
        
class RecheckAll(threading.Thread):
    """
    recheck all services/hosts
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self, name="RecheckAll")
        self.setDaemon(1)
        

    def run(self):
        # get RecheckingAll flag to decide if rechecking all is possible (only if not already running)
        global RecheckingAll
        
        if RecheckingAll == False:
            RecheckingAll = True
            # put all rechecking threads into one dictionary
            rechecks_dict = dict()
            try:
                # debug
                if str(self.conf.debug_mode) == "True":
                    #print "Recheck all: Rechecking all services on all hosts on all servers..."
                    # workaround, take Debug method from first server reachable
                    self.servers.values()[0].Debug(debug="Recheck all: Rechecking all services on all hosts on all servers...")
                for server in self.servers.values():      
                    # only test enabled servers and only if not already 
                    if str(self.conf.servers[server.get_name()].enabled):
                        # set server status for status field in popwin
                        server.status = "Rechecking all started"
                        gobject.idle_add(self.output.popwin.UpdateStatus, server)

                        for host in server.hosts.values():
                            # construct an unique key which refers to rechecking thread in dictionary
                            rechecks_dict[server.get_name() + ": " + host.get_name()] = Recheck(server=server, host=host.get_name(), service="")
                            rechecks_dict[server.get_name() + ": " + host.get_name()].start()
                            # debug
                            if str(self.conf.debug_mode) == "True":
                                #print "Recheck all:", "rechecking", server.get_name() + ": " + host.get_name()                                
                                server.Debug(server=server.get_name(), host=host.get_name(), debug="Rechecking...")
                            for service in host.services.values():
                                # dito
                                if service.is_passive_only() == True:
                                    continue
                                rechecks_dict[server.get_name() + ": " + host.get_name() + ": " + service.get_name()] = Recheck(server=server, host=host.get_name(), service=service.get_name())
                                rechecks_dict[server.get_name() + ": " + host.get_name() + ": " + service.get_name()].start()
                                # debug
                                if str(self.conf.debug_mode) == "True":
                                    server.Debug(server=server.get_name(), host=host.get_name(), service=service.get_name(), debug="Rechecking...")
        
                # wait until all rechecks have been done
                while len(rechecks_dict) > 0:
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        #print "Recheck all: # of checks which still need to be done:", len(rechecks_dict)
                        # once again taking .Debug() from first server
                        self.servers.values()[0].Debug(server=server.get_name(), debug="Recheck all: # of checks which still need to be done: " + str(len(rechecks_dict)))

                    for i in rechecks_dict.copy():
                        # if a thread is stopped pop it out of the dictionary
                        if rechecks_dict[i].isAlive() == False:
                            rechecks_dict.pop(i)
                    # wait a second        
                    time.sleep(1)
                    
                # debug
                if str(self.conf.debug_mode) == "True":
                    #print "Recheck all: All servers, hosts and services are rechecked."
                    # once again taking .Debug() from first server
                    self.servers.values()[0].Debug(server=server.get_name(), debug="Recheck all: All servers, hosts and services are rechecked.")                
                # reset global flag
                RecheckingAll = False
                
                # after all and after a short delay to let the monitor apply the recheck requests refresh all to make changes visible soon
                time.sleep(5)
                RefreshAllServers(servers=self.servers, output=self.output, conf=self.conf)
                # do some cleanup
                del rechecks_dict
                #gc.collect()
                               
            except:
                RecheckingAll = False          
        else:
            # debug
            if str(self.conf.debug_mode) == "True":
                #print "Recheck all: Already rechecking all services on all hosts on all servers."
                # once again taking .Debug() from first server
                self.servers.values()[0].Debug(debug="Recheck all: Already rechecking all services on all hosts on all servers.")                

        
class Acknowledge(threading.Thread):
    """
    exceute remote cgi command with parameters from acknowledge dialog 
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)

    def run(self):
        self.server.set_acknowledge(self)
        
    
class Downtime(threading.Thread):
    """
    exceute remote cgi command with parameters from acknowledge dialog 
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)

    def run(self):
        self.server.set_downtime(self)
                   

def Downtime_get_start_end(server, host):
    # get start and end time from Nagios as HTML - the objectified HTML does not contain the form elements :-(
    # this used to happen in GUI.action_downtime_dialog_show but for a more strict separation it better stays here
    return server.get_start_end(host)


class SubmitCheckResult(threading.Thread):
    """
    exceute remote cgi command with parameters from submit check result dialog 
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)

    def run(self):
        self.server.set_submit_check_result(self)
        

class CheckForNewVersion(threading.Thread):
    """
        Check for new version of nagstamon using connections of configured servers 
    """    
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)
        
    
    def run(self):
        # try all servers respectively their net connections, one of them should be able to connect
        # to nagstamon.sourceforge.net
        
        # debug
        if str(self.output.conf.debug_mode) == "True":
            #print "Checking for new version..."
            # once again taking .Debug() from first server
            self.servers.values()[0].Debug(debug="Checking for new version...")

        
        for s in self.servers.values():
            # if connecton of a server is not yet used do it now
            if s.CheckingForNewVersion == False:
                # set the flag to lock that connection
                s.CheckingForNewVersion = True
                # remove newline
                result = s.FetchURL("http://nagstamon.sourceforge.net/latest_version", giveback="raw")
                version, error = result.result.split("\n")[0], result.error
                
                # debug
                if str(self.output.conf.debug_mode) == "True":
                    #print "Latest version from sourceforge.net:", version
                    # once again taking .Debug() from first server
                    self.servers.values()[0].Debug(debug="Latest version from sourceforge.net: " + str(version))
                
                # if we got a result notify user
                if error == "":
                    if version == self.output.version:
                        version_status = "latest"
                    else:
                        version_status = "out_of_date"
                    # if we got a result reset all servers checkfornewversion flags, 
                    # notify the user and break out of the for loop
                    for s in self.servers.values(): s.CheckingForNewVersion = False
                    # do not tell user that the version is latest when starting up nagstamon
                    if not (self.mode == "startup" and version_status == "latest"):
                        # gobject.idle_add is necessary to start gtk stuff from thread
                        gobject.idle_add(self.output.CheckForNewVersionDialog, version_status, version) 
                    break
                # reset the servers CheckingForNewVersion flag to allow a later check
                s.CheckingForNewVersion = False
                

class PlaySound(threading.Thread):
    """
        play notification sound in a threadified way to omit hanging gui
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)


    def run(self):
        if self.sound == "WARNING":
            if str(self.conf.notification_default_sound) == "True":
                self.Play(self.Resources + "/warning.wav")
            else:
                self.Play(self.conf.notification_custom_sound_warning)
        elif self.sound == "CRITICAL":
            if str(self.conf.notification_default_sound) == "True":
                self.Play(self.Resources + "/critical.wav")
            else:
                self.Play(self.conf.notification_custom_sound_critical)
        elif self.sound == "DOWN":
            if str(self.conf.notification_default_sound) == "True":
                self.Play(self.Resources + "/hostdown.wav")
            else:
                self.Play(self.conf.notification_custom_sound_down)
        elif self.sound =="FILE":
            self.Play(self.file)
            
    
    def Play(self, file):
        """
            depending on platform choose method to play sound
        """
        # debug
        if str(self.conf.debug_mode) == "True":
            # once again taking .Debug() from first server
            self.servers.values()[0].Debug(debug="Playing sound: " + file)
        if not platform.system() == "Windows":
            commands.getoutput("play -q %s" % file)
        else:
            winsound.PlaySound(file, winsound.SND_FILENAME)
            
                    
class Notification(threading.Thread):
    """
        Flash statusbar in a threadified way to omit hanging gui
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)


    def run(self):
        # counter for repeated sound
        soundcount = 0
        # in case of notifying in statusbar do some flashing and honking
        while self.output.Notifying == True:
            # as long as flashing flag is set statusbar flashes until someone takes care
            if self.output.statusbar.Flashing == True:
                if self.output.statusbar.isShowingError == False:
                    # check again because in the mean time this flag could have been changed by NotificationOff()
                    gobject.idle_add(self.output.statusbar.Flash)
            # if wanted play notification sound, if it should be repeated every minute (2*interval/0.5=interval) do so.
            if str(self.conf.notification_sound) == "True":
                if soundcount == 0:
                    sound = PlaySound(sound=self.sound, Resources=self.Resources, conf=self.conf, servers=self.servers)
                    sound.start()
                    soundcount += 1
                elif str(self.conf.notification_sound_repeat) == "True" and soundcount >= 2*int(self.conf.update_interval)*60:
                    soundcount = 0
                else:
                    soundcount += 1       
            time.sleep(0.5)
        # reset statusbar
        self.output.statusbar.Label.set_markup(self.output.statusbar.statusbar_labeltext)
        

class MoveStatusbar(threading.Thread):
    """
        Move statusbar in a threadified way to omit hanging gui and Windows-GTK 2.22 trouble
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)


    def run(self):
        # avoid flickering popwin while moving statusbar around
        # gets re-enabled from popwin.setShowable()
        self.output.popwin.Close()
        self.output.popwin.showPopwin = False  
        # in case of moving statusbar do some moves
        while self.output.statusbar.Moving == True:
            gobject.idle_add(self.output.statusbar.Move)
            time.sleep(0.01)
        


def OpenNagios(widget, server, output):   
    # open Nagios main page in your favorite web browser when nagios button is clicked
    # first close popwin
    output.popwin.Close()
    # start browser with URL
    server.open_nagios()


def OpenServices(widget, server, output):
    # open Nagios services in your favorite web browser when service button is clicked
    # first close popwin
    output.popwin.Close()
    # start browser with URL
    server.open_services()
 
   
def OpenHosts(widget, server, output):
    # open Nagios hosts in your favorite web browser when hosts button is clicked
    # first close popwin
    output.popwin.Close()
    # start browser with URL
    server.open_hosts()

    
def TreeViewNagios(server, host, service):
    # if the clicked row does not contain a service it mus be a host, 
    # so the nagios query is different 
    server.open_tree_view(host, service)

        
def TreeViewHTTP(host):
    # open Browser with URL of some Host
    webbrowser.open("http://" + host)


# contains dict with available server classes
# key is type of server, value is server class
# used for automatic config generation
# and holding this information in one place
REGISTERED_SERVERS = [] 
 
def register_server(server):
    """ Once new server class in created,
    should be registered with this function
    for being visible in config and
    accessible in application.
    """
    if server.TYPE not in [x[0] for x in REGISTERED_SERVERS]:
        REGISTERED_SERVERS.append((server.TYPE, server))


def get_registered_servers():
    """ Returns available server classes dict """
    return dict(REGISTERED_SERVERS)


def get_registered_server_type_list():
    """ Returns available server type name list with order of registering """
    return [x[0] for x in REGISTERED_SERVERS]


def CreateServer(server=None, conf=None, debug_queue=None):
    # create Server from config
    registered_servers = get_registered_servers()
    if server.type not in registered_servers:
        print 'Server type not supported: %s' % server.type
        return
    # give argument servername so CentreonServer could use it for initializing MD5 cache
    nagiosserver = registered_servers[server.type](conf=conf, name=server.name)
    nagiosserver.type = server.type
    nagiosserver.nagios_url = server.nagios_url
    nagiosserver.nagios_cgi_url = server.nagios_cgi_url
    nagiosserver.username = server.username
    if server.save_password or not server.enabled:
        nagiosserver.password = server.password
    else:
        pwdialog = GUI.PasswordDialog(
            "Password for " + server.username + " on " + server.nagios_url + ": ")
        if pwdialog.password == None:
            nagiosserver.password = ""
        else:
            nagiosserver.password = pwdialog.password        
    nagiosserver.use_proxy = server.use_proxy
    nagiosserver.use_proxy_from_os = server.use_proxy_from_os
    nagiosserver.proxy_address = server.proxy_address
    nagiosserver.proxy_username = server.proxy_username
    nagiosserver.proxy_password = server.proxy_password
    
    # access to thread-safe debug queue
    nagiosserver.debug_queue = debug_queue     
    
    # use server-owned attributes instead of redefining them with every request
    nagiosserver.passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
    nagiosserver.passman.add_password(None, server.nagios_url, server.username, server.password)
    nagiosserver.passman.add_password(None, server.nagios_cgi_url, server.username, server.password)  
    nagiosserver.basic_handler = urllib2.HTTPBasicAuthHandler(nagiosserver.passman)
    nagiosserver.digest_handler = urllib2.HTTPDigestAuthHandler(nagiosserver.passman)  
    nagiosserver.proxy_auth_handler = urllib2.ProxyBasicAuthHandler(nagiosserver.passman)    
    
    if str(nagiosserver.use_proxy) == "False":
        # use empty proxyhandler
        nagiosserver.proxy_handler = urllib2.ProxyHandler({})
    elif str(server.use_proxy_from_os) == "False":
        # if proxy from OS is not used there is to add a authenticated proxy handler
        nagiosserver.passman.add_password(None, nagiosserver.proxy_address, nagiosserver.proxy_username, nagiosserver.proxy_password)
        nagiosserver.proxy_handler = urllib2.ProxyHandler({"http": nagiosserver.proxy_address, "https": nagiosserver.proxy_address})
        nagiosserver.proxy_auth_handler = urllib2.ProxyBasicAuthHandler(nagiosserver.passman)   

    # create permanent urlopener for server to avoid memory leak with millions of openers    
    nagiosserver.urlopener = BuildURLOpener(nagiosserver)        
    # server's individual preparations for HTTP connections (for example cookie creation)
    if str(server.enabled) == "True":
        nagiosserver.init_HTTP()    

    # debug
    if str(conf.debug_mode) == "True":
        nagiosserver.Debug(server=server.name, debug="Created server.")

    return nagiosserver


def not_empty(x):
    '''tiny helper function for BeautifulSoup in GenericServer.py to filter text elements'''
    return bool(x.replace('&nbsp;', '').strip())


def BuildURLOpener(server):
    """
    if there should be no proxy used use an empty proxy_handler - only necessary in Windows,
    where IE proxy settings are used automatically if available
    In UNIX $HTTP_PROXY will be used
    The MultipartPostHandler is needed for submitting multipart forms from Opsview
    """
    # trying with changed digest/basic auth order as some digest auth servers do not
    # seem to work wi the previous way
    if str(server.use_proxy) == "False":
        server.proxy_handler = urllib2.ProxyHandler({})
        urlopener = urllib2.build_opener(server.digest_handler,\
                                         server.basic_handler,\
                                         server.proxy_handler,\
                                         urllib2.HTTPCookieProcessor(server.Cookie),\
                                         MultipartPostHandler)
    elif str(server.use_proxy) == "True":
        if str(server.use_proxy_from_os) == "True":
            urlopener = urllib2.build_opener(server.digest_handler,\
                                             server.basic_handler,\
                                             urllib2.HTTPCookieProcessor(server.Cookie),\
                                             MultipartPostHandler)
        else:
            # if proxy from OS is not used there is to add a authenticated proxy handler
            server.passman.add_password(None, server.proxy_address, server.proxy_username, server.proxy_password)
            server.proxy_handler = urllib2.ProxyHandler({"http": server.proxy_address, "https": server.proxy_address})
            server.proxy_auth_handler = urllib2.ProxyBasicAuthHandler(server.passman)
            urlopener = urllib2.build_opener(server.proxy_handler,\
                                            server.proxy_auth_handler,\
                                            server.digest_handler,\
                                            server.basic_handler,\
                                            urllib2.HTTPCookieProcessor(server.Cookie),\
                                            MultipartPostHandler)
    return urlopener


def OpenNagstamonDownload(output=None):
    """
        Opens Nagstamon Download page after being offered by update check
    """
    # first close popwin
    output.popwin.Close()
    # start browser with URL
    webbrowser.open("http://nagstamon.sourceforge.net/download")
       

def HostIsFilteredOutByRE(host, conf=None):
    """
        helper for applying RE filters in nagstamonGUI.RefreshDisplay()
    """
    try:
        if str(conf.re_host_enabled) == "True":
            pattern = re.compile(conf.re_host_pattern)           
            if len(pattern.findall(host)) > 0:
                if str(conf.re_host_reverse) == "True":
                    return False
                else:
                    return True
            else:
                if str(conf.re_host_reverse) == "True":
                    return True
                else:
                    return False
        
        # if RE are disabled return True because host is not filtered      
        return False
    except:
        pass
        
        
def ServiceIsFilteredOutByRE(service, conf=None):
    """
        helper for applying RE filters in nagstamonGUI.RefreshDisplay()
    """
    try:
        if str(conf.re_service_enabled) == "True":
            pattern = re.compile(conf.re_service_pattern)           
            if len(pattern.findall(service)) > 0:
                if str(conf.re_service_reverse) == "True":
                    return False
                else:
                    return True
            else:
                if str(conf.re_service_reverse) == "True":
                    return True 
                else:
                    return False
        
        # if RE are disabled return True because host is not filtered      
        return False
    except:
        pass
    

def HumanReadableDuration(seconds):
    """
    convert seconds given by Opsview to the form Nagios gives them
    like 70d 3h 34m 34s
    """
    timedelta = str(datetime.timedelta(seconds=int(seconds)))
    try:
        if timedelta.find("day") == -1:
            hms = timedelta.split(":")
            if len(hms) == 1:
                return "0d 0h 0m %ss" % (hms[0])
            elif len(hms) == 2:
                return "0d 0h %sm %ss" % (hms[0], hms[1])
            else:
                return "0d %sh %sm %ss" % (hms[0], hms[1], hms[2])
        else:
            # waste is waste - does anyone need it?
            days, waste, hms = str(timedelta).split(" ")
            hms = hms.split(":")
            return "%sd %sh %sm %ss" % (days, hms[0], hms[1], hms[2])
    except:
        # in case of any error return seconds we got
        return seconds

    
def MachineSortableDuration(raw):
    """
    Monitors gratefully shows duration even in weeks and months which confuse the
    sorting of popup window sorting - this functions wants to fix that
    """
    # dictionary for duration date string components
    d = {"M":0, "w":0, "d":0, "h":0, "m":0, "s":0}
    
    # if for some reason the value is empty/none make it compatible: 0s
    if raw == None: raw = "0s"

    # strip and replace necessary for Nagios duration values,
    # split components of duration into dictionary
    for c in raw.strip().replace("  ", " ").split(" "):
        number, period = c[0:-1],c[-1]
        d[period] = int(number) 
    # convert collected duration data components into seconds for being comparable
    return 16934400 * d["M"] + 604800 * d["w"] + 86400 * d["d"] + 3600 * d["h"] + 60 * d["m"] + d["s"]

    
def MD5ify(string):
    """
    makes something md5y of a given username or password for Centreon web interface access
    """
    return md5(string).hexdigest()


# <IMPORT>
# Borrowed from http://pipe.scs.fsu.edu/PostHandler/MultipartPostHandler.py
# Released under LGPL
# Thank you Will Holcomb!
class Callable:
    def __init__(self, anycallable):
        self.__call__ = anycallable

        
class MultipartPostHandler(urllib2.BaseHandler):
    handler_order = urllib2.HTTPHandler.handler_order - 10 # needs to run first

    def http_request(self, request):
        data = request.get_data()
        if data is not None and type(data) != str:
            v_vars = []
            try:
                for(key, value) in data.items():
                    v_vars.append((key, value))
            except TypeError:
                systype, value, traceback = sys.exc_info()
                raise TypeError, "not a valid non-string sequence or mapping object", traceback

            boundary, data = self.multipart_encode(v_vars)
            contenttype = 'multipart/form-data; boundary=%s' % boundary
            if(request.has_header('Content-Type')
               and request.get_header('Content-Type').find('multipart/form-data') != 0):
                print "Replacing %s with %s" % (request.get_header('content-type'), 'multipart/form-data')
            request.add_unredirected_header('Content-Type', contenttype)

            request.add_data(data)
        return request

    def multipart_encode(vars, boundary = None, buffer = None):
        if boundary is None:
            boundary = mimetools.choose_boundary()
        if buffer is None:
            buffer = ''
        for(key, value) in vars:
            buffer += '--%s\r\n' % boundary
            buffer += 'Content-Disposition: form-data; name="%s"' % key
            buffer += '\r\n\r\n' + value + '\r\n'
        buffer += '--%s--\r\n\r\n' % boundary
        return boundary, buffer
    
    multipart_encode = Callable(multipart_encode)
    https_request = http_request
    
# </IMPORT>

