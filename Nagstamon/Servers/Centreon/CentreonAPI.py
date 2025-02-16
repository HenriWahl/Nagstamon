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

import traceback
import urllib.request
import urllib.parse
import urllib.error
import sys
# API V2
import pprint
import json
import requests

from datetime import datetime, timedelta

from Nagstamon.Objects import *
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Config import conf
from Nagstamon.Helpers import webbrowser_open


# This class support Centreon V2 API
# Things to do :
#  - BROWSER_URLS -> move into define_url() to be consistent

class CentreonServer(GenericServer):

    def __init__(self, **kwds):

        GenericServer.__init__(self, **kwds)

        self.TYPE = 'Centreon'

        # Centreon API uses a token
        self.token = None

        # HARD/SOFT state mapping
        self.HARD_SOFT = {'(H)': 'hard', '(S)': 'soft'}

        # Entries for monitor default actions in context menu
        # Removed Monitor, as I don’t know a way to show directly the service
        #  or host details page, so i show the main ressource page
        # self.MENU_ACTIONS = ['Monitor', 'Recheck', 'Acknowledge', 'Submit check result', 'Downtime']
        self.MENU_ACTIONS = ['Recheck', 'Acknowledge', 'Downtime']

        # URLs of the Centreon pages
        self.urls_centreon = None

        # limit number of services retrived
        self.limit_services_number = 9999

    def init_config(self):
        '''
        init_config, called at thread start
        '''
        # Version check
        result = self.fetch_url(f'{self.monitor_cgi_url}/api/latest/platform/versions', no_auth=True, giveback='raw')

        data = json.loads(result.result)
        error = result.error
        status_code = result.status_code

        # check if any error occured
        errors_occured = self.check_for_error(data, error, status_code)
        if errors_occured is not None:
            return (errors_occured)

        self.centreon_version_major = int(data["web"]["major"])
        self.centreon_version_minor = int(data["web"]["minor"])
        if conf.debug_mode is True:
            self.debug(server='[' + self.get_name() + ']', debug='Centreon version detected : ' + str(self.centreon_version_major) + '.' + str(self.centreon_version_minor))

        if self.centreon_version_major >= 21:
            # URLs for browser shortlinks/buttons on popup window
            self.BROWSER_URLS = {'monitor': '$MONITOR$/monitoring/resources',
                                 'hosts': '$MONITOR$/monitoring/resources',
                                 'services': '$MONITOR$/monitoring/resources',
                                 'history': '$MONITOR$/main.php?p=20301'}
            # RestAPI version
            if self.centreon_version_major == 21:
                self.restapi_version = "latest"
            elif self.centreon_version_major == 22:
                self.restapi_version = "v22.04"
            elif self.centreon_version_major == 23 and self.centreon_version_minor == 4:
                self.restapi_version = "v23.04"
            elif self.centreon_version_major == 23 and self.centreon_version_minor == 10:
                self.restapi_version = "v23.10"
            elif self.centreon_version_major == 24:
                self.restapi_version = "v24.04"
            else:
                self.restapi_version = "v24.04"
            if conf.debug_mode is True:
                self.debug(server='[' + self.get_name() + ']', debug='Centreon API version used : ' + self.restapi_version)

        else:
            if conf.debug_mode is True:
                self.debug(server='[' + self.get_name() + ']', debug='Unsupported Centreon version, must be >= 21')

        # Changed this because define_url was called 2 times
        if not self.tls_error and self.urls_centreon is None:
            self.define_url()

    def init_HTTP(self):
        GenericServer.init_HTTP(self)
        if self.session is None:
            self.session.headers.update({'Content-Type': 'application/json'})
            self.token = self.get_token().result

    def define_url(self):
        urls_centreon_api_v2 = {
            'resources': self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/resources',
            'login': self.monitor_cgi_url + '/api/' + self.restapi_version + '/login',
            'services': self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/resources',
            'hosts': self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/resources'
        }

        self.urls_centreon = urls_centreon_api_v2

    def open_monitor(self, host, service=''):
        # Used for self.MENU_ACTIONS = ['Monitor']
        # Autologin seems deprecated as admin must enable it globaly and use the old pages
        # Ex : http://10.66.113.52/centreon/main.php?autologin=1&useralias=admin&token=xxxxxx
        # if self.use_autologin is True:
        #     auth = '&autologin=1&useralias=' + self.username + '&token=' + self.autologin_key
        # else:
        #     auth = ''
        # webbrowser_open(self.urls_centreon['resources'] + auth )
        webbrowser_open(self.monitor_cgi_url)

    def get_token(self):
        try:
            cgi_data = {
                "security": {
                    "credentials": {
                        "login": self.username,
                        "password": self.password
                    }
                }
            }

            # Post json
            json_string = json.dumps(cgi_data)
            result = self.fetch_url(self.urls_centreon['login'], cgi_data=json_string, giveback='raw')

            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="Fetched JSON: " + pprint.pformat(data))

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not None:
                return (errors_occured)

            token = data["security"]["token"]
            # ID of the user is needed by some requests
            user_id = data["contact"]["id"]

            if conf.debug_mode:
                self.debug(server='[' + self.get_name() + ']',
                           debug='API login : ' + self.username + ' / ' + self.password + ' > Token : ' + token + ' > User ID : ' + str(
                               user_id))

            self.user_id = user_id
            self.session.headers.update({'X-Auth-Token': token})
            return Result(result=token)

        except:
            traceback.print_exc(file=sys.stdout)
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

    def get_host(self, host):
        # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
        url_hosts = self.urls_centreon['hosts'] + '?types=["host"]&search={"h.name":"' + host + '"}'

        try:
            # Get json
            result = self.fetch_url(url_hosts, giveback='raw')

            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not None:
                return (errors_occured)

            fqdn = str(data["result"][0]["fqdn"])

            if conf.debug_mode:
                self.debug(server='[' + self.get_name() + ']',
                           debug='Get Host FQDN or address : ' + host + " / " + fqdn)

            # Give back host or ip
            return Result(result=fqdn)

        except:
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

    def get_host_and_service_id(self, host, service=''):
        if service == "":
            # Hosts only
            # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
            url_hosts = self.urls_centreon['hosts'] + '?types=["host"]&search={"h.name":"' + host + '"}'

            try:
                # Get json
                result = self.fetch_url(url_hosts, giveback='raw')

                data = json.loads(result.result)
                error = result.error
                status_code = result.status_code

                # check if any error occured
                errors_occured = self.check_for_error(data, error, status_code)
                if errors_occured is not None:
                    return (errors_occured)

                host_id = data["result"][0]["id"]

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']', debug='Get Host ID : ' + host + " / " + str(host_id))
                return host_id

            except:
                traceback.print_exc(file=sys.stdout)
                # set checking flag back to False
                self.isChecking = False
                result, error = self.error(sys.exc_info())
                return Result(result=result, error=error)
        else:
            # Host + Service
            if host == "Meta_Services":
                url_service = self.urls_centreon[
                                  'services'] + '?types=["metaservice"]&search={"s.name":"' + service + '"}'
            else:
                url_service = self.urls_centreon[
                                  'services'] + '?types=["service"]&search={"$and":[{"h.name":{"$eq":"' + host + '"}}, {"s.description":{"$eq":"' + service + '"}}]}'

            try:
                # Get json
                result = self.fetch_url(url_service, giveback='raw')

                data = json.loads(result.result)
                error = result.error
                status_code = result.status_code

                # check if any error occured
                errors_occured = self.check_for_error(data, error, status_code)
                if errors_occured is not None:
                    return (errors_occured)

                if host == "Meta_Services":
                    host_id = 0
                else:
                    host_id = data["result"][0]["parent"]["id"]
                service_id = data["result"][0]["id"]

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']',
                               debug='Get Host / Service ID : ' + str(host_id) + " / " + str(service_id))
                return host_id, service_id

            except:
                traceback.print_exc(file=sys.stdout)
                # set checking flag back to False
                self.isChecking = False
                result, error = self.error(sys.exc_info())
                return Result(result=result, error=error)

    def get_start_end(self, host):
        # I don’t know how to get this info...
        # self.defaults_downtime_duration_hours = 2
        # self.defaults_downtime_duration_minutes = 0
        start = datetime.now()
        end = datetime.now() + timedelta(hours=2)

        return (str(start.strftime('%Y-%m-%d %H:%M')),
                str(end.strftime('%Y-%m-%d %H:%M')))

    def _get_status(self):
        '''
        Get status from Centreon Server
        '''
        # Be sure that the session is still active
        result = self.check_session()
        if result is not None:
            if result.result == 'ERROR':
                if 'urls_centreon' in result.error:
                    result.error = 'Connection error'
                return result

        # filter regexep to reduce network traffic
        # waiting to find a solution to reverse regexp
        # my first idea is 
        # begin by (^(?!(.*
        # ending by )))
        # replace | by )))(^(?!(.*
        # replace )( by )|(
        self.re_service_filter = ''
        self.re_host_filter = ''
        if conf.re_service_enabled is True and conf.re_service_reverse is True:
            self.re_service_filter = '&search={"s.description":{"$rg":"' + str(conf.re_service_pattern) + '"}}'
        if conf.re_host_enabled is True and conf.re_host_reverse is True:
            self.re_host_filter = '&search={"h.name":{"$rg":"' + str(conf.re_host_pattern) + '"}}'
        
        # Services URL
        # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["service"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
        url_services = self.urls_centreon[
                           'services'] + '?types=["metaservice","service"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]' + self.re_service_filter + '&limit=' + str(
            self.limit_services_number)

        # Hosts URL
        # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
        url_hosts = self.urls_centreon[
                        'hosts'] + '?types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]' + self.re_host_filter + '&limit=' + str(
            self.limit_services_number)

        # Hosts
        try:
            # Get json
            result = self.fetch_url(url_hosts, giveback='raw')

            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not None:
                return (errors_occured)

            if data["meta"]["total"] == 0:
                self.debug(server='[' + self.get_name() + ']', debug='No host down')
            else:
                for alerts in data["result"]:
                    new_host = alerts["name"]
                    self.new_hosts[new_host] = GenericHost()
                    self.new_hosts[new_host].name = alerts["name"]
                    self.new_hosts[new_host].server = self.name
                    # API inconsistency, even by fixing exact version number, changed starting with 22.04
                    if self.centreon_version_major == 21 or (self.centreon_version_major == 22 and self.centreon_version_minor == 4):
                        self.new_hosts[new_host].criticality = alerts["severity_level"]
                    else:
                        self.new_hosts[new_host].criticality = alerts["severity"]
                    self.new_hosts[new_host].status = alerts["status"]["name"]
                    self.new_hosts[new_host].last_check = alerts["last_check"]
                    # last_state_change = datetime.strptime(alerts["last_status_change"], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None)
                    self.new_hosts[new_host].duration = alerts["duration"]
                    self.new_hosts[new_host].attempt = alerts["tries"]
                    self.new_hosts[new_host].status_information = alerts["information"]
                    # Change starting with 23.10
                    if (self.centreon_version_major >= 23 and self.centreon_version_minor >= 10) or self.centreon_version_major > 23:
                        self.new_hosts[new_host].passiveonly = alerts["has_passive_checks_enabled"]
                        self.new_hosts[new_host].notifications_disabled = not alerts["is_notification_enabled"]
                        self.new_hosts[new_host].acknowledged = alerts["is_acknowledged"]
                        self.new_hosts[new_host].scheduled_downtime = alerts["is_in_downtime"]
                    else:
                        self.new_hosts[new_host].passiveonly = alerts["passive_checks"]
                        self.new_hosts[new_host].notifications_disabled  = not alerts["notification_enabled"]
                        self.new_hosts[new_host].acknowledged = alerts["acknowledged"]
                        self.new_hosts[new_host].scheduled_downtime = alerts["in_downtime"]
                    # avoid crash if flapping is not configured in Centreon
                    # according to https://github.com/HenriWahl/Nagstamon/issues/866#issuecomment-1302257034
                    self.new_hosts[new_host].flapping = alerts.get("flapping", False)
                    if "(S)" in alerts["tries"]:
                        self.new_hosts[new_host].status_type = self.HARD_SOFT['(S)']
                    else:
                        self.new_hosts[new_host].status_type = self.HARD_SOFT['(H)']
                    self.debug(server='[' + self.get_name() + ']', debug='Host indexed : ' + new_host)

        except:
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # Services
        try:
            # Get json
            result = self.fetch_url(url_services, giveback='raw')

            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not None:
                return (errors_occured)

            if data["meta"]["total"] == 0:
                self.debug(server='[' + self.get_name() + ']', debug='No service down')
            else:
                for alerts in data["result"]:
                    if alerts["type"] == "metaservice":
                        new_host = "Meta_Services"
                    else:
                        new_host = alerts["parent"]["name"]
                    new_service = alerts["name"]
                    # Needed if non-ok services are on a UP host
                    if not new_host in self.new_hosts:
                        self.new_hosts[new_host] = GenericHost()
                        self.new_hosts[new_host].name = new_host
                        self.new_hosts[new_host].status = 'UP'
                    self.new_hosts[new_host].services[new_service] = GenericService()
                    # Attributs à remplir
                    self.debug(server='[' + self.get_name() + ']',
                               debug='Service indexed : ' + new_host + ' / ' + new_service)

                    self.new_hosts[new_host].services[new_service].server = self.name
                    self.new_hosts[new_host].services[new_service].host = new_host
                    self.new_hosts[new_host].services[new_service].name = new_service
                    self.new_hosts[new_host].services[new_service].status = alerts["status"]["name"]
                    self.new_hosts[new_host].services[new_service].last_check = alerts["last_check"]
                    # last_state_change = datetime.strptime(alerts["last_state_change"], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None)
                    # self.new_hosts[new_host].services[new_service].duration = datetime.now() - last_state_change
                    self.new_hosts[new_host].services[new_service].duration = alerts["duration"]
                    self.new_hosts[new_host].services[new_service].attempt = alerts["tries"]
                    self.new_hosts[new_host].services[new_service].status_information = alerts["information"]
                    # Change starting with 23.10
                    if (self.centreon_version_major >= 23 and self.centreon_version_minor >= 10) or self.centreon_version_major > 23:
                        self.new_hosts[new_host].services[new_service].passiveonly = alerts["has_passive_checks_enabled"]
                        self.new_hosts[new_host].services[new_service].notifications_disabled = not alerts["is_notification_enabled"]
                        self.new_hosts[new_host].services[new_service].acknowledged = alerts["is_acknowledged"]
                        self.new_hosts[new_host].services[new_service].scheduled_downtime = alerts["is_in_downtime"]
                    else:
                        self.new_hosts[new_host].services[new_service].passiveonly = alerts["passive_checks"]
                        self.new_hosts[new_host].services[new_service].notifications_disabled = not alerts["notification_enabled"]
                        self.new_hosts[new_host].services[new_service].acknowledged = alerts["acknowledged"]
                        self.new_hosts[new_host].services[new_service].scheduled_downtime = alerts["in_downtime"]
                    # avoid crash if flapping is not configured in Centreon
                    # according to https://github.com/HenriWahl/Nagstamon/issues/866#issuecomment-1302257034
                    self.new_hosts[new_host].services[new_service].flapping = alerts.get("flapping", False)
                    if "(S)" in alerts["tries"]:
                        self.new_hosts[new_host].services[new_service].status_type = self.HARD_SOFT['(S)']
                    else:
                        self.new_hosts[new_host].services[new_service].status_type = self.HARD_SOFT['(H)']
                    # API inconsistency, even by fixing exact version number, changed starting with 22.04
                    if self.centreon_version_major == 21 or (self.centreon_version_major == 22 and self.centreon_version_minor == 4):
                        self.new_hosts[new_host].services[new_service].criticality = alerts["severity_level"]
                    else:
                        self.new_hosts[new_host].services[new_service].criticality = alerts["severity"]

        except:
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # return True if all worked well
        return Result()

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None):
        try:

            acknowledgements = {
                "acknowledgement": {
                    "comment": comment,
                    "with_services": True,
                    "is_notify_contacts": notify,
                    "is_persistent_comment": persistent,
                    "is_sticky": sticky
                },
                "resources": [
                ]
            }

            # host
            if service == '':
                host_id = self.get_host_and_service_id(host)
                if self.centreon_version_major >= 24:
                    new_resource = {
                        "type": "host",
                        "id": host_id,
                        "parent": {
                            "id": host_id
                        }
                    }
                else:
                    new_resource = {
                        "type": "host",
                        "id": host_id,
                        "parent": {
                            "id": None
                        }
                    }

                acknowledgements["resources"].append(new_resource)

                # Post json
                json_string = json.dumps(acknowledgements)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/hosts/{host_id}/acknowledgements
                result = self.fetch_url(self.urls_centreon['resources'] + '/acknowledge', cgi_data=json_string,
                                        giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']',
                               debug="Set Ack on Host, status code : " + str(status_code))

            # Service
            if service != '' or all_services:
                if not all_services:
                    all_services = [service]

                for s in all_services:
                    host_id, service_id = self.get_host_and_service_id(host, service)

                    if host == "Meta_Services":
                        new_resource = {
                            "type": "metaservice",
                            "id": service_id,
                            "parent": {
                                "id": None
                            }
                        }

                    else:
                        new_resource = {
                            "type": "service",
                            "id": service_id,
                            "parent": {
                                "id": host_id
                            }
                        }

                    acknowledgements["resources"].append(new_resource)
                    if conf.debug_mode:
                        self.debug(server='[' + self.get_name() + ']',
                                   debug="Stack ack for Host (" + host + ") / Service (" + service + ")")

                # Post json
                json_string = json.dumps(acknowledgements)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/services/acknowledgements
                result = self.fetch_url(self.urls_centreon['resources'] + '/acknowledge', cgi_data=json_string,
                                        giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']',
                               debug="Set Acks, status code : " + str(status_code))

        except:
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

    def _set_recheck(self, host, service):
        rechecks = {
            "resources": [
            ]
        }

        # This new parameter was added in 23.04
        if self.centreon_version_major >= 23:
            property_to_add = {
                "check": {
                    "is_forced": True
                }
            }
            rechecks.update(property_to_add)

        try:
            # Host
            if service == '':
                host_id = self.get_host_and_service_id(host)

                new_resource = {
                    "type": "host",
                    "id": host_id,
                    "parent": None
                }

                rechecks["resources"].append(new_resource)

                # Post json
                json_string = json.dumps(rechecks)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/resources/check
                result = self.fetch_url(self.urls_centreon['resources'] + '/check', cgi_data=json_string, giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']',
                               debug="Recheck on Host : " + host + ", status code : " + str(status_code))

            # Service
            else:
                host_id, service_id = self.get_host_and_service_id(host, service)

                if host == "Meta_Services":
                    new_resource = {
                        "type": "metaservice",
                        "id": service_id,
                        "parent": None
                    }

                else:
                    new_resource = {
                        "type": "service",
                        "id": service_id,
                        "parent": {
                            "id": host_id
                        }
                    }

                rechecks["resources"].append(new_resource)

                # Post json
                json_string = json.dumps(rechecks)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/resources/check
                result = self.fetch_url(self.urls_centreon['resources'] + '/check', cgi_data=json_string, giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']',
                               debug="Reckeck on Host (" + host + ") / Service (" + service + "), status code : " + str(
                                   status_code))

        except:
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        obj_start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M')
        obj_end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M')

        # Nagstamon don’t provide the TZ, we need to get it from the OS
        obj_start_time = obj_start_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
        obj_end_time = obj_end_time.replace(tzinfo=datetime.now().astimezone().tzinfo)

        # duration unit is second
        duration = (hours * 3600) + (minutes * 60)

        #  API require boolean
        if fixed == 1:
            fixed = True
        else:
            fixed = False

        downtimes = {
            "downtime": {
                "comment": comment,
                "with_services": True,
                "is_fixed": fixed,
                "duration": duration,
                "start_time": obj_start_time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                "end_time": obj_end_time.strftime('%Y-%m-%dT%H:%M:%S%z')
            },
            "resources": [
            ]
        }

        try:
            if service == '':
                # Host
                host_id = self.get_host_and_service_id(host)

                new_resource = {
                    "type": "host",
                    "id": host_id,
                    "parent": None
                }

                downtimes["resources"].append(new_resource)

                # Post json
                json_string = json.dumps(downtimes)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/resources/downtime
                result = self.fetch_url(self.urls_centreon['resources'] + '/downtime', cgi_data=json_string,
                                        giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']',
                               debug="Downtime on Host : " + host + ", status code : " + str(status_code))

            # Service
            else:
                host_id, service_id = self.get_host_and_service_id(host, service)

                if host == "Meta_Services":
                    new_resource = {
                        "type": "metaservice",
                        "id": service_id,
                        "parent": {
                            "id": None
                        }
                    }

                else:
                    new_resource = {
                        "type": "service",
                        "id": service_id,
                        "parent": {
                            "id": host_id
                        }
                    }

                downtimes["resources"].append(new_resource)

                # Post json
                json_string = json.dumps(downtimes)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/resources/downtime
                result = self.fetch_url(self.urls_centreon['resources'] + '/downtime', cgi_data=json_string,
                                        giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']',
                               debug="Downtime on Host (" + host + ") / Service (" + service + "), status code : " + str(
                                   status_code))


        except:
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

    def check_session(self):
        if conf.debug_mode:
            self.debug(server='[' + self.get_name() + ']', debug='Checking session status')

        try:
            if conf.debug_mode:
                self.debug(server='[' + self.get_name() + ']',
                           debug='Check-session, the token expire if not been used for more than one hour. Current Token = ' + str(
                               self.token))

            cgi_data = {'limit': '0'}
            # Get en empty service list, to check the status of the current token
            # This request must be done in a GET, so just encode the parameters and fetch
            result = self.fetch_url(self.urls_centreon['resources'] + '?' + urllib.parse.urlencode(cgi_data),
                                    giveback="raw")

           # If we got an 403 or 401 (and 500 for version 21.), the token expired and must be renewed
            if self.centreon_version_major == 21:
                ressources_response_list = [401, 403, 500]
            else:
                ressources_response_list = [401, 403]

            if result.status_code in ressources_response_list:
                self.token = self.get_token().result
                if conf.debug_mode:
                    self.debug(server='[' + self.get_name() + ']', debug='Check-session, session renewed')
                result = self.fetch_url(self.urls_centreon['resources'] + '?' + urllib.parse.urlencode(cgi_data),
                                        giveback="raw")
            if not 'ConnectTimeoutError' in result.error and \
                    not 'NewConnectionError' in result.error:
                data = json.loads(result.result)
                error = result.error
                status_code = result.status_code
            else:
                return Result(result='ERROR',
                              error='Connection error')

            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="Check-session, Fetched JSON: " + pprint.pformat(data))
                self.debug(server=self.get_name(),
                           debug="Check-session, Error : " + error + ", Status code : " + str(status_code))

        except:
            traceback.print_exc(file=sys.stdout)
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)
