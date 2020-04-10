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

# Initial implementation by Stephan Schwarz (@stearz)
#
# This Server class connects against Prometheus.
# The monitor URL in the setup should be something like
# http://prometheus.example.com
#
# Status/TODOs:
#
# * Currently we can only fetch and display alerts from Prometheus.
#   In the future it would be great to be able to interract with
#   alertmanager, so that managing alerts (e.g. silencing) is possible

import sys
import urllib.request, urllib.parse, urllib.error
import copy
import pprint
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


class PrometheusServer(GenericServer):
    """
       special treatment for Prometheus API
    """
    TYPE = 'Prometheus'

    # Prometheus actions are limited to visiting the monitor for now
    MENU_ACTIONS = ['Monitor']
    BROWSER_URLS= {'monitor': '$MONITOR$/alerts'}


    def init_HTTP(self):
        """
            things to do if HTTP is not initialized
        """
        GenericServer.init_HTTP(self)

        # prepare for JSON
        self.session.headers.update({'Accept': 'application/json',
                                     'Content-Type': 'application/json'})


    def init_config(self):
        """
	        dummy init_config, called at thread start
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
        """
	        to be implemented in a future release
        """
        pass


    def _get_status(self):
        """
	        Get status from Prometheus Server
        """
        # get all alerts from the API server
        try:
            result = self.FetchURL(self.monitor_url + "/api/v1/alerts", giveback="raw")
            data, error, status_code = json.loads(result.result), result.error, result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            # if there are errors return them
            if errors_occured != False:
                return(errors_occured)

            if conf.debug_mode:
                self.Debug(server=self.get_name(), debug="Fetched JSON: " + pprint.pformat(data))

### Debug Ausgaben nutzen und dann geht's weiter

            for alert in data["alerts"]:
                self.new_hosts[alert["labels"]["job"] = GenericHost()
                self.new_hosts[alert["labels"]["job"]].name = str(alert["labels"]["job"])
                self.new_hosts[alert["labels"]["job"]].server = self.name

#                self.new_hosts[alert["labels"]["job"]].status = str(alert["severity"].upper())
#                self.new_hosts[alert["labels"]["job"]].status_type = str(alert["state_type"])
#                self.new_hosts[alert["labels"]["job"]].last_check = datetime.fromtimestamp(int(alert["last_check"])).strftime("%Y-%m-%d %H:%M:%S %z")
#                self.new_hosts[alert["labels"]["job"]].duration = HumanReadableDurationFromSeconds(alert["state_duration"])
#                self.new_hosts[alert["labels"]["job"]].attempt = alert["current_check_attempt"]+ "/" + alert["max_check_attempts"]
#                self.new_hosts[alert["labels"]["job"]].status_information = alert["value"].replace("\n", " ")

#                # if host is in downtime add it to known maintained hosts
#                if alert['downtime'] != "0":
#                    self.new_hosts[alert["labels"]["job"]].scheduled_downtime = True
#                #if host.has_key("acknowledged"):
#                if 'acknowledged' in host:
#                    self.new_hosts[alert["labels"]["job"]].acknowledged = True
#                #if host.has_key("flapping"):
#                if 'flapping' in host:
#                    self.new_hosts[alert["labels"]["job"]].flapping = True

                #services
                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]] = PrometheusService()
                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].host = str(alert["labels"]["job"])
                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].name = services[alert["labels"]["alertname"]]
                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].server = self.name

                # states come in lower case from Opsview
                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].status = services[alert["severity"]].upper()
#                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].status_type = service["state_type"]
#                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].last_check = datetime.fromtimestamp(int(service["last_check"])).strftime("%Y-%m-%d %H:%M:%S %z")
#                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].duration = HumanReadableDurationFromSeconds(service["state_duration"])
#                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].attempt = service["current_check_attempt"]+ "/" + service["max_check_attempts"]
                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].status_information = service[alert["value"]].replace("\n", " ")
#                if service['downtime'] != '0':
#                    self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].scheduled_downtime = True
#                #if service.has_key("acknowledged"):
#                if 'acknowledged' in service:
#                    self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].acknowledged = True
#                #f service.has_key("flapping"):
#                if 'flapping' in service:
#                    self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].flapping = True
#                # extra opsview id for service, needed for submitting check results
#                self.new_hosts[alert["labels"]["job"]].services[alert["labels"]["alertname"]].service_object_id = service["service_object_id"]

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()


    def open_monitor_webpage(self, host, service):
        webbrowser_open('%s' % (self.monitor_url))
