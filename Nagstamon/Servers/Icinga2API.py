# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2024 Henri Wahl <henri@nagstamon.de> et al.
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

import arrow
import copy
import json
import logging
import sys
import dateutil.parser
import urllib.parse

from Nagstamon.Config import conf
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Objects import (GenericHost, GenericService, Result)

log = logging.getLogger(__name__)


class Icinga2APIServer(GenericServer):
    """
        object of Icinga2 server API
    """
    TYPE = 'Icinga2API'

    # ICINGA2API does not provide a web interface for humans
    MENU_ACTIONS = []
    BROWSER_URLS = {}


    def __init__(self, **kwds):
        """
        Prepare all urls needed by nagstamon and icinga
        """
        GenericServer.__init__(self, **kwds)

        self.url = conf.servers[self.get_name()].monitor_url
        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password

        self.SERVICE_SEVERITY_CODE_TEXT_MAP = {
            0: 'OK',
            1: 'WARNING',
            2: 'CRITICAL',
            3: 'UNKNOWN'
        }
        self.HOST_SEVERITY_CODE_TEXT_MAP = {
            0: 'UP',
            1: 'DOWN',
            2: 'UNREACHABLE'
        }
    def _insert_service_to_hosts(self, service: GenericService):
        """
        We want to create hosts for faulty services as GenericService requires
        that logic.
        """
        service_host = service.get_host_name()
        if service_host not in self.new_hosts:
            self.new_hosts[service_host] = GenericHost()
            self.new_hosts[service_host].name = service_host
            self.new_hosts[service_host].site = service.site
        self.new_hosts[service_host].services[service.name] = service

    def _get_status(self):
        """
            Get status from Icinga Server and translate it into Nagstamon magic
            generic array
        """
        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - the down ones
        try:
            # We ask icinga for hosts which are not doing well
            hosts = self._get_host_events()
            assert isinstance(hosts, list), "Fail to list hosts"
            for host in hosts:
                host_name = host['attrs']['name']
                if host_name not in self.new_hosts:
                    self.new_hosts[host_name] = GenericHost()
                    self.new_hosts[host_name].name = host_name
                    self.new_hosts[host_name].site = self.name
                    try:
                        self.new_hosts[host_name].status = self.HOST_SEVERITY_CODE_TEXT_MAP.get(host['attrs']['state'])
                    except KeyError:
                        self.new_hosts[host_name].status = 'UNKNOWN'
                    if int(host['attrs']['state_type']) > 0:  # if state is not SOFT, icinga does not report attempts properly
                        self.new_hosts[host_name].attempt = "{}/{}".format(
                            int(host['attrs']['max_check_attempts']),
                            int(host['attrs']['max_check_attempts']))
                    else:
                        self.new_hosts[host_name].attempt = "{}/{}".format(
                            int(host['attrs']['check_attempt']),
                            int(host['attrs']['max_check_attempts']))
                    self.new_hosts[host_name].last_check = arrow.get(host['attrs']['last_check']).humanize()
                    self.new_hosts[host_name].duration = arrow.get(host['attrs']['previous_state_change']).humanize()
                    self.new_hosts[host_name].status_information = host['attrs']['last_check_result']['output']
                    self.new_hosts[host_name].passiveonly = not(host['attrs']['enable_active_checks'])
                    self.new_hosts[host_name].notifications_disabled = not(host['attrs']['enable_notifications'])
                    self.new_hosts[host_name].flapping = host['attrs']['flapping']
                    self.new_hosts[host_name].acknowledged = host['attrs']['acknowledgement']
                    self.new_hosts[host_name].scheduled_downtime = bool(host['attrs']['downtime_depth'])
                    self.new_hosts[host_name].status_type = {0: "soft", 1: "hard"}[host['attrs']['state_type']]
                del host_name
            del hosts

        except Exception as e:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            log.exception(e)
            return Result(result=result, error=error)

        # services
        try:
            services = self._get_service_events()
            for service in services:
                new_service = GenericService()
                new_service.host = service['attrs']['host_name']
                new_service.name = service['attrs']['name']
                try:
                    new_service.status = self.SERVICE_SEVERITY_CODE_TEXT_MAP.get(service['attrs']['state'])
                except KeyError:
                    new_service.status = 'UNKNOWN'
                if int(service['attrs']['state_type']) > 0:  # if state is not SOFT, icinga does not report attempts properly
                    new_service.attempt = "{}/{}".format(
                        int(service['attrs']['max_check_attempts']),
                        int(service['attrs']['max_check_attempts']))
                else:
                    new_service.attempt = "{}/{}".format(
                        int(service['attrs']['check_attempt']),
                        int(service['attrs']['max_check_attempts']))
                if service['attrs']['last_check_result'] is None:
                    new_service.status_information = 'UNKNOWN'
                else:
                    new_service.status_information = service['attrs']['last_check_result']['output']
                new_service.last_check = arrow.get(service['attrs']['last_check']).humanize()
                new_service.duration = arrow.get(service['attrs']['previous_state_change']).humanize()
                new_service.passiveonly = not(service['attrs']['enable_active_checks'])
                new_service.notifications_disabled = not(service['attrs']['enable_notifications'])
                new_service.flapping = service['attrs']['flapping']
                new_service.acknowledged = service['attrs']['acknowledgement']
                new_service.scheduled_downtime = bool(service['attrs']['downtime_depth'])
                new_service.status_type = {0: "soft", 1: "hard"}[service['attrs']['state_type']]
                self._insert_service_to_hosts(new_service)
            del services

        except Exception as e:
            log.exception(e)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

    def _list_objects(self, object_type, filter):
        """List objects"""
        result = self.FetchURL(
            f'{self.url}/objects/{object_type}?{urllib.parse.urlencode({"filter": filter})}',
            giveback='raw'
        )
        # purify JSON result of unnecessary control sequence \n
        jsonraw, error, status_code = copy.deepcopy(result.result.replace('\n', '')),\
                                      copy.deepcopy(result.error),\
                                      result.status_code

        # check if any error occured
        errors_occured = self.check_for_error(jsonraw, error, status_code)
        # if there are errors return them
        if errors_occured is not None:
            return(errors_occured)

        jsondict = json.loads(jsonraw)
        return jsondict.get('results', [])

    def _get_service_events(self):
        """
        Suck faulty service events from API
        """
        return self._list_objects('services', 'service.state!=ServiceOK')

    def _get_host_events(self):
        """
        Suck faulty hosts from API
        """
        return self._list_objects('hosts', 'host.state!=0')

    def _set_recheck(self, host, service):
        """
        Please check again Icinga!
        """
        pass

    def _set_acknowledge(self, host, service, author, comment, sticky,
                         notify, persistent, all_services=None):
        '''
        Send acknowledge to monitor server
        '''
        pass

    def _set_submit_check_result(self, host, service, state, comment,
                                 check_output, performance_data):
        '''
        Submit check results
        '''
        pass

    def _set_downtime(self, host, service, author, comment, fixed, start_time,
                      end_time, hours, minutes):
        """
        Submit downtime
        """
        pass


0
