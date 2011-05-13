# encoding: utf-8

import sys
import urllib
import webbrowser
import traceback
import base64

from Nagstamon import Actions 
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer


class OpsviewService(GenericService):
    """
    add Opsview specific service property to generic service class
    """
    service_object_id = ""
    

class OpsviewServer(GenericServer):   
    """  
       special treatment for Opsview XML based API
    """   
    TYPE = 'Opsview'
    
    # Arguments available for submitting check results 
    SUBMIT_CHECK_RESULT_ARGS = ["comment"]  
    
    
    def init_HTTP(self):      
        if self.HTTPheaders == {}:
            GenericServer.init_HTTP(self)
            # special Opsview treatment, transmit username and passwort for XML requests
            # http://docs.opsview.org/doku.php?id=opsview3.4:api
            # this is only necessary when accessing the API and expecting a XML answer
            self.HTTPheaders["xml"] = {"Content-Type":"text/xml", "X-Username":self.get_username(), "X-Password":self.get_password()}          
            
        # get cookie to access Opsview web interface to access Opsviews Nagios part       
        if len(self.Cookie) == 0:         
            # put all necessary data into url string
            logindata = urllib.urlencode({"login_username":self.get_username(),\
                             "login_password":self.get_password(),\
                             "back":"",\
                             "app": "",\
                             "login":"Log In"})

            # the following is necessary for Opsview servers
            # get cookie from login page via url retrieving as with other urls
            try:
                # login and get cookie
                urlcontent = self.urlopener.open(self.nagios_url + "/login", logindata)
                urlcontent.close()
            except:
                self.Error(sys.exc_info())
               
                
    def get_start_end(self, host):
        """
        for GUI to get actual downtime start and end from server - they may vary so it's better to get
        directly from web interface
        """
        try:
            result = self.FetchURL(self.nagios_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"55", "host":host}))
            html = result.result
            start_time = html.find(attrs={"name":"starttime"}).attrMap["value"]
            end_time = html.find(attrs={"name":"endtime"}).attrMap["value"]            
            # give values back as tuple
            return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"                 
            
            
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
        # to build value for hidden form field old cgi_data is used
        cgi_data = { "from" : url + "?" + cgi_data, "comment": comment, "starttime": start_time, "endtime": end_time }
        self.FetchURL(self.nagios_url + action, giveback="raw", cgi_data=cgi_data)
        
        
    def _set_submit_check_result(self, host, service, state, comment, check_output, performance_data):
        """
        worker for submitting check result
        """ 
        # decision about host or service - they have different URLs
        if service == "":
            # host - here Opsview uses the plain oldschool Nagios way of CGI
            url = self.nagios_cgi_url + "/cmd.cgi"   
            cgi_data = urllib.urlencode({"cmd_typ":"87", "cmd_mod":"2", "host":host,\
                                         "plugin_state":{"up":"0", "down":"1", "unreachable":"2"}[state], "plugin_output":check_output,\
                                         "performance_data":performance_data, "btnSubmit":"Commit"})  
            self.FetchURL(url, giveback="raw", cgi_data=cgi_data) 
            
        if service != "":
            # service @ host - here Opsview brews something own            
            url = self.nagios_url + "/state/service/" + self.hosts[host].services[service].service_object_id + "/change"
            cgi_data = urllib.urlencode({"state":{"ok":"0", "warning":"1", "critical":"2", "unknown":"3"}[state],\
                                         "comment":comment, "submit":"Commit"})          
            # running remote cgi command        
            self.FetchURL(url, giveback="raw", cgi_data=cgi_data) 
            
        
    def _get_status(self):
        """
        Get status from Opsview Server
        """
        # following http://docs.opsview.org/doku.php?id=opsview3.4:api to get ALL services in ALL states except OK
        # because we filter them out later
        # the API seems not to let hosts information directly, we hope to get it from service informations
        try:
            opsapiurl = self.nagios_url + "/api/status/service?state=1&state=2&state=3"
            result = self.FetchURL(opsapiurl, giveback="xml")
            xmlobj, error = result.result, result.error
            if error != "": return Result(result=xmlobj, error=error)
            
            for host in xmlobj.data.findAll("list"):                
                # host
                hostdict = dict(host._getAttrMap())
                self.new_hosts[hostdict["name"]] = GenericHost()
                self.new_hosts[hostdict["name"]].name = str(hostdict["name"])
                # states come in lower case from Opsview
                self.new_hosts[hostdict["name"]].status = str(hostdict["state"].upper())
                self.new_hosts[hostdict["name"]].last_check = str(hostdict["last_check"])
                self.new_hosts[hostdict["name"]].duration = Actions.HumanReadableDuration(hostdict["state_duration"])
                self.new_hosts[hostdict["name"]].attempt = str(hostdict["current_check_attempt"])+ "/" + str(hostdict["max_check_attempts"])
                self.new_hosts[hostdict["name"]].status_information = str(hostdict["output"].replace("\n", " "))
                # if host is in downtime add it to known maintained hosts
                if hostdict["downtime"] == "2":
                    self.new_hosts[hostdict["name"]].scheduled_downtime = True
                if hostdict.has_key("acknowledged"):
                    self.new_hosts[hostdict["name"]].acknowledged = True

                #services
                #for service in host.getchildren()[:-1]:
                for service in host.findAll("services"):   
                    servicedict = dict(service._getAttrMap())
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]] = OpsviewService()
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].host = str(hostdict["name"])
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].name = str(servicedict["name"])
                    # states come in lower case from Opsview
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].status = str(servicedict["state"].upper())
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].last_check = str(servicedict["last_check"])
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].duration = Actions.HumanReadableDuration(servicedict["state_duration"])
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].attempt = str(servicedict["current_check_attempt"])+ "/" + str(servicedict["max_check_attempts"])
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].status_information= str(servicedict["output"].replace("\n", " "))
                    if servicedict["downtime"] == "2":
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].scheduled_downtime = True
                    if servicedict.has_key("acknowledged"):
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]].acknowledged = True
                    # extra opsview id for service, needed for submitting check results
                    self.new_hosts[hostdict["name"]].services[servicedict["name"]].service_object_id = str(servicedict["service_object_id"])


        except:
            # set checking flag back to False
            self.isChecking = False
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
            self.Debug(server=self.get_name(), debug="Open monitor web page " + self.nagios_url + "/status/service?filter=unhandled&includeunhandledhosts=1")   
            
    def open_services(self):
        webbrowser.open(self.nagios_url + "/status/service?state=1&state=2&state=3")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open services web page " + self.nagios_url + "/status/service?state=1&state=2&state=3")

    def open_hosts(self):
        webbrowser.open(self.nagios_url + "/status/host?hostgroupid=1&state=1")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open hosts web page " + self.nagios_url + "/status/host?hostgroupid=1&state=1")
