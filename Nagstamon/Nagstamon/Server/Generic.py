# encoding: utf-8
import urllib
import urllib2
import cookielib
import sys
import socket
import gc
import copy
import webbrowser
import datetime
import time
import traceback
import base64
import re

try:
    import lxml.etree, lxml.objectify
except Exception, err:
    print
    print err
    print
    print "Could not load lxml.etree, lxml.objectify and lxml.html.clean, maybe you need to install python lxml."
    print
    sys.exit()
# fedora 8 and maybe others use lxml 2 which is more careful and offers more modules
# but which also makes necessary to clean Nagios html output
# if not available should be ok because not needed
try:
    import lxml.html.clean
except:
    pass

from Nagstamon.Actions import HostIsFilteredOutByRE, ServiceIsFilteredOutByRE
from Nagstamon.Objects import *


class GenericServer(object):
    """
        Abstract server which serves as template for all other types
        Default values are for Nagios servers
    """
    
    TYPE = 'Generic'
    
    # GUI sortable columns stuff
    DEFAULT_SORT_COLUMN_ID = 2
    COLOR_COLUMN_ID = 2
    HOST_COLUMN_ID = 0
    SERVICE_COLUMN_ID = 1
    
    COLUMNS = [
        HostColumn,
        ServiceColumn,
        StatusColumn,
        LastCheckColumn,
        DurationColumn,
        AttemptColumn,
        StatusInformationColumn
    ]
    
    DISABLED_CONTROLS = []

    # Nagios CGI flags translation dictionary for acknowledging hosts/services 
    HTML_ACKFLAGS = {True:"on", False:"off"}

    
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        
        self.type = ""
        self.nagios_url = ""
        self.nagios_cgi_url = ""
        self.username = ""
        self.password = ""
        self.use_proxy = False
        self.use_proxy_from_os = False
        self.proxy_address = ""
        self.proxy_username = ""
        self.proxy_password = ""        
        self.hosts = dict()
        self.hosts_in_maintenance = list()
        self.hosts_acknowledged = list()
        self.new_hosts = dict()
        self.new_hosts_in_maintenance = list()
        self.new_hosts_acknowledged = list()
        self.thread = ""
        self.isChecking = False
        self.debug = False
        self.CheckingForNewVersion = False
        self.WorstStatus = "UP"
        self.States = ["UP", "UNKNOWN", "WARNING", "CRITICAL", "UNREACHABLE", "DOWN"]
        self.nagitems_filtered_list = list()
        self.nagitems_filtered = {"services":{"CRITICAL":[], "WARNING":[], "UNKNOWN":[]}, "hosts":{"DOWN":[], "UNREACHABLE":[]}}
        self.downs = 0
        self.unreachables = 0
        self.unknowns = 0
        self.criticals = 0
        self.warnings = 0
        self.status = ""
        self.status_description = ""
        # needed for looping server thread
        self.count = 0
        # needed for RecheckAll - save start_time once for not having to get it for every recheck
        self.start_time = None
        self.Cookie = cookielib.CookieJar()        
        # use server-owned attributes instead of redefining them with every request
        self.passman = None   
        self.auth_handler = None
        self.digest_handler = None
        self.proxy_handler = None
        self.proxy_auth_handler = None        
        self.urlopener = None
        # headers for HTTP requests, might be needed for authorization on Nagios/Icinga Hosts
        self.HTTPheaders = {}
        # attempt to use only one bound list of TreeViewColumns instead of ever increasing one
        self.TreeView = None
        self.TreeViewColumns = list()
        self.ListStore = None
        self.ListStoreColumns = list()
        
    
    def init_HTTP(self):
        """
        partly not constantly working Basic Authorization requires extra Autorization headers,
        different between various server types
        """
        if self.HTTPheaders == {}:
            for giveback in ["raw", "obj"]:
                self.HTTPheaders[giveback] = {"Authorization": "Basic " + base64.b64encode(self.get_username() + ":" + self.get_password())}
        

    def get_name(self):
        """
        return stringified name
        """
        return str(self.name)    
    
    
    def get_username(self):
        """
        return stringified username
        """
        return str(self.username)  
        
    
    def get_password(self):
        """
        return stringified username
        """
        return str(self.password)  
        

    @classmethod
    def get_columns(cls, row):
        """ Gets columns filled with row data """
        for column_class in cls.COLUMNS:
            yield column_class(row)        
        
        
    def set_recheck(self, thread_obj):
        self._set_recheck(thread_obj.host, thread_obj.service)
        
        
    def _set_recheck(self, host, service):
        if service != "":
            if self.hosts[host].services[service].is_passive_only():
                # Do not check passive only checks
                return
        # get start time from Nagios as HTML to use same timezone setting like the locally installed Nagios
        result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"96", "host":host}), giveback="raw")
        html = result.result
        self.start_time = html.split("NAME='start_time' VALUE='")[1].split("'></b></td></tr>")[0]          
            
        # decision about host or service - they have different URLs
        if service == "":
            # host
            cmd_typ = "96"
        else:
            # service @ host
            cmd_typ = "7"
        # ignore empty service in case of rechecking a host   
        cgi_data = urllib.urlencode([("cmd_typ", cmd_typ),\
                                     ("cmd_mod", "2"),\
                                     ("host", host),\
                                     ("service", service),\
                                     ("start_time", self.start_time),\
                                     ("force_check", "on"),\
                                     ("btnSubmit", "Commit")])
        # execute POST request
        self.FetchURL(self.nagios_cgi_url + "/cmd.cgi", giveback="raw", cgi_data=cgi_data)
    
        
    def set_acknowledge(self, thread_obj):
        if thread_obj.acknowledge_all_services == True:
            all_services = thread_obj.all_services
        else:
            all_services = []
        self._set_acknowledge(thread_obj.host, thread_obj.service, thread_obj.author, thread_obj.comment,\
                              thread_obj.sticky, thread_obj.notify, thread_obj.persistent, all_services)
     
        
    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        url = self.nagios_cgi_url + "/cmd.cgi"      
        
        # decision about host or service - they have different URLs
        # do not care about the doube %s (%s%s) - its ok, "flags" cares about the necessary "&"
        if service == "":
            # host
            cgi_data = urllib.urlencode({"cmd_typ":"33", "cmd_mod":"2", "host":host, "com_author":author,\
                                         "sticky_ack":self.HTML_ACKFLAGS[sticky], "send_notification":self.HTML_ACKFLAGS[notify], "persistent":self.HTML_ACKFLAGS[persistent],\
                                         "com_data":comment, "btnSubmit":"Commit"})
            
        # if host is acknowledged and all services should be to or if a service is acknowledged
        # (and all other on this host too)
        if service != "" or len(all_services) > 0:
            # service @ host
            cgi_data = urllib.urlencode({"cmd_typ":"34", "cmd_mod":"2", "host":host, "service":service,\
                                         "sticky_ack":self.HTML_ACKFLAGS[sticky], "send_notification":self.HTML_ACKFLAGS[notify], "persistent":self.HTML_ACKFLAGS[persistent],\
                                         "com_author":author, "com_data":comment, "btnSubmit":"Commit"})          
        # running remote cgi command        
        self.FetchURL(url, giveback="raw", cgi_data=cgi_data)        

        # acknowledge all services on a host
        for s in all_services:
            # service @ host
            cgi_data = urllib.urlencode({"cmd_typ":"34", "cmd_mod":"2", "host":host, "service":s, "com_author":author, "com_data":comment, "btnSubmit":"Commit"})
            #running remote cgi command        
            self.FetchURL(url, giveback="raw", cgi_data=cgi_data)
            
    
    def set_downtime(self, thread_obj):
        self._set_downtime(thread_obj.host, thread_obj.service, thread_obj.author, thread_obj.comment, thread_obj.fixed,
                           thread_obj.start_time, thread_obj.end_time, thread_obj.hours, thread_obj.minutes)
    
        
    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        # decision about host or service - they have different URLs
        if service == "":
            # host
            cmd_typ = "55"
        else:
            # service @ host
            cmd_typ = "56"

        # for some reason Icinga is very fastidiuos about the order of CGI arguments, so please
        # here we go... it took DAYS :-(
        cgi_data = urllib.urlencode([("cmd_typ", cmd_typ),\
                                     ("cmd_mod", "2"),\
                                     ("trigger", "0"),\
                                     ("childoptions", "0"),\
                                     ("host", host),\
                                     ("service", service),\
                                     ("com_author", author),\
                                     ("com_data", comment),\
                                     ("fixed", fixed),\
                                     ("start_time", start_time),\
                                     ("end_time", end_time),\
                                     ("hours", hours),\
                                     ("minutes", minutes),\
                                     ("btnSubmit","Commit")])        
        # running remote cgi command
        result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi", giveback="raw", cgi_data=cgi_data)
        raw = result.result
        
    
    def get_start_end(self, host):
        """
        for GUI to get actual downtime start and end from server - they may vary so it's better to get
        directly from web interface
        """
        try:
            result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"55", "host":host}), giveback="raw")
            html = result.result
            start_time = html.split("NAME='start_time' VALUE='")[1].split("'></b></td></tr>")[0]
            end_time = html.split("NAME='end_time' VALUE='")[1].split("'></b></td></tr>")[0]
            # give values back as tuple
            return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"

        
    def open_tree_view(self, host, service=""):
        """
        open monitor from treeview context menu
        """
        # only type is important so do not care of service "" in case of host monitor       
        if service == "":
            typ = 1
        else:
            typ = 2      
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), host=host, service=service, debug="Open host/service monitor web page " + self.nagios_cgi_url + '/extinfo.cgi?' + urllib.urlencode({"type":typ, "host":host, "service":service}))
        webbrowser.open(self.nagios_cgi_url + '/extinfo.cgi?' + urllib.urlencode({"type":typ, "host":host, "service":service}))

        
    def open_nagios(self):
        webbrowser.open(self.nagios_url)
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open monitor web page " + self.nagios_url)

        
    def open_services(self):
        webbrowser.open(self.nagios_cgi_url + "/status.cgi?host=all&servicestatustypes=253")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open services web page " + self.nagios_url + "/status.cgi?host=all&servicestatustypes=253")
        
            
    def open_hosts(self):
        webbrowser.open(self.nagios_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open hosts web page " + self.nagios_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12")

            
    def _get_status(self):
        """
        Get status from Nagios Server
        """
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services":[], "hosts":[]}       
        
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        # hoststatus
        hoststatustypes = 12
        if str(self.conf.filter_all_down_hosts) == "True":
            hoststatustypes = hoststatustypes - 4
        if str(self.conf.filter_all_unreachable_hosts) == "True":
            hoststatustypes = hoststatustypes - 8
        # servicestatus
        servicestatustypes = 253
        if str(self.conf.filter_all_unknown_services) == "True":
            servicestatustypes = servicestatustypes - 8
        if str(self.conf.filter_all_warning_services) == "True":
            servicestatustypes = servicestatustypes - 4
        if str(self.conf.filter_all_critical_services) == "True":
            servicestatustypes = servicestatustypes - 16
        # serviceprops & hostprops both have the same values for the same states so I
        # group them together
        hostserviceprops = 0
        if str(self.conf.filter_acknowledged_hosts_services) == "True":
            hostserviceprops = hostserviceprops + 8
        if str(self.conf.filter_hosts_services_disabled_notifications) == "True":
            hostserviceprops = hostserviceprops + 8192
        if str(self.conf.filter_hosts_services_disabled_checks) == "True":
            hostserviceprops = hostserviceprops + 32
        if str(self.conf.filter_hosts_services_maintenance) == "True":
            hostserviceprops = hostserviceprops + 2
        
        # services (unknown, warning or critical?)
        nagcgiurl_services = self.nagios_cgi_url + "/status.cgi?host=all&servicestatustypes=" + str(servicestatustypes) + "&serviceprops=" + str(hostserviceprops)
        # hosts (up or down or unreachable)
        nagcgiurl_hosts = self.nagios_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=" + str(hoststatustypes) + "&hostprops=" + str(hostserviceprops)
        # fetching hosts in downtime and acknowledged hosts at once is not possible because these 
        # properties get added and nagios display ONLY hosts that have BOTH states
        # hosts that are in scheduled downtime, we will later omit services on those hosts
        # hostproperty 1 = HOST_SCHEDULED_DOWNTIME 
        nagcgiurl_hosts_in_maintenance = self.nagios_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hostprops=1"
        # hosts that are acknowledged, we will later omit services on those hosts
        # hostproperty 4 = HOST_STATE_ACKNOWLEDGED 
        nagcgiurl_hosts_acknowledged = self.nagios_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hostprops=4"

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            result = self.FetchURL(nagcgiurl_hosts)
            htobj, error = result.result, result.error
            
            if error != "": return Result(result=copy.deepcopy(htobj), error=error)            
            # workaround for Nagios < 2.7 which has an <EMBED> in its output
            # put a copy of a part of htobj into table to be able to delete htobj
            try:
                table = copy.deepcopy(htobj.body.table[self.HTML_BODY_TABLE_INDEX])
            except:
                table = copy.deepcopy(htobj.body.embed.table)
            
            # do some cleanup    
            del htobj
            
            for i in range(1, len(table.tr)):
                try:
                    # ignore empty <tr> rows
                    if not table.tr[i].countchildren() == 1:
                        n = {}
                        # host
                        try:
                            n["host"] = str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text)
                        except:
                            n["host"] = str(nagitems[len(nagitems)-1]["host"])
                        # status
                        n["status"] = str(table.tr[i].td[1].text)
                        # last_check
                        n["last_check"] = str(table.tr[i].td[2].text)
                        # duration
                        n["duration"] = str(table.tr[i].td[3].text)
                        # status_information
                        n["status_information"] = str(table.tr[i].td[4].text)
                        # attempts are not shown in case of hosts so it defaults to "N/A"
                        n["attempt"] = "N/A"
                        
                        # add dictionary full of information about this host item to nagitems
                        nagitems["hosts"].append(n)
                        # after collection data in nagitems create objects from its informations
                        # host objects contain service objects
                        if not self.new_hosts.has_key(n["host"]):
                            new_host = n["host"]
                            self.new_hosts[new_host] = GenericHost()
                            self.new_hosts[new_host].name = n["host"]
                            self.new_hosts[new_host].status = n["status"]
                            self.new_hosts[new_host].last_check = n["last_check"]
                            self.new_hosts[new_host].duration = n["duration"]
                            self.new_hosts[new_host].attempt = n["attempt"]
                            self.new_hosts[new_host].status_information= n["status_information"]
                except:
                    self.Error(sys.exc_info())
                
            # do some cleanup
            del table
            
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            #result = Result()
            result = self.FetchURL(nagcgiurl_services)
            htobj, error = result.result, result.error          
            if error != "": return Result(result=copy.deepcopy(htobj), error=error)
            # put a copy of a part of htobj into table to be able to delete htobj
            table = copy.deepcopy(htobj.body.table[self.HTML_BODY_TABLE_INDEX])
            
            # do some cleanup    
            del htobj
            
            for i in range(1, len(table.tr)):
                try:
                    # ignore empty <tr> rows - there are a lot of them - a Nagios bug? 
                    if not table.tr[i].countchildren() == 1:
                        n = {}
                        # host
                        # the resulting table of Nagios status.cgi table omits the
                        # hostname of a failing service if there are more than one
                        # so if the hostname is empty the nagios status item should get
                        # its hostname from the previuos item - one reason to keep "nagitems"
                        try:
                            n["host"] = str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text)
                        except:
                            n["host"] = str(nagitems["services"][len(nagitems["services"])-1]["host"])
                        # service
                        n["service"] = str(table.tr[i].td[1].table.tr.td.table.tr.td.a.text)
                        # status
                        n["status"] = str(table.tr[i].td[2].text)
                        # last_check
                        n["last_check"] = str(table.tr[i].td[3].text)
                        # duration
                        n["duration"] = str(table.tr[i].td[4].text)
                        # attempt
                        n["attempt"] = str(table.tr[i].td[5].text)
                        # status_information
                        n["status_information"] = str(table.tr[i].td[6].text)
                        n["passiveonly"] = False
                        n["notifications"] = True
                        n["flapping"] = False
                        td_html = lxml.etree.tostring(table.tr[i].td[1].table.tr.td[1]);
                        icons = re.findall(">\[{2}([a-z]+)\]{2}<", td_html)
                        # e.g. ['comment', 'passiveonly', 'ndisabled', 'flapping']
                        for icon in icons:
                            if (icon == "passiveonly"):
                                n["passiveonly"] = True
                            elif (icon == "ndisabled"):
                                n["notifications"] = False
                            elif (icon == "flapping"):
                                n["flapping"] = True
                        # cleaning        
                        del td_html, icons

                        # add dictionary full of information about this service item to nagitems - only if service
                        nagitems["services"].append(n)
                        # after collection data in nagitems create objects of its informations
                        # host objects contain service objects
                        if not self.new_hosts.has_key(n["host"]):
                            self.new_hosts[n["host"]] = GenericHost()
                            self.new_hosts[n["host"]].name = n["host"]
                            self.new_hosts[n["host"]].status = "UP"
                        # if a service does not exist create its object
                        if not self.new_hosts[n["host"]].services.has_key(n["service"]):
                            new_service = n["service"]
                            self.new_hosts[n["host"]].services[new_service] = GenericService()
                            self.new_hosts[n["host"]].services[new_service].host = n["host"]
                            self.new_hosts[n["host"]].services[new_service].name = n["service"]
                            self.new_hosts[n["host"]].services[new_service].status = n["status"]
                            self.new_hosts[n["host"]].services[new_service].last_check = n["last_check"]
                            self.new_hosts[n["host"]].services[new_service].duration = n["duration"]
                            self.new_hosts[n["host"]].services[new_service].attempt = n["attempt"]
                            self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"]
                            self.new_hosts[n["host"]].services[new_service].passiveonly = n["passiveonly"]
                except:
                    self.Error(sys.exc_info())
                                
            # do some cleanup
            del table
            
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error) 
                
         # hosts which are in scheduled downtime
        try:
            #result = Result()
            result = self.FetchURL(nagcgiurl_hosts_in_maintenance)           
            htobj, error = result.result, result.error                
            if error != "": return Result(result=copy.deepcopy(htobj), error=error)
            # workaround for Nagios < 2.7 which has an <EMBED> in its output
            try:
                table = copy.deepcopy(htobj.body.table[self.HTML_BODY_TABLE_INDEX])
            except:
                table = copy.deepcopy(htobj.body.embed.div.table)
            
            # do some cleanup    
            del htobj

            for i in range(1, len(table.tr)):
                try:
                    # ignore empty <tr> rows
                    if not table.tr[i].countchildren() == 1:
                        # host
                        try:
                            self.new_hosts_in_maintenance.append(str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text))
                            # get real status of maintained host
                            if self.new_hosts.has_key(self.new_hosts_in_maintenance[-1]):
                                self.new_hosts[self.new_hosts_in_maintenance[-1]].status = str(table.tr[i].td[1].text)
                        except:
                            self.Error(sys.exc_info())
                except:
                    self.Error(sys.exc_info())

            # do some cleanup
            del table
        
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
       
        # hosts which are acknowledged
        try:
            #result = Result()
            result = self.FetchURL(nagcgiurl_hosts_acknowledged)                                              
            htobj, error = result.result, result.error
            if error != "": return Result(result=copy.deepcopy(htobj), error=error)
            # workaround for Nagios < 2.7 which has an <EMBED> in its output
            try:
                table = copy.deepcopy(htobj.body.table[self.HTML_BODY_TABLE_INDEX])
            except:
                table = copy.deepcopy(htobj.body.embed.table)
                
            # do some cleanup    
            del htobj               

            for i in range(1, len(table.tr)):
                try:
                    # ignore empty <tr> rows
                    if not table.tr[i].countchildren() == 1:
                        # host
                        try:
                            self.new_hosts_acknowledged.append(str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text))
                            # get real status of acknowledged host
                            if self.new_hosts.has_key(self.new_hosts_acknowledged[-1]):
                                self.new_hosts[self.new_hosts_acknowledged[-1]].status = str(table.tr[i].td[1].text)
                        except:
                            self.Error(sys.exc_info())
                except:
                    self.Error(sys.exc_info())

            # do some cleanup
            del table

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
                
        # some cleanup
        del nagitems
        
        #dummy return in case all is OK
        return Result()
    

        
    def GetStatus(self):
        """
        get nagios status information from nagcgiurl and give it back
        as dictionary
        """

        # set checking flag to be sure only one thread cares about this server
        self.isChecking = True        
        
        # check if server is enabled, if not, do not get any status
        if str(self.conf.servers[self.get_name()].enabled) == "False":
            self.WorstStatus = "UP"
            # dummy filtered items
            self.nagitems_filtered = {"services":{"CRITICAL":[], "WARNING":[], "UNKNOWN":[]}, "hosts":{"DOWN":[], "UNREACHABLE":[]}}
            self.isChecking = False          
            return Result()    

        # some filtering is already done by the server specific _get_status()
        status = self._get_status()
        self.status, self.status_description = status.result, status.error

        if status.error != "":
            self.isChecking = False
            return Result(result=self.status, error=self.status_description)

        # this part has been before in GUI.RefreshDisplay() - wrong place, here it needs to be reset
        self.nagitems_filtered = {"services":{"CRITICAL":[], "WARNING":[], "UNKNOWN":[]}, "hosts":{"DOWN":[], "UNREACHABLE":[]}}
        
        # initialize counts for various service/hosts states
        # count them with every miserable host/service respective to their meaning
        self.downs = 0
        self.unreachables = 0
        self.unknowns = 0
        self.criticals = 0
        self.warnings = 0

        for host in self.new_hosts.values():
            # filtering out hosts, sorting by severity
            if host.status == "DOWN" and HostIsFilteredOutByRE(host.name, self.conf) == False\
            and (not (host.name in self.new_hosts_in_maintenance and \
            str(self.conf.filter_hosts_services_maintenance) == "True") and \
            not (host.name in self.new_hosts_acknowledged and \
            str(self.conf.filter_acknowledged_hosts_services) == "True")) and \
            str(self.conf.filter_all_down_hosts) == "False": 
                self.nagitems_filtered["hosts"]["DOWN"].append(host)
                self.downs += 1
            if host.status == "UNREACHABLE" and HostIsFilteredOutByRE(host.name, self.conf) == False\
            and (not host.name in self.new_hosts_acknowledged and not host.name in self.new_hosts_in_maintenance) and \
            str(self.conf.filter_all_unreachable_hosts) == "False": 
                self.nagitems_filtered["hosts"]["UNREACHABLE"].append(host)  
                self.unreachables += 1

            for service in host.services.values():
                # check hard/soft state, find out number of attempts and max attempts for
                # checking if soft state services should be shown
                real_attempt, max_attempt = service.attempt.split("/")
                # omit services on hosts in maintenance and acknowledged hosts
                if (not (host.name in self.new_hosts_in_maintenance and \
                str(self.conf.filter_hosts_services_maintenance) == "True") or \
                not (host.name in self.new_hosts_acknowledged and \
                str(self.conf.filter_acknowledged_hosts_services) == "True")) and \
                not (host.name in self.new_hosts_in_maintenance and\
                str(self.conf.filter_services_on_hosts_in_maintenance) == "True") and \
                not (real_attempt <> max_attempt and \
                str(self.conf.filter_services_in_soft_state) == "True") and \
                not (host.status == "DOWN" and \
                str(self.conf.filter_services_on_down_hosts) == "True") and \
                not (host.status == "UNREACHABLE" and \
                str(self.conf.filter_services_on_unreachable_hosts) == "True") and \
                HostIsFilteredOutByRE(host.name, self.conf) == False and \
                ServiceIsFilteredOutByRE(service.get_name(), self.conf) == False:
                    # sort by severity
                    if service.status == "CRITICAL" and str(self.conf.filter_all_critical_services) == "False": 
                        self.nagitems_filtered["services"]["CRITICAL"].append(service)
                        self.criticals += 1
                    if service.status == "WARNING" and str(self.conf.filter_all_warning_services) == "False": 
                        self.nagitems_filtered["services"]["WARNING"].append(service)
                        self.warnings += 1
                    if service.status == "UNKNOWN" and str(self.conf.filter_all_unknown_services) == "False": 
                        self.nagitems_filtered["services"]["UNKNOWN"].append(service)
                        self.unknowns += 1

        # find out if there has been some status change to notify user
        # compare sorted lists of filtered nagios items
        new_nagitems_filtered_list = []
        
        for i in self.nagitems_filtered["hosts"].values():
            for h in i:
                new_nagitems_filtered_list.append((h.name, h.status))   
            
        for i in self.nagitems_filtered["services"].values():
            for s in i:
                new_nagitems_filtered_list.append((s.host, s.name, s.status))  
                 
        # sort for better comparison
        new_nagitems_filtered_list.sort()

        # if both lists are identical there was no status change
        if (self.nagitems_filtered_list == new_nagitems_filtered_list):       
            self.WorstStatus = "UP"
        else:
            # if the new list is shorter than the first and there are no different hosts 
            # there one host/service must have been recovered, which is not worth a notification
            diff = []
            for i in new_nagitems_filtered_list:
                if not i in self.nagitems_filtered_list:
                    # collect differences
                    diff.append(i)
            if len(diff) == 0:
                self.WorstStatus = "UP"
            else:
                # if there are different hosts/services in list of new hosts there must be a notification
                # get list of states for comparison
                diff_states = []
                for d in diff:
                    diff_states.append(d[-1])
                # temporary worst state index   
                worst = 0
                for d in diff_states:
                    # only check worst state if it is valid
                    if d in self.States:
                        if self.States.index(d) > worst:
                            worst = self.States.index(d)
                            
                # final worst state is one of the predefined states
                self.WorstStatus = self.States[worst]
            
        # copy of listed nagitems for next comparison
        self.nagitems_filtered_list = new_nagitems_filtered_list

        # do some cleanup
        self.hosts.clear()
        del self.hosts_acknowledged[:], self.hosts_in_maintenance[:]

        # put new informations into respective dictionaries      
        self.hosts, self.hosts_acknowledged, self.hosts_in_maintenance = copy.deepcopy(self.new_hosts), copy.deepcopy(self.new_hosts_acknowledged), copy.deepcopy(self.new_hosts_in_maintenance)
        
        # do some cleanup
        del self.new_hosts_acknowledged[:], self.new_hosts_in_maintenance[:]
        self.new_hosts.clear()
        
        # after all checks are done unset checking flag
        self.isChecking = False
        
        # return True if all worked well    
        return Result()
    
    
    def FetchURL(self, url, giveback="obj", cgi_data=None, remove_tags=["link", "br", "img", "hr", "script", "th", "form", "div", "p"]):   
        """
        get content of given url, cgi_data only used if present
        "obj" FetchURL gives back a dict full of miserable hosts/services,
        "raw" it gives back pure HTML - useful for finding out IP or new version
        existence of cgi_data forces urllib to use POST instead of GET requests
        remove_tags became necessary for different expectations of GetStatus() and
        GetHost() - one wants div elements, the other don't 
        NEW: gives back a list containing result and, if necessary, a more clear error description
        """        
        
        # run this method which checks itself if there is some action to take for initializing connection
        self.init_HTTP()

        try:
            try:
                request = urllib2.Request(url, cgi_data, self.HTTPheaders[giveback])
                urlcontent = self.urlopener.open(request)
                # use opener - if cgi_data is not empty urllib uses a POST request
                del url, cgi_data, request                               
            except:
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)
           
            # give back pure HTML or XML in case giveback is "raw"
            if giveback == "raw":                           
                result = Result(result=urlcontent.read())
                urlcontent.close()
                del urlcontent
                return result
            
            # give back lxml-objectified data
            if giveback == "obj":
                # the heart of the whole Nagios-status-monitoring engine:
                # first step: parse the read HTML
                html = lxml.etree.HTML(urlcontent.read())
                    
                # second step: make pretty HTML of it
                #prettyhtml = lxml.etree.tostring(html, pretty_print=True)
                prettyhtml = lxml.etree.tostring(html, pretty_print=False)               
                del html
                prettyhtml = re.sub(r"<img\ssrc=\"[^\"]*/([a-z]+)\.gif\"[^>]+>", "[[\\1]]", prettyhtml)
                
                hier dann einfach <a href= blabla durch "" ersetzen, dito das </a>
                
                print prettyhtml

                # third step: clean HTML from tags which embarass libxml2 2.7
                # only possible when module lxml.html.clean has been loaded
                if sys.modules.has_key("lxml.html.clean"):
                    # clean html from tags which libxml2 2.7 is worried about
                    # this is the case with all tags that do not need a closing end tag like link, br, img
                    cleaner = lxml.html.clean.Cleaner(remove_tags=remove_tags, page_structure=True, style=False,\
                                                      safe_attrs_only=True, scripts=False, javascript=False)
                    prettyhtml = cleaner.clean_html(prettyhtml)
                    del cleaner
                    
                    # lousy workaround for libxml2 2.7 which worries about attributes without value
                    # we hope that nobody names a server '" nowrap>' - chances are pretty small because this "name"
                    # contains unallowed characters and is far from common sense
                    prettyhtml = prettyhtml.replace(' nowrap', '')
    
                # fourth step: make objects of tags for easy access              
                htobj = lxml.objectify.fromstring(prettyhtml)
                
                #do some cleanup
                urlcontent.close()
                del urlcontent, prettyhtml
        
                # give back HTML object from Nagios webseite
                return Result(result=htobj)            
                
            # special Opsview XML
            elif giveback == "opsxml":
                # objectify the xml and give it back after some cleanup
                xml = lxml.etree.XML(urlcontent.read())
                xmlpretty = lxml.etree.tostring(xml, pretty_print=True)
                xmlobj = lxml.objectify.fromstring(xmlpretty)
                urlcontent.close()
                del urlcontent, xml, xmlpretty               
                return Result(result=copy.deepcopy(xmlobj))
           
        except:
            # do some cleanup        
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)      

        result, error = self.Error(sys.exc_info())
        return Result(result=result, error=error)   
    

    def GetHost(self, host):
        """
        find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
        have their ip saved in Nagios
        """
        
        # initialize ip string
        ip = ""

        # glue nagios cgi url and hostinfo 
        nagcgiurl_host  = self.nagios_cgi_url + "/extinfo.cgi?type=1&host=" + host
        
        # get host info
        result = self.FetchURL(nagcgiurl_host, giveback="obj", remove_tags=["link", "br", "img", "hr", "script", "th", "form", "p"])
        htobj = result.result

        try:
            # take ip from object path
            ip = str(htobj.body.table.tr.td[1].div[5].text)
            # Workaround for Nagios 3.1 where there are groups listed whose the host is a member of
            if ip == "Member of":
                ip = str(htobj.body.table.tr.td[1].div[7].text)

            # workaround for URL-ified IP as described in SF bug 2967416
            # https://sourceforge.net/tracker/?func=detail&aid=2967416&group_id=236865&atid=1101370
            if not ip.find("://") == -1:
                ip = ip.split("://")[1]
            # print IP in debug mode
            if str(self.conf.debug_mode) == "True":    
                self.Debug(server=self.get_name(), host=host, debug ="IP of %s:" % (host) + " " + ip)
            # when connection by DNS is not configured do it by IP
            if str(self.conf.connect_by_dns_yes) == "True":
                # try to get DNS name for ip, if not available use ip
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except:
                    address = ip
            else:
                address = ip
        except:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
         
        # do some cleanup
        del htobj    

        # give back host or ip
        return Result(result=address)

    
    def Hook(self):
        """
        allows to add some extra actions for a monitor server to be executed in RefreshLoop
        inspired by Centreon and its seemingly Alzheimer desease regarding session ID/Cookie/whatever
        """
        # do some garbage collection
        gc.collect()  
    
    
    def Error(self, error):
        """
        Handle errors somehow - print them or later log them into not yet existing log file
        """
        if str(self.conf.debug_mode) == "True":
            debug = ""
            for line in traceback.format_exception(error[0], error[1], error[2], 5):
                debug += line
            self.Debug(server=self.get_name(), debug=debug, head="ERROR")
            
        return ["ERROR", traceback.format_exception_only(error[0], error[1])[0]]
    
    
    def Debug(self, server="", host="", service="", debug="", head="DEBUG"):
        """
        centralized debugging
        """
        debug_string =  " ".join((head + ":",  str(datetime.datetime.now()), server, host, service, debug))     
        # give debug info to debug loop for thread-save log-file writing
        self.debug_queue.put(debug_string)
        
