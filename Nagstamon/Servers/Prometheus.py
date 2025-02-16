# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
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
# http://prometheus.example.com:9090
#
# Release Notes:
#
#   [1.1.0] - 2020-06-12:
#     * fixed:
#         Some more errors with unset fields from Prometheus
#     * added:
#         Feature for configuring which labels get mapped to servicename and hostname...
#                          ...and which annotations get mapped to status_information
#
#   [1.0.2] - 2020-06-07:
#     * fixed:
#         Missing message field in alert stopped integration from working
#         Alerts with an unknown severity were not shown
#
#   [1.0.1] - 2020-05-13:
#     * fixed:
#         Nagstamon crashes due to missing url handling
#
#   [1.0.0] - 2020-04-20:
#     * added:
#         Inital version
#
import sys
import urllib.request
import urllib.parse
import urllib.error
import pprint
import json

from datetime import datetime, timedelta, timezone
import dateutil.parser

from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Helpers import webbrowser_open


class PrometheusService(GenericService):
    """
    add Prometheus specific service property to generic service class
    """
    service_object_id = ""
    labels = {}


class PrometheusServer(GenericServer):
    """
    special treatment for Prometheus API
    """
    TYPE = 'Prometheus'

    # Prometheus actions are limited to visiting the monitor for now
    MENU_ACTIONS = ['Monitor']
    BROWSER_URLS = {
        'monitor':  '$MONITOR$/alerts',
        'hosts':    '$MONITOR$/targets',
        'services': '$MONITOR$/service-discovery',
        'history':  '$MONITOR$/graph'
    }

    API_PATH_ALERTS = "/api/v1/alerts"

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

        return (str(start.strftime("%Y-%m-%d %H:%M:%S")),
                str(end.strftime("%Y-%m-%d %H:%M:%S")))

    def _get_duration(self, timestring):
        """
        calculates the duration (delta) from Prometheus' activeAt (ISO8601
        format) until now an returns a human friendly string
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

    def _set_downtime(self, host, service, author, comment, fixed, start_time,
                      end_time, hours, minutes):
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
            result = self.fetch_url(self.monitor_url + self.API_PATH_ALERTS,
                                    giveback="raw")
            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not None:
                return(errors_occured)

            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="Fetched JSON: " + pprint.pformat(data))

            for alert in data["data"]["alerts"]:
                if conf.debug_mode:
                    self.debug(
                        server=self.get_name(),
                        debug="Processing Alert: " + pprint.pformat(alert)
                    )

                labels = alert.get("labels", {})

                # skip alerts with none severity
                severity = labels.get("severity", "UNKNOWN").upper()
                if severity == "NONE":
                    continue

                hostname = "unknown"
                for host_label in self.map_to_hostname.split(','):
                    if host_label in labels:
                        hostname = labels.get(host_label)
                        break

                servicename = "unknown"
                for service_label in self.map_to_servicename.split(','):
                    if service_label in labels:
                        servicename = labels.get(service_label)
                        break

                service = PrometheusService()
                service.host = str(hostname)
                service.name = servicename
                service.server = self.name
                service.status = severity
                service.last_check = "n/a"
                service.attempt = alert.get("state", "firirng")
                service.duration = str(self._get_duration(alert["activeAt"]))

                annotations = alert.get("annotations", {})
                status_information = ""
                for status_information_label in self.map_to_status_information.split(','):
                    if status_information_label in annotations:
                        status_information = annotations.get(status_information_label)
                        break
                service.status_information = status_information

                if hostname not in self.new_hosts:
                    self.new_hosts[hostname] = GenericHost()
                    self.new_hosts[hostname].name = str(hostname)
                    self.new_hosts[hostname].server = self.name
                self.new_hosts[hostname].services[servicename] = service

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

    def open_monitor_webpage(self, host, service):
        """
        open monitor from tablewidget context menu
        """
        webbrowser_open('%s' % (self.monitor_url))

    def open_monitor(self, host, service=''):
        """
        open monitor for alert
        """
        url = '%s/graph?g0.range_input=1h&g0.expr=%s'
        url = url % (self.monitor_url,
                     urllib.parse.quote('ALERTS{alertname="%s"}' % service))
        webbrowser_open(url)
