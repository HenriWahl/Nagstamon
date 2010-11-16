# encoding: utf-8

import sys
import urllib
import webbrowser
import traceback

import nagstamonActions
from nagstamonObjects import *
from Generic import GenericServer


class OpsviewServer(GenericServer):
    """  
       special treatment for Opsview XML based API
    """   
    TYPE = 'Opsview'
    
    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        # get action url for opsview downtime form
        if service == "":
            # host
            cgi_data = urllib.urlencode({"cmd_typ":"55", "host":host})
        else:
            # service
            cgi_data = urllib.urlencode({"cmd_typ":"56", "host":host, "service":service})
        url = self.nagios_cgi_url + "/cmd.cgi"
        result = self.FetchURL(url, giveback="raw", cgi_data=cgi_data)
        html = result.result
        # which opsview form action to call
        action = html.split('" enctype="multipart/form-data">')[0].split('action="')[-1]
        # this time cgi_data does not get encoded because it will be submitted via multipart
        # to build value for hidden from field old cgi_data is used
        cgi_data = { "from" : url + "?" + cgi_data, "comment": comment, "starttime": start_time, "endtime": end_time }
        self.FetchURL(self.nagios_url + action, giveback="raw", cgi_data=cgi_data)
        

    def get_start_end(self, host):
        """
        get start and end time for downtime from Opsview server
        """
        try:
            result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"55", "host":host}), giveback="raw")
            html = result.result
            start_time = html.split('name="starttime" value="')[1].split('"')[0]
            end_time = html.split('name="endtime" value="')[1].split('"')[0]        
            # give values back as tuple
            return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"   
        
        
    def _get_status(self):
        """
        Get status from Opsview Server
        """
        # following http://docs.opsview.org/doku.php?id=opsview3.4:api to get ALL services in ALL states except OK
        # because we filter them out later
        # the API seems not to let hosts information directly, we hope to get it from service informations
        try:
            opsapiurl = self.nagios_url + "/api/status/service?state=1&state=2&state=3"
            result = self.FetchURL(opsapiurl, giveback="opsxml")
            xobj, error = result.result, result.error
            if error != "": return Result(result=xobj, error=error)
            for host in xobj.data.getchildren()[:-1]:
                # host
                hostdict = dict(host.items())
                # if host is in downtime add it to known maintained hosts
                if hostdict["downtime"] == "2":
                    self.new_hosts_in_maintenance.append(hostdict["name"])
                if hostdict.has_key("acknowledged"):
                    self.new_hosts_acknowledged.append(hostdict["name"])
                self.new_hosts[hostdict["name"]] = GenericHost()
                self.new_hosts[hostdict["name"]].name = hostdict["name"]
                # states come in lower case from Opsview
                self.new_hosts[hostdict["name"]].status = hostdict["state"].upper()
                self.new_hosts[hostdict["name"]].last_check = hostdict["last_check"]
                self.new_hosts[hostdict["name"]].duration = nagstamonActions.HumanReadableDuration(hostdict["state_duration"])
                self.new_hosts[hostdict["name"]].attempt = str(hostdict["current_check_attempt"])+ "/" + str(hostdict["max_check_attempts"])
                self.new_hosts[hostdict["name"]].status_information= hostdict["output"]
    
                #services
                for service in host.getchildren()[:-1]:
                    servicedict = dict(service.items())
                    # to get this filters to work they must be applied here - similar to Nagios servers
                    if not (str(self.conf.filter_hosts_services_maintenance) == "True" \
                    and servicedict["downtime"] == "2") \
                    and not (str(self.conf.filter_acknowledged_hosts_services) == "True" \
                    and servicedict.has_key("acknowledged")):
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]] = GenericService()
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].host = hostdict["name"]
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].name = servicedict["name"]
                        # states come in lower case from Opsview
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].status = servicedict["state"].upper()
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].last_check = servicedict["last_check"]
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].duration = nagstamonActions.HumanReadableDuration(servicedict["state_duration"])
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].attempt = str(servicedict["current_check_attempt"])+ "/" + str(servicedict["max_check_attempts"])
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].status_information= servicedict["output"]
        except:
            # set checking flag back to False
            self.isChecking = False
            #return self.Error(sys.exc_info())
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
        
        #dummy return in case all is OK
        return Result()

        
    def open_tree_view(self, host, service):
        webbrowser.open('%s/status/service?host=%s' % (self.nagios_url, host))
        
    def open_nagios(self):
        webbrowser.open(self.nagios_url + "/status/service?filter=unhandled&includeunhandledhosts=1")
        # debug
        if str(self.conf.debug_mode) == "True":
            #print self.get_name(), ":", "Open monitor web page", self.nagios_url + "/status/service?filter=unhandled&includeunhandledhosts=1"
            self.Debug(server=self.get_name(), debug="Open monitor web page " + self.nagios_url + "/status/service?filter=unhandled&includeunhandledhosts=1")   
            
    def open_services(self):
        webbrowser.open(self.nagios_url + "/status/service?state=1&state=2&state=3")
        # debug
        if str(self.conf.debug_mode) == "True":
            #print self.get_name(), ":", "Open hosts web page", self.nagios_url + "/status/service?state=1&state=2&state=3"  
            self.Debug(server=self.get_name(), debug="Open services web page " + self.nagios_url + "/status/service?state=1&state=2&state=3")

    def open_hosts(self):
        webbrowser.open(self.nagios_url + "/status/host?hostgroupid=1&state=1")
        # debug
        if str(self.conf.debug_mode) == "True":
            #print self.get_name(), ":", "Open hosts web page", self.nagios_url + "/status/host?hostgroupid=1&state=1"      
            self.Debug(server=self.get_name(), debug="Open hosts web page " + self.nagios_url + "/status/host?hostgroupid=1&state=1")

            
