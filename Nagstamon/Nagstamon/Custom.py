# -*- coding: utf-8 -*-

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

""" Module for implementing custom servers,
columns and other stuff.
Imported in GUI module.
"""
from Nagstamon.Actions import register_server

from Nagstamon.Server.Nagios import NagiosServer
from Nagstamon.Server.Centreon import CentreonServer
from Nagstamon.Server.Icinga import IcingaServer
from Nagstamon.Server.Multisite import MultisiteServer
from Nagstamon.Server.op5Monitor import Op5MonitorServer
from Nagstamon.Server.Opsview import OpsviewServer
from Nagstamon.Server.Thruk import ThrukServer
from Nagstamon.Server.Zabbix import ZabbixServer


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

