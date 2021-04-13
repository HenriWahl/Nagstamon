# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2021 Henri Wahl <henri@nagstamon.de> et al.
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
#   [1.0.2] - 2021-04-10:
#     * added:
#         Better debug output
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
import requests

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
    MENU_ACTIONS = ['Monitor', 'Downtime']
    BROWSER_URLS = {
        'monitor':  '$MONITOR$/#/alerts',
        'hosts':    '$MONITOR$/#/alerts',
        'services': '$MONITOR$/#/alerts',
        'history':  '$MONITOR$/#/alerts'
    }

    API_PATH_ALERTS = "/api/v2/alerts"
    API_PATH_SILENCES = "/api/v2/silences"

    def _get_status(self):
        """
        Get status from Alertmanager Server
        """
        if conf.debug_mode:
            self.Debug(server=self.get_name(),debug="detection config (map_to_status_information): '" + str(self.map_to_status_information) + "'")
            self.Debug(server=self.get_name(),debug="detection config (map_to_hostname): '" + str(self.map_to_hostname) + "'")
            self.Debug(server=self.get_name(),debug="detection config (map_to_servicename): '" + str(self.map_to_servicename) + "'")

        # get all alerts from the API server
        try:
            result = self.FetchURL(self.monitor_url + self.API_PATH_ALERTS,
                                   giveback="raw")
            
            if conf.debug_mode:
                self.Debug(server=self.get_name(),debug="received status code '" + str(result.status_code) + "' with this content in result.result: \n\
-----------------------------------------------------------------------------------------------------------------------------\n\
" + result.result + "\
-----------------------------------------------------------------------------------------------------------------------------")

            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not False:
                return(errors_occured)

            for alert in data:
                if conf.debug_mode:
                    self.Debug(
                        server=self.get_name(),
                        debug="processing alert with fingerprint '" + alert['fingerprint'] + "':"
                    )

                labels = alert.get("labels", {})

                # skip alerts with none severity
                severity = labels.get("severity", "UNKNOWN").upper()

                if severity == "NONE":
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),debug="[" + alert['fingerprint'] + "]: detected severity from labels '" + severity + "' -> skipping alert")
                    continue

                if conf.debug_mode:
                    self.Debug(server=self.get_name(),debug="[" + alert['fingerprint'] + "]: detected severity from labels '" + severity + "'")

                hostname = "unknown"
                for host_label in self.map_to_hostname.split(','):
                    if host_label in labels:
                        hostname = labels.get(host_label)
                        break

                if conf.debug_mode:
                    self.Debug(server=self.get_name(),debug="[" + alert['fingerprint'] + "]: detected hostname from labels: '" + hostname + "'")

                servicename = "unknown"
                for service_label in self.map_to_servicename.split(','):
                    if service_label in labels:
                        servicename = labels.get(service_label)
                        break

                if conf.debug_mode:
                    self.Debug(server=self.get_name(),debug="[" + alert['fingerprint'] + "]: detected servicename from labels: '" + servicename + "'")

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
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),debug="[" + alert['fingerprint'] + "]: detected status: '" + service.attempt + "' -> interpreting as silenced")
                else:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),debug="[" + alert['fingerprint'] + "]: detected status: '" + service.attempt + "'")
                
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

        # Get local TZ
        LOCAL_TIMEZONE = datetime.now(timezone(timedelta(0))).astimezone().tzinfo

        # Convert local dates to UTC
        start_time_dt = dateutil.parser.parse(start_time).replace(tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc).isoformat()
        end_time_dt = dateutil.parser.parse(end_time).replace(tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc).isoformat()

        # API Spec: https://github.com/prometheus/alertmanager/blob/master/api/v2/openapi.yaml
        silence_data = {
            "matchers": [
                {
                    "name": "instance",
                    "value": host,
                    "isRegex": False,
                    "isEqual": False
                },
                {
                    "name": "alertname",
                    "value": service,
                    "isRegex": False,
                    "isEqual": False
                }
            ],
            "startsAt": start_time_dt,
            "endsAt": end_time_dt,
            "createdBy": author,
            "comment": comment
        }

        post = requests.post(self.monitor_url + self.API_PATH_SILENCES, json=silence_data)

        #silence_id = post.json()["silenceID"]