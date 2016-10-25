# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2016 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

"""Module Servers"""

import urllib.request, urllib.error, urllib.parse
from collections import OrderedDict

# load all existing server types
from Nagstamon.Servers.Nagios import NagiosServer
from Nagstamon.Servers.Centreon import CentreonServer
from Nagstamon.Servers.Icinga import IcingaServer
from Nagstamon.Servers.IcingaWeb2 import IcingaWeb2Server
from Nagstamon.Servers.Multisite import MultisiteServer
from Nagstamon.Servers.op5Monitor import Op5MonitorServer
from Nagstamon.Servers.Opsview import OpsviewServer
from Nagstamon.Servers.Thruk import ThrukServer
from Nagstamon.Servers.Zabbix import ZabbixServer
from Nagstamon.Servers.Livestatus import LivestatusServer
from Nagstamon.Servers.Zenoss import ZenossServer

from Nagstamon.Config import conf

from Nagstamon.Helpers import STATES

# dictionary for servers
servers = OrderedDict()

# contains dict with available server classes
# key is type of server, value is server class
# used for automatic config generation
# and holding this information in one place
SERVER_TYPES = OrderedDict()


def register_server(server):
    """
        Once new server class is created, should be registered with this function
        for being visible in config and accessible in application.
    """
    if server.TYPE not in SERVER_TYPES:
        SERVER_TYPES[server.TYPE] = server


def get_enabled_servers():
    """
        list of enabled servers which connections outside should be used to check
    """
    return([x for x in servers.values() if x.enabled == True])


def get_worst_status():
    """
        get worst status of all servers
    """
    worst_status = 'UP'
    for server in get_enabled_servers():
        if STATES.index(server.worst_status_current) > STATES.index(worst_status):
            worst_status = server.worst_status_current
    return worst_status


def get_status_count():
    """
        get all states of all servers and count them
    """
    state_count = {'UNKNOWN': 0,
                   'WARNING': 0,
                   'CRITICAL': 0,
                   'UNREACHABLE': 0,
                   'DOWN': 0}
    for server in get_enabled_servers():
        state_count['UNKNOWN'] += server.unknown
        state_count['WARNING'] += server.warning
        state_count['CRITICAL'] += server.critical
        state_count['UNREACHABLE'] += server.unreachable
        state_count['DOWN'] += server.down

    return(state_count)


def get_errors():
    """
        find out if any server has any error, used by statusbar error label
    """
    for server in get_enabled_servers():
        if server.has_error:
            return True
            break

    # return default value
    return False


def create_server(server=None):
    # create Server from config
    if server.type not in SERVER_TYPES:
        print(('Server type not supported: %s' % server.type))
        return
    # give argument servername so CentreonServer could use it for initializing MD5 cache
    new_server = SERVER_TYPES[server.type](name=server.name)
    new_server.type = server.type
    new_server.enabled = server.enabled
    new_server.monitor_url = server.monitor_url
    new_server.monitor_cgi_url = server.monitor_cgi_url
    new_server.username = server.username
    new_server.password = server.password
    new_server.use_proxy = server.use_proxy
    new_server.use_proxy_from_os = server.use_proxy_from_os
    new_server.proxy_address = server.proxy_address
    new_server.proxy_username = server.proxy_username
    new_server.proxy_password = server.proxy_password
    new_server.authentication = server.authentication
    new_server.timeout = server.timeout

    # if password is not to be saved ask for it at startup
    if (server.enabled == True and server.save_password == False and server.use_autologin == False):
        new_server.refresh_authentication = True

    # Special FX
    # Centreon
    new_server.use_autologin = server.use_autologin
    new_server.autologin_key = server.autologin_key
    # Icinga
    new_server.use_display_name_host = server.use_display_name_host
    new_server.use_display_name_service = server.use_display_name_service
    # IcingaWeb2
    new_server.no_cookie_auth = server.no_cookie_auth
    # Check_MK Multisite
    new_server.force_authuser = server.force_authuser

    # OP5 api filters
    new_server.host_filter = server.host_filter
    new_server.service_filter = server.service_filter

    # server's individual preparations for HTTP connections (for example cookie creation)
    # is done in GetStatus() method of monitor
    if server.enabled == True:
        new_server.enabled = True

    # start with high thread counter so server update thread does not have to wait
    new_server.thread_counter = conf.update_interval_seconds

    # debug
    if conf.debug_mode == True:
        new_server.Debug(server=server.name, debug="Created server.")

    return new_server


# moved registration process here because of circular dependencies
for server in (CentreonServer, IcingaServer, IcingaWeb2Server, MultisiteServer, NagiosServer,
               Op5MonitorServer, OpsviewServer, ThrukServer, ZabbixServer,
               LivestatusServer, ZenossServer):
    register_server(server)

# create servers
for server in conf.servers.values():
    created_server = create_server(server)
    if created_server is not None:
        servers[server.name] = created_server
        # for the next time no auth needed
        servers[server.name].refresh_authentication = False
