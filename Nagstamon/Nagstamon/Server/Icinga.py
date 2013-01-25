# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer
import urllib
import sys
# this seems to be necessary for json to be packaged by pyinstaller
from encodings import hex_codec
import json
import base64

# to let Linux distributions use their own BeautifulSoup if existent try importing local BeautifulSoup first
# see https://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3302612&group_id=236865
try:
    from BeautifulSoup import BeautifulSoup
except:
    from Nagstamon.BeautifulSoup import BeautifulSoup

from Nagstamon.Objects import *
from Nagstamon.Actions import *

class IcingaServer(GenericServer):    
    """
        object of Incinga server
    """   
    TYPE = 'Icinga'
    # flag to handle JSON or HTML correctly - checked by get_server_version()
    json = False


    def init_HTTP(self):
        """
        partly not constantly working Basic Authorization requires extra Autorization headers,
        different between various server types
        """
        if self.HTTPheaders == {}:
            for giveback in ["raw", "obj"]:
                self.HTTPheaders[giveback] = {"Authorization": "Basic " + base64.b64encode(self.get_username() + ":" + self.get_password())}


    def get_server_version(self):
        """
        Try to get Icinga version for different URLs and JSON capabilities
        """
        #tacraw = self.FetchURL("%s/tac.cgi?jsonoutput" % (self.monitor_cgi_url), giveback="raw").result
        tacraw = self.FetchURL("%s/tac.cgi?jsonoutput" % (self.monitor_cgi_url), giveback="raw").result
        if tacraw.startswith("<"):
            self.json = False
            tacsoup = BeautifulSoup(tacraw)
            self.version = tacsoup.find("a", { "class" : "homepageURL" })
            # only extract version if HTML seemed to be OK
            if self.version.__dict__.has_key("contents"):
                self.version = self.version.contents[0].split("Icinga ")[1]
        elif tacraw.startswith("{"):
            jsondict = json.loads(tacraw)
            self.version = jsondict["cgi_json_version"]
            self.json = True


    def _get_status(self):
        """
        Get status from Icinga Server
        """
        # create Icinga items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services":[], "hosts":[]}
        
        # new_hosts dictionary
        self.new_hosts = dict()
        
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        # update: http://docs.icinga.org/latest/en/cgiparams.html
        # hoststatus
        hoststatustypes = 12
        # servicestatus
        servicestatustypes = 253
        # serviceprops & hostprops both have the same values for the same states so I
        # group them together
        hostserviceprops = 0
        # services (unknown, warning or critical?)
        nagcgiurl_services = "%s/status.cgi?host=all&servicestatustypes=%s&serviceprops=%s&jsonoutput" % (self.monitor_cgi_url,\
                                                                                                          str(servicestatustypes),\
                                                                                                          str(hostserviceprops))
        # hosts (up or down or unreachable)
        nagcgiurl_hosts = "%s/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=%s&hostprops=%s&jsonoutput" % (self.monitor_cgi_url,\
                                                                                                                    str(hoststatustypes),\
                                                                                                                    str(hostserviceprops))
        # hosts - mostly the down ones
        # now using JSON output from Icinga
        try:
            result = self.FetchURL(nagcgiurl_hosts, giveback="raw")            
            jsonraw, error = result.result, result.error

            if error != "": return Result(result=jsonraw, error=error) 
            
            jsondict = json.loads(jsonraw)                                  
            hosts = jsondict["status"]["host_status"]

            for host in hosts:
                # make dict of tuples for better reading
                h = dict(host.items())
                
                # new host item
                n = {}

                # host 
                # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might 
                # better be host_name instead of host_display_name
                n["host"] = h["host_name"]
                # status
                n["status"] = h["status"]
                # last_check
                n["last_check"] = h["last_check"]
                # duration
                n["duration"] = h["duration"]
                # status information
                n["status_information"] = h["status_information"]
                # attempts
                n["attempt"] = h["attempts"]
                # status flags 
                n["passiveonly"] = not(h["active_checks_enabled"])
                n["notifications_disabled"] = not(h["notifications_enabled"])
                n["flapping"] = h["is_flapping"]
                n["acknowledged"] = h["has_been_acknowledged"]
                n["scheduled_downtime"] = h["in_scheduled_downtime"]

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
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            result = self.FetchURL(nagcgiurl_services, giveback="raw")
            jsonraw, error = result.result, result.error
            
            if error != "": return Result(result=jsonraw, error=error)
          
            jsondict = json.loads(jsonraw)                       
            services = jsondict["status"]["service_status"]
            
            for service in services:
                # make dict of tuples for better reading
                s = dict(service.items())

                # new service item
                n = {}
                # host
                # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might 
                # better be host_name instead of host_display_name
                n["host"] = s["host_name"]
                # service                                             
                n["service"] = s["service_description"]
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
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error) 

        # some cleanup
        del nagitems
        
        #dummy return in case all is OK
        return Result()