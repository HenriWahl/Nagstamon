# adapted from the Zenoss.py code

# Copyright (C) 2017 Vyron Tsingaras <v.tsingaras@interworks.cloud> interworks.cloud
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

from datetime import timezone, datetime
import sys
import traceback
from requests.structures import CaseInsensitiveDict

from Nagstamon.config import conf
from Nagstamon.objects import (GenericHost, GenericService, Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.thirdparty.sensu_api import SensuAPI, SensuAPIException
from Nagstamon.helpers import human_readable_duration_from_timestamp, webbrowser_open


class SensuServer(GenericServer):
    TYPE = 'Sensu'
    SEVERITY_CODE_TEXT_MAP = dict()
    SEVERITY_STATUS_TEXT_MAP = CaseInsensitiveDict()

    MENU_ACTIONS = ['Monitor', 'Recheck', 'Acknowledge', 'Submit check result', 'Downtime']

    sensu_api = None
    authentication = 'basic'
    api_url = ''
    uchiwa_url = ''
    uchiwa_datacenter = ''
    username = ''
    password = ''

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Prepare all urls needed by nagstamon
        self.urls = {}
        self.statemap = {}

        self.api_url = conf.servers[self.get_name()].monitor_cgi_url
        self.uchiwa_url = conf.servers[self.get_name()].monitor_url
        self.uchiwa_datacenter = conf.servers[self.get_name()].monitor_site
        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password
        self.ignore_cert = conf.servers[self.get_name()].ignore_cert
        self.custom_cert_use = conf.servers[self.get_name()].custom_cert_use
        self.custom_cert_ca_file = conf.servers[self.get_name()].custom_cert_ca_file

        self.BROWSER_URLS = {
            'monitor': '$MONITOR$',
            'hosts': '$MONITOR$/#/clients',
            'services': '$MONITOR$/#/checks',
            'history': '$MONITOR$/#/clients'
        }

        self.SEVERITY_CODE_TEXT_MAP = {
            0: 'OK',
            1: 'WARNING',
            2: 'CRITICAL',
            3: 'UNKNOWN'
        }
        # SEVERITY_STATUS_TEXT_MAP is a Case-Insensitive dict
        self.SEVERITY_STATUS_TEXT_MAP['OK'] = 0
        self.SEVERITY_STATUS_TEXT_MAP['WARNING'] = 1
        self.SEVERITY_STATUS_TEXT_MAP['CRITICAL'] = 2
        self.SEVERITY_STATUS_TEXT_MAP['UNKNOWN'] = 3

    def init_HTTP(self):
        """
            things to do if HTTP is not initialized
        """
        GenericServer.init_HTTP(self)

        if self.custom_cert_use:
            verify = self.custom_cert_ca_file
        else: 
            verify = not self.ignore_cert

        try:
            self.sensu_api = SensuAPI(
                self.api_url,
                username=self.username,
                password=self.password,
                verify=verify
            )
        except SensuAPIException:
                self.error(sys.exc_info())

    def _insert_service_to_hosts(self, service: GenericService):
        service_host = service.get_host_name()
        if service_host not in self.new_hosts:
            self.new_hosts[service_host] = GenericHost()
            self.new_hosts[service_host].name = service_host
            self.new_hosts[service_host].site = service.site

        self.new_hosts[service_host].services[service.name] = service

    @staticmethod
    def _aslocaltimestr(utc_dt):
        local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')

    def _get_status(self):
        self.new_hosts = dict()

        try:
            events = self._get_all_events()
            for event in events:
                event_check = event['check']
                event_client = event['client']

                new_service = GenericService()
                new_service.event_id = event['id']
                new_service.host = event_client['name']
                new_service.name = event_check['name']
                # Uchiwa needs the 'dc' for re_check; Sensu does not
                if 'dc' in event:
                  new_service.site = event['dc']
                else:
                  new_service.site = ''
                new_service.status = ''
                try:
                    new_service.status = self.SEVERITY_CODE_TEXT_MAP[event_check['status']]
                except KeyError:
                    new_service.status = 'UNKNOWN'
                last_check_time = datetime.utcfromtimestamp(int(event['timestamp']))
                new_service.last_check = self._aslocaltimestr(last_check_time)
                new_service.duration = human_readable_duration_from_timestamp(int(event['last_state_change']))
                new_service.status_information = event_check['output']
                # needs a / with a number on either side to work
                new_service.attempt = str(event['occurrences']) + '/1'
                new_service.passiveonly = False
                new_service.notifications_disabled = event['silenced']
                new_service.flapping = False
                new_service.acknowledged = event['silenced']
                new_service.scheduled_downtime = False

                self._insert_service_to_hosts(new_service)
        except:
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            print(traceback.format_exc())
            return Result(result=result, error=error)

        return Result(error="")

    def get_username(self):
        return str(self.username)

    def get_password(self):
        return str(self.password)

    def set_acknowledge(self, info_dict):
        subscription = self._format_client_subscription(info_dict['host'])
        try:
            silenece_args = {
                'check': info_dict['service'],
                'subscription': subscription,
                'reason': info_dict['comment'],
                'creator': info_dict['author'],
                'expire_on_resolve': True
            }
            self.sensu_api.post_silence_request(silenece_args)
        except SensuAPIException as e:
            pass

    @staticmethod
    def _format_client_subscription(client: str):
        return 'client:' + client

    def _acknowledge_client_check(self, client: str, check: str, comment: str = None, author: str = None):
        subscription = self._format_client_subscription(client)
        try:
            silenece_args = {
                'check': check,
                'subscription': subscription,
                'reason': comment,
                'creator': author,
                'expire_on_resolve': True
            }
            self.sensu_api.post_silence_request(silenece_args)
        except SensuAPIException as e:
            pass

    def _get_all_events(self):
        events = self.sensu_api.get_events()
        return events

    def _get_event_duration_string(self, start_seconds: int, end_seconds: int):
        sec = end_seconds - start_seconds

        days, rem = divmod(sec, 60 * 60 * 24)
        hours, rem = divmod(rem, 60 * 60)
        mins, sec = divmod(rem, 60)

        if days == 0 and hours == 0 and mins == 0 and sec == 0:
            return None
        return '%sd %sh %sm %ss' % (days, hours, mins, sec)

    def set_recheck(self, info_dict):
        if info_dict['service'] == 'keepalive':
            if conf.debug_mode:
                self.debug(server=self.name, debug='Keepalive results must come from the client running on host {0}, unable to recheck'.format(info_dict['host']))
        else:
            standalone = self.sensu_api.get_event(info_dict['host'], info_dict['service'])['check']['standalone']
            if standalone:
                if conf.debug_mode:
                    self.debug(server=self.name, debug='Service {0} on host {1} is a standalone service, will not recheck'.format(info_dict['service'], info_dict['host']))
            else:
                self.sensu_api.post_check_request(
                    info_dict['service'],
                    self._format_client_subscription(info_dict['host']),
                    self.hosts[info_dict['host']].site
                )

    def set_downtime(self, info_dict):
        subscription = self._format_client_subscription(info_dict['host'])

        silence_args = {
            'check': info_dict['service'],
            'subscription': subscription,
            'reason': info_dict['comment'],
            'creator': info_dict['author'],
            'expire': int(info_dict['hours']) * 3600 + int(info_dict['minutes']) * 60,
            'expire_on_resolve': False
        }
        self.sensu_api.post_silence_request(silence_args)

    def set_submit_check_result(self, info_dict):
        sensu_status = None
        try:
            sensu_status = self.SEVERITY_STATUS_TEXT_MAP[info_dict['state']]
        except KeyError:
            sensu_status = 3  # 3 stands for UNKNOWN, anything other than 0,1,2 is UNKNOWN to Sensu
        self.sensu_api.post_result_data(info_dict['host'], info_dict['service'],
                                        info_dict['check_output'], sensu_status)

    def get_start_end(self, host):
        return 'Not Supported!', 'Not Supported!'

    def open_monitor(self, host, service=''):
        '''
            open monitor from tablewidget context menu
        '''
        detail_url = self.monitor_url + '/#/client/' + self.uchiwa_datacenter + '/' + host
        if service != '':
            detail_url += '?check=' + service
        webbrowser_open(detail_url)
