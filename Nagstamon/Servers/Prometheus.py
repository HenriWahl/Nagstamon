# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2020 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

from datetime import datetime, timedelta, timezone
import dateutil.parser

from ast import literal_eval

from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Helpers import (HumanReadableDurationFromSeconds,
                               webbrowser_open)

class PrometheusService(GenericService):
    """
	    add Prometheus specific service property to generic service class
    """
    service_object_id = ""


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


    def _get_duration(self, timestring):
        """
            calculates the duration (delta) from Prometheus' activeAt (ISO8601 format) until now
            an returns a human friendly string
        """
        time_object = dateutil.parser.parse(timestring)
        duration = datetime.now(timezone.utc) - time_object
        h = int(duration.seconds / 3600)
        m = int(duration.seconds % 3600 / 60)
        s = int(duration.seconds % 60)
        if duration.days > 0:
            return "%sd %sh %02dm %02ds" % (duration.days, h, m, s)
        elif h > 0:
            return "%sh %02dm %02ds" % (h, m, s)
        elif m > 0:
            return "%02dm %02ds" % (m, s)
        else:
            return "%02ds" % (s)


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

            for alert in data["data"]["alerts"]:
                if conf.debug_mode:
                    self.Debug(server=self.get_name(), debug="Processing Alert: " + pprint.pformat(alert))

                if alert["labels"]["severity"] != "none":
                    if "pod_name" in alert["labels"]:
                        hostname = alert["labels"]["pod_name"]
                    elif "namespace" in alert["labels"]:
                        hostname = alert["labels"]["namespace"]
                    else:
                        hostname = "unknown"

                    self.new_hosts[hostname] = GenericHost()
                    self.new_hosts[hostname].name = str(hostname)
                    self.new_hosts[hostname].server = self.name

                    if "alertname" in alert["labels"]:
                        servicename = alert["labels"]["alertname"]
                    else:
                        servicename = "unknown"

                    self.new_hosts[hostname].services[servicename] = PrometheusService()
                    self.new_hosts[hostname].services[servicename].host = str(hostname)
                    self.new_hosts[hostname].services[servicename].name = servicename
                    self.new_hosts[hostname].services[servicename].server = self.name

                    self.new_hosts[hostname].services[servicename].status = alert["labels"]["severity"].upper()
                    self.new_hosts[hostname].services[servicename].last_check = "n/a"
                    self.new_hosts[hostname].services[servicename].attempt = alert["state"].upper()
                    self.new_hosts[hostname].services[servicename].duration = str(self._get_duration(alert["activeAt"]))
                    self.new_hosts[hostname].services[servicename].status_information = alert["annotations"]["message"].replace("\n", " ")

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()


    def open_monitor_webpage(self, host, service):
        webbrowser_open('%s' % (self.monitor_url))
