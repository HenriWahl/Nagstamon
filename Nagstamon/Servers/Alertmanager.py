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
# This Server class connects against Prometheus' Alertmanager.
# The monitor URL in the setup should be something like
# http://alertmanager.example.com
#
# Release Notes:
#
#   [1.0.1] - 2020-11-27:
#     * added:
#         Support for hiding suppressed alerts with the scheduled downtime filter
#
#   [1.0.0] - 2020-11-08:
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
from Nagstamon.Servers.Prometheus import PrometheusServer,PrometheusService
from Nagstamon.Helpers import webbrowser_open


class AlertmanagerService(PrometheusService):
    """
    add Alertmanager specific service property to generic service class
    """
    service_object_id = ""


class AlertmanagerServer(PrometheusServer):
    """
    special treatment for Alertmanager API
    """
    TYPE = 'Alertmanager'

    # Alertmanager actions are limited to visiting the monitor for now
    MENU_ACTIONS = ['Monitor']
    BROWSER_URLS = {
        'monitor':  '$MONITOR$/#/alerts',
        'hosts':    '$MONITOR$/#/alerts',
        'services': '$MONITOR$/#/alerts',
        'history':  '$MONITOR$/#/alerts'
    }

    API_PATH_ALERTS = "/api/v2/alerts"

    def _get_status(self):
        """
        Get status from Alertmanager Server
        """
        # get all alerts from the API server
        try:
            result = self.FetchURL(self.monitor_url + self.API_PATH_ALERTS,
                                   giveback="raw")
            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not False:
                return(errors_occured)

            if conf.debug_mode:
                self.Debug(server=self.get_name(),
                           debug="Fetched JSON: " + pprint.pformat(data))

            for alert in data:
                if conf.debug_mode:
                    self.Debug(
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
                service.last_check = str(self._get_duration(alert["updatedAt"]))

                if "status" in alert:
                    service.attempt = alert["status"].get("state", "unknown")
                else:
                    service.attempt = "unknown"

                if service.attempt == "suppressed":
                    service.scheduled_downtime = True
                
                service.duration = str(self._get_duration(alert["startsAt"]))

                # Alertmanager specific extensions
                service.generatorURL = alert.get("generatorURL", {})
                service.fingerprint = alert.get("fingerprint", {})

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
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

    def open_monitor(self, host, service=''):
        """
        open monitor for alert
        """
        url = self.monitor_url
        webbrowser_open(url)


    def _set_downtime(self, host, service, author, comment, fixed, start_time,
                      end_time, hours, minutes):
        """
        to be implemented in a future release
        """
        pass
