# encoding: utf-8

import sys
import re
from Nagstamon.Server.Generic import GenericServer
from Nagstamon.BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
from Nagstamon.Objects import *
import urllib
import urllib2


def not_empty(x):
    '''tiny helper function to filter text elements'''
    return bool(x.replace('&nbsp;', '').strip())


class LxmlFreeGenericServer(GenericServer):
    '''This is a version of GenericServer that only replaces the use of lxml
       with standard etree and html5lib.
    '''
    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)
        
        # dictionary to translate status bitmaps on webinterface into status flags
        # this are defaults from Nagios
        self.STATUS_MAPPING = { "ack.gif" : "acknowledged",\
                                  "passiveonly.gif" : "passive",\
                                  "ndisabled.gif" : "notifications_disabled",\
                                  "downtime.gif" : "scheduled_downtime",\
                                  "flapping.gif" : "flapping" }

    def FetchURL(self, url, giveback='soup', cgi_data=None, remove_tags=None):
        """
        Multipurpose URL fetching method, usable everywhere where URLS are retrieved
        """
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="FetchURL: " + url + " CGI Data: " + str(cgi_data))
        
        if not remove_tags:
            remove_tags = ["link", "br", "img", "hr", "script", "th", "form", "div", "p"]
            
        self.init_HTTP()            
            
        if giveback == 'soup':
            try:
                request = urllib2.Request(url, cgi_data, self.HTTPheaders['obj'])
                # use opener - if cgi_data is not empty urllib uses a POST request
                urlcontent = self.urlopener.open(request)
                del url, cgi_data, request
                doc = BeautifulSoup(urlcontent, convertEntities=BeautifulSoup.ALL_ENTITIES)
                return Result(result=doc)
            except:
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)
            
        # generic XML
        elif giveback == "xml":
            request = urllib2.Request(url, cgi_data)
            urlcontent = self.urlopener.open(request)
            xmlobj = BeautifulStoneSoup(urlcontent.read(), convertEntities=BeautifulStoneSoup.XML_ENTITIES)
            urlcontent.close()
            del urlcontent          
            return Result(result=copy.deepcopy(xmlobj))   
            
        # special Opsview XML
        elif giveback == "opsxml":
            request = urllib2.Request(url, cgi_data, self.HTTPheaders['opsxml'])
            urlcontent = self.urlopener.open(request)
            xmlobj = BeautifulStoneSoup(urlcontent.read(), convertEntities=BeautifulStoneSoup.XML_ENTITIES)
            urlcontent.close()
            del urlcontent          
            return Result(result=copy.deepcopy(xmlobj))   
        
        else:
            return GenericServer.FetchURL(self, url, giveback, cgi_data, remove_tags)
        
    
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

            # put a copy of a part of htobj into table to be able to delete htobj
            table = copy.deepcopy(htobj('table', {'class': 'status'})[0])

            # do some cleanup
            del htobj
            
            # access table rows
            trs = table('tr', recursive=False)
            # kick out table heads
            trs.pop(0)
            
            for tr in trs:
                try:
                    # ignore empty <tr> rows
                    if len(tr('td', recursive=False)) > 1:
                        n = {}
                        # get tds in one tr
                        tds = tr('td', recursive=False)
                        # host                        
                        try:
                            n["host"] = str(tds[0].table.tr.td.table.tr.td.a.string)
                        except:
                            n["host"] = str(nagitems[len(nagitems)-1]["host"])
                        # status
                        n["status"] = str(tds[1].string)
                        # last_check
                        n["last_check"] = str(tds[2].string)
                        # duration
                        n["duration"] = str(tds[3].string)
                        # division between Nagios and Icinga in real life... where
                        # Nagios has only 5 columns there are 7 in Icinga 1.3...
                        # ... and 6 in Icinga 1.2 :-)
                        if len(tds) < 7:
                            # the old Nagios table
                            # status_information
                            n["status_information"] = str(tds[4].string)
                            # attempts are not shown in case of hosts so it defaults to "N/A"
                            n["attempt"] = "N/A"
                        else:
                            # attempts are shown for hosts
                            n["attempt"] = str(tds[4].string)
                            # status_information
                            n["status_information"] = str(tds[5].string)
                            
                        # status flags 
                        n["passiveonly"] = False
                        n["notifications_disabled"] = False
                        n["flapping"] = False
                        n["scheduled_downtime"] = False
                        
                        # map status icons to status flags                       
                        icons = tds[0].findAll('img')
                        for i in icons:
                            icon = i["src"].split("/")[-1]
                            if icon in self.STATUS_MAPPING:
                                n[icon] = True
                        
                        # cleaning
                        del icons                            

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
                            self.new_hosts[new_host].passiveonly = n["passiveonly"]
                            self.new_hosts[new_host].notifications_disabled = n["notifications_disabled"]
                            self.new_hosts[new_host].flapping = n["flapping"]
                            self.new_hosts[new_host].scheduled_downtime = n["scheduled_downtime"]
                except:
                    self.Error(sys.exc_info())
                
            # do some cleanup
            del table, tr, trs, tds
            
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
            table = copy.deepcopy(htobj('table', {'class': 'status'})[0])
            
            # do some cleanup    
            del htobj
            
            trs = table('tr', recursive=False)
            trs.pop(0)
            for tr in trs:
                try:
                    # ignore empty <tr> rows - there are a lot of them - a Nagios bug? 
                    tds = tr('td', recursive=False)
                    if len(tds) > 1:
                        n = {}
                        # host
                        # the resulting table of Nagios status.cgi table omits the
                        # hostname of a failing service if there are more than one
                        # so if the hostname is empty the nagios status item should get
                        # its hostname from the previuos item - one reason to keep "nagitems"
                        try:
                            n["host"] = str(tds[0](text=not_empty)[0])
                        except:
                            n["host"] = nagitems["services"][len(nagitems["services"])-1]["host"]
                        # service                                             
                        n["service"] = str(tds[1](text=not_empty)[0])
                        # status
                        n["status"] = str(tds[2](text=not_empty)[0])
                        # last_check
                        n["last_check"] = str(tds[3](text=not_empty)[0])
                        # duration
                        n["duration"] = str(tds[4](text=not_empty)[0])
                        # attempt
                        n["attempt"] = str(tds[5](text=not_empty)[0])
                        # status_information
                        n["status_information"] = str(tds[6](text=not_empty)[0])
                        # status flags 
                        n["passiveonly"] = False
                        n["notifications_disabled"] = False
                        n["flapping"] = False
                        n["scheduled_downtime"] = False
                        
                        # map status icons to status flags
                        icons = tds[1].findAll('img')
                        for i in icons:
                            icon = i["src"].split("/")[-1]
                            if icon in self.STATUS_MAPPING:
                                n[icon] = True
                        
                        # cleaning
                        del icons
                        
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
                            self.new_hosts[n["host"]].services[new_service].notifications_disabled = n["notifications_disabled"]
                            self.new_hosts[n["host"]].services[new_service].flapping = n["flapping"]
                            self.new_hosts[n["host"]].services[new_service].scheduled_downtime = n["scheduled_downtime"]
                except:
                    self.Error(sys.exc_info())
                                
            # do some cleanup
            del table, tr, trs, tds
            
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error) 
        
        ### the following is just for checking if .property flags work - will vanish soon
                
        # hosts which are in scheduled downtime
        for host in self.new_hosts.values():
            if host.is_in_scheduled_downtime():
                self.new_hosts_in_maintenance.append(host.name)    
                
        # hosts which are acknowledged       
        for host in self.new_hosts.values():
            if host.is_acknowledged():
                self.new_hosts_acknowledged.append(host.name)            
    
                
        # some cleanup
        del nagitems
        
        #dummy return in case all is OK
        return Result()
    

    def get_start_end(self, host):
        """
        for GUI to get actual downtime start and end from server - they may vary so it's better to get
        directly from web interface
        """
        try:
            #result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"55", "host":host}), giveback="raw")
            result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"55", "host":host}), giveback="soup")
            html = result.result
            print html.find(attrs={"name":"start_time"}).attrMap["value"]
            ###rint dir(html.find(attrs={"name":"start_time"}))            
            #start_time = html.split("NAME='start_time' VALUE='")[1].split("'></b></td></tr>")[0]
            #end_time = html.split("NAME='end_time' VALUE='")[1].split("'></b></td></tr>")[0]
            start_time = html.find(attrs={"name":"start_time"}).attrMap["value"]
            end_time = html.find(attrs={"name":"end_time"}).attrMap["value"]            
            # give values back as tuple
            return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"    
        

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
        result = self.FetchURL(nagcgiurl_host, giveback="soup", remove_tags=["link", "br", "img", "hr", "script", "th", "form", "p"])
        htobj = result.result

        try:
            # take ip from html soup
            ip = htobj.findAll(name="div", attrs={"class":"data"})[-1].text    

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
        