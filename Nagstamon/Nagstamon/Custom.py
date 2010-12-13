# -*- coding: utf-8 -*-

""" Module for implementing custom servers,
columns and other stuff.
Imported in GUI module.
"""
from Nagstamon.Actions import register_server

from Nagstamon.Server.Nagios import NagiosServer
from Nagstamon.Server.Icinga import IcingaServer
from Nagstamon.Server.Opsview import OpsviewServer
from Nagstamon.Server.Centreon import CentreonServer

# moved registration process because of circular dependencies
# order of registering affects sorting in server type list in add new server dialog
register_server(NagiosServer)
register_server(IcingaServer)
register_server(OpsviewServer)
register_server(CentreonServer)
