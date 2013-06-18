# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2013 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

from Nagstamon.Server.Generic import GenericServer
import sys
import cookielib
import base64
import json
import datetime
import urllib
import copy

# to let Linux distributions use their own BeautifulSoup if existent try importing local BeautifulSoup first
# see https://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3302612&group_id=236865
try:
    from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
except:
    from Nagstamon.BeautifulSoup import BeautifulSoup, BeautifulStoneSoup

from Nagstamon.Actions import HostIsFilteredOutByRE, ServiceIsFilteredOutByRE, StatusInformationIsFilteredOutByRE, not_empty
from Nagstamon.Objects import *


class ThrukServer(GenericServer):
    """
        Thruk is derived from generic (Nagios) server
    """
    TYPE = 'Thruk'

    # GUI sortable columns stuff
    DEFAULT_SORT_COLUMN_ID = 2
    # lost any memory what this COLOR_COLUMN_ID is used for...
    #COLOR_COLUMN_ID = 2
    HOST_COLUMN_ID = 0
    SERVICE_COLUMN_ID = 1
    # used for $STATUS$ variable for custom actions
    STATUS_INFO_COLUMN_ID = 6

    COLUMNS = [
        HostColumn,
        ServiceColumn,
        StatusColumn,
        LastCheckColumn,
        DurationColumn,
        AttemptColumn,
        StatusInformationColumn
    ]

    # autologin is used only by Centreon
    DISABLED_CONTROLS = ["input_checkbutton_use_autologin", "label_autologin_key", "input_entry_autologin_key"]

    # dictionary to translate status bitmaps on webinterface into status flags
    # this are defaults from Nagios
    # "disabled.gif" is in Nagios for hosts the same as "passiveonly.gif" for services
    STATUS_MAPPING = { "ack.gif" : "acknowledged",\
                       "passiveonly.gif" : "passiveonly",\
                       "disabled.gif" : "passiveonly",\
                       "ndisabled.gif" : "notifications_disabled",\
                       "downtime.gif" : "scheduled_downtime",\
                       "flapping.gif" : "flapping"}

    # Entries for monitor default actions in context menu
    MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Submit check result", "Downtime"]

    # Arguments available for submitting check results
    SUBMIT_CHECK_RESULT_ARGS = ["check_output", "performance_data"]

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS = { "monitor": "$MONITOR$",\
                    "hosts": "$MONITOR-CGI$/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12",\
                    "services": "$MONITOR-CGI$/status.cgi?dfl_s0_value_sel=5&dfl_s0_servicestatustypes=29&dfl_s0_op=%3D&style=detail&dfl_s0_type=host&dfl_s0_serviceprops=0&dfl_s0_servicestatustype=4&dfl_s0_servicestatustype=8&dfl_s0_servicestatustype=16&dfl_s0_servicestatustype=1&hidetop=&dfl_s0_hoststatustypes=15&dfl_s0_val_pre=&hidesearch=2&dfl_s0_value=all&dfl_s0_hostprops=0&nav=&page=1&entries=all",\
                    "history": "$MONITOR-CGI$/history.cgi?host=all&page=1&entries=all"}

    STATES_MAPPING = {"hosts" : {0 : "OK", 1 : "DOWN", 2 : "UNREACHABLE"},\
                      "services" : {0 : "OK", 1 : "WARNING",  2 : "CRITICAL", 3 : "UNKNOWN"}}


    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # flag for newer cookie authentication
        self.CookieAuth = False


    def init_HTTP(self):
        """
        partly not constantly working Basic Authorization requires extra Autorization headers,
        different between various server types
        """
        if self.HTTPheaders == {}:
            for giveback in ["raw", "obj"]:
                self.HTTPheaders[giveback] = {"Authorization": "Basic " + base64.b64encode(self.get_username() + ":" + self.get_password())}

        # only if cookies are needed
        if self.CookieAuth:
            # get cookie to access Check_MK web interface
            if len(self.Cookie) < 2:
                # put all necessary data into url string
                logindata = urllib.urlencode({"login":self.get_username(),\
                                 "password":self.get_password(),\
                                 "submit":"Login"})
                # get cookie from login page via url retrieving as with other urls
                try:
                    # login and get cookie
                    # empty referer seems to be ignored so add it manually
                    urlcontent = self.urlopener.open(self.monitor_cgi_url + "/login.cgi?", logindata + "&referer=")
                    urlcontent.close()
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
                                                        "columns=host_name,description,state,last_check,"\
                                                        "last_state_change,plugin_output,current_attempt,"\
                                                        "max_check_attempts,active_checks_enabled,is_flapping,"\
                                                        "notifications_enabled,acknowledged,state_type,"\
                                                        "scheduled_downtime_depth"
        # hosts (up or down or unreachable)
        self.cgiurl_hosts = self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&"\
                                                    "view_mode=json&columns=name,state,last_check,last_state_change,"\
                                                    "plugin_output,current_attempt,max_check_attempts"\
                                                    "active_checks_enabled,notifications_enabled,is_flapping"\
                                                    "acknowledged,scheduled_downtime_depth,state_type"

        # test for cookies
        # put all necessary data into url string
        logindata = urllib.urlencode({"login":self.get_username(),\
                                 "password":self.get_password(),\
                                 "submit":"Login"})
        # get cookie from login page via url retrieving as with other urls
        try:
            # login and get cookie
            # empty referer seems to be ignored so add it manually
            urlcontent = self.urlopener.open(self.monitor_cgi_url + "/login.cgi?", logindata + "&referer=")
            urlcontent.close()
            if len(self.Cookie) > 0:
                self.CookieAuth = True
        except:
            self.Error(sys.exc_info())


    def _get_status(self):
        """
        Get status from Thruk Server
        """
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services":[], "hosts":[]}

        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            # JSON experiments
            result = self.FetchURL(self.cgiurl_hosts, giveback="raw")
            jsonraw, error = copy.deepcopy(result.result), copy.deepcopy(result.error)
            if error != "": return Result(result=jsonraw, error=error)

            # in case basic auth did not work try form login cookie based login
            if jsonraw.startswith("<"):
                self.CookieAuth = True
                return Result(result=None, error="Login failed.")

            # in case JSON is not empty evaluate it
            elif not jsonraw == "[]":
                hosts = json.loads(jsonraw)

                for h in hosts:
                    # new host item
                    n = {}

                    # host
                    n["host"] = h["name"]
                    # status
                    n["status"] = self.STATES_MAPPING["hosts"][h["state"]]
                    # last_check
                    n["last_check"] = datetime.datetime.fromtimestamp(int(h["last_check"])).isoformat(" ")
                    # duration
                    n["duration"] = Actions.HumanReadableDurationThruk(h["last_state_change"])
                    # status information
                    n["status_information"] = h["plugin_output"]
                    # attempts
                    n["attempt"] = "%s/%s" % (h["current_attempt"], h["max_check_attempts"])
                    # status flags
                    n["passiveonly"] = not(bool(int(h["active_checks_enabled"])))
                    n["notifications_disabled"] = not(bool(int(h["notifications_enabled"])))
                    n["flapping"] = bool(int(h["is_flapping"]))
                    n["acknowledged"] = bool(int(h["acknowledged"]))
                    n["scheduled_downtime"] = bool(int(h["scheduled_downtime_depth"]))
                    n["status_type"] = {0: "soft", 1: "hard"}[h["state_type"]]

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
                        self.new_hosts[new_host].status_type = n["status_type"]
                        del n
                    del h
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:

            # JSON experiments
            result = self.FetchURL(self.cgiurl_services, giveback="raw")
            jsonraw, error = copy.deepcopy(result.result), copy.deepcopy(result.error)

            if error != "": return Result(result=jsonraw, error=error)

            # in case basic auth did not work try form login cookie based login
            if jsonraw.startswith("<"):
                self.CookieAuth = True
                return Result(result=None, error="Login failed.")

            # in case JSON is not empty evaluate it
            elif not jsonraw == "[]":
                services = json.loads(jsonraw)

                for s in services:
                    # new service item
                    n = {}
                    n["host"] = s["host_name"]
                    n["service"] = s["description"]
                    # status
                    n["status"] = self.STATES_MAPPING["services"][s["state"]]
                    # last_check
                    n["last_check"] = datetime.datetime.fromtimestamp(int(s["last_check"])).isoformat(" ")
                    # duration
                    n["duration"] = Actions.HumanReadableDurationThruk(s["last_state_change"])
                    # status information
                    n["status_information"] = s["plugin_output"]
                    # attempts
                    n["attempt"] = "%s/%s" % (s["current_attempt"], s["max_check_attempts"])
                    # status flags
                    n["passiveonly"] = not(bool(int(s["active_checks_enabled"])))
                    n["notifications_disabled"] = not(bool(int(s["notifications_enabled"])))
                    n["flapping"] = bool(int(s["is_flapping"]))
                    n["acknowledged"] = bool(int(s["acknowledged"]))
                    n["scheduled_downtime"] = bool(int(s["scheduled_downtime_depth"]))
                    n["status_type"] = {0: "soft", 1: "hard"}[s["state_type"]]

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
                        self.new_hosts[n["host"]].services[new_service].status_type = n["status_type"]
                        del s
                    del n

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # some cleanup
        del nagitems

        #dummy return in case all is OK
        return Result()

