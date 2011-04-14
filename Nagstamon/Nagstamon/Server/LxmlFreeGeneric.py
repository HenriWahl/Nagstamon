# encoding: utf-8

import sys
import re
from Nagstamon.Server.Generic import GenericServer
from Nagstamon.BeautifulSoup import BeautifulSoup
from Nagstamon.Objects import *
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

    def FetchURL(self, url, giveback='soup', cgi_data=None, remove_tags=None):
        if not remove_tags:
            remove_tags = ["link", "br", "img", "hr", "script", "th", "form", "div", "p"]
        if giveback == 'soup':
            self.init_HTTP()

            try:
                # debug
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), debug="FetchURL: " + url + " CGI Data: " + str(cgi_data))

                request = urllib2.Request(url, cgi_data, self.HTTPheaders['obj'])
                # use opener - if cgi_data is not empty urllib uses a POST request
                urlcontent = self.urlopener.open(request)
                del url, cgi_data, request
                doc = BeautifulSoup(urlcontent)
                return Result(result=doc)
            except:
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)
        else:
            return GenericServer.FetchURL(self, url, giveback, cgi_data, remove_Tags)
        
    
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
            
            
            print type(htobj)
            print dir(htobj)
            
            print htobj.tr
            
            import sys
            sys.exit()
                        
            if error != "": return Result(result=copy.deepcopy(htobj), error=error)            

            # put a copy of a part of htobj into table to be able to delete htobj
            table = copy.deepcopy(htobj('table', {'class': self.STATUS_CLASS})[0])

            # do some cleanup
            del htobj

            trs = table('tr', recursive=False)
            # table heads?
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
                            #n["host"] = str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text)
                            n["host"] = str(tds[0].table.tr.td.table.tr.td.string)
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
            table = copy.deepcopy(htobj('table', {'class': self.STATUS_CLASS})[0])
            
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
                            #n["host"] = str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text)
                            n["host"] = str(tds[0](text=not_empty)[0])
                        except:
                            n["host"] = str(nagitems["services"][len(nagitems["services"])-1]["host"])
                        # service
                        #n["service"] = str(table.tr[i].td[1].table.tr.td.table.tr.td.a.string)
                        n["service"] = str(tds[1](text=not_empty)[0])
                        # status
                        n["status"] = str(tds[2].string)
                        # last_check
                        n["last_check"] = str(tds[3].string)
                        # duration
                        n["duration"] = str(tds[4].string)
                        # attempt
                        n["attempt"] = str(tds[5].string)
                        # status_information
                        n["status_information"] = str(tds[6].string.replace('&nbsp;', ''))
                        n["passiveonly"] = False
                        n["notifications"] = True
                        n["flapping"] = False
                        td_html = str(tds[1].table.tr('td', recursive=False)[1])
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
                table = copy.deepcopy(htobj('table', {'class': self.STATUS_CLASS})[0])
            except:
                table = copy.deepcopy(htobj.body.embed.div.table)
            
            # do some cleanup    
            del htobj

            trs = table('tr', recursive=False)
            trs.pop(0)
            for tr in trs:
                try:
                    # ignore empty <tr> rows
                    if tr('td', recursive=False) > 1:
                        # host
                        try:
                            #self.new_hosts_in_maintenance.append(str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text))
                            self.new_hosts_in_maintenance.append(str(tr('td', recursive=False)[0].table.tr.td.table.tr.td.string))
                            # get real status of maintained host
                            if self.new_hosts.has_key(self.new_hosts_in_maintenance[-1]):
                                self.new_hosts[self.new_hosts_in_maintenance[-1]].status = str(tr('td')[1].string)
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
                table = copy.deepcopy(htobj('table', {'class': self.STATUS_CLASS})[0])
            except:
                table = copy.deepcopy(htobj.body.embed.table)
                
            # do some cleanup    
            del htobj               

            trs = table('tr', recursive=False)
            trs.pop(0)
            for tr in trs:
                try:
                    # ignore empty <tr> rows
                    if len(tr('td', recursive=False)) > 1:
                        # host
                        try:
                            #self.new_hosts_acknowledged.append(str(table.tr[i].td[0].table.tr.td.table.tr.td.a.text))
                            self.new_hosts_acknowledged.append(str(tr.td.table.tr.td.table.tr.td.string))                            # get real status of acknowledged host
                            if self.new_hosts.has_key(self.new_hosts_acknowledged[-1]):
                                self.new_hosts[self.new_hosts_acknowledged[-1]].status = str(tr.td[1].string)
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
