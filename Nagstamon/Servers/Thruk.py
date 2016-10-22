# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2014 Henri Wahl <h.wahl@ifw-dresden.de> et al.
# Thruk additions copyright by dcec@Github
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

from Nagstamon.Servers.Generic import GenericServer
import sys
import json
import datetime
import copy

from Nagstamon.Helpers import HumanReadableDurationFromTimestamp
from Nagstamon.Objects import (GenericHost, GenericService, Result)


class ThrukServer(GenericServer):
    """
        Thruk is derived from generic (Nagios) server
    """
    TYPE = 'Thruk'

    # dictionary to translate status bitmaps on webinterface into status flags
    # this are defaults from Nagios
    # "disabled.gif" is in Nagios for hosts the same as "passiveonly.gif" for services
    STATUS_MAPPING = { "ack.gif" : "acknowledged", \
                       "passiveonly.gif" : "passiveonly", \
                       "disabled.gif" : "passiveonly", \
                       "ndisabled.gif" : "notifications_disabled", \
                       "downtime.gif" : "scheduled_downtime", \
                       "flapping.gif" : "flapping"}

    # Entries for monitor default actions in context menu
    MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Submit check result", "Downtime"]

    # Arguments available for submitting check results
    SUBMIT_CHECK_RESULT_ARGS = ["check_output", "performance_data"]

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS = { "monitor": "$MONITOR$", \
                    "hosts": "$MONITOR-CGI$/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&page=1&entries=all", \
                    "services": "$MONITOR-CGI$/status.cgi?dfl_s0_value_sel=5&dfl_s0_servicestatustypes=29&dfl_s0_op=%3D&style=detail&dfl_s0_type=host&dfl_s0_serviceprops=0&dfl_s0_servicestatustype=4&dfl_s0_servicestatustype=8&dfl_s0_servicestatustype=16&dfl_s0_servicestatustype=1&hidetop=&dfl_s0_hoststatustypes=15&dfl_s0_val_pre=&hidesearch=2&dfl_s0_value=all&dfl_s0_hostprops=0&nav=&page=1&entries=all", \
                    "history": "$MONITOR-CGI$/history.cgi?host=all&page=1&entries=all"}

    STATES_MAPPING = {"hosts" : {0 : "OK", 1 : "DOWN", 2 : "UNREACHABLE"}, \
                      "services" : {0 : "OK", 1 : "WARNING", 2 : "CRITICAL", 3 : "UNKNOWN"}}


    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # flag for newer cookie authentication
        self.CookieAuth = False


    def reset_HTTP(self):
        """
            brute force reset by GenericServer disturbs logging in into Thruk
        """
        # only reset session if Thruks 2 cookies are there
        try:
            # only reset session if Thruks 2 cookies are there
            if len(self.session.cookies) > 1:
                self.session = None
        except:
            self.Error(sys.exc_info())


    def init_HTTP(self):
        """
            partly not constantly working Basic Authorization requires extra Autorization headers,
            different between various server types
        """
        GenericServer.init_HTTP(self)

        # only if cookies are needed
        if self.CookieAuth:
            # get cookie to access Thruk web interface
            # Thruk first send a test cookie, later an auth cookie
            if len(self.session.cookies) < 2:
                # get cookie from login page via url retrieving as with other urls
                try:
                    # login and get cookie
                    self.login()
                except:
                    self.Error(sys.exc_info())


    def init_config(self):
        """
            set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        # Thruk allows requesting only needed information to reduce traffic
        self.cgiurl_services = self.monitor_cgi_url + "/status.cgi?host=all&servicestatustypes=28&view_mode=json&"\
                                                      "entries=all&columns=host_name,description,state,last_check,"\
                                                      "last_state_change,plugin_output,current_attempt,"\
                                                      "max_check_attempts,active_checks_enabled,is_flapping,"\
                                                      "notifications_enabled,acknowledged,state_type,"\
                                                      "scheduled_downtime_depth"
        # hosts (up or down or unreachable)
        self.cgiurl_hosts = self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&"\
                                                    "view_mode=json&entries=all&"\
                                                    "columns=name,state,last_check,last_state_change,"\
                                                    "plugin_output,current_attempt,max_check_attempts,"\
                                                    "active_checks_enabled,notifications_enabled,is_flapping,"\
                                                    "acknowledged,scheduled_downtime_depth,state_type"

        # get cookie from login page via url retrieving as with other urls
        try:
            # login and get cookie
            self.login()

            if len(self.session.cookies) > 0:
                self.CookieAuth = True
        except:
            self.Error(sys.exc_info())


    def login(self):
        """
            use pure session instead of FetchURL to get Thruk session
        """
        self.session.post(self.monitor_cgi_url + '/login.cgi?',
                          data={'login': self.get_username(),
                                'password': self.get_password(),
                                'submit': 'Login',
                                'referer': ''})


    def _get_status(self):
        """
            Get status from Thruk Server
        """
        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            # JSON experiments
            result = self.FetchURL(self.cgiurl_hosts, giveback='raw')
            jsonraw, error, status_code = copy.deepcopy(result.result),\
                                          copy.deepcopy(result.error),\
                                          result.status_code
            
            # check if any error occured
            errors_occured = self.check_for_error(jsonraw, error, status_code)
            # if there are errors return them
            if errors_occured != False:
                return(errors_occured)     

            # in case basic auth did not work try form login cookie based login
            if jsonraw.startswith("<"):
                self.CookieAuth = True
                return Result(result=None, error="Login failed")

            # in case JSON is not empty evaluate it
            elif not jsonraw == "[]":
                hosts = json.loads(jsonraw)

                for h in hosts:
                    if h["name"] not in self.new_hosts:
                        self.new_hosts[h["name"]] = GenericHost()
                        self.new_hosts[h["name"]].name = h["name"]
                        self.new_hosts[h["name"]].server = self.name
                        self.new_hosts[h["name"]].status = self.STATES_MAPPING["hosts"][h["state"]]
                        self.new_hosts[h["name"]].last_check = datetime.datetime.fromtimestamp(int(h["last_check"])).isoformat(" ")
                        self.new_hosts[h["name"]].duration = HumanReadableDurationFromTimestamp(h["last_state_change"])
                        self.new_hosts[h["name"]].attempt = "%s/%s" % (h["current_attempt"], h["max_check_attempts"])
                        self.new_hosts[h["name"]].status_information = h["plugin_output"].replace("\n", " ").strip()
                        self.new_hosts[h["name"]].passiveonly = not(bool(int(h["active_checks_enabled"])))
                        self.new_hosts[h["name"]].notifications_disabled = not(bool(int(h["notifications_enabled"])))
                        self.new_hosts[h["name"]].flapping = bool(int(h["is_flapping"]))
                        self.new_hosts[h["name"]].acknowledged = bool(int(h["acknowledged"]))
                        self.new_hosts[h["name"]].scheduled_downtime = bool(int(h["scheduled_downtime_depth"]))
                        self.new_hosts[h["name"]].status_type = {0: "soft", 1: "hard"}[h["state_type"]]
                    del h
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            # JSON experiments
            result = self.FetchURL(self.cgiurl_services, giveback="raw")
            jsonraw, error, status_code = copy.deepcopy(result.result),\
                                          copy.deepcopy(result.error),\
                                          result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(jsonraw, error, status_code)
            # if there are errors return them
            if errors_occured != False:
                return(errors_occured)
            
            # in case basic auth did not work try form login cookie based login
            if jsonraw.startswith("<"):
                self.CookieAuth = True
                return Result(result=None, error="Login failed")

            # in case JSON is not empty evaluate it
            elif not jsonraw == "[]":
                services = json.loads(jsonraw)

                for s in services:
                    # host objects contain service objects
                    if s["host_name"] not in self.new_hosts:
                        self.new_hosts[s["host_name"]] = GenericHost()
                        self.new_hosts[s["host_name"]].name = s["host_name"]
                        self.new_hosts[s["host_name"]].server = self.name
                        self.new_hosts[s["host_name"]].status = "UP"

                    # if a service does not exist create its object
                    if s["description"] not in self.new_hosts[s["host_name"]].services:
                        # ##new_service = s["description"]
                        self.new_hosts[s["host_name"]].services[s["description"]] = GenericService()
                        self.new_hosts[s["host_name"]].services[s["description"]].host = s["host_name"]
                        self.new_hosts[s["host_name"]].services[s["description"]].name = s["description"]
                        self.new_hosts[s["host_name"]].services[s["description"]].server = self.name
                        self.new_hosts[s["host_name"]].services[s["description"]].status = self.STATES_MAPPING["services"][s["state"]]
                        self.new_hosts[s["host_name"]].services[s["description"]].last_check = datetime.datetime.fromtimestamp(int(s["last_check"])).isoformat(" ")
                        self.new_hosts[s["host_name"]].services[s["description"]].duration = HumanReadableDurationFromTimestamp(s["last_state_change"])
                        self.new_hosts[s["host_name"]].services[s["description"]].attempt = "%s/%s" % (s["current_attempt"], s["max_check_attempts"])
                        self.new_hosts[s["host_name"]].services[s["description"]].status_information = s["plugin_output"].replace("\n", " ").strip()
                        self.new_hosts[s["host_name"]].services[s["description"]].passiveonly = not(bool(int(s["active_checks_enabled"])))
                        self.new_hosts[s["host_name"]].services[s["description"]].notifications_disabled = not(bool(int(s["notifications_enabled"])))
                        self.new_hosts[s["host_name"]].services[s["description"]].flapping = not(bool(int(s["notifications_enabled"])))
                        self.new_hosts[s["host_name"]].services[s["description"]].acknowledged = bool(int(s["acknowledged"]))
                        self.new_hosts[s["host_name"]].services[s["description"]].scheduled_downtime = bool(int(s["scheduled_downtime_depth"]))
                        self.new_hosts[s["host_name"]].services[s["description"]].status_type = {0: "soft", 1: "hard"}[s["state_type"]]
                        del s
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

