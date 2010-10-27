# -*- coding: utf-8 -*-

""" Module for implementing custom servers,
columns and other stuff.
Imported in nagstamonGUI module.
"""

from nagstamonActions import register_server
from nagstamonServer.Nagios import NagiosServer
from nagstamonServer.Icinga import IcingaServer
from nagstamonServer.Opsview import OpsviewServer
from nagstamonServer.Centreon import CentreonServer


# moved registration process because of circular dependencies
# order of registering affects sorting in server type list in add new server dialog
register_server(NagiosServer)
register_server(IcingaServer)
register_server(OpsviewServer)
register_server(CentreonServer)
