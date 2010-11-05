# encoding: utf-8

import urllib
import webbrowser
import socket
import time
import sys
import cookielib
import traceback

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

import nagstamonActions
from nagstamonObjects import *
from Generic import GenericServer


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

        # cache MD5 username + password to reduce load
        self.MD5_username = nagstamonActions.MD5ify(self.conf.servers[self.name].username)   
        self.MD5_password = nagstamonActions.MD5ify(self.conf.servers[self.name].password)
        
    
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
            print self.name, ":", "Open monitor web page", self.nagios_cgi_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password
        
        
    def open_services(self):
        webbrowser.open(self.nagios_cgi_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password + "&p=20202&o=svcpb")
        # debug
        if str(self.conf.debug_mode) == "True":
            print self.name, ":", "Open hosts web page", self.nagios_cgi_url + "/index.php?p=20202&o=svcpb"
        
    def open_hosts(self):
        webbrowser.open(self.nagios_cgi_url + "/index.php?autologin=1&p=1&useralias=" + self.MD5_username + "&password=" + self.MD5_password + "&p=20103&o=hpb")
        # debug
        if str(self.conf.debug_mode) == "True":
            print self.name, ":", "Open hosts web page", self.nagios_cgi_url + "/index.php?p=20103&o=hpb"

            
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
                    self.SID = self._get_sid()
                    result = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
                    raw, error = result.result, result.error
                start_time = raw.split('name="start" type="text" value="')[1].split('"')[0]
                end_time = raw.split('name="end" type="text" value="')[1].split('"')[0]
                # give values back as tuple      
                return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"            
            
    
    def GetHost(self, host):
        """
        Centreonified way to get host ip - attribute "a" in down hosts xml is of now use for up
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
        htobj = lxml.objectify.fromstring(raw)
               
        if htobj.__dict__.has_key("l"):   
            # when connection by DNS is not configured do it by IP
            try:
                if str(self.conf.connect_by_dns_yes) == "True":
                   # try to get DNS name for ip, if not available use ip
                    try:
                        address = socket.gethostbyaddr(htobj.l.a.text)[0]
                    except:
                        self.Error(sys.exc_info())
                        address = htobj.l.a.text
                else:
                    address = htobj.l.a.text
            except:
                self.Error(sys.exc_info())
                address = "ERROR"
        
        else: address = "ERROR"    

        # print IP in debug mode
        if str(self.conf.debug_mode) == "True":    
            print "Address of %s:" % (host), address
        
        # give back host or ip
        #return [address]
        return Result(result=address)
        
            
    def _get_sid(self):
        """
        gets a shiny new SID for XML HTTP requests to Centreon cutting it out via .partition() from raw HTML
        additionally get php session cookie
        """
        try:
            # why not get a new cookie with every new session id?    
            self.Cookie = cookielib.CookieJar()    
            self.FetchURL(self.nagios_cgi_url + "/index.php?" + urllib.urlencode({"p":1, "autologin":1, "useralias":self.MD5_username, "password":self.MD5_password}), giveback="raw")
            sid = self.Cookie._cookies.values()[0].values()[0]["PHPSESSID"].value
            #debug
            print self.name, sid
            return Result(result=sid)
        except:
            #return self.Error(sys.exc_info())
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
            # if for some reason host_id could not be retrieved because
            # we get a login page clear cookies and SID and try again
            if host_id == "":
                if str(self.conf.debug_mode) == "True":
                    print self.name, ":", host, "ID could not be retrieved, trying again..."                  
                self.SID = self._get_sid()
                result = self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
                raw, error = result.result, result.error
                host_id = raw.partition("var host_id= '")[2].partition("'")[0]

        else:
            if str(self.conf.debug_mode) == "True":
                print self.name, ":", host, "ID could not be retrieved."

        # only if host_id is an usable integer return it    
        try:
            if int(host_id):
                return host_id
            else:
                return ""
        except:
            #debug
            print "host_id:", host_id
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
                    print self.name, ":", host, service, "IDs could not be retrieved, trying again..." 
                self.SID = self._get_sid()
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
                print self.name, ":", host, service, "IDs could not be retrieved."
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
            self.SID = self._get_sid()     
            
        # services (unknown, warning or critical?)
        nagcgiurl_services = self.nagios_cgi_url + "/include/monitoring/status/Services/xml/serviceXML.php?" + urllib.urlencode({"num":0, "limit":999, "o":"svcpb", "sort_type":"status", "sid":self.SID})

        # hosts (up or down or unreachable)
        nagcgiurl_hosts = self.nagios_cgi_url + "/include/monitoring/status/Hosts/xml/hostXML.php?" + urllib.urlencode({"num":0, "limit":999, "o":"hpb", "sort_type":"status", "sid":self.SID})

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:           
            result = self.FetchURL(nagcgiurl_hosts, giveback="raw")
            raw, error = result.result, result.error
            
            if error != "": return Result(result=raw, error=error)

            htobj = lxml.objectify.fromstring(raw)
            # in case there are no children session id is invalid
            if htobj.getchildren() == []:
                if str(self.conf.debug_mode) == "True": 
                    print self.name, "bad session ID, retrieving new one..." 
                # try again...
                self.SID = self._get_sid()
                result = self.FetchURL(nagcgiurl_hosts, giveback="raw")
                raw, error = result.result, result.error
                if error != "": return Result(result=raw, error=error)
                htobj = lxml.objectify.fromstring(raw)
                time.sleep(1)
                 
            if htobj.__dict__.has_key("l"):
                for l in htobj.l:
                    try:                       
                        n = {}
                        # host
                        n["host"] = l.hn.text
                        # status
                        n["status"] = l.cs.text
                        # last_check
                        n["last_check"] = l.lc.text
                        # duration
                        n["duration"] = l.lsc.text
                        # status_information
                        n["status_information"] = l.ou.text
                        # attempts are not shown in case of hosts so it defaults to "N/A"
                        n["attempt"] = l.tr.text
                        # host acknowledged or not, has to be filtered
                        n["acknowledged"] = l.ha.text
                        # host notification disabled or not, has to be filtered
                        n["notification_enabled"] = l.ne.text
                        # host check enabled or not, has to be filtered
                        n["check_enabled"] = l.ace.text
                        # host down for maintenance or not, has to be filtered
                        n["in_downtime"] = l.hdtm.text
                        
                        # store information about acknowledged and down hosts for further reference
                        if n["in_downtime"] == "1" : self.new_hosts_in_maintenance.append(n["host"])
                        if n["acknowledged"] == "1" : self.new_hosts_acknowledged.append(n["host"])
                         
                        # what works in cgi-Nagios via cgi request has to be filtered out here "manually"
                        if not (str(self.conf.filter_acknowledged_hosts_services) == "True" and \
                           n["acknowledged"] == "1") and \
                           not (str(self.conf.filter_hosts_services_disabled_notifications) == "True" and \
                           n["notification_enabled"] == "0") and \
                           not (str(self.conf.filter_hosts_services_disabled_checks) == "True" and \
                           n["check_enabled"] == "0") and \
                           not (str(self.conf.filter_hosts_services_maintenance) == "True" and \
                           n["in_downtime"] == "1") and\
                           not (str(self.conf.filter_all_down_hosts) == "True" and n["status"] == "DOWN") and\
                           not (str(self.conf.filter_all_unreachable_hosts) == "True" and n["status"] == "UNREACHABLE"):
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
                        # set checking flag back to False
                        self.isChecking = False
                        #return self.Error(sys.exc_info())
                        result, error = self.Error(sys.exc_info())
                        return Result(result=result, error=error)
            
        except:
            # set checking flag back to False
            self.isChecking = False
            #return self.Error(sys.exc_info())
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
      
        # services
        try:
            result = self.FetchURL(nagcgiurl_services, giveback="raw")
            raw, error = result.result, result.error
            if error != "": return Result(result=raw, error=error)
            htobj = lxml.objectify.fromstring(raw)     
            # in case there are no children session id is invalid
            if htobj.getchildren == []:
                # debug
                if str(self.conf.debug_mode) == "True": 
                    print self.name, "bad session ID, retrieving new one..." 
                # try again...
                self.SID = self._get_sid()
                result = self.FetchURL(nagcgiurl_services, giveback="raw")  
                raw, error = result.result, result.error               
                
                if error != "": return Result(result=raw, error=error)

                htobj = lxml.objectify.fromstring(raw)                           
            
            if htobj.__dict__.has_key("l"):
                for l in htobj.l:
                    try:
                        n = {}
                        # host
                        # the resulting table of Nagios status.cgi table omits the
                        # hostname of a failing service if there are more than one
                        # so if the hostname is empty the nagios status item should get
                        # its hostname from the previuos item - one reason to keep "nagitems"
                        n["host"] = l.hn.text
                        # service
                        n["service"] = l.sd.text
                        # status
                        n["status"] = l.cs.text
                        # last_check
                        n["last_check"] = l.lc.text
                        # duration
                        n["duration"] = l.d.text
                        # attempt
                        n["attempt"] = l.ca.text
                        # status_information
                        n["status_information"] = l.po.text
                        # service is acknowledged or not, has to be filtered
                        n["acknowledged"] = l.pa.text
                        # service notification enabled or not, has to be filtered
                        n["notification_enabled"] = l.ne.text
                        # service check enabled or not, has to be filtered
                        n["check_enabled"] = l.ac.text
                        # service down for maintenance or not, has to be filtered
                        n["in_downtime"] = l.dtm.text

                        # what works in cgi-Nagios via cgi request has to be filtered out here "manually"
                        if not (str(self.conf.filter_acknowledged_hosts_services) == "True" and \
                           n["acknowledged"] == "1") and \
                           not (str(self.conf.filter_hosts_services_disabled_notifications) == "True" and \
                           n["notification_enabled"] == "0") and \
                           not (str(self.conf.filter_hosts_services_disabled_checks) == "True" and \
                           n["check_enabled"] == "0") and \
                           not (str(self.conf.filter_hosts_services_maintenance) == "True" and \
                           n["in_downtime"] == "1") and\
                           not (str(self.conf.filter_all_unknown_services) == "True" and n["status"] == "UNKNOWN") and\
                           not (str(self.conf.filter_all_warning_services) == "True" and n["status"] == "WARNING") and\
                           not (str(self.conf.filter_all_critical_services) == "True" and n["status"] == "CRITICAL"): 
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
                    except:
                        # set checking flag back to False
                        self.isChecking = False
                        #return self.Error(sys.exc_info())
                        result, error = self.Error(sys.exc_info())
                        return Result(result=result, error=error)
                                            
            # do some cleanup
            del htobj
            
        except:
            # set checking flag back to False
            self.isChecking = False
            #return self.Error(sys.exc_info())
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
                    print self.name, host +": " + self.nagios_cgi_url + "/main.php?"+ cgi_data     
                
                # running remote cgi command, also possible with GET method     
                self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")      
            else:
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
                        print self.name, host, s +": " + self.nagios_cgi_url + "/main.php?" + cgi_data            
                        
                    # running remote cgi command with GET method, for some strange reason only working if
                    # giveback="raw"
                    self.FetchURL(self.nagios_cgi_url + "/main.php?" + cgi_data, giveback="raw")
        except:
            self.Error(sys.exc_info())
            

    def _set_recheck(self, host, service):
        """
        host and service ids are needed to tell Centreon what whe want
        """
        # yes this procedure IS resource waste... suggestions welcome!
        try:
        # decision about host or service - they have different URLs
            if not service:
                # ... it can only be a host, get its id
                host_id = self._get_host_id(host)
                # fill and encode CGI data
                cgi_data = urllib.urlencode({"cmd":"host_schedule_check", "actiontype":1,\
                                             "host_id":host_id, "sid":self.SID})
                url = self.nagios_cgi_url + "/include/monitoring/objectDetails/xml/hostSendCommand.php?" + cgi_data
                
            else:
                # service @ host
                host_id, service_id = self._get_host_and_service_id(host, service)
                # fill and encode CGI data
                cgi_data = urllib.urlencode({"cmd":"service_schedule_check", "actiontype":1,\
                                             "host_id":host_id, "service_id":service_id, "sid":self.SID})
                url = self.nagios_cgi_url + "/include/monitoring/objectDetails/xml/serviceSendCommand.php?" + cgi_data

            # execute POST request
            self.FetchURL(url, giveback="raw")
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
                    print self.name, host +": " + self.nagios_cgi_url + "/main.php?"+ cgi_data                
    
            else:
                # service
                host_id, service_id = self._get_host_and_service_id(host, service)
                cgi_data = urllib.urlencode({"p":"20305",\
                                             "host_id":host_id,\
                                             "service_id":service_id,\
                                             "submitA":"Save",\
                                             #"persistent":int(fixed),\
                                             "persistant":int(fixed),\
                                             "start":start_time,\
                                             "end":end_time,\
                                             "comment":comment,\
                                             "o":"as"})
                # debug
                if str(self.conf.debug_mode) == "True": 
                    print self.name, host +": " + self.nagios_cgi_url + "/main.php?"+ cgi_data
           
            # running remote cgi command
            self.FetchURL(self.nagios_cgi_url + "/main.php", giveback="raw", cgi_data=cgi_data)   
        except:
            self.Error(sys.exc_info())

        
    def Hook(self):
        """
        in case count is down get a new SID, just in case
        """
        # a SIDcount of 300 should make 15 min when being run every 3 secs as it is at 
        # the moment in nagstamonActions.RefreshLoopOneServer()
        if self.SIDcount >= 300:
            if str(self.conf.debug_mode) == "True":
                print self.name + ":", "old SID:", self.SID, self.Cookie
            self.SID = self._get_sid()
            if str(self.conf.debug_mode) == "True":
                print self.name + ":", "new SID:", self.SID, self.Cookie
            self.SIDcount = 0
        else:
            self.SIDcount += 1          
            