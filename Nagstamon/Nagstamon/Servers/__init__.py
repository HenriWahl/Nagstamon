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

import urllib.request, urllib.error, urllib.parse
from collections import OrderedDict

# load all existing server types
from Nagstamon.Servers.Nagios import NagiosServer
from Nagstamon.Servers.Centreon import CentreonServer
from Nagstamon.Servers.Icinga import IcingaServer
from Nagstamon.Servers.Multisite import MultisiteServer
from Nagstamon.Servers.op5Monitor import Op5MonitorServer
from Nagstamon.Servers.Opsview import OpsviewServer
from Nagstamon.Servers.Thruk import ThrukServer
from Nagstamon.Servers.Zabbix import ZabbixServer

from Nagstamon.Config import conf

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


def CreateServer(server=None):
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
    # add resources, needed for auth dialog
    #new_server.Resources = resources
    new_server.username = server.username
    new_server.password = server.password
    new_server.use_proxy = server.use_proxy
    new_server.use_proxy_from_os = server.use_proxy_from_os
    new_server.proxy_address = server.proxy_address
    new_server.proxy_username = server.proxy_username
    new_server.proxy_password = server.proxy_password

    # if password is not to be saved ask for it at startup
    if (server.enabled == "True" and server.save_password == "False" and server.use_autologin == "False" ):
        new_server.refresh_authentication = True

    # access to thread-safe debug queue
    #new_server.debug_queue = debug_queue

    """
    # use server-owned attributes instead of redefining them with every request
    new_server.passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    new_server.passman.add_password(None, server.monitor_url, server.username, server.password)
    new_server.passman.add_password(None, server.monitor_cgi_url, server.username, server.password)
    new_server.basic_handler = urllib.request.HTTPBasicAuthHandler(new_server.passman)
    new_server.digest_handler = urllib.request.HTTPDigestAuthHandler(new_server.passman)
    new_server.proxy_auth_handler = urllib.request.ProxyBasicAuthHandler(new_server.passman)

    if str(new_server.use_proxy) == "False":
        # use empty proxyhandler
        new_server.proxy_handler = urllib.request.ProxyHandler({})
    elif str(server.use_proxy_from_os) == "False":
        # if proxy from OS is not used there is to add a authenticated proxy handler
        new_server.passman.add_password(None, new_server.proxy_address, new_server.proxy_username, new_server.proxy_password)
        new_server.proxy_handler = urllib.request.ProxyHandler({"http": new_server.proxy_address, "https": new_server.proxy_address})
        new_server.proxy_auth_handler = urllib.request.ProxyBasicAuthHandler(new_server.passman)
    """

    # Special FX
    # Centreon
    new_server.use_autologin = server.use_autologin
    new_server.autologin_key = server.autologin_key
    # Icinga
    new_server.use_display_name_host = server.use_display_name_host
    new_server.use_display_name_service = server.use_display_name_service

    """
    # create permanent urlopener for server to avoid memory leak with millions of openers
    new_server.urlopener = BuildURLOpener(new_server)
    """

    # server's individual preparations for HTTP connections (for example cookie creation), version of monitor
    if server.enabled == True:
        new_server.init_HTTP()

    # debug
    if conf.debug_mode == True:
        new_server.Debug(server=server.name, debug="Created server.")

    return new_server


# moved registration process here because of circular dependencies
for server in (CentreonServer, IcingaServer, MultisiteServer, NagiosServer,
               Op5MonitorServer, OpsviewServer, ThrukServer, ZabbixServer):
    register_server(server)

# create servers
#for server in list(conf.servers.values()):
for server in conf.servers.values():
    """
    if ( server.use_autologin == "False" and server.save_password == "False" and server.enabled == "True" ) or ( server.enabled == "True" and server.use_autologin == "True" and server.autologin_key == "" ):
        # the auth dialog will fill the server's username and password with the given values
        if platform.system() == "Darwin":
            # MacOSX gets instable with default theme "Clearlooks" so use custom one with theme "Murrine"
            gtk.rc_parse_string('gtk-theme-name = "Murrine"')

        GUI.AuthenticationDialog(server=server, Resources=Resources, conf=conf, debug_queue=debug_queue)
    """
    created_server = CreateServer(server)

    if created_server is not None:
        servers[server.name] = created_server
        # for the next time no auth needed
        servers[server.name].refresh_authentication = False
