# encoding: utf-8

import urllib
import webbrowser
import socket
import time
import sys
import cookielib
import traceback
import gc
   
from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer

class CentreonServer(GenericServer): 
    TYPE = 'Centreon'
    # centreon generic web interface uses a sid which is needed to ask for news
    SID = None   
    # count for SID regeneration
    SIDcount = 0
    
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        GenericServer.__init__(self, **kwds)
        
        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Recheck", "Acknowledge", "Downtime"]        

        # cache MD5 username + password to reduce load
        self.MD5_username = Actions.MD5ify(self.conf.servers[self.get_name()].username)   
        self.MD5_password = Actions.MD5ify(self.conf.servers[self.get_name()].password)

        
    def init_HTTP(self):  
        """
        initialize HTTP connection
        """
        if self.HTTPheaders == {}:
            GenericServer.init_HTTP(self)
            # Centreon xml giveback method just should exist
            self.HTTPheaders["xml"] = {}                             
        
    
    def open_tree_view(self, host, service=""):
        # must be a host if service is empty...
        if service == "":
            webbrowser.open(self.nagios_cgi_url + "/index.php?" + urllib.urlencode({"p":201, "autologin":1,\
            "o":"hd", "useralias":self.MD5_username, "password":self.MD5_password, "host_name":host}))
        else:
            webbrowser.open(self.nagios_cgi_url + "/index.php?" + urllib.urlencode({"p":202, "autologin":1,\
            "o":"svcd", "useralias":self.MD5_username, "password":self.MD5_password, "host_name":host,\
             "service_description":service}))       

            
    def open_nagios(self):
        webbrowser.open(self.nagios_cgi_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password)
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open monitor web page " + self.nagios_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password)

        
    def open_services(self):
        webbrowser.open(self.nagios_cgi_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password + "&p=20202&o=svcpb")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open services web page " + "/index.php?p=20202&o=svcpb")

            
    def open_hosts(self):
        webbrowser.open(self.nagios_cgi_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password + "&p=20103&o=hpb")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open hosts web page " + self.nagios_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password + "&p=20103&o=hpb")
            
            
    def get_start_end(self, host):
        """
        get start and end time for downtime from Centreon server
        """
        try:
            cgi_data = urllib.urlencode({"p":"20305",\
                                         "o":"ah",\
                                         "host_name":host})
            result = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
            raw, error = result.result, result.error
            if error == "":
                # session id might have been invalid, so if necessary get a new one
                if raw.find('name="start" type="text" value="') == -1:
                    self.SID = self._get_sid().result
                    result = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
                    raw, error = result.result, result.error
                start_time = raw.split('name="start" type="text" value="')[1].split('"')[0]
                end_time = raw.split('name="end" type="text" value="')[1].split('"')[0]
                del raw
                # give values back as tuple      
                return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"            
            
    
    def GetHost(self, host):
        """
        Centreonified way to get host ip - attribute "a" in down hosts xml is of no use for up
        hosts so we need to get ip anyway from web page
        """
        # do a web interface search limited to only one result - the hostname
        cgi_data = urllib.urlencode({"sid":self.SID,\
                                    "search":host,\
                                    "num":0,\
                                    "limit":1,\
                                    "sort_type":"hostname",\
                                    "order":"ASC",\
                                    "date_time_format_status":"d/m/Y H:i:s",\
                                    "o":"h",\
                                    "p":20102,\
                                    "time":0})
        
        result = self.FetchURL(self.nagios_cgi_url + "/include/monitoring/status/Hosts/xml/hostXML.php?"\
                              + cgi_data, giveback="raw")
        raw = result.result
        # cut off <xml blabla>
        xmlraw = ElementTree.fromstring(raw.split("\n")[1])
        xmlobj = Actions.ObjectifyXML(xmlraw)   
        del raw, xmlraw

        if len(xmlobj) != 0:
            # when connection by DNS is not configured do it by IP
            try:
                if str(self.conf.connect_by_dns_yes) == "True":
                   # try to get DNS name for ip, if not available use ip
                    try:
                        address = socket.gethostbyaddr(xmlobj[0].a.text)[0]
                        del xmlobj
                    except:
                        self.Error(sys.exc_info())
                        address = str(xmlobj[0].a.text)                        
                        del xmlobj
                else:
                    address = str(xmlobj[0].a.text)
                    del xmlobj
            except:
                result, error = self.Error(sys.exc_info())
                return Result(error=error)
        
        else:   
            result, error = self.Error(sys.exc_info())
            return Result(error=error)
        
        # print IP in debug mode
        if str(self.conf.debug_mode) == "True":    
            self.Debug(server=self.get_name(), host=host, debug ="IP of %s:" % (host) + " " + address)
        # give back host or ip
        return Result(result=address)
        
            
    def _get_sid(self):
        """
        gets a shiny new SID for XML HTTP requests to Centreon cutting it out via .partition() from raw HTML
        additionally get php session cookie
        """
        try:
            raw = self.FetchURL(self.nagios_cgi_url + "/index.php?" + urllib.urlencode({"p":1, "autologin":1, "useralias":self.MD5_username, "password":self.MD5_password}), giveback="raw")
            del raw
            sid = str(self.Cookie._cookies.values()[0].values()[0]["PHPSESSID"].value)
            return Result(result=sid)
        except:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
        
        
    def _get_host_id(self, host):
        """
        get host_id via parsing raw html
        """
        cgi_data = urllib.urlencode({"p":201, "autologin":1,\
                                    "o":"hd", "host_name":host,\
                                    "useralias":self.MD5_username,\
                                    "password":self.MD5_password})
        result = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
        raw, error = result.result, result.error

        if error == "":
            host_id = raw.partition("var host_id = '")[2].partition("'")[0]
            del raw
            # if for some reason host_id could not be retrieved because
            # we get a login page clear cookies and SID and try again
            if host_id == "":
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), debug = "Host ID could not be retrieved, trying again...")
                self.SID = self._get_sid().result
                result = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
                raw, error = result.result, result.error
                host_id = raw.partition("var host_id= '")[2].partition("'")[0]
                del raw
        else:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug = "Host ID could not be retrieved.")

        # some cleanup        
        del result, error        
        
        # only if host_id is an usable integer return it    
        try:
            if int(host_id):
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), host=host, debug = "Host ID is " + host_id)
                return host_id
            else:
                return ""
        except:
            return ""
        

    def _get_host_and_service_id(self, host, service):
        """
        parse a ton of html to get a host and a service id...
        """
        cgi_data = urllib.urlencode({"p":"20305",\
                                     "host_name":host,\
                                     "service_description":service,\
                                     "o":"as"})
        result = self.FetchURL(self.nagios_cgi_url + "/main.php?"+ cgi_data, giveback="raw")
        raw, error = result.result, result.error
        
        # ids to give back, should contain to items, a host and a service id
        ids = []
        
        if error == "":
            if raw.find('selected="selected"') == -1:
                # looks there was this old SID problem again - get a new one 
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), host=host, service=service, debug = "IDs could not be retrieved, trying again...")                
                self.SID = self._get_sid().result
                result = self.FetchURL(self.nagios_cgi_url + "/main.php?"+ cgi_data, giveback="raw")
                raw, error = result.result, result.error
                
            # search ids
            for l in raw.splitlines():
                if l.find('selected="selected"') <> -1:
                    ids.append(l.split('value="')[1].split('"')[0])
            else:
                return ids
        else:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), host=host, service=service, debug = "IDs could not be retrieved.")                

            return "", ""    
        
        
    def _get_status(self):
        """
        Get status from Centreon Server
        """
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services":[], "hosts":[]}       
        
        # get sid in case this has not yet been done
        if self.SID == None or self.SID == "":
            self.SID = self._get_sid().result     
            
        # services (unknown, warning or critical?)
        nagcgiurl_services = self.nagios_cgi_url + "/include/monitoring/status/Services/xml/serviceXML.php?" + urllib.urlencode({"num":0, "limit":999, "o":"svcpb", "sort_type":"status", "sid":self.SID})

        # hosts (up or down or unreachable)
        nagcgiurl_hosts = self.nagios_cgi_url + "/include/monitoring/status/Hosts/xml/hostXML.php?" + urllib.urlencode({"num":0, "limit":999, "o":"hpb", "sort_type":"status", "sid":self.SID})

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:           
            result = self.FetchURL(nagcgiurl_hosts, giveback="xml")  
            xmlobj, error = result.result, result.error            
            if error != "": return Result(result=xmlobj, error=error)

            # in case there are no children session id is invalid
            if xmlobj == "<response>bad session id</response>":    
                del xmlobj
                if str(self.conf.debug_mode) == "True": 
                    self.Debug(server=self.get_name(), debug="Bad session ID, retrieving new one...")                

                # try again...
                self.SID = self._get_sid().result
                result = self.FetchURL(nagcgiurl_hosts, giveback="xml")
                xmlobj, error = result.result, result.error
                if error != "": return Result(result=xmlobj, error=error)   
                
            for l in xmlobj.findAll("l"):
                try:                       
                    n = {}
                    # host
                    n["host"] = str(l.hn.text)
                    # status
                    n["status"] = str(l.cs.text)
                    # last_check
                    n["last_check"] = str(l.lc.text)
                    # duration
                    n["duration"] = str(l.lsc.text)
                    # status_information
                    n["status_information"] = str(l.ou.text)
                    # attempts are not shown in case of hosts so it defaults to "N/A"
                    n["attempt"] = str(l.tr.text).split(" ")[0]
                    # host acknowledged or not, has to be filtered
                    n["acknowledged"] = str(l.ha.text)
                    # host notification disabled or not, has to be filtered
                    n["notification_enabled"] = str(l.ne.text)
                    # host check enabled or not, has to be filtered
                    n["check_enabled"] = str(l.ace.text)
                    # host down for maintenance or not, has to be filtered
                    n["scheduled_downtime"] = str(l.hdtm.text)
                    # is host flapping?
                    # the "is" flag indicates "is_flapping"... and doesn't seem to exist on hosts
                    # because python whines when l.is.text is used we go the .find() way
                    if l.find("is") != None:
                        n["flapping"] = str(l.find("is").text)
                    else:
                        n["flapping"] = "0"
                    # active checks enabled or passiveonly?
                    n["passiveonly"] = str(l.ace.text)
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
                        self.new_hosts[new_host].acknowledged = bool(int(n["acknowledged"]))
                        self.new_hosts[new_host].scheduled_downtime = bool(int(n["scheduled_downtime"]))
                        self.new_hosts[new_host].flapping = bool(int(n["flapping"]))
                        self.new_hosts[new_host].notifications_disabled = not bool(int(n["notification_enabled"]))
                        self.new_hosts[new_host].passiveonly = not bool(int(n["passiveonly"]))
                except:
                    # set checking flag back to False
                    self.isChecking = False
                    #return self.Error(sys.exc_info())
                    result, error = self.Error(sys.exc_info())
                    return Result(result=result, error=error)
            
            del xmlobj                
                
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            result = self.FetchURL(nagcgiurl_services, giveback="xml")            
            xmlobj, error = result.result, result.error
            if error != "": return Result(result=xmlobj, error=error)
            
            # in case there are no children session id is invalid
            if xmlobj == "<response>bad session id</response>": 
                # debug
                if str(self.conf.debug_mode) == "True": 
                    self.Debug(server=self.get_name(), debug="Bad session ID, retrieving new one...")                                
                # try again...
                self.SID = self._get_sid().result
                #result = self.FetchURL(nagcgiurl_services, giveback="raw")  
                result = self.FetchURL(nagcgiurl_services, giveback="xml")                
                xmlobj, error = result.result, result.error                
                if error != "": return Result(result=xmlobj, error=error)

            for l in xmlobj.findAll("l"):
                try:
                    n = {}
                    # host
                    # the resulting table of Nagios status.cgi table omits the
                    # hostname of a failing service if there are more than one
                    # so if the hostname is empty the nagios status item should get
                    # its hostname from the previuos item - one reason to keep "nagitems"
                    n["host"] = str(l.hn.text)
                    # service
                    n["service"] = str(l.sd.text)
                    # status
                    n["status"] = str(l.cs.text)
                    # last_check
                    n["last_check"] = str(l.lc.text)
                    # duration
                    n["duration"] = str(l.d.text)
                    # attempt
                    n["attempt"] = str(l.ca.text).split(" ")[0]
                    # status_information
                    n["status_information"] = str(l.po.text)
                    # service is acknowledged or not, has to be filtered
                    n["acknowledged"] = str(l.pa.text)
                    # service notification enabled or not, has to be filtered
                    n["notification_enabled"] = str(l.ne.text)
                    # active service check enabled or not, has to be filtered
                    n["passiveonly"] = str(l.ac.text)
                    # service down for maintenance or not, has to be filtered
                    n["scheduled_downtime"] = str(l.dtm.text)
                    # is service flapping?
                    # the "is" flag indicates "is_flapping"... and python whines when using l.is.text so we need to
                    # use .find("is") instead
                    n["flapping"] = str(l.find("is").text)
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
                        self.new_hosts[n["host"]].services[new_service].acknowledged = bool(int(n["acknowledged"]))
                        self.new_hosts[n["host"]].services[new_service].scheduled_downtime = bool(int(n["scheduled_downtime"]))
                        self.new_hosts[n["host"]].services[new_service].flapping = bool(int(n["flapping"]))
                        self.new_hosts[n["host"]].services[new_service].notifications_disabled = not bool(int(n["notification_enabled"]))
                        self.new_hosts[n["host"]].services[new_service].passiveonly = not bool(int(n["passiveonly"]))
                except:
                    # set checking flag back to False
                    self.isChecking = False
                    result, error = self.Error(sys.exc_info())
                    return Result(result=result, error=error)
                                        
            # do some cleanup
            del xmlobj
            
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
     
        # some cleanup
        del nagitems
        
        # return True if all worked well    
        return Result()        
        

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        # decision about host or service - they have different URLs
        try:
            if service == "":
                # host
                cgi_data = urllib.urlencode({"p":"20105", "cmd":"14", "host_name":host, \
                        "author":author, "comment":comment, "submit":"Add", "notify":int(notify),\
                        "persistent":int(persistent), "sticky":int(sticky), "ackhostservice":"0", "o":"hd", "en":"1"})
                # debug
                if str(self.conf.debug_mode) == "True": 
                    #print self.get_name(), host +": " + self.nagios_cgi_url + "/main.php?"+ cgi_data     
                    self.Debug(server=self.get_name(), host=host, debug=self.nagios_cgi_url + "/main.php?"+ cgi_data)                

                # running remote cgi command, also possible with GET method     
                raw = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw") 
                del raw
                
            # if host is acknowledged and all services should be to or if a service is acknowledged
            # (and all other on this host too)
            if service != "" or len(all_services) > 0:
                # service(s) @ host
                # if all_services is empty only one service has to be checked - the one clicked
                # otherwise if there all services should be acknowledged
                if len(all_services) == 0: all_services = [service]
    
                # acknowledge all services on a host
                for s in all_services:
                    # service @ host
                    # in case the Centreon guys one day fix their typos "persistent" and 
                    # "persistent" will both be given (it is "persistant" in scheduling for downtime)
                    cgi_data = urllib.urlencode({"p":"20215", "cmd":"15", "host_name":host, \
                            "author":author, "comment":comment, "submit":"Add", "notify":int(notify),\
                            "service_description":s, "force_check":"1", \
                            "persistent":int(persistent), "persistant":int(persistent),\
                            "sticky":int(sticky), "o":"svcd", "en":"1"}) 
                    # debug
                    if str(self.conf.debug_mode) == "True": 
                        self.Debug(server=self.get_name(), host=host, service=s, debug=self.nagios_cgi_url + "/main.php?" + cgi_data)                

                    # running remote cgi command with GET method, for some strange reason only working if
                    # giveback is "raw"
                    raw = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
                    del raw
        except:
            self.Error(sys.exc_info())
            

    def _set_recheck(self, host, service):
        """
        host and service ids are needed to tell Centreon what whe want
        """
        # yes this procedure IS resource waste... suggestions welcome!
        try:
        # decision about host or service - they have different URLs
            if service == "":
                # ... it can only be a host, get its id
                host_id = self._get_host_id(host)
                # fill and encode CGI data
                cgi_data = urllib.urlencode({"cmd":"host_schedule_check", "actiontype":1,\
                                             "host_id":host_id, "sid":self.SID})
                url = self.nagios_cgi_url + "/include/monitoring/objectDetails/xml/hostSendCommand.php?" + cgi_data
                del host_id
            else:
                # service @ host
                host_id, service_id = self._get_host_and_service_id(host, service)
                # fill and encode CGI data
                cgi_data = urllib.urlencode({"cmd":"service_schedule_check", "actiontype":1,\
                                             "host_id":host_id, "service_id":service_id, "sid":self.SID})
                url = self.nagios_cgi_url + "/include/monitoring/objectDetails/xml/serviceSendCommand.php?" + cgi_data
                del host_id, service_id
            # execute POST request
            raw = self.FetchURL(url, giveback="raw")
            del raw
        except:
            self.Error(sys.exc_info())
       

    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        """
        gets actual host and service ids and apply them to downtime cgi  
        """
        try:
            if service == "":
                # host
                host_id = self._get_host_id(host)
                cgi_data = urllib.urlencode({"p":"20305",\
                                             "host_id":host_id,\
                                             "submitA":"Save",\
                                             "persistent":int(fixed),\
                                             "persistant":int(fixed),\
                                             "start":start_time,\
                                             "end":end_time,\
                                             "comment":comment,\
                                             "o":"ah"})
                # debug
                if str(self.conf.debug_mode) == "True": 
                    self.Debug(server=self.get_name(), host=host, debug=self.nagios_cgi_url + "/main.php?" + cgi_data)                

            else:
                # service
                host_id, service_id = self._get_host_and_service_id(host, service)
                cgi_data = urllib.urlencode({"p":"20305",\
                                             "host_id":host_id,\
                                             "service_id":service_id,\
                                             "submitA":"Save",\
                                             "persistant":int(fixed),\
                                             "start":start_time,\
                                             "end":end_time,\
                                             "comment":comment,\
                                             "o":"as"})
                # debug
                if str(self.conf.debug_mode) == "True": 
                    self.Debug(server=self.get_name(), host=host, service=service, debug=self.nagios_cgi_url + "/main.php?" + cgi_data)                

            # running remote cgi command
            raw = self.FetchURL(self.nagios_cgi_url + "/main.php", giveback="raw", cgi_data=cgi_data)   
            del raw
        except:
            self.Error(sys.exc_info())

        
    def Hook(self):
        """
        in case count is down get a new SID, just in case
        """
        # a SIDcount of 300 should make 15 min when being run every 3 secs as it is at 
        # the moment in Actions.RefreshLoopOneServer()
        if self.SIDcount >= 300:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="Old SID: " + self.SID + " " + str(self.Cookie))                
            self.SID = self._get_sid().result
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="New SID: " +  self.SID + " " + str(self.Cookie))
            self.SIDcount = 0
        else:
            self.SIDcount += 1         
        
        # do some garbage collection
        gc.collect()
 
