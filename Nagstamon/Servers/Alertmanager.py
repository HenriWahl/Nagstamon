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
#   [1.1.0] - 2021-05-18:
#     * changed:
#         Using logging module for all outputs
#         Some refactoring for testing support
#     * added:
#         Initial tests based on unittest and pylint (see tests/test_Alertmanager.py)
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
import json
import re
import time

from datetime import datetime, timedelta, timezone
import logging
import dateutil.parser
import requests

from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost, Result)
from Nagstamon.Servers.Prometheus import PrometheusServer, PrometheusService
from Nagstamon.Helpers import webbrowser_open

# logging --------------------------------------------
log = logging.getLogger('Alertmanager.py')
handler = logging.StreamHandler(sys.stdout)
if conf.debug_mode is True:
    log_level = logging.DEBUG
    handler.setLevel(logging.DEBUG)
else:
    log_level = logging.INFO
    handler.setLevel(logging.INFO)
log.setLevel(log_level)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)
# ----------------------------------------------------


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
    MENU_ACTIONS = ['Monitor', 'Downtime', 'Acknowledge']
    BROWSER_URLS = {
        'monitor':  '$MONITOR$/#/alerts',
        'hosts':    '$MONITOR$/#/alerts',
        'services': '$MONITOR$/#/alerts',
        'history':  '$MONITOR$/#/alerts'
    }

    API_PATH_ALERTS = "/api/v2/alerts"
    API_PATH_SILENCES = "/api/v2/silences"
    API_FILTERS = '?filter='

    # vars specific to alertmanager class
    map_to_hostname = ''
    map_to_servicename = ''
    map_to_status_information = ''
    name = ''
    alertmanager_filter = ''

    @staticmethod
    def timestring_to_utc(timestring):
        local_time = datetime.now(timezone(timedelta(0))).astimezone().tzinfo
        parsed_time = dateutil.parser.parse(timestring)
        utc_time = parsed_time.replace(tzinfo=local_time).astimezone(timezone.utc)
        return utc_time.isoformat()


    def _detect_from_labels(self, labels, config_label_list, default_value="", list_delimiter=","):
        result = default_value
        for each_label in config_label_list.split(list_delimiter):
            if each_label in labels:
                result = labels.get(each_label)
                break
        return result


    def _process_alert(self, alert):
        result = {}

        # Alertmanager specific extensions
        generatorURL = alert.get("generatorURL", {})
        fingerprint = alert.get("fingerprint", {})
        log.debug("processing alert with fingerprint '%s':", fingerprint)

        labels = alert.get("labels", {})
        state = alert.get("status", {"state": "active"})["state"]
        severity = labels.get("severity", "UNKNOWN").upper()

        # skip alerts with none severity
        if severity == "NONE":
            log.debug("[%s]: detected detected state '%s' and severity '%s' from labels -> skipping alert", fingerprint, state, severity)
            return False
        log.debug("[%s]: detected detected state '%s' and severity '%s' from labels", fingerprint, state, severity)

        hostname = self._detect_from_labels(labels,self.map_to_hostname,"unknown")
        hostname = re.sub(':[0-9]+', '', hostname)        
        log.debug("[%s]: detected hostname from labels: '%s'", fingerprint, hostname)

        servicename = self._detect_from_labels(labels,self.map_to_servicename,"unknown")                
        log.debug("[%s]: detected servicename from labels: '%s'", fingerprint, servicename)

        if "status" in alert:
            attempt = alert["status"].get("state", "unknown")
        else:
            attempt = "unknown"

        if attempt == "suppressed":
            scheduled_downtime = True
            acknowledged = True
            log.debug("[%s]: detected status: '%s' -> interpreting as silenced", fingerprint, attempt)
        else:
            scheduled_downtime = False
            acknowledged = False
            log.debug("[%s]: detected status: '%s'", fingerprint, attempt)
        
        duration = str(self._get_duration(alert["startsAt"]))

        annotations = alert.get("annotations", {})
        status_information = self._detect_from_labels(annotations,self.map_to_status_information,'')
        
        result['host'] = str(hostname)
        result['name'] = servicename
        result['server'] = self.name
        result['status'] = severity
        result['labels'] = labels
        result['last_check'] = str(self._get_duration(alert["updatedAt"]))
        result['attempt'] = attempt
        result['scheduled_downtime'] = scheduled_downtime
        result['acknowledged'] = acknowledged
        result['duration'] = duration
        result['generatorURL'] = generatorURL
        result['fingerprint'] = fingerprint
        result['status_information'] = status_information

        return result


    def _get_status(self):
        """
        Get status from Alertmanager Server
        """
        
        log.debug("detection config (map_to_status_information): '%s'", self.map_to_status_information)
        log.debug("detection config (map_to_hostname): '%s'", self.map_to_hostname)
        log.debug("detection config (map_to_servicename): '%s'", self.map_to_servicename)
        log.debug("detection config (alertmanager_filter): '%s'", self.alertmanager_filter)

        # get all alerts from the API server
        try:
            if self.alertmanager_filter != '':
                result = self.FetchURL(self.monitor_url + self.API_PATH_ALERTS + self.API_FILTERS
                                        + self.alertmanager_filter, giveback="raw")
            else:
                result = self.FetchURL(self.monitor_url + self.API_PATH_ALERTS,
                                       giveback="raw")
            
            if result.status_code == 200:
                log.debug("received status code '%s' with this content in result.result: \n\
-----------------------------------------------------------------------------------------------------------------------------\n\
%s\
-----------------------------------------------------------------------------------------------------------------------------", result.status_code, result.result)
            else:
                log.error("received status code '%s'", result.status_code)
            # when result is not JSON catch it
            try:
                data = json.loads(result.result)
            except json.decoder.JSONDecodeError:
                data = ''
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not False:
                return(errors_occured)

            for alert in data:
                alert_data = self._process_alert(alert)
                if not alert_data:
                    break

                service = PrometheusService()
                service.host = alert_data['host']
                service.name = alert_data['name']
                service.server = alert_data['server']
                service.status = alert_data['status']
                service.labels = alert_data['labels']
                service.scheduled_downtime = alert_data['scheduled_downtime']
                service.acknowledged = alert_data['acknowledged']
                service.last_check = alert_data['last_check']
                service.attempt = alert_data['attempt']
                service.duration = alert_data['duration']

                service.generatorURL = alert_data['generatorURL']
                service.fingerprint = alert_data['fingerprint']

                service.status_information = alert_data['status_information']

                if service.host not in self.new_hosts:
                    self.new_hosts[service.host] = GenericHost()
                    self.new_hosts[service.host].name = str(service.host)
                    self.new_hosts[service.host].server = self.name
                self.new_hosts[service.host].services[service.name] = service

        except Exception as e:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            log.exception(e)
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

        # Convert local dates to UTC
        start_time_dt = self.timestring_to_utc(start_time) 
        end_time_dt = self.timestring_to_utc(end_time)

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


    # Overwrite function from generic server to add expire_time value
    def set_acknowledge(self, info_dict):
        '''
            different monitors might have different implementations of _set_acknowledge
        '''
        if info_dict['acknowledge_all_services'] is True:
            all_services = info_dict['all_services']
        else:
            all_services = []

        # Make sure expire_time is set
        #if not info_dict['expire_time']:
        #    info_dict['expire_time'] = None

        self._set_acknowledge(info_dict['host'],
                              info_dict['service'],
                              info_dict['author'],
                              info_dict['comment'],
                              info_dict['sticky'],
                              info_dict['notify'],
                              info_dict['persistent'],
                              all_services,
                              info_dict['expire_time'])


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[], expire_time=None):
        alert = self.hosts[host].services[service]
        endsAt = self.timestring_to_utc(expire_time)

        cgi_data = {}
        cgi_data["matchers"] = []
        for name, value in alert.labels.items():
            cgi_data["matchers"].append({
                "name": name,
                "value": value,
                "isRegex": False
            })
        cgi_data["startsAt"] = datetime.utcfromtimestamp(time.time()).isoformat()
        cgi_data["endsAt"] = endsAt or cgi_data["startAt"]
        cgi_data["comment"] = comment or "Nagstamon silence"
        cgi_data["createdBy"] = author or "Nagstamon"
        cgi_data = json.dumps(cgi_data)

        result = self.FetchURL(self.monitor_url + self.API_PATH_SILENCES, giveback="raw", cgi_data=cgi_data)
        return result
