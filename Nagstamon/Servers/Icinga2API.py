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

import arrow
import copy
import datetime
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
    MENU_ACTIONS = ['Recheck', 'Acknowledge', 'Submit check result', 'Downtime']
    STATES_MAPPING = {'hosts' : {0 : 'UP', 1 : 'DOWN', 2 : 'UNREACHABLE'}, \
                     'services' : {0 : 'OK', 1 : 'WARNING', 2 : 'CRITICAL', 3 : 'UNKNOWN'}}
    STATES_MAPPING_REV = {'hosts' : { 'UP': 0, 'DOWN': 1, 'UNREACHABLE': 2}, \
                         'services' : {'OK': 0, 'WARNING': 1, 'CRITICAL': 2, 'UNKNOWN': 3}}
    BROWSER_URLS = {}


    def __init__(self, **kwds):
        """
        Prepare all urls needed by nagstamon and icinga
        """
        GenericServer.__init__(self, **kwds)

        self.url = conf.servers[self.get_name()].monitor_url
        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password

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
                        self.new_hosts[host_name].status = self.STATES_MAPPING['hosts'].get(host['attrs']['state'])
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
            result, error = self.error(sys.exc_info())
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
                    new_service.status = self.STATES_MAPPING['services'].get(service['attrs']['state'])
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
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()

    def _list_objects(self, object_type, filter):
        """List objects"""
        result = self.fetch_url(
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


    def _trigger_action(self, action, **data):
        """Trigger on action using Icinga2 API"""
        action_data = {k: v for k, v in data.items() if v is not None}
        self.debug(server=self.get_name(), debug=f"Trigger action {action} with data={action_data}")
        try:
            response = self.session.post(
                f'{self.url}/actions/{action}',
                headers={'Accept': 'application/json'},
                json=action_data,
            )
            self.debug(
                server=self.get_name(),
                debug=f"API return on triggering action {action} (status={response.status_code}): "
                f"{response.text}"
            )
            if 200 <= response.status_code <= 299:
                return True
            self.error(f"Fail to trigger action {action}: {response.json().get('status', 'Unknown error')}")
        except IOError as err:
            log.exception("Fail to trigger action %s with data %s", action, data)
            self.error(f"Fail to trigger action {action}: {err}")

    def _set_recheck(self, host, service):
        """
        Please check again Icinga!
        """
        self._trigger_action(
            "reschedule-check",
            type="Service" if service else "Host",
            filter=(
                'host.name == host_name && service.name == service_name'
                if service else 'host.name == host_name'
            ),
            filter_vars=(
                {'host_name': host, 'service_name': service}
                if service else {'host_name': host}
            ),
        )

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

    def _set_acknowledge(self, host, service, author, comment, sticky,
                         notify, persistent, all_services=None, expire_time=None):
        '''
        Send acknowledge to monitor server
        '''
        self._trigger_action(
            "acknowledge-problem",
            type="Service" if service else "Host",
            filter=(
                'host.name == host_name && service.name == service_name'
                if service else 'host.name == host_name'
            ),
            filter_vars=(
                {'host_name': host, 'service_name': service}
                if service else {'host_name': host}
            ),
            author=author,
            comment=comment,
            sticky=sticky,
            notify=notify,
            expiry=(
                dateutil.parser.parse(expire_time).timestamp()
                if expire_time else None
            ),
            persistent=persistent,
        )

        if len(all_services) > 0:
            for s in all_services:
                # cheap, recursive solution...
                self._set_acknowledge(host, s, author, comment, sticky, notify, persistent, [], expire_time)

    def _set_submit_check_result(self, host, service, state, comment,
                                 check_output, performance_data):
        '''
        Submit check results
        '''
        self._trigger_action(
            "process-check-result",
            type="Service" if service else "Host",
            filter=(
                'host.name == host_name && service.name == service_name'
                if service else 'host.name == host_name'
            ),
            filter_vars=(
                {'host_name': host, 'service_name': service}
                if service else {'host_name': host}
            ),
            exit_status=self.STATES_MAPPING_REV['services' if service else 'hosts'][state.upper()],
            plugin_output=check_output,
            performance_data=performance_data,
        )

    def _set_downtime(self, host, service, author, comment, fixed, start_time,
                      end_time, hours, minutes):
        """
        Submit downtime
        """
        self._trigger_action(
            "schedule-downtime",
            type="Service" if service else "Host",
            filter=(
                'host.name == host_name && service.name == service_name'
                if service else 'host.name == host_name'
            ),
            filter_vars=(
                {'host_name': host, 'service_name': service}
                if service else {'host_name': host}
            ),
            author=author,
            comment=comment,
            start_time=(
                datetime.datetime.now().timestamp()
                if start_time == '' or start_time == 'n/a'
                else dateutil.parser.parse(start_time).timestamp()
            ),
            end_time=(
                (datetime.datetime.now() + datetime.timedelta(hours=hours, minutes=minutes)).timestamp()
                if end_time == '' or end_time == 'n/a'
                else dateutil.parser.parse(end_time).timestamp()
            ),
            fixed=fixed,
            duration=(
                (hours * 3600 + minutes * 60)
                if not fixed else None
            ),
        )
