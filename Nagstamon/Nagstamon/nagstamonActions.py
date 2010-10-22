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
import nagstamonGUI

# import hashlib for centreon url autologin encoding
import hashlib

# flag which indicates if already rechecking all
RecheckingAll = False


def StartRefreshLoop(servers=None, output=None, conf=None):
    """
    the everlasting refresh cycle - starts refresh cycle for every server as thread
    """
    for server in servers.values():
        if str(conf.servers[server.name].enabled) == "True":
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
        threading.Thread.__init__(self, name=self.server.name)
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
                # check if server is already checked
                if self.server.isChecking == False:              
                    # set server status for status field in popwin
                    self.server.status = "Refreshing"
                    gobject.idle_add(self.output.popwin.UpdateStatus, self.server)
                    # get current status
                    server_status = self.server.GetStatus()
    
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        print self.server.name, ": server return value :", server_status 

                    if server_status == "ERROR":
                        # set server status for status field in popwin
                        # shorter error message - see https://sourceforge.net/tracker/?func=detail&aid=3017044&group_id=236865&atid=1101373
                        if str(self.conf.long_display) == "True":
                            self.server.status = "ERROR"
                        else:
                            self.server.status = "ERR" 
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
                            gobject.idle_add(self.output.statusbar.ShowErrorMessage, self.server.status)
                            # wait some seconds
                            time.sleep(5) 
                            # set statusbar error message status back
                            self.output.statusbar.isShowingError = False
                            
                        # wait a moment
                        time.sleep(10)
                            
                        # do some cleanup
                        gc.collect()

                    else:
                        # set server status for status field in popwin
                        self.server.status = "Connected"
                        # tell gobject to care about GUI stuff - refresh display status
                        gobject.idle_add(self.output.RefreshDisplayStatus)
                        # do some cleanup
                        gc.collect()
                        # wait for the doRefresh flag to be True, if it is, do a refresh
                        if self.doRefresh == True:
                            if str(self.conf.debug_mode) == "True":
                                print self.server.name, ":", "Refreshing output - server is already checking:", self.server.isChecking                                        

                            # reset refresh flag
                            self.doRefresh = False

                            # do some cleanup
                            del self.server.count
                            gc.collect()
                            self.server.count = 0         
    
            else:
                # sleep and count
                time.sleep(3)
                self.server.count += 3
                gc.collect()

                    
def RefreshAllServers(servers=None, output=None, conf=None):
    """
    one refreshing action, starts threads, one per polled server
    """    
    for server in servers.values():        
        # check if server is already checked
        if server.isChecking == False and str(conf.servers[server.name].enabled) == "True":
            #debug
            if str(conf.debug_mode) == "True":
                print "Checking server:", server.name
    
            server.thread.Refresh()

            # set server status for status field in popwin
            server.status = "Refreshing"
            gobject.idle_add(output.popwin.UpdateStatus, server)
            
    # do some cleanup
    gc.collect()
    

class Recheck(threading.Thread):
    """
    recheck a clicked service/host
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self, name=self.server.name + "-Recheck")
        self.setDaemon(1)
        

    def run(self):
        try:
            self.server.set_recheck(self)
        except:
            import sys, traceback
            traceback.print_exc(file=sys.stdout)
            pass
               
        
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
                    print "Recheck all: Rechecking all services on all hosts on all servers..."

                for server in self.servers.values():                
                    # only test enabled servers and only if not already 
                    if str(self.conf.servers[server.name].enabled):
                        # set server status for status field in popwin
                        server.status = "Rechecking all started"
                        gobject.idle_add(self.output.popwin.UpdateStatus, server)
                        
                        for host in server.hosts.values():
                            # construct an unique key which refers to rechecking thread in dictionary
                            rechecks_dict[server.name + ": " + host.name] = Recheck(server=server, host=host.name, service=None)
                            rechecks_dict[server.name + ": " + host.name].start()
                            # debug
                            if str(self.conf.debug_mode) == "True":
                                print "Recheck all:", "rechecking", server.name + ": " + host.name
                            for service in host.services.values():
                                # dito
                                rechecks_dict[server.name + ": " + host.name + ": " + service.name] = Recheck(server=server, host=host.name, service=service.name)
                                rechecks_dict[server.name + ": " + host.name + ": " + service.name].start()
                                # debug
                                if str(self.conf.debug_mode) == "True":
                                    print "Recheck all:", "rechecking", server.name + ": " + host.name + ": " + service.name
                                    
                # wait until all rechecks have been done
                while len(rechecks_dict) > 0:
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        print "Recheck all: # of checks which still need to be done:", len(rechecks_dict)
                    
                    for i in rechecks_dict.copy():
                        # if a thread is stopped pop it out of the dictionary
                        if rechecks_dict[i].isAlive() == False:
                            rechecks_dict.pop(i)
                    # wait a second        
                    time.sleep(1)
                    
                # debug
                if str(self.conf.debug_mode) == "True":
                    print "Recheck all: All servers, hosts and services are rechecked."
                
                # reset global flag
                RecheckingAll = False
                
                # after all and after a short delay to let Nagios apply the recheck requests refresh all to make changes visible soon
                time.sleep(5)
                RefreshAllServers(servers=self.servers, output=self.output, conf=self.conf)
                # do some cleanup
                del rechecks_dict
                gc.collect()
                               
            except:
                RecheckingAll = False
                import traceback
                traceback.print_exc(file=sys.stdout)
           
        else:
            # debug
            if str(self.conf.debug_mode) == "True":
                print "Recheck all: Already rechecking all services on all hosts on all servers."
                
        
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
           print "Checking for new version..."
        
        for s in self.servers.values():
            # if connecton of a server is not yet used do it now
            if s.CheckingForNewVersion == False:
                # set the flag to lock that connection
                s.CheckingForNewVersion = True
                # remove newline
                version = s.FetchURL("http://nagstamon.sourceforge.net/latest_version", giveback="raw").split("\n")[0]
                
                # debug
                if str(self.output.conf.debug_mode) == "True":
                   print "Latest version from sourceforge.net:", version
                
                # if we got a result notify user
                if version != "ERROR":
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
            print "Playing sound:", file
        try:
            if not platform.system() == "Windows":
                commands.getoutput("play -q %s" % file)
            else:
                winsound.PlaySound(file, winsound.SND_FILENAME)
        except:
            pass
            
                    
class FlashStatusbar(threading.Thread):
    """
        Flash statusbar in a threadified way to omit hanging gui
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)


    def run(self):
        # in case of notifying in statusbar do some flashing
        try:
            if self.output.Notifying == True:
                # as long as flashing flag is set statusbar flashes until someone takes care
                while self.output.statusbar.Flashing == True:
                    if self.output.statusbar.isShowingError == False:
                        # check again because in the mean time this flag could have been changed by NotificationOff()
                        gobject.idle_add(self.output.statusbar.Flash)
                        time.sleep(0.5)
            # reset statusbar
            self.output.statusbar.Label.set_markup(self.output.statusbar.statusbar_labeltext)
        except:
            pass


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


def CreateServer(server=None, conf=None):
    # create Server from config
    registered_servers = get_registered_servers()
    if server.type not in registered_servers:
        print 'Server type not supported: %s' % server.type
        return
    # give argument servername so CentreonServer could use it for initializing MD5 cache
    nagiosserver = registered_servers[server.type](conf=conf, name=server.name)
    #nagiosserver.name = server.name
    nagiosserver.type = server.type
    nagiosserver.nagios_url = server.nagios_url
    nagiosserver.nagios_cgi_url = server.nagios_cgi_url
    nagiosserver.username = server.username
    if server.save_password or not server.enabled:
        nagiosserver.password = server.password
    else:
        pwdialog = nagstamonGUI.PasswordDialog(
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
    
    # debug
    if str(conf.debug_mode) == "True":
        print "Created Server", server.name

    return nagiosserver


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
            #result = pattern.findall(host)
            
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
            #result = pattern.findall(service)
            
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
    return hashlib.md5(string).hexdigest()
    
       
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

