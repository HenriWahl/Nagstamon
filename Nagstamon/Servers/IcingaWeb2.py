# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2014 Henri Wahl <h.wahl@ifw-dresden.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

# Initial implementation by Marcus Mönnig
#
# This Server class connects against IcingaWeb2. The monitor URL in the setup should be
# something like http://icinga2/icingaweb2
#
# Status/TODOs:
#
# * The IcingaWeb2 REST API is not (fully) implemented yet, so currently this implementation is
#   limited to "view only". Once https://dev.icinga.org/issues/9606 and/or https://dev.icinga.org/issues/7300
#   get implemented, the action part (schedule downtime, acknowledge, etc.) can be implemented in
#   this class.


from Nagstamon.Servers.Generic import GenericServer
import urllib.request, urllib.parse, urllib.error
import sys
import copy
import json
import datetime
import webbrowser
from bs4 import BeautifulSoup
from Nagstamon.Objects import (GenericHost, GenericService, Result)
from Nagstamon.Helpers import not_empty
from Nagstamon.Config import (conf, AppInfo)
from collections import OrderedDict


def strfdelta(tdelta, fmt):
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)

class IcingaWeb2Server(GenericServer):
    """
        object of Incinga server
    """
    TYPE = u'IcingaWeb2'
    MENU_ACTIONS = ['Monitor']
    STATES_MAPPING = {"hosts" : {0 : "UP", 1 : "DOWN", 2 : "UNREACHABLE"},\
                     "services" : {0 : "OK", 1 : "WARNING",  2 : "CRITICAL", 3 : "UNKNOWN"}}
    BROWSER_URLS = { "monitor": "$MONITOR-CGI$/dashboard",\
                    "hosts": "$MONITOR-CGI$/monitoring/list/hosts",\
                    "services": "$MONITOR-CGI$/monitoring/list/services",\
                    "history": "$MONITOR-CGI$/monitoring/list/eventhistory?timestamp>=-7 days"}

    def init_config(self):
        """
            set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # dummy default empty cgi urls - get filled later when server version is known
        self.cgiurl_services = None
        self.cgiurl_hosts = None
        self.use_display_name_host = False
        self.use_display_name_service = False



    def init_HTTP(self):
        GenericServer.init_HTTP(self)

        if not "Referer" in self.session.headers:
            self.session.headers["Referer"] = self.monitor_cgi_url + "/icingaweb2/monitoring"


    def get_server_version(self):
        """
            Try to get Icinga version
        """
        result = self.FetchURL("%s/about" % (self.monitor_cgi_url), giveback="raw")

        if result.error != "":
            return result
        else:
            aboutraw = result.result

        aboutsoup = BeautifulSoup(aboutraw)
        self.version =  aboutsoup.find("dt",text="Version").parent.findNext("dd").contents[0]



    def _get_status(self):
        """
            Get status from Icinga Server, prefer JSON if possible
        """
        try:
            if self.version == '':
                # we need to get the server version
                result = self.get_server_version()
            if self.version != "":
                # define CGI URLs for hosts and services
                if self.cgiurl_hosts == self.cgiurl_services == None:
                    # services (unknown, warning or critical?)
                    self.cgiurl_services = {"hard": self.monitor_cgi_url + "/monitoring/list/services?service_state>0&service_state<=3&service_state_type=1&addColumns=service_last_check&format=json",\
                                            "soft": self.monitor_cgi_url + "/monitoring/list/services?service_state>0&service_state<=3&service_state_type=0&addColumns=service_last_check&format=json"}
                    # hosts (up or down or unreachable)
                    self.cgiurl_hosts = {"hard": self.monitor_cgi_url + "/monitoring/list/hosts?host_state>0&host_state<=2&host_state_type=1&addColumns=host_last_check&format=json",\
                                         "soft": self.monitor_cgi_url + "/monitoring/list/hosts?host_state>0&host_state<=2&host_state_type=0&addColumns=host_last_check&format=json"}
                self._get_status_JSON()
            else:
                # error result in case version still was ""
                return result
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()


    def _get_status_JSON(self):
        """
            Get status from Icinga Server - the JSON way
        """
        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # now using JSON output from Icinga
        try:
            for status_type in "hard", "soft":
                result = self.FetchURL(self.cgiurl_hosts[status_type], giveback="raw")
                # purify JSON result of unnecessary control sequence \n
                jsonraw, error = copy.deepcopy(result.result.replace("\n", "")), copy.deepcopy(result.error)

                if error != "": return Result(result=jsonraw, error=error)

                hosts = copy.deepcopy(json.loads(jsonraw))

                for host in hosts:
                    # make dict of tuples for better reading
                    h = dict(host.items())

                    # host
                    if self.use_display_name_host == False:
                        # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                        # better be host_name instead of host_display_name
                        # legacy Icinga adjustments
                        if 'host_name' in h: host_name = h['host_name']
                        elif 'host' in h: host_name = h['host']
                    else:
                        # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                        # problems with that so here we go with extra display_name option
                        host_name = h["host_display_name"]

                    # host objects contain service objects
                    ###if not self.new_hosts.has_key(host_name):
                    if not host_name in self.new_hosts:
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].server = self.name
                        self.new_hosts[host_name].status = self.STATES_MAPPING["hosts"][h["host_state"]]
                        self.new_hosts[host_name].last_check = datetime.datetime.utcfromtimestamp(h["host_last_check"])
                        duration=datetime.datetime.now()-datetime.datetime.utcfromtimestamp(h["host_last_state_change"])
                        self.new_hosts[host_name].duration = strfdelta(duration, "{days}d {hours}h {minutes}m {seconds}s")
                        self.new_hosts[host_name].attempt = h["host_attempt"]
                        self.new_hosts[host_name].status_information= h["host_output"].replace("\n", " ").strip()
                        self.new_hosts[host_name].passiveonly = not(h["host_active_checks_enabled"])
                        self.new_hosts[host_name].notifications_disabled = not(h["host_notifications_enabled"])
                        self.new_hosts[host_name].flapping = h["host_is_flapping"]
                        self.new_hosts[host_name].acknowledged = h["host_acknowledged"]
                        self.new_hosts[host_name].scheduled_downtime = h["host_in_downtime"]
                        self.new_hosts[host_name].status_type = status_type
                    del h, host_name
        except:


            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            for status_type in "hard", "soft":
                result = self.FetchURL(self.cgiurl_services[status_type], giveback="raw")
                # purify JSON result of unnecessary control sequence \n
                jsonraw, error = copy.deepcopy(result.result.replace("\n", "")), copy.deepcopy(result.error)

                if error != "": return Result(result=jsonraw, error=error)


                services = copy.deepcopy(json.loads(jsonraw))


                for service in services:
                    # make dict of tuples for better reading
                    s = dict(service.items())

                    if str(self.use_display_name_host) == "False":
                        # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                        # better be host_name instead of host_display_name
                        # legacy Icinga adjustments
                        ###if s.has_key("host_name"): host_name = s["host_name"]
                        if 'host_name' in s: host_name = s['host_name']
                        ###elif s.has_key("host"): host_name = s["host"]
                        elif 'host' in s: host_name = s['host']
                    else:
                        # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                        # problems with that so here we go with extra display_name option
                        host_name = s["host_display_name"]

                    # host objects contain service objects
                    ###if not self.new_hosts.has_key(host_name):
                    if not host_name in self.new_hosts:
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].status = "UP"

                    if str(self.use_display_name_host) == "False":
                        # legacy Icinga adjustments
                        ###if s.has_key("service_description"): service_name = s["service_description"]
                        if 'service_description' in s: service_name = s["service_description"]
                        ###elif s.has_key("description"): service_name = s["description"]
                        elif 'description' in s: service_name = s['description']
                        ###elif s.has_key("service"): service_name = s["service"]
                        elif 'service' in s: service_name = s['service']
                    else:
                        service_name = s["service_display_name"]

                    # if a service does not exist create its object
                    ###if not self.new_hosts[host_name].services.has_key(service_name):
                    if not service_name in self.new_hosts[host_name].services:
                        self.new_hosts[host_name].services[service_name] = GenericService()
                        self.new_hosts[host_name].services[service_name].host = host_name
                        self.new_hosts[host_name].services[service_name].name = service_name
                        self.new_hosts[host_name].services[service_name].server = self.name
                        self.new_hosts[host_name].services[service_name].status = self.STATES_MAPPING["services"][s["service_state"]]
                        self.new_hosts[host_name].services[service_name].last_check = datetime.datetime.utcfromtimestamp(s["service_last_check"])
                        duration=datetime.datetime.now()-datetime.datetime.utcfromtimestamp(s["service_last_state_change"])
                        self.new_hosts[host_name].services[service_name].duration = strfdelta(duration, "{days}d {hours}h {minutes}m {seconds}s")
                        self.new_hosts[host_name].services[service_name].attempt = s["service_attempt"]
                        self.new_hosts[host_name].services[service_name].status_information = s["service_output"].replace("\n", " ").strip()
                        self.new_hosts[host_name].services[service_name].passiveonly = not(s["service_active_checks_enabled"])
                        self.new_hosts[host_name].services[service_name].notifications_disabled = not(s["service_notifications_enabled"])
                        self.new_hosts[host_name].services[service_name].flapping = s["service_is_flapping"]
                        self.new_hosts[host_name].services[service_name].acknowledged = s["service_acknowledged"]
                        self.new_hosts[host_name].services[service_name].scheduled_downtime = s["service_in_downtime"]

                        self.new_hosts[host_name].services[service_name].status_type = status_type
                    del s, host_name, service_name
        except:

            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # some cleanup
        del jsonraw, error, hosts, services

        #dummy return in case all is OK
        return Result()



    def set_recheck(self, info_dict):
        # Not implemented since there is no REST API call yet
        # This empty implementation prevents an error when selecting "Recheck all" from the
        # context menu. (The "Recheck all" menu element is always visible.)
        None


    def _set_recheck(self, host, service):
        # Not implemented since there is no REST API call yet
        # This empty implementation prevents an error when selecting "Recheck all" from the
        # context menu. (The "Recheck all" menu element is always visible.)
        None
