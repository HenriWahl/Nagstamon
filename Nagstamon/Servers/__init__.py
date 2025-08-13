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

"""Module Servers"""

import urllib.request
import urllib.error
import urllib.parse

from collections import OrderedDict

# load all existing server types
from Nagstamon.Servers.Nagios import NagiosServer
from Nagstamon.Servers.Centreon import CentreonServer
from Nagstamon.Servers.Icinga import IcingaServer
from Nagstamon.Servers.IcingaWeb2 import IcingaWeb2Server
from Nagstamon.Servers.IcingaDBWeb import IcingaDBWebServer
from Nagstamon.Servers.IcingaDBWebNotifications import IcingaDBWebNotificationsServer
from Nagstamon.Servers.Icinga2API import Icinga2APIServer
from Nagstamon.Servers.Multisite import MultisiteServer
from Nagstamon.Servers.op5Monitor import Op5MonitorServer
from Nagstamon.Servers.Opsview import OpsviewServer
from Nagstamon.Servers.Thruk import ThrukServer
from Nagstamon.Servers.Zabbix import ZabbixServer
from Nagstamon.Servers.ZabbixProblemBased import ZabbixProblemBasedServer
from Nagstamon.Servers.Livestatus import LivestatusServer
from Nagstamon.Servers.Zenoss import ZenossServer
from Nagstamon.Servers.Monitos3 import Monitos3Server
from Nagstamon.Servers.Monitos4x import Monitos4xServer
from Nagstamon.Servers.SnagView3 import SnagViewServer
from Nagstamon.Servers.Sensu import SensuServer
from Nagstamon.Servers.SensuGo import SensuGoServer
from Nagstamon.Servers.Prometheus import PrometheusServer
from Nagstamon.Servers.Alertmanager import AlertmanagerServer

from Nagstamon.config import conf

from Nagstamon.helpers import STATES


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
    return [x for x in servers.values() if x.enabled is True]


def get_worst_status():
    """
        get worst status of all servers
    """
    worst_status = 'UP'
    for server in get_enabled_servers():
        worst_status_current = server.get_worst_status_current()
        if STATES.index(worst_status_current) > STATES.index(worst_status):
            worst_status = worst_status_current
        del worst_status_current
    return worst_status


def get_status_count():
    """
        get all states of all servers and count them
    """
    state_count = {'UNKNOWN': 0,
                   'INFORMATION': 0,
                   'WARNING': 0,
                   'AVERAGE': 0,
                   'HIGH': 0,
                   'CRITICAL': 0,
                   'DISASTER': 0,
                   'UNREACHABLE': 0,
                   'DOWN': 0}
    for server in get_enabled_servers():
        state_count['UNKNOWN'] += server.unknown
        state_count['INFORMATION'] += server.information
        state_count['WARNING'] += server.warning
        state_count['AVERAGE'] += server.average
        state_count['HIGH'] += server.high
        state_count['CRITICAL'] += server.critical
        state_count['DISASTER'] += server.disaster
        state_count['UNREACHABLE'] += server.unreachable
        state_count['DOWN'] += server.down

    return state_count


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
    # apparently somewhat hacky but at the end works - might be used for others than Centreon as well
    if hasattr(new_server, 'ClassServerReal'):
        new_server = new_server.ClassServerReal(name=server.name)
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

    # SSL/TLS
    new_server.ignore_cert = server.ignore_cert
    new_server.custom_cert_use = server.custom_cert_use
    new_server.custom_cert_ca_file = server.custom_cert_ca_file

    # ECP authentication
    new_server.idp_ecp_endpoint = server.idp_ecp_endpoint

    # if password is not to be saved ask for it at startup
    if (server.enabled is True and server.save_password is False and
            server.use_autologin is False):
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

    # IcingaDBWebNotifications
    new_server.notification_filter = server.notification_filter
    new_server.notification_lookback = server.notification_lookback

    # Checkmk Multisite
    new_server.force_authuser = server.force_authuser
    new_server.checkmk_view_hosts = server.checkmk_view_hosts
    new_server.checkmk_view_services = server.checkmk_view_services

    # OP5 api filters
    new_server.host_filter = server.host_filter
    new_server.service_filter = server.service_filter

    # Opsview hashtag filter and can_change_only option
    new_server.hashtag_filter = server.hashtag_filter
    new_server.can_change_only = server.can_change_only

    # Zabbix
    new_server.use_description_name_service = server.use_description_name_service

    # Prometheus & Alertmanager
    new_server.alertmanager_filter = server.alertmanager_filter
    new_server.map_to_hostname = server.map_to_hostname
    new_server.map_to_servicename = server.map_to_servicename
    new_server.map_to_status_information = server.map_to_status_information
    new_server.map_to_ok = server.map_to_ok
    new_server.map_to_unknown = server.map_to_unknown
    new_server.map_to_warning = server.map_to_warning
    new_server.map_to_critical = server.map_to_critical
    new_server.map_to_down = server.map_to_down

    # Thruk
    new_server.disabled_backends = server.disabled_backends

    # server's individual preparations for HTTP connections (for example cookie creation)
    # is done in GetStatus() method of monitor
    if server.enabled is True:
        new_server.enabled = True

    # start with high thread counter so server update thread does not have to wait
    new_server.thread_counter = conf.update_interval_seconds

    # debug
    if conf.debug_mode is True:
        new_server.debug(server=server.name, debug="Created server.")

    return new_server


# moved registration process here because of circular dependencies
servers_list = [AlertmanagerServer,
                CentreonServer,
                IcingaServer,
                IcingaDBWebServer,
                IcingaDBWebNotificationsServer,
                IcingaWeb2Server,
                Icinga2APIServer,
                LivestatusServer,
                Monitos3Server,
                Monitos4xServer,
                MultisiteServer,
                NagiosServer,
                Op5MonitorServer,
                OpsviewServer,
                PrometheusServer,
                SensuGoServer,
                SensuServer,
                SnagViewServer,
                ThrukServer,
                ZabbixProblemBasedServer,
                ZabbixServer,
                ZenossServer]

for server in servers_list:
    register_server(server)

# create servers
for server in conf.servers.values():
    created_server = create_server(server)
    if created_server is not None:
        servers[server.name] = created_server
        # for the next time no auth needed
        servers[server.name].refresh_authentication = False
