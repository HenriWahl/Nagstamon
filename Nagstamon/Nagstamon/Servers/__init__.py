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

"""Module Servers"""

# contains dict with available server classes
# key is type of server, value is server class
# used for automatic config generation
# and holding this information in one place
SERVER_TYPES = []

def register_server(server):
    """ Once new server class in created,
    should be registered with this function
    for being visible in config and
    accessible in application.
    """
    if server.TYPE not in [x[0] for x in SERVER_TYPES]:
        SERVER_TYPES.append((server.TYPE, server))


def get_registered_servers():
    """ Returns available server classes dict """
    return dict(SERVER_TYPES)


def get_registered_server_type_list():
    """ Returns available server type name list with order of registering """
    return [x[0] for x in REGISTERED_SERVERS]


# load all existing server types
from Nagstamon.Servers.Nagios import NagiosServer
from Nagstamon.Servers.Centreon import CentreonServer
from Nagstamon.Servers.Icinga import IcingaServer
from Nagstamon.Servers.Multisite import MultisiteServer
from Nagstamon.Servers.op5Monitor import Op5MonitorServer
from Nagstamon.Servers.Opsview import OpsviewServer
from Nagstamon.Servers.Thruk import ThrukServer
from Nagstamon.Servers.Zabbix import ZabbixServer


# moved registration process because of circular dependencies
# order of registering affects sorting in server type list in add new server dialog
register_server(NagiosServer)
register_server(CentreonServer)
register_server(MultisiteServer)
register_server(IcingaServer)
register_server(Op5MonitorServer)
register_server(OpsviewServer)
register_server(ThrukServer)
register_server(ZabbixServer)
