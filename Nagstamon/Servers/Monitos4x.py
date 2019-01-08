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

# Initial implementation by Marcus Mönnig
#
# This Server class connects against monitos 4.
#
# Status/TODOs:
#

import copy
import datetime
import json
import logging
import sys
import time

import requests
from bs4 import BeautifulSoup

from Nagstamon.Helpers import webbrowser_open
from Nagstamon.Objects import (GenericHost, GenericService, Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Config import conf

log = logging.getLogger('monitos4x')
log.setLevel('INFO')

def strfdelta(tdelta, fmt):
    d = {'days': tdelta.days}
    d['hours'], rem = divmod(tdelta.seconds, 3600)
    d['minutes'], d['seconds'] = divmod(rem, 60)
    return fmt.format(**d)

class Monitos4xServer(GenericServer):
    """
        object of monitos 4x server from Freicon GmbH & Co. KG
    """
    TYPE = 'monitos4x'
    MENU_ACTIONS = [
        'Monitor',
        'Recheck',
        'Acknowledge',
        'Submit check result',
        'Downtime'
    ]
    STATES_MAPPING = {
        'hosts': {
            0: 'UP',
            1: 'DOWN',
            2: 'UNREACHABLE',
            4: 'PENDING'
        },
        'services': {
            0: 'OK',
            1: 'WARNING',
            2: 'CRITICAL',
            3: 'UNKNOWN',
            4: 'PENDING'
        }
    }
    STATES_MAPPING_REV = {
        'hosts': {
            'UP': 0,
            'DOWN': 1,
            'UNREACHABLE': 2,
            'PENDING': 4
        },
        'services': {
            'OK': 0,
            'WARNING': 1,
            'CRITICAL': 2,
            'UNKNOWN': 3,
            'PENDING': 4
        }
    }
    BROWSER_URLS = {
        'monitor': '$MONITOR$',
        'hosts': '$MONITOR$',
        'services': '$MONITOR$',
        'history': '$MONITOR$/#/alert/ticker'
    }

    def init_config(self):
        """
            Set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # dummy default empty cgi urls - get filled later when server version is known
        self.cgiurl_services = None
        self.cgiurl_hosts = None

    def init_HTTP(self):
        """
            Initializing of session object
        """

        GenericServer.init_HTTP(self)

        self.session.auth = NoAuth()
        if self.use_autologin is False:
            if len(self.session.cookies) == 0:
                form_inputs = dict()
                if '@' in self.username:
                    user = self.username.split('@')
                    form_inputs['module'] = 'ldap'
                    form_inputs['_username'] = user[0]
                else:
                    form_inputs['module'] = 'sv'
                    form_inputs['_username'] = self.username

                form_inputs['urm:login:client'] = ''
                form_inputs['_password'] = self.password

                # call login page to get temporary cookie
                self.FetchURL('{0}/security/login'.format(self.monitor_url))
                # submit login form to retrieve authentication cookie
                self.FetchURL(
                    '{0}/security/login_check'.format(self.monitor_url),
                    cgi_data=form_inputs,
                    multipart=True
                )

    def _get_status(self):
        """
            Get status from monitos 4 Server - only JSON
        """
        # define CGI URLs for hosts and services

        if self.use_autologin is True:
            if self.cgiurl_hosts is None:
                # hosts (up, down, unreachable)
                self.cgiurl_hosts = self.monitor_cgi_url + '/api/host?include=status,configuration&limit=100&filter[states]=0,1,2' + '&authtoken=' + self.autologin_key

            if self.cgiurl_services is None:
                # services (warning, critical, unknown)
                self.cgiurl_services = self.monitor_cgi_url + \
                                       '/api/serviceinstance?include=status,configuration&limit=100&filter[states]=1,2,3' + '&authtoken=' + self.autologin_key
        else:
            if self.cgiurl_hosts is None:
                # hosts (up, down, unreachable)
                self.cgiurl_hosts = self.monitor_cgi_url + '/api/host?include=status,configuration&limit=100&filter[states]=0,1,2'

            if self.cgiurl_services is None:
                # services (warning, critical, unknown)
                self.cgiurl_services = self.monitor_cgi_url + '/api/serviceinstance?include=status,configuration&limit=100&filter[states]=1,2,3'

        self.new_hosts = dict()

        # hosts
        try:
            form_data = dict()

            page = 1

            # loop trough all api pages
            while True:
                cgiurl_hosts_page = self.cgiurl_hosts + '&page=' + str(page)

                result = self.FetchURL(
                    cgiurl_hosts_page, giveback='raw', cgi_data=None)

                # authentication errors get a status code 200 too
                if result.status_code < 400 and \
                        result.result.startswith('<'):
                    # in case of auth error reset HTTP session and try again
                    self.reset_HTTP()
                    result = self.FetchURL(
                        cgiurl_hosts_page, giveback='raw', cgi_data=None)

                    if result.status_code < 400 and \
                            result.result.startswith('<'):
                        self.refresh_authentication = True
                        return Result(result=result.result,
                                      error='Authentication error',
                                      status_code=result.status_code)

                # purify JSON result
                jsonraw = copy.deepcopy(result.result.replace('\n', ''))
                error = copy.deepcopy(result.error)
                status_code = result.status_code

                if error != '' or status_code >= 400:
                    return Result(result=jsonraw,
                                  error=error,
                                  status_code=status_code)

                self.check_for_error(jsonraw, error, status_code)

                hosts = json.loads(jsonraw)
                if not hosts['data']:
                    break

                page+=1

                for host in hosts['data']:
                    h = dict(host)

                    # Skip if host is disabled
                    if h['syncEnabled'] is not None:
                        if not int(h['syncEnabled']):
                            continue

                    # host
                    host_name = h['name']

                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug=time.strftime('%a %H:%M:%S') + ' host_name is: ' + host_name)

                    # If a host does not exist, create its object
                    if host_name not in self.new_hosts:
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].uuid = h['uuid']
                        self.new_hosts[host_name].server = 'monitos'

                        try:
                            self.new_hosts[host_name].status = self.STATES_MAPPING['hosts'][int(
                                h['status']['currentState'])]
                        except:
                            pass

                        try:
                            self.new_hosts[host_name].last_check = datetime.datetime.fromtimestamp(
                                int(h['status']['lastCheck']))
                        except:
                            pass

                        self.new_hosts[host_name].attempt = h['configuration']['maxCheckAttempts']

                        try:
                            self.new_hosts[host_name].status_information = BeautifulSoup(h['status']['output'].replace('\n', ' ').strip(), 'html.parser').text
                        except:
                            self.new_hosts[host_name].services[service_name].status_information = 'Cant parse output'

                        self.new_hosts[host_name].passiveonly = not (
                            int(h['status']['checksEnabled']))

                        try:
                            self.new_hosts[host_name].notifications_disabled = not (int(s['status']['notificationsEnabled']))
                        except:
                            self.new_hosts[host_name].notifications_disabled = False

                        try:
                            self.new_hosts[host_name].flapping = (int(h['status']['isFlapping']))
                        except:
                            self.new_hosts[host_name].flapping = False

                        if h['status']['acknowleged'] is None:
                            self.new_hosts[host_name].acknowledged = 0
                        else:
                            self.new_hosts[host_name].acknowledged = int(h['status']['acknowleged'])

                        self.new_hosts[host_name].scheduled_downtime = int(h['status']['scheduledDowntimeDepth'])

                        try:
                            self.new_hosts[host_name].status_type = 'soft' if int(h['status']['stateType']) == 0 else 'hard'
                        except:
                            self.new_hosts[host_name].status_type = 'hard'

                        # extra duration needed for calculation
                        if h['status']['lastStateChange'] is None:
                            self.Debug(server=self.get_name(), debug=time.strftime('%a %H:%M:%S') + 'Host has wrong lastStateChange - host_name is: ' + host_name)
                        else:
                            duration = datetime.datetime.now(
                            ) - datetime.datetime.fromtimestamp(int(h['status']['lastStateChange']))
                            self.new_hosts[host_name].duration = strfdelta(
                                duration, '{days}d {hours}h {minutes}m {seconds}s')

                    del h, host_name
                del hosts
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            form_data = dict()

            page = 1

            # loop trough all api pages
            while True:
                cgiurl_services_page = self.cgiurl_services + '&page=' + str(page)

                result = self.FetchURL(cgiurl_services_page,
                                       giveback='raw', cgi_data=None)

                # purify JSON result
                jsonraw = copy.deepcopy(result.result.replace('\n', ''))
                error = copy.deepcopy(result.error)
                status_code = result.status_code

                if error != '' or status_code >= 400:
                    return Result(result=jsonraw,
                                  error=error,
                                  status_code=status_code)

                self.check_for_error(jsonraw, error, status_code)

                services = json.loads(jsonraw)
                if not services['data']:
                    break

                page+=1

                for service in services['data']:
                    s = dict(service)

                    # Skip if host is disabled
                    if s['syncEnabled'] is not None:
                        if not int(s['syncEnabled']):
                            continue

                    # host and service
                    host_name = s['configuration']['hostName']
                    service_name = s['configuration']['serviceDescription']

                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug=time.strftime('%a %H:%M:%S') + ' host_name is: ' + host_name + ' service_name is: ' + service_name)

                    # If host not in problem list, create it
                    if host_name not in self.new_hosts:
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].uuid = s['configuration']['host']['uuid']
                        self.new_hosts[host_name].status = self.STATES_MAPPING['services'][0]

                    # If a service does not exist, create its object
                    if service_name not in self.new_hosts[host_name].services:
                        self.new_hosts[host_name].services[service_name] = GenericService(
                        )
                        self.new_hosts[host_name].services[service_name].host = s['configuration']['hostName']
                        self.new_hosts[host_name].services[service_name].uuid = s['uuid']
                        self.new_hosts[host_name].services[service_name].name = service_name
                        self.new_hosts[host_name].services[service_name].server = 'monitos'

                        try:
                            self.new_hosts[host_name].services[service_name].status = self.STATES_MAPPING['services'][int(
                                s['status']['currentState'])]
                        except:
                            pass

                        try:
                            self.new_hosts[host_name].services[service_name].last_check = datetime.datetime.fromtimestamp(
                                int(s['status']['lastCheck']))
                        except:
                            pass

                        self.new_hosts[host_name].services[service_name].attempt = s['configuration']['maxCheckAttempts']

                        try:
                            self.new_hosts[host_name].services[service_name].status_information = BeautifulSoup(s['status']['output'].replace('\n', ' ').strip(), 'html.parser').text
                        except:
                            self.new_hosts[host_name].services[service_name].status_information = 'Cant parse output'

                        self.new_hosts[host_name].services[service_name].passiveonly = not (int(s['status']['checksEnabled']))

                        try:
                            self.new_hosts[host_name].services[service_name].notifications_disabled = not (
                                int(s['status']['notificationsEnabled']))
                        except:
                            self.new_hosts[host_name].services[service_name].notifications_disabled = False

                        try:
                            self.new_hosts[host_name].services[service_name].flapping = (int(s['status']['isFlapping']))
                        except:
                            self.new_hosts[host_name].services[service_name].flapping = False

                        if s['status']['acknowleged'] is None:
                            self.new_hosts[host_name].services[service_name].acknowledged  = 0
                        else:
                            self.new_hosts[host_name].services[service_name].acknowledged = int(s['status']['acknowleged'])

                        try:
                            if int(s['status']['scheduledDowntimeDepth']) != 0:
                                self.new_hosts[host_name].services[service_name].scheduled_downtime = True
                        except:
                            self.new_hosts[host_name].services[service_name].scheduled_downtime = False

                        try:
                            self.new_hosts[host_name].services[service_name].status_type = 'soft' if int(s['status']['stateType']) == 0 else 'hard'
                        except:
                            self.new_hosts[host_name].services[service_name].status_type = 'hard'

                        # extra duration needed for calculation
                        if s['status']['lastStateChange'] is None:
                            self.Debug(server=self.get_name(), debug=time.strftime('%a %H:%M:%S')
                                                                     + 'Service has wrong lastStateChange - host_name is ' + host_name + ' service_name is: ' + service_name)
                        else:
                            duration = datetime.datetime.now(
                            ) - datetime.datetime.fromtimestamp(int(s['status']['lastStateChange']))
                            self.new_hosts[host_name].services[service_name].duration = strfdelta(
                                duration, '{days}d {hours}h {minutes}m {seconds}s')

                    del s, host_name, service_name
                del services
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        del jsonraw, error, hosts

        # dummy return in case all is OK
        return Result()

    def _set_recheck(self, host, service):
        """
            Do a POST-Request to recheck the given host or service in monitos 4

            :param host: String - Host name
            :param service: String - Service name
        """
        form_data = dict()

        type = 'host'
        if service == '':
            uuid = self.hosts[host].uuid
        else:
            type = 'serviceinstance'
            uuid = self.hosts[host].services[service].uuid

        if self.use_autologin is True:
            self.session.post('{0}/api/{1}/{2}/reschedule?authtoken={3}'.format(self.monitor_url, type ,uuid, self.autologin_key))
        else:
            self.session.post('{0}/api/{1}/{2}/reschedule'.format(self.monitor_url, type ,uuid))

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        """
            Do a POST-Request to set an acknowledgement for a host, service or host with all services in monitos 4

            :param host: String - Host name
            :param service: String - Service name
            :param author: String - Author name (username)
            :param comment: String - Additional comment
            :param sticky: Bool - Sticky Acknowledgement
            :param notify: Bool - Send Notifications
            :param persistent: Bool - Persistent comment
            :param all_services: Array - List of all services (filled only if 'Acknowledge all services on host' is set)
        """
        form_data = dict()

        type = 'host'

        if len(all_services) > 0:  # Host & all Services
            uuid = self.hosts[host].uuid
            form_data = json.dumps(
                {'comment': comment, 'notify': int(notify), 'persistent': int(persistent),
                 'sticky': int(sticky), 'includeServices': 1})
        elif service == '':  # Host
            uuid = self.hosts[host].uuid
            form_data = json.dumps(
                {'comment': comment, 'notify': int(notify), 'persistent': int(persistent),
                 'sticky': int(sticky), 'includeServices': 0})
        else:  # Service
            uuid = self.hosts[host].services[service].uuid
            type = 'serviceinstance'
            form_data = json.dumps(
                {'comment': comment, 'notify': int(notify),
                 'persistent': int(persistent), 'sticky': int(sticky)})

        if self.use_autologin is True:
            self.session.post('{0}/api/{1}/{2}/acknowledge?authtoken={3}'.format(self.monitor_url, type ,uuid, self.autologin_key), data=form_data)
        else:
            self.session.post('{0}/api/{1}/{2}/acknowledge'.format(self.monitor_url, type ,uuid), data=form_data)

    def _set_submit_check_result(self, host, service, state, comment, check_output, performance_data):
        """
            Do a POST-Request to submit a check result to monitos 4

            :param host: String - Host name
            :param service: String - Service name
            :param state: String - Selected state
            :param comment: NOT IN USE - String - Additional comment
            :param check_output: String - Check output
            :param performance_data: String - Performance data
        """
        state = state.upper()

        form_data = dict()

        type = 'host'

        if service == '':  # Host
            uuid = self.hosts[host].uuid

            if state == 'OK' or state == 'UNKNOWN':
                log.info('Setting OK or UNKNOWN to UP')
                state = 'UP'

            state_number = self.STATES_MAPPING_REV['hosts'][state]

            if performance_data == '':
                form_data = json.dumps(
                    {'exit_status': state_number, 'plugin_output': check_output})
            else:
                form_data = json.dumps({'exit_status': state_number, 'plugin_output': check_output, 'performance_data': performance_data})
        else:  # Service
            if state == 'UP':
                log.info('Setting UP or OK')
                state = 'OK'
            if state == 'UNREACHABLE':
                log.info('Setting UNREACHABLE to CRITICAL')
                state = 'CRITICAL'

            type = 'serviceinstance'
            uuid = self.hosts[host].services[service].uuid

            state_number = self.STATES_MAPPING_REV['services'][state]

            if performance_data == '':
                form_data = json.dumps(
                    {'exit_status': state_number, 'plugin_output': check_output})
            else:
                form_data = json.dumps(
                    {'exit_status': state_number, 'plugin_output': check_output, 'performance_data': performance_data})

        if self.use_autologin is True:
            self.session.post('{0}/api/{1}/{2}/checkresult?authtoken={3}'.format(self.monitor_url, type ,uuid, self.autologin_key), data=form_data)
        else:
            self.session.post('{0}/api/{1}/{2}/checkresult'.format(self.monitor_url, type ,uuid), data=form_data)

    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        """
            Do a PUT-Request to create a downtime for a host or service in monitos 4

            :param host: String - Host name
            :param service: String - Service name
            :param author: String - Author name (username)
            :param comment: String - Additional comment
            :param fixed: Bool - Fixed Downtime
            :param start_time: String - Date in Y-m-d H:M:S format - Start of Downtime
            :param end_time: String - Date in Y-m-d H:M:S format - End of Downtime
            :param hours: Integer - Flexible Downtime
            :param minutes: Integer - Flexible Downtime
        """
        form_data = dict()

        if service == '':
            type = 'sv_host'
            uuid = self.hosts[host].uuid
        else:
            type = 'sv_service_status'
            uuid = self.hosts[host].services[service].uuid

        # Format start_time and end_time from user-friendly format to timestamp
        start_time = time.mktime(datetime.datetime.strptime(
            start_time, "%Y-%m-%d %H:%M:%S").timetuple())
        start_time = str(start_time).split('.')[0]

        end_time = time.mktime(datetime.datetime.strptime(
            end_time, "%Y-%m-%d %H:%M:%S").timetuple())
        end_time = str(end_time).split('.')[0]

        duration = (hours * 60 * 60) + (minutes * 60)

        if fixed:
            form_data = json.dumps({'start': start_time, 'end': end_time, 'comment': comment,
                                    'is_recurring': 'FALSE', 'includeServices': 'TRUE',
                                    'includeChildren': 'FALSE', 'schedule_now': 'FALSE',
                                    'id': uuid, 'type': type})

        else:
            form_data = json.dumps({'start': start_time, 'end': end_time, 'comment': comment,
                                    'is_recurring': 'FALSE', 'includeServices': 'TRUE',
                                    'includeChildren': 'FALSE', 'schedule_now': 'FALSE',
                                    'id': uuid, 'duration': duration, 'type': type})

        if self.use_autologin is True:
            self.session.post('{0}/api/downtime?authtoken={1}'.format(self.monitor_url, self.autologin_key), data=form_data)
        else:
            self.session.post('{0}/api/downtime'.format(self.monitor_url), data=form_data)

    def get_start_end(self, host):
        """
            Set default of start time to "now" and end time is "now + 24 hours"

            :param host: String - Host name
        """

        start = datetime.datetime.now()
        end = datetime.datetime.now() + datetime.timedelta(hours=24)

        return str(start.strftime("%Y-%m-%d %H:%M:%S")), str(end.strftime("%Y-%m-%d %H:%M:%S"))

    def open_monitor(self, host, service=''):
        """
            Open specific Host or Service in monitos 4 browser window

            :param host: String - Host name
            :param service: String - Service name
        """

        if service == '':
            url = '{0}/#/object/details/{1}'.format(
                self.monitor_url, self.hosts[host].uuid)
        else:
            url = '{0}/#/object/details/{1}'.format(
                self.monitor_url, self.hosts[host].services[service].uuid)

        webbrowser_open(url)

class NoAuth(requests.auth.AuthBase):
    """
        Override to avoid auth headers
        Needed for LDAP login
    """

    def __call__(self, r):
        return r
