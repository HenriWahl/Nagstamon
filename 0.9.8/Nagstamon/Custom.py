# -*- coding: utf-8 -*-

""" Module for implementing custom servers,
columns and other stuff.
Imported in GUI module.
"""
from Nagstamon.Actions import register_server

from Nagstamon.Server.Nagios import NagiosServer
from Nagstamon.Server.Centreon import CentreonServer
from Nagstamon.Server.Icinga import IcingaServer
from Nagstamon.Server.Multisite import MultisiteServer
from Nagstamon.Server.Ninja import NinjaServer
from Nagstamon.Server.Opsview import OpsviewServer


# moved registration process because of circular dependencies
# order of registering affects sorting in server type list in add new server dialog
register_server(NagiosServer)
register_server(CentreonServer)
register_server(MultisiteServer)
register_server(IcingaServer)
register_server(NinjaServer)
register_server(OpsviewServer)

