# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2022 Henri Wahl <henri@nagstamon.de> et al.
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

import urllib.request
import urllib.parse
import urllib.error
import socket
import sys
import re
import copy
# API V2
import pprint
import json
import requests

from datetime import datetime, timedelta

from Nagstamon.Objects import *
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Config import conf
from Nagstamon.Helpers import webbrowser_open


class CentreonServer(GenericServer):
    TYPE = 'Centreon'

    # Centreon API uses a token
    token = None

    # HARD/SOFT state mapping
    HARD_SOFT = {'(H)': 'hard', '(S)': 'soft'}

    # Entries for monitor default actions in context menu
    MENU_ACTIONS = ['Monitor', 'Recheck', 'Acknowledge', 'Downtime']

    # URLs of the Centreon pages
    urls_centreon = None

    # limit number of services retrived
    limit_services_number = 9999

    def init_config(self):
        '''
        dummy init_config, called at thread start, not really needed here, just omit extra properties
        '''

        # FIX but be provided by user
        self.user_provided_centreon_version = "20.04"

        if re.search('2(0|1|2)\.(04|10)', self.user_provided_centreon_version):
            self.centreon_version = 20.04
            if conf.debug_mode is True:
                self.Debug(server='[' + self.get_name() + ']', debug='Centreon version selected : 20.04 <=> 22.04')
            # URLs for browser shortlinks/buttons on popup window
            self.BROWSER_URLS = {'monitor': '$MONITOR$/monitoring/resources',
            'hosts': '$MONITOR$/monitoring/resources',
            'services': '$MONITOR$/monitoring/resources',
            'history': '$MONITOR$/main.php?p=20301'}
            # RestAPI version
            self.restapi_version = "latest"

        else:
            if conf.debug_mode is True:
                self.Debug(server='[' + self.get_name() + ']', debug='No Centreon version provided')

        # set URLs here already
        # self.init_HTTP()

        # Changed this because define_url was called 2 times
        #if not self.tls_error and self.centreon_version is not None:
        if not self.tls_error and self.urls_centreon is None:
            self.define_url()


    def init_HTTP(self):
        if self.session is None:
            GenericServer.init_HTTP(self)
            self.session.headers.update({'Content-Type': 'application/json'})
            self.token = self.get_token().result


    def define_url(self):
        urls_centreon_api_v2 = {
            'main': self.monitor_cgi_url + '/monitoring/resources',
            'login': self.monitor_cgi_url + '/api/' + self.restapi_version + '/login',
            'services': self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/resources',
            'hosts': self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/resources'
        }

        if self.centreon_version == 20.04:
            self.urls_centreon = urls_centreon_api_v2
        if conf.debug_mode == True:
            self.Debug(server='[' + self.get_name() + ']', debug='URLs defined for Centreon %s' % (self.centreon_version))


    def open_monitor(self, host, service=''):
        if self.use_autologin is True:
            auth = '&autologin=1&useralias=' + self.username + '&token=' + self.autologin_key
        else:
            auth = ''

        webbrowser_open(self.urls_centreon['main'] + auth )


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
            result = self.FetchURL(self.monitor_cgi_url + '/api/' + self.restapi_version + '/login', cgi_data=json_string, giveback='raw')

            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            if conf.debug_mode:
                self.Debug(server=self.get_name(),
                           debug="Fetched JSON: " + pprint.pformat(data))


            # check if any error occured
            errors_occured = self.check_for_error(data, error, status_code)
            if errors_occured is not False:
                return(errors_occured)

            token = data["security"]["token"]
            # ID of the user is needed by some requests
            user_id = data["contact"]["id"]

            if conf.debug_mode == True:
                self.Debug(server='[' + self.get_name() + ']', debug='API login : ' + self.username + ' / ' + self.password + ' > Token : ' + token + ' > User ID : ' + str(user_id))

            self.user_id = user_id
            self.session.headers.update({'X-Auth-Token': token})
            return Result(result=token)

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


    def GetHost(self, host):
        if self.centreon_version == 20.04:
            # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
            url_hosts = self.urls_centreon['hosts'] + '?types=["host"]&search={"h.name":"' + host + '"}'

        try:
            if self.centreon_version == 20.04:
                # Get json
                result = self.FetchURL(url_hosts, giveback='raw')

                data = json.loads(result.result)
                error = result.error
                status_code = result.status_code

                # check if any error occured
                errors_occured = self.check_for_error(data, error, status_code)
                if errors_occured is not False:
                    return(errors_occured)

                fqdn = str(data["result"][0]["fqdn"])

                if conf.debug_mode == True:
                    self.Debug(server='[' + self.get_name() + ']', debug='Get Host FQDN or address : ' + host + " / " + fqdn)

                # Give back host or ip
                return Result(result=fqdn)

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


    def get_host_and_service_id(self, host, service=''):
        if service == "":
            # Hosts only
            if self.centreon_version == 20.04:
                # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
                url_hosts = self.urls_centreon['hosts'] + '?types=["host"]&search={"h.name":"' + host + '"}'

            try:
                if self.centreon_version == 20.04:
                    # Get json
                    result = self.FetchURL(url_hosts, giveback='raw')

                    data = json.loads(result.result)
                    error = result.error
                    status_code = result.status_code

                    # check if any error occured
                    errors_occured = self.check_for_error(data, error, status_code)
                    if errors_occured is not False:
                        return(errors_occured)

                    host_id = str(data["result"][0]["id"])

                    if conf.debug_mode == True:
                        self.Debug(server='[' + self.get_name() + ']', debug='Get Host ID : ' + host + " / " + host_id)
                    return host_id

            except:
                import traceback
                traceback.print_exc(file=sys.stdout)
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)
        else:
            # Host + Service
            if self.centreon_version == 20.04:
                url_service = self.urls_centreon['services'] + '?types=["service"]&search={"$and":[{"h.name":{"$eq":"'+host+'"}}, {"s.description":{"$eq":"'+service+'"}}]}'

            try:
                if self.centreon_version == 20.04:
                    # Get json
                    result = self.FetchURL(url_service, giveback='raw')

                    data = json.loads(result.result)
                    error = result.error
                    status_code = result.status_code

                    # check if any error occured
                    errors_occured = self.check_for_error(data, error, status_code)
                    if errors_occured is not False:
                        return(errors_occured)

                    host_id = str(data["result"][0]["parent"]["id"])
                    service_id = str(data["result"][0]["id"])

                    if conf.debug_mode == True:
                        self.Debug(server='[' + self.get_name() + ']', debug='Get Host / Service ID : ' + host_id + " / " + service_id)
                    return host_id,service_id

            except:
                import traceback
                traceback.print_exc(file=sys.stdout)
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)


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

        # Services URL
        if self.centreon_version == 20.04 :
            # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["service"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
            url_services = self.urls_centreon['services'] + '?types=["metaservice","service"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]&limit=' +  str(self.limit_services_number)

        # Hosts URL
        if self.centreon_version == 20.04:
            # https://demo.centreon.com/centreon/api/latest/monitoring/resources?page=1&limit=30&sort_by={"status_severity_code":"asc","last_status_change":"desc"}&types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]
            url_hosts = self.urls_centreon['hosts'] + '?types=["host"]&statuses=["WARNING","DOWN","CRITICAL","UNKNOWN"]&limit=' + str(self.limit_services_number)

        # Hosts
        try:
            if self.centreon_version >= 20.04:
                # Get json
                result = self.FetchURL(url_hosts, giveback='raw')

                data = json.loads(result.result)
                error = result.error
                status_code = result.status_code

                # if conf.debug_mode:
                #     self.Debug(server=self.get_name(),
                #                debug="Get Hosts status Fetched JSON: " + pprint.pformat(data))

                # check if any error occured
                errors_occured = self.check_for_error(data, error, status_code)
                if errors_occured is not False:
                    return(errors_occured)

                for alerts in data["result"]:
                    new_host = alerts["name"]
                    self.new_hosts[new_host] = GenericHost()
                    self.new_hosts[new_host].name = alerts["name"]
                    self.new_hosts[new_host].server = self.name
                    self.new_hosts[new_host].criticality = alerts["severity_level"]
                    self.new_hosts[new_host].status = alerts["status"]["name"]
                    self.new_hosts[new_host].last_check = alerts["last_check"]
                    # last_state_change = datetime.strptime(alerts["last_status_change"], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None)
                    self.new_hosts[new_host].duration = alerts["duration"]
                    self.new_hosts[new_host].attempt = alerts["tries"]
                    self.new_hosts[new_host].status_information = alerts["information"]
                    self.new_hosts[new_host].passiveonly = alerts["passive_checks"]
                    self.new_hosts[new_host].notifications_disabled = not alerts["notification_enabled"]
                    self.new_hosts[new_host].flapping = alerts["flapping"]
                    self.new_hosts[new_host].acknowledged = alerts["acknowledged"]
                    self.new_hosts[new_host].scheduled_downtime = alerts["in_downtime"]
                    if "(S)" in alerts["tries"]:
                        self.new_hosts[new_host].status_type = self.HARD_SOFT['(S)']
                    else:
                        self.new_hosts[new_host].status_type = self.HARD_SOFT['(H)']
                    self.Debug(server='[' + self.get_name() + ']', debug='Host indexed : ' + new_host)

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # Services
        try:
            if self.centreon_version >= 20.04:
                # Get json
                result = self.FetchURL(url_services, giveback='raw')

                data = json.loads(result.result)
                error = result.error
                status_code = result.status_code

                # if conf.debug_mode:
                #     self.Debug(server=self.get_name(),
                #                debug="Get Services status Fetched JSON: " + pprint.pformat(data))

                # check if any error occured
                errors_occured = self.check_for_error(data, error, status_code)
                if errors_occured is not False:
                    return(errors_occured)

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
                    self.Debug(server='[' + self.get_name() + ']', debug='Service indexed : ' + new_host + ' / ' + new_service)

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
                    self.new_hosts[new_host].services[new_service].passiveonly = alerts["passive_checks"]
                    self.new_hosts[new_host].services[new_service].notifications_disabled = not alerts["notification_enabled"]
                    self.new_hosts[new_host].services[new_service].flapping = alerts["flapping"]
                    self.new_hosts[new_host].services[new_service].acknowledged = alerts["acknowledged"]
                    self.new_hosts[new_host].services[new_service].scheduled_downtime = alerts["in_downtime"]
                    if "(S)" in alerts["tries"]:
                        self.new_hosts[new_host].services[new_service].status_type = self.HARD_SOFT['(S)']
                    else:
                        self.new_hosts[new_host].services[new_service].status_type = self.HARD_SOFT['(H)']
                    self.new_hosts[new_host].services[new_service].criticality = alerts["severity_level"]

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # return True if all worked well
        return Result()


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        try:
            # host
            if service == '':
                cgi_data = {
                    "comment": comment,
                    "is_notify_contacts": notify,
                    "is_persistent_comment": persistent,
                    "is_sticky": sticky,
                    "with_services": True
                }

                host_id = self.get_host_and_service_id(host)

                # Post json
                json_string = json.dumps(cgi_data)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/hosts/{host_id}/acknowledgements
                result = self.FetchURL(self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/hosts/' + host_id + '/acknowledgements', cgi_data=json_string, giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.Debug(server='[' + self.get_name() + ']',
                               debug="Set Ack on Host, status code : " + str(status_code))


            # Service
            if service != '' or len(all_services) > 0:
                if len(all_services) == 0:
                    all_services = [service]

                acknowledgements_list=[]

                for s in all_services:
                    host_id, service_id = self.get_host_and_service_id(host, service)

                    ack = {
                        "comment": comment,
                        "is_notify_contacts": notify,
                        "is_persistent_comment": persistent,
                        "is_sticky": sticky,
                        "resource_id": service_id,
                        "parent_resource_id": host_id
                    }

                    acknowledgements_list.append(ack)

                # Post json
                json_string = json.dumps(acknowledgements_list)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/services/acknowledgements
                result = self.FetchURL(self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/services/acknowledgements', cgi_data=json_string, giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.Debug(server='[' + self.get_name() + ']',
                               debug="Set Ack on Host ("+host+") / Service ("+service+"), status code : " + str(status_code))

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


    def _set_recheck(self, host, service):
        try:
            # Host
            if service == '':
                cgi_data = {
                    "is_forced": True
                }

                host_id = self.get_host_and_service_id(host)

                # Post json
                json_string = json.dumps(cgi_data)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/hosts/{host_id}/check
                result = self.FetchURL(self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/hosts/' + host_id + '/check', cgi_data=json_string, giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.Debug(server='[' + self.get_name() + ']',
                               debug="Recheck on Host : "+host+", status code : " + str(status_code))

            # Service
            else:
                cgi_data = {
                    "is_forced": True
                }

                host_id, service_id = self.get_host_and_service_id(host, service)

                # Post json
                json_string = json.dumps(cgi_data)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/hosts/{host_id}/services/{service_id}/check
                result = self.FetchURL(self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/hosts/' + host_id + '/services/' + service_id + '/check', cgi_data=json_string, giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.Debug(server='[' + self.get_name() + ']',
                               debug="Recheck on Host ("+host+") / Service ("+service+"), status code : " + str(status_code))


        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        obj_start_time = datetime.strptime(start_time, '%m/%d/%Y %H:%M')
        obj_end_time = datetime.strptime(end_time, '%m/%d/%Y %H:%M')

        # Nagstamon don’t provide the TZ, we need to get it from the OS
        obj_start_time = obj_start_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
        obj_end_time = obj_end_time.replace(tzinfo=datetime.now().astimezone().tzinfo)

        # duration unit is second
        duration = (hours * 3600) + (minutes * 60)

        # API require boolean
        if fixed == 1:
            fixed = True
        else:
            fixed = False

        try:
            if service == '':
            # Host
                cgi_data = {
                    "start_time": obj_start_time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    "end_time": obj_end_time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    "is_fixed": fixed,
                    "duration": duration,
                    "author_id": self.user_id,
                    "comment": comment,
                    "with_services": True
                }

                host_id = self.get_host_and_service_id(host)

                # Post json
                json_string = json.dumps(cgi_data)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/hosts/{host_id}/downtimes
                result = self.FetchURL(self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/hosts/' + host_id + '/downtimes', cgi_data=json_string, giveback='raw')

                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.Debug(server='[' + self.get_name() + ']',
                               debug="Downtime on Host : "+host+", status code : " + str(status_code))

            # Service
            else:
                cgi_data = {
                    "start_time": obj_start_time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    "end_time": obj_end_time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    "is_fixed": fixed,
                    "duration": duration,
                    "author_id": self.user_id,
                    "comment": comment
                }

                host_id, service_id = self.get_host_and_service_id(host, service)

                # Post json
                json_string = json.dumps(cgi_data)
                # {protocol}://{server}:{port}/centreon/api/{version}/monitoring/hosts/{host_id}/services/{service_id}/downtimes
                result = self.FetchURL(self.monitor_cgi_url + '/api/' + self.restapi_version + '/monitoring/hosts/' + host_id + '/services/' + service_id + '/downtimes', cgi_data=json_string, giveback='raw')


                error = result.error
                status_code = result.status_code

                if conf.debug_mode:
                    self.Debug(server='[' + self.get_name() + ']',
                               debug="Downtime on Host ("+host+") / Service ("+service+"), status code : " + str(status_code))


        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


    def check_session(self):
        if conf.debug_mode == True:
            self.Debug(server='[' + self.get_name() + ']', debug='Checking session status')
        # Not needed anymore as URLs are set at start
        # if 'url_centreon' not in self.__dict__:
        #     self.init_config()
        try:
            if conf.debug_mode == True:
                self.Debug(server='[' + self.get_name() + ']', debug='Check-session, the token will be deleted if it has not been used for more than one hour. Current Token = ' + self.token )

            cgi_data = {'limit':'0'}
            self.session = requests.Session()
            self.session.headers['Content-Type'] = 'application/json'
            self.session.headers['X-Auth-Token'] = self.token

            # Get en empty service list, to check the status of the current token
            # This request must be done in a GET, so just encode the parameters and fetch
            result = self.FetchURL(self.urls_centreon['services'] + '?' + urllib.parse.urlencode(cgi_data), giveback="raw")

            data = json.loads(result.result)
            error = result.error
            status_code = result.status_code

            if conf.debug_mode:
                self.Debug(server=self.get_name(),
                           debug="Check-session, Fetched JSON: " + pprint.pformat(data))
                self.Debug(server=self.get_name(),
                           debug="Check-session, Error : " + error + " Status code : " + str(status_code))

            # If we got an 401, the token expired and must be renewed
            if status_code == 401:
                self.token = self.get_token().result
                if conf.debug_mode == True:
                    self.Debug(server='[' + self.get_name() + ']', debug='Check-session, session renewed')

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
