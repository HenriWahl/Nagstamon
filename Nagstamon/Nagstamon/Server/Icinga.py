# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer
import urllib
import sys
import json

from Nagstamon.Objects import *
from Nagstamon.Actions import *

class IcingaServer(GenericServer):    
    """
        object of Incinga server
    """   
    TYPE = 'Icinga'


    def _get_status(self):
        """
        Get status from Icinga Server via JSON
        """
        # create Icinga items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services":[], "hosts":[]}       
        
        # new_hosts dictionary
        self.new_hosts = dict()
        
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        # hoststatus
        hoststatustypes = 12
        # servicestatus
        servicestatustypes = 253
        # serviceprops & hostprops both have the same values for the same states so I
        # group them together
        hostserviceprops = 0
        # services (unknown, warning or critical?)
        ###nagcgiurl_services = self.monitor_cgi_url + "/status.cgi?host=all&servicestatustypes=" + str(servicestatustypes) + "&serviceprops=" + str(hostserviceprops)
        nagcgiurl_services = "%s/status.cgi?host=all&servicestatustypes=%s&serviceprops=%s&jsonoutput" % (self.monitor_cgi_url,\
                                                                                                str(servicestatustypes),\
                                                                                                str(hostserviceprops))
        # hosts (up or down or unreachable)
        nagcgiurl_hosts = self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=" + str(hoststatustypes) + "&hostprops=" + str(hostserviceprops)
        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            result = self.FetchURL(nagcgiurl_hosts)
            htobj, error = result.result, result.error

            if error != "": return Result(result=htobj, error=error) 
            # put a copy of a part of htobj into table to be able to delete htobj
            table = htobj('table', {'class': 'status'})[0]

            # do some cleanup
            del htobj
            
            # access table rows
            # some Icinga versions have a <tbody> tag in cgi output HTML which
            # omits the <tr> tags being found
            if len(table('tbody')) == 0:
                trs = table('tr', recursive=False)
            else:
                tbody = table('tbody')[0]
                trs = tbody('tr', recursive=False)
            
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
                            if len(tds[4](text=not_empty)) == 0:
                                n["status_information"] = ""
                            else:    
                                n["status_information"] = str(tds[4].string).encode("utf-8")
                            # attempts are not shown in case of hosts so it defaults to "N/A"
                            n["attempt"] = "N/A"
                        else:
                            # attempts are shown for hosts
                            # to fix http://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3280961&group_id=236865 .attempt needs
                            # to be stripped
                            n["attempt"] = str(tds[4].string).strip()
                            # status_information
                            if len(tds[5](text=not_empty)) == 0:
                                n["status_information"] = ""
                            else:    
                                n["status_information"] = str(tds[5].string).encode("utf-8")
                            
                        # status flags 
                        n["passiveonly"] = False
                        n["notifications_disabled"] = False
                        n["flapping"] = False
                        n["acknowledged"] = False
                        n["scheduled_downtime"] = False
                        
                        # map status icons to status flags                       
                        icons = tds[0].findAll('img')
                        for i in icons:
                            icon = i["src"].split("/")[-1]
                            if icon in self.STATUS_MAPPING:
                                n[self.STATUS_MAPPING[icon]] = True
                        
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
                            self.new_hosts[new_host].status_information= n["status_information"].encode("utf-8")
                            self.new_hosts[new_host].passiveonly = n["passiveonly"]
                            self.new_hosts[new_host].notifications_disabled = n["notifications_disabled"]
                            self.new_hosts[new_host].flapping = n["flapping"]
                            self.new_hosts[new_host].acknowledged = n["acknowledged"]
                            self.new_hosts[new_host].scheduled_downtime = n["scheduled_downtime"]
                except:
                    self.Error(sys.exc_info())
                
            # do some cleanup
            del table, trs
            
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            #result = Result()
            ###result = self.FetchURL(nagcgiurl_services)
            result = self.FetchURL(nagcgiurl_services, giveback="raw")
            ###htobj, error = result.result, result.error
            jsonraw, error = result.result, result.error
            
            #if error != "": return Result(result=copy.deepcopy(htobj), error=error)
            if error != "": return Result(result=jsonraw, error=error)
          
            ###table = htobj('table', {'class': 'status'})[0]
            jsondict = json.loads(jsonraw)
                       
            services = jsondict["status"]["service_status"]
            
            for service in services: 
                """
                   (u'host_display_name', u'web_de-www')
                   (u'status', u'CRITICAL')
                   (u'status_information', u'CRITICAL - Socket timeout after 10 seconds')
                   (u'active_checks_enabled', True)
                   (u'has_been_acknowledged', True)
                   (u'notifications_enabled', True)
                   (u'action_url', None)
                   (u'last_check', u'01-18-2013 15:46:08')
                   (u'service_display_name', u'HTTP')
                   (u'attempts', u'1/4')
                   (u'notes_url', None)
                   (u'host_name', u'web_de-www')
                   (u'is_flapping', False)
                   (u'duration', u'12d 23h 53m 37s')
                   (u'service_description', u'HTTP')
                   (u'state_type', u'HARD')
                   (u'in_scheduled_downtime', False)
                   (u'passive_checks_enabled', True)
                """    
                
                s = dict(service.items())

                # new item
                n = {}

                # host
                n["host"] = s["host_display_name"]
                # service                                             
                n["service"] = s["service_display_name"]
                # status
                n["status"] = s["status"]
                # last_check
                n["last_check"] = s["last_check"]
                # duration
                n["duration"] = s["duration"]
                # attempt
                n["attempt"] = s["attempts"]
                # status_information
                n["status_information"] = s["status_information"]
                # status flags 
                n["passiveonly"] = not(s["active_checks_enabled"])
                n["notifications_disabled"] = not(s["notifications_enabled"])
                n["flapping"] = s["is_flapping"]
                n["acknowledged"] = s["has_been_acknowledged"]
                n["scheduled_downtime"] = s["in_scheduled_downtime"]

                # add dictionary full of information about this service item to nagitems - only if service
                nagitems["services"].append(n)
                
                # after collection data in nagitems create objects of its informations
                # host objects contain service objects
                if not self.new_hosts.has_key(n["host"]):
                    self.new_hosts[n["host"]] = GenericHost()
                    self.new_hosts[n["host"]].name = n["host"]
                    self.new_hosts[n["host"]].status = "UP"
                    #### trying to fix https://sourceforge.net/tracker/index.php?func=detail&aid=3299790&group_id=236865&atid=1101370
                    #### if host is not down but in downtime or any other flag this should be evaluated too
                    #### map status icons to status flags
                    ###icons = tds[0].findAll('img')
                    ###for i in icons:
                    ###    icon = i["src"].split("/")[-1]
                    ###    if icon in self.STATUS_MAPPING:
                    ###        self.new_hosts[n["host"]].__dict__[self.STATUS_MAPPING[icon]] = True
                    #### cleaning
                    ###del icons
                    
                    
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
                    self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"].encode("utf-8")
                    self.new_hosts[n["host"]].services[new_service].passiveonly = n["passiveonly"]
                    self.new_hosts[n["host"]].services[new_service].notifications_disabled = n["notifications_disabled"]
                    self.new_hosts[n["host"]].services[new_service].flapping = n["flapping"]
                    self.new_hosts[n["host"]].services[new_service].acknowledged = n["acknowledged"]
                    self.new_hosts[n["host"]].services[new_service].scheduled_downtime = n["scheduled_downtime"]

            #### some Icinga versions have a <tbody> tag in cgi output HTML which
            #### omits the <tr> tags being found
            ###if len(table('tbody')) == 0:
            ###    trs = table('tr', recursive=False)
            ###else:
            ###    tbody = table('tbody')[0]
            ###    trs = tbody('tr', recursive=False)

            # do some cleanup    
            ###del htobj
            
            # kick out table heads
            ###trs.pop(0)
 
            # do some cleanup
            ###del table, trs
            
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error) 

        # some cleanup
        del nagitems
        
        #dummy return in case all is OK
        return Result()