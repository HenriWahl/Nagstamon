# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2015 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

import requests
# disable annoying InsecureRequestWarning warnings
try:
    requests.packages.urllib3.disable_warnings()
except:
    # older requests version might not have the packages submodule
    # for example the one in Ubuntu 14.04
    pass

# import sys
# import socket
# import copy
# import webbrowser
# import datetime
# import traceback
# import platform
# import urllib.parse
# from bs4 import BeautifulSoup
#
# from Nagstamon.Helpers import (HostIsFilteredOutByRE,
#                                ServiceIsFilteredOutByRE,
#                                StatusInformationIsFilteredOutByRE,
#                                CriticalityIsFilteredOutByRE,
#                                not_empty,
#                                debug_queue,
#                                STATES)
# from Nagstamon.Objects import (GenericService, GenericHost, Result)
# from Nagstamon.Config import (conf, AppInfo)

# from collections import OrderedDict

from Nagstamon.Objects import Result
from Nagstamon.Objects import GenericHost
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Config import conf

import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('Livestatus')

import json
import socket
import time


def format_timestamp(timestamp):
    ts_tuple = time.localtime(timestamp)
    return time.strftime('%Y-%m-%d %H:%M:%S', ts_tuple)


def duration(timestamp):
    """human representation of a duration"""
    factors = (60 * 60 * 24, 60 * 60, 60, 1)
    result = []
    diff = time.time() - timestamp
    for f in factors:
        x = int(diff / f)
        result.append(x)
        diff = diff - x * f
    return '%02dd %02dh %02dm %02ds' % tuple(result)


class LivestatusServer(GenericServer):
    '''
        Abstract server which serves as template for all other types
        Default values are for Nagios servers
    '''

    TYPE = 'Livestatus'

    def init_HTTP(self):
        """create the socket to livestatus"""
        log.debug('init_HTTP')
        if getattr(self, 'socket', None):
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffersize = 2**20  # max response we process is 1MB
        log.info('connecting')
        self.socket.connect(('monitoring2.acc.gsi.de', 6558))

    def reset_HTTP(self):
        """close any open sockets"""
        log.debug('reset_HTTP')
        if getattr(self, 'socket', None) is not None:
            self.socket.close()
        self.socket = None

    def communicate(self, cmd, raw=[], headers={}):
        """ """
        data = [cmd, ]
        headers['OutputFormat'] = 'json'
        headers['ColumnHeaders'] = 'on'
        for k, v in headers.items():
            data.append('%s: %s' % (k, v))
        for line in raw:
            data.append(line)
        data.append('')
        data.append('')
        log.debug('sending %s', data)
        self.socket.send('\n'.join(data).encode('utf8'))
        # TODO: handle reconnect
        result = bytes()
        line = self.socket.recv(self.buffersize)
        while len(line) > 0:
            result += line
            line = self.socket.recv(self.buffersize)
        result = result.decode('utf8')
        log.debug('received %s', result)
        self.reset_HTTP()  # close connection
        if result:
            return json.loads(result)
        return result

    def table(self, data):
        """take a livestatus answer and format it as a table"""
        try:
            header = data[0]
        except IndexError:
            raise StopIteration
        for line in data[1:]:
            yield(dict(zip(header, line)))

    def _get_status(self):
        """fetch any host/service not in OK state
        store the information in self.new_hosts
        """
        # GenericHost()
        # .name, .server, .status, .last_check, .duration, .attempt, .status_information
        # .passiveonly, .notifications_disabled, .flapping, .acknowledged
        # .scheduled_downtime, .status_type
        log.debug('_get_status')
        self.new_hosts = dict()
        # hosts
        filters = []
        host_states = {0: 'UP', 1: 'DOWN', 2: 'UNKNOWN'}
        filters.append('Filter: state != 0')  # ignore OK state
        if conf.filter_acknowledged_hosts_services:
            filters.append('Filter: acknowledged != 1')
        data = self.communicate("GET hosts", raw=filters)
        for h in self.table(data):
            # see http://docs.icinga.org/icinga2/latest/doc/module/icinga2/chapter/appendix#schema-livestatus
            host = GenericHost()
            host.name = h['name']
            host.server = self.name
            host.status = host_states[h['state']]
            host.last_check = format_timestamp(host['last_check'])
            host.duration = duration(host['last_state_change'])
            host.attempt = host['current_attempt']
            host.status_information = host['plugin_output']  # CRITICAL: Host Unreachable(...)
            host.passiveonly = False
            host.notification_disabled = host['notification_disabled'] == 1
            host.flapping = host['is_flapping'] == 1
            host.acknowledged = host['acknowledged'] == 1
            host.scheduled_downtime = host['scheduled_downtime_depth'] == 1
            if host['state'] == host['last_hard_state']:
                host.status_type = 'hard'
            else:
                host.status_type = 'soft'
            self.new_hosts[host.name] = host
            log.info("host %s is %s", host.name, host.status)
        # services
        # TODO services
        # are attached to hosts;
        # self.new_hosts['foo'] = GenericHost()
        # self.new_hosts['foo'].status = 'UP'
        # self.new_hosts['foo'].services['foos-service'] = GenericService()
        data = self.communicate("GET services", raw=filters)

        return Result()

    def GGetStatus(self, output=None):
        log.debug('GetStatus')
        # init_HTTP()
        # _get_status() -> sets object attributes new_hosts return Result object status.result, status.error
