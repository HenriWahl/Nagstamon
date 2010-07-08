# encoding: utf-8

import urllib
import urllib2
import cookielib
import sys
import socket
import gc
import copy

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

          
class NagiosServer(object):
    """
        object of Nagios server - when nagstamon will be able to poll various servers this
        will be useful   
    """
    
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        self.name = ""
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
        self.downs = 0
        self.unreachables = 0
        self.unknowns = 0
        self.criticals = 0
        self.warnings = 0
        self.status = ""
        self.Cookie = None

    
    def __del__(self):
        """
        hopefully a __del__() method may make this object better collectable for gc
        """
        del(self)
        
    
    def GetStatus(self):
        """
        get nagios status information from nagcgiurl and give it back
        as dictionary
        """

        # set checking flag to be sure only one thread cares about this server
        self.isChecking = True        
        
        # check if server is enabled, if not, do not get any status
        if str(self.conf.servers[self.name].enabled) == "False":
            self.WorstStatus = "UP"
            # dummy filtered items
            self.nagitems_filtered = {"services":{"CRITICAL":[], "WARNING":[], "UNKNOWN":[]}, "hosts":{"DOWN":[], "UNREACHABLE":[]}}
            self.isChecking = False          
            return True      

        # decide which server type to use, both methods fill self.new_hosts et al. which
        # after this get filtered
        # some filtering is already done by the server specific GetStatus*() 
        if self.type == "Opsview":
            if self.GetStatusOpsview() == "ERROR":
                return "ERROR"
        if self.type == "Nagios" or self.type == "Centreon":
            if self.GetStatusNagios() == "ERROR":
                return "ERROR"

        # this part has been before in GUI.RefreshDisplay() - wrong place 
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
            if host.status == "DOWN" and nagstamonActions.HostIsFilteredOutByRE(host.name, self.conf) == False\
            and (not (host.name in self.new_hosts_in_maintenance and \
            str(self.conf.filter_hosts_services_maintenance) == "True") and \
            not (host.name in self.new_hosts_acknowledged and \
            str(self.conf.filter_acknowledged_hosts_services) == "True")) and \
            str(self.conf.filter_all_down_hosts) == "False": 
                self.nagitems_filtered["hosts"]["DOWN"].append(host)
                self.downs += 1
            if host.status == "UNREACHABLE" and nagstamonActions.HostIsFilteredOutByRE(host.name, self.conf) == False\
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
                nagstamonActions.HostIsFilteredOutByRE(host.name, self.conf) == False and \
                nagstamonActions.ServiceIsFilteredOutByRE(service.name, self.conf) == False:
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
        self.nagitems_filtered_list = copy.copy(new_nagitems_filtered_list)

        # do some cleanup
        self.hosts.clear()
        del self.hosts_acknowledged[::], self.hosts_in_maintenance[::]

        # put new informations into respective dictionaries      
        self.hosts, self.hosts_acknowledged, self.hosts_in_maintenance = copy.copy(self.new_hosts), copy.copy(self.new_hosts_acknowledged), copy.copy(self.new_hosts_in_maintenance)
        
        # do some cleanup
        del self.new_hosts_acknowledged[::], self.new_hosts_in_maintenance[::]
        self.new_hosts.clear()
        gc.collect()
        
        # after all checks are done unset checking flag
        self.isChecking = False
        
        # return True if all worked well    
        return True
    
    
    def GetStatusOpsview(self):
        """
        Get status from Opsview Server
        """
        # following http://docs.opsview.org/doku.php?id=opsview3.4:api to get ALL services in ALL states except OK
        # because we filter them out later
        # the API seems not to let hosts information directly, we hope to get it from service informations
        try:
            opsapiurl = self.nagios_url + "/api/status/service?state=1&state=2&state=3"
            xobj = self.FetchURL(opsapiurl, giveback="opsxml")
    
            for host in xobj.data.getchildren()[:-1]:
                # host
                hostdict = dict(host.items())
                # if host is in downtime add it to known maintained hosts
                if hostdict["downtime"] == "2":
                    self.new_hosts_in_maintenance.append(hostdict["name"])
                if hostdict.has_key("acknowledged"):
                    self.new_hosts_acknowledged.append(hostdict["name"])
                self.new_hosts[hostdict["name"]] = NagiosHost()
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
                        self.new_hosts[hostdict["name"]].services[servicedict["name"]] = NagiosService()
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
            return "ERROR"
        
        
    def GetStatusNagios(self):
        """
        Get status form Nagios Server
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
            htobj = self.FetchURL(nagcgiurl_hosts)
            # workaround for Nagios < 2.7 which has an <EMBED> in its output
            # do a copy of a part of htobj into table to be able to delete htobj
            try:
                table = copy.copy(htobj.body.div.table)
            except:
                table = copy.copy(htobj.body.embed.div.table)
            
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
                            self.new_hosts[n["host"]] = NagiosHost()
                            self.new_hosts[n["host"]].name = n["host"]
                            self.new_hosts[n["host"]].status = n["status"]
                            self.new_hosts[n["host"]].last_check = n["last_check"]
                            self.new_hosts[n["host"]].duration = n["duration"]
                            self.new_hosts[n["host"]].attempt = n["attempt"]
                            self.new_hosts[n["host"]].status_information= n["status_information"]
                except:
                    pass
                
            # do some cleanup
            del table
            
        except:
            # set checking flag back to False
            self.isChecking = False
            return "ERROR"

        # services
        try:
            htobj = self.FetchURL(nagcgiurl_services)

            for i in range(1, len(htobj.body.table[2].tr)):
                try:
                    # ignore empty <tr> rows - there are a lot of them - a Nagios bug? 
                    if not htobj.body.table[2].tr[i].countchildren() == 1:
                        n = {}
                        # host
                        # the resulting table of Nagios status.cgi table omits the
                        # hostname of a failing service if there are more than one
                        # so if the hostname is empty the nagios status item should get
                        # its hostname from the previuos item - one reason to keep "nagitems"
                        try:
                            n["host"] = str(htobj.body.table[2].tr[i].td[0].table.tr.td.table.tr.td.a.text)
                        except:
                            n["host"] = str(nagitems["services"][len(nagitems["services"])-1]["host"])
                        # service
                        n["service"] = str(htobj.body.table[2].tr[i].td[1].table.tr.td.table.tr.td.a.text)
                        # status
                        n["status"] = str(htobj.body.table[2].tr[i].td[2].text)
                        # last_check
                        n["last_check"] = str(htobj.body.table[2].tr[i].td[3].text)
                        # duration
                        n["duration"] = str(htobj.body.table[2].tr[i].td[4].text)
                        # attempt
                        n["attempt"] = str(htobj.body.table[2].tr[i].td[5].text)
                        # status_information
                        n["status_information"] = str(htobj.body.table[2].tr[i].td[6].text)
                        # add dictionary full of information about this service item to nagitems - only if service
                        nagitems["services"].append(n)
                        
                        # after collection data in nagitems create objects of its informations
                        # host objects contain service objects
                        if not self.new_hosts.has_key(n["host"]):
                            self.new_hosts[n["host"]] = NagiosHost()
                            self.new_hosts[n["host"]].name = n["host"]
                            self.new_hosts[n["host"]].status = "UP"
                        # if a service does not exist create its object
                        if not self.new_hosts[n["host"]].services.has_key(n["service"]):
                            self.new_hosts[n["host"]].services[n["service"]] = NagiosService()
                            self.new_hosts[n["host"]].services[n["service"]].host = n["host"]
                            self.new_hosts[n["host"]].services[n["service"]].name = n["service"]
                            self.new_hosts[n["host"]].services[n["service"]].status = n["status"]
                            self.new_hosts[n["host"]].services[n["service"]].last_check = n["last_check"]
                            self.new_hosts[n["host"]].services[n["service"]].duration = n["duration"]
                            self.new_hosts[n["host"]].services[n["service"]].attempt = n["attempt"]
                            self.new_hosts[n["host"]].services[n["service"]].status_information = n["status_information"]
                except:
                    pass
                                
            # do some cleanup
            del htobj
            
        except:
            # set checking flag back to False
            self.isChecking = False
            return "ERROR"
       
         # hosts which are in scheduled downtime
        try:
            htobj = self.FetchURL(nagcgiurl_hosts_in_maintenance)
           
            # workaround for Nagios < 2.7 which has an <EMBED> in its output
            try:
                table = copy.copy(htobj.body.div.table)
            except:
                table = copy.copy(htobj.body.embed.div.table)
            
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
                            #if self.new_hosts.has_key(self.new_hosts_acknowledged[-1]):
                            #    self.new_hosts[self.new_hosts_acknowledged[-1]].status = str(table.tr[i].td[1].text)
                            if self.new_hosts.has_key(self.new_hosts_in_maintenance[-1]):
                                self.new_hosts[self.new_hosts_in_maintenance[-1]].status = str(table.tr[i].td[1].text)
                        except:
                            pass
                except:
                    pass

            # do some cleanup
            del table
        
        except:
            # set checking flag back to False
            self.isChecking = False
            return "ERROR"
        
        # hosts which are acknowledged
        try:
            htobj = self.FetchURL(nagcgiurl_hosts_acknowledged)
            # workaround for Nagios < 2.7 which has an <EMBED> in its output
            try:
                table = copy.copy(htobj.body.div.table)
            except:
                table = copy.copy(htobj.body.embed.div.table)
            
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
                            pass
                except:
                    pass

            # do some cleanup
            del table

        except:
            # set checking flag back to False
            self.isChecking = False
            return "ERROR"
        
        # some cleanup
        del nagitems
                   
    
    def FetchURL(self, url, giveback="obj", cgi_data=None):
        """
        get content of given url, cgi_data only used if present
        giveback may be "dict", "html" or "none" 
        "dict" FetchURL gives back a dict full of miserable hosts/services,
        "html" it gives back pure HTML - useful for finding out IP or new version
        "none" it gives back pure nothing - useful if for example acknowledging a service
        existence of cgi_data forces urllib to use POST instead of GET requests
        """
        # using httppasswordmgrwithdefaultrealm because using password in plain
        # url like http://username:password@nagios-server causes trouble with
        # passwords containing special characters like "?"
        # see http://www.voidspace.org.uk/python/articles/authentication.shtml#doing-it-properly
        # attention: the example from above webseite is wrong, passman.add_password needs the 
        # WHOLE URL, with protocol!

        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, url, self.username, self.password)
        auth_handler = urllib2.HTTPBasicAuthHandler(passman)
        digest_handler = urllib2.HTTPDigestAuthHandler(passman)
        
        # get my cookie to access Opsview web interface to access Opsviews Nagios part
        if self.Cookie == None and self.type == "Opsview":
            # put all necessary data into url string
            logindata = urllib.urlencode({"login_username":self.username,\
                             "login_password":self.password,\
                             "back":"",\
                             "app": "",\
                             "login":"Log In"})
            
            # the cookie jar will contain Opsview web session and auth ticket cookies 
            self.Cookie = cookielib.CookieJar()
            
            # the following is necessary for Opsview servers
            # get cookie from login page via url retrieving as with other urls
            try:
                # if there should be no proxy used use an empty proxy_handler - only necessary in Windows,
                # where IE proxy settings are used automatically if available
                # In UNIX $HTTP_PROXY will be used
                if str(self.use_proxy) == "False":
                    proxy_handler = urllib2.ProxyHandler({})
                    urlopener = urllib2.build_opener(auth_handler, digest_handler, proxy_handler, urllib2.HTTPCookieProcessor(self.Cookie))
                elif str(self.use_proxy) == "True":
                    if str(self.use_proxy_from_os) == "True":
                        urlopener = urllib2.build_opener(auth_handler, digest_handler, urllib2.HTTPCookieProcessor(self.Cookie))
                    else:
                        # if proxy from OS is not used there is to add a authenticated proxy handler
                        passman.add_password(None, self.proxy_address, self.proxy_username, self.proxy_password)
                        proxy_handler = urllib2.ProxyHandler({"http": self.proxy_address, "https": self.proxy_address})
                        proxy_auth_handler = urllib2.ProxyBasicAuthHandler(passman)
                        urlopener = urllib2.build_opener(proxy_handler, proxy_auth_handler, auth_handler, digest_handler, urllib2.HTTPCookieProcessor(self.Cookie))
                
                # create url opener
                urllib2.install_opener(urlopener)
                # login and get cookie
                urlcontent = urllib2.urlopen(self.nagios_url + "/login", logindata)
                
            except:
                pass

            # if something goes wrong with accessing the URL it can be caught
        try:
            # if there should be no proxy used use an empty proxy_handler - only necessary in Windows,
            # where IE proxy settings are used automatically if available
            # In UNIX $HTTP_PROXY will be used
            # The MultipartPostHandler is needed for submitting multipart forms from Opsview
            if str(self.use_proxy) == "False":
                proxy_handler = urllib2.ProxyHandler({})
                urlopener = urllib2.build_opener(auth_handler, digest_handler, proxy_handler, urllib2.HTTPCookieProcessor(self.Cookie), nagstamonActions.MultipartPostHandler)
            elif str(self.use_proxy) == "True":
                if str(self.use_proxy_from_os) == "True":
                    urlopener = urllib2.build_opener(auth_handler, digest_handler, urllib2.HTTPCookieProcessor(self.Cookie), nagstamonActions.MultipartPostHandler)
                else:
                    # if proxy from OS is not used there is to add a authenticated proxy handler
                    passman.add_password(None, self.proxy_address, self.proxy_username, self.proxy_password)
                    proxy_handler = urllib2.ProxyHandler({"http": self.proxy_address, "https": self.proxy_address})
                    proxy_auth_handler = urllib2.ProxyBasicAuthHandler(passman)
                    urlopener = urllib2.build_opener(proxy_handler, proxy_auth_handler, auth_handler, digest_handler, urllib2.HTTPCookieProcessor(self.Cookie), nagstamonActions.MultipartPostHandler)
            
            # create url opener
            urllib2.install_opener(urlopener)
            try:
                # special Opsview treatment, transmit username and passwort for XML requests
                # http://docs.opsview.org/doku.php?id=opsview3.4:api
                # this is only necessary when accessing the API and expecting a XML answer
                if self.type == "Opsview" and giveback == "opsxml":
                    headers = {"Content-Type":"text/xml", "X-Username":self.username, "X-Password":self.password}
                    request = urllib2.Request(url, cgi_data, headers)
                    urlcontent = urllib2.urlopen(request)            
                else:
                    # use opener - if cgi_data is not empty urllib uses a POST request
                    urlcontent = urllib2.urlopen(url, cgi_data)
            except:
                return "ERROR"
            
            # give back pure HTML or XML in case giveback is "raw"
            if giveback == "raw":
                return urlcontent.read()
            
            # give back pure nothing if giveback is "nothing" - useful for POST requests
            if giveback == "nothing":
                # do some cleanup
                del passman, auth_handler, digest_handler, urlcontent
                return None   
            
            # give back lxml-objectified data
            if giveback == "obj":
                # the heart of the whole Nagios-status-monitoring engine:
                # first step: parse the read HTML
                html = lxml.etree.HTML(urlcontent.read())
                    
                # second step: make pretty HTML of it
                prettyhtml = lxml.etree.tostring(copy.copy(html), pretty_print=True)
                
                # third step: clean HTML from tags which embarass libxml2 2.7
                # only possible when module lxml.html.clean has been loaded
                if sys.modules.has_key("lxml.html.clean"):
                    # clean html from tags which libxml2 2.7 is worried about
                    # this is the case with all tags that do not need a closing end tag like link, br, img
                    cleaner = lxml.html.clean.Cleaner(remove_tags=["link", "br", "img"], page_structure=True, style=False)
                    prettyhtml = copy.copy(cleaner.clean_html(prettyhtml))
                    
                    # lousy workaround for libxml2 2.7 which worries about attributes without value
                    # we hope that nobody names a server '" nowrap>' - chances are pretty small because this "name"
                    # contains unallowed characters and is far from common sense
                    prettyhtml = prettyhtml.replace('" nowrap>', '">')
                    
                    # cleanup cleaner
                    del cleaner
    
                # fourth step: make objects of tags for easy access
                htobj = copy.copy(lxml.objectify.fromstring(prettyhtml))
                
                #do some cleanup
                del passman, auth_handler, digest_handler, urlcontent, html, prettyhtml
        
                # give back HTML object from Nagios webseite
                return htobj
                
            elif self.type == "Opsview" and giveback == "opsxml":
                # objectify the xml and give it back after some cleanup
                xml = lxml.etree.XML(urlcontent.read())
                xmlpretty = lxml.etree.tostring(xml, pretty_print=True)
                xmlobj = copy.copy(lxml.objectify.fromstring(xmlpretty))
                del passman, auth_handler, urlcontent, xml, xmlpretty
                return xmlobj
            
            else:
                # in case some error regarding the type occured raise exception
                raise
            
        except:
            # do some cleanup
            del passman, auth_handler, digest_handler, urlcontent
            return "ERROR"
        
        # in case the wrong giveback type has been specified return error
        # do some cleanup
        try:
            del passman, auth_handler, digest_handler, urlcontent
        except:
            pass
        return "ERROR"

    
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
        htobj = self.FetchURL(nagcgiurl_host, giveback="obj")

        try:
            # take ip from object path
            if self.type == "Opsview":
                # Opsview puts a lot of Javascript into HTML page so the wanted
                # information table is embedded in another DIV
                ip = str(htobj.body.div[3].table.tr.td[1].getchildren()[-2])
            else:
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
                print "IP of %s:" % (host), ip
            # when connection by DNS is not configured do it by IP
            if str(self.conf.connect_by_dns_yes) == "True":
                # try to get DNS name for ip, if not available use ip
                try:
                    host = socket.gethostbyaddr(ip)[0]
                except:
                    host = ip
            else:
                host = ip
        except:
            host = "ERROR"
         
        # do some cleanup
        del htobj    

        # give back host or ip
        return host
    
    
    def __del__(self):
        """
        hopefully a __del__() method may make this object better collectable for gc
        """
        del(self)
    
    
class NagiosHost(object):
    """
        one host which is monitored by a Nagios server, gets populated with services
    """
    def __init__(self):
        self.name = ""
        self.status = ""
        self.last_check = ""
        self.duration = ""
        self.attempt = ""
        self.status_information = ""
        self.services = dict()
        
        
    def __del__(self):
        """
        hopefully a __del__() method may make this object better collectable for gc
        """
        del(self)
        
        
class NagiosService(object):
    """
        one service which runs on a host
    """
    def __init__(self):
        self.name = ""
        self.host = ""
        self.status = ""
        self.last_check = ""
        self.duration = ""
        self.attempt = ""
        self.status_information = ""
        
        
    def __del__(self):
        """
        hopefully a __del__() method may make this object better collectable for gc
        """
        del(self)
 
