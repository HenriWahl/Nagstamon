# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
#
# Based on https://github.com/duncs/Nagstamon by @duncs
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

import sys
import urllib.request, urllib.parse, urllib.error
import copy
import pprint
import re
import json

from datetime import datetime, timedelta
from ast import literal_eval

from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Helpers import (HumanReadableDurationFromSeconds,
                               webbrowser_open)


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

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS= {'monitor': '$MONITOR$/monitoring',
                   'hosts': '$MONITOR$/monitoring/#!/allproblems',
                   'services': '$MONITOR$/monitoring/#!/allproblems',
                   'history': '$MONITOR$/monitoring/#!/events'}


    def init_HTTP(self):
        """
            things to do if HTTP is not initialized
        """
        GenericServer.init_HTTP(self)

        # prepare for JSON
        self.session.headers.update({'Accept': 'application/json',
                                     'Content-Type': 'application/json'})

        # get cookie to access Opsview web interface to access Opsviews Nagios part
        if len(self.session.cookies) == 0:

            if conf.debug_mode:
                self.debug(server=self.get_name(), debug="Fetching Login token")

            logindata = json.dumps({'username': self.get_username(),
                                   'password': self.get_password()})

            # the following is necessary for Opsview servers
            # get cookie from login page via url retrieving as with other urls
            try:
                # login and get cookie
                resp = literal_eval(self.fetch_url(self.monitor_url + "/rest/login",
                                                   giveback='raw',
                                                   cgi_data=logindata).result)

                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug="Login Token: " + resp.get('token'))

                self.session.headers.update({'X-Opsview-Username': self.get_username(),
                                             'X-Opsview-Token':resp.get('token')})
            except:
                self.error(sys.exc_info())


    def init_config(self):
        """
	        dummy init_config, called at thread start, not really needed here, just omit extra properties
        """
        pass


    def get_start_end(self, host):
        """
            Set a default of starttime of "now" and endtime is "now + 24 hours"
        directly from web interface
        """
        start = datetime.now()
        end = datetime.now() + timedelta(hours=24)

        return str(start.strftime("%Y-%m-%d %H:%M:%S")), str(end.strftime("%Y-%m-%d %H:%M:%S"))


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        url = self.monitor_url + "/rest/downtime?"

        data = dict();
        data["comment"]=str(comment)
        data["starttime"]=start_time
        data["endtime"]=end_time

        if service == "":
            data["hst.hostname"]=str(host)

        if service != "":
            data["svc.hostname"]=str(host)
            data["svc.servicename"]=str(service)

        cgi_data = urllib.parse.urlencode(data)

        self.debug(server=self.get_name(), debug="Downtime url: " + url)
        self.fetch_url(url + cgi_data, giveback="raw", cgi_data=({ }))


    def _set_submit_check_result(self, host, service, state, comment, check_output, performance_data):
        """
            worker for submitting check result
        """
        url = self.monitor_url + "/rest/status?"

        data = dict();
        data["comment"]=str(comment)
        data["new_state"]=({"ok":0,"warning":1,"critical":2,"unknown":3})[state]

        if service == "":
            data["hst.hostname"]=str(host)

        if service != "":
            data["svc.hostname"]=str(host)
            data["svc.servicename"]=str(service)

        cgi_data = urllib.parse.urlencode(data)

        self.debug(server=self.get_name(), debug="Submit result url: " + url)
        self.fetch_url(url + cgi_data, giveback="raw", cgi_data=({ }))


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None):
        """
            Sumit acknowledgement for host or service
        """
        url = self.monitor_url + "/rest/acknowledge?"

        data=dict();
        data["notify"]=str(notify)
        data["sticky"]=str(sticky)
        data["comment"]=str(comment)
        data["host"]=str(host)

        if service != "":
            data["servicecheck"]=str(service)

        cgi_data = urllib.parse.urlencode(data)

        self.debug(server=self.get_name(), debug="ACK url: " + url)
        self.fetch_url(url + cgi_data, giveback="raw", cgi_data=({ }))


    def _set_recheck(self, host, service):
        """
            Sumit recheck request for host or service
        """
        url = self.monitor_url + "/rest/recheck?"

        data=dict();
        data["host"]=str(host)

        if service != "":
            data["servicecheck"]=str(service)

        cgi_data = urllib.parse.urlencode(data)

        self.debug(server=self.get_name(), debug="Recheck url: " + url)
        self.fetch_url(url + cgi_data, giveback="raw", cgi_data=({ }))


    def _get_status(self):
        """
	        Get status from Opsview Server
        """
        if self.can_change_only:
            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="Showing only objects that the user can change or put in downtime")

            can_change = '&can_change=true'
        else:
            can_change = ''

        if self.hashtag_filter != '':
            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="Raw hashtag filter string: " +
                           self.hashtag_filter)

            trimmed_hashtags = re.sub(r'[#\s]', '', self.hashtag_filter).split(",")
            list_of_non_empty_hashtags = [i for i in trimmed_hashtags if i]

            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="List of trimmed hashtags" +
                           pprint.pformat(list_of_non_empty_hashtags))

            keywords = "&keyword=" + "&keyword=".join(list_of_non_empty_hashtags)

            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="Keyword string" + pprint.pformat(keywords))
        else:
            keywords = ''

        # following XXXX to get ALL services in ALL states except OK
        # because we filter them out later
        # the REST API gets all host and service info in one call
        try:
            result = self.fetch_url(self.monitor_url + "/rest/status/service?state=1&state=2&state=3" + can_change + keywords, giveback="raw")

            data, error, status_code = json.loads(result.result), result.error, result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            # if there are errors return them
            if errors_occured is not None:
                return errors_occured
                
            if conf.debug_mode:
                self.debug(server=self.get_name(), debug="Fetched JSON: " + pprint.pformat(data))

            for host in data["list"]:
                self.new_hosts[host["name"]] = GenericHost()
                self.new_hosts[host["name"]].name = str(host["name"])
                self.new_hosts[host["name"]].server = self.name
                # states come in lower case from Opsview
                self.new_hosts[host["name"]].status = str(host["state"].upper())
                self.new_hosts[host["name"]].status_type = str(host["state_type"])
                self.new_hosts[host["name"]].last_check = datetime.fromtimestamp(int(host["last_check"])).strftime("%Y-%m-%d %H:%M:%S %z")
                self.new_hosts[host["name"]].duration = HumanReadableDurationFromSeconds(host["state_duration"])
                self.new_hosts[host["name"]].attempt = host["current_check_attempt"]+ "/" + host["max_check_attempts"]
                self.new_hosts[host["name"]].status_information = host["output"].replace("\n", " ")

                # if host is in downtime add it to known maintained hosts
                if host['downtime'] != "0":
                    self.new_hosts[host["name"]].scheduled_downtime = True
                #if host.has_key("acknowledged"):
                if 'acknowledged' in host:
                    self.new_hosts[host["name"]].acknowledged = True
                #if host.has_key("flapping"):
                if 'flapping' in host:
                    self.new_hosts[host["name"]].flapping = True

                #services
                for service in host["services"]:
                    self.new_hosts[host["name"]].services[service["name"]] = OpsviewService()
                    self.new_hosts[host["name"]].services[service["name"]].host = str(host["name"])
                    self.new_hosts[host["name"]].services[service["name"]].name = service["name"]
                    self.new_hosts[host["name"]].services[service["name"]].server = self.name

                    # states come in lower case from Opsview
                    self.new_hosts[host["name"]].services[service["name"]].status = service["state"].upper()
                    self.new_hosts[host["name"]].services[service["name"]].status_type = service["state_type"]
                    self.new_hosts[host["name"]].services[service["name"]].last_check = datetime.fromtimestamp(int(service["last_check"])).strftime("%Y-%m-%d %H:%M:%S %z")
                    self.new_hosts[host["name"]].services[service["name"]].duration = HumanReadableDurationFromSeconds(service["state_duration"])
                    self.new_hosts[host["name"]].services[service["name"]].attempt = service["current_check_attempt"]+ "/" + service["max_check_attempts"]
                    self.new_hosts[host["name"]].services[service["name"]].status_information= service["output"].replace("\n", " ")
                    if service['downtime'] != '0':
                        self.new_hosts[host["name"]].services[service["name"]].scheduled_downtime = True
                    #if service.has_key("acknowledged"):
                    if 'acknowledged' in service:
                        self.new_hosts[host["name"]].services[service["name"]].acknowledged = True
                    #f service.has_key("flapping"):
                    if 'flapping' in service:
                        self.new_hosts[host["name"]].services[service["name"]].flapping = True
                    # extra opsview id for service, needed for submitting check results
                    self.new_hosts[host["name"]].services[service["name"]].service_object_id = service["service_object_id"]

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()

    def open_monitor(self, host, service=''):
        '''
            open monitor from tablewidget context menu
        '''
        base_url = self.monitor_url + '/monitoring/#!?'
        host_url = base_url + urllib.parse.urlencode({'autoSelectHost': host})
        service_url = base_url + urllib.parse.urlencode({'autoSelectHost': host,
                                                         'autoSelectService': service},
                                                        quote_via=urllib.parse.quote)
        if service == '':
            if conf.debug_mode:
                self.debug(server=self.get_name(), host=host, service=service,
                           debug='Open host monitor web page ' + host_url)
            webbrowser_open(host_url)
        else:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='Open service monitor web page ' + service_url)
            webbrowser_open(service_url)

    def open_monitor_webpage(self):
        webbrowser_open('%s/monitoring/' % (self.monitor_url))
