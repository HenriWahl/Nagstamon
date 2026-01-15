# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2026 Henri Wahl <henri@nagstamon.de> et al.
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

import json

from . import CentreonAPI
from ..Generic import GenericServer
from Nagstamon.config import conf

class CentreonServer(GenericServer):
    """
    Use this class as switch
    """
    TYPE = 'Centreon'
    def __init__(self, **kwds):
        # like all servers we need to initialize Generic
        GenericServer.__init__(self, **kwds)
        # due to not being initialized right now we need to access config directly to get this instance's config
        server_conf = conf.servers.get(kwds.get('name'))
        if server_conf.enabled:
            self.authentication = conf.servers[self.get_name()].authentication
            # because auf being very early in init process the property ignore_cert is not known yet
            # add it here to be able to fetch URL and ignore certs if activated
            self.ignore_cert = conf.servers[self.get_name()].ignore_cert
            self.custom_cert_use = conf.servers[self.get_name()].custom_cert_use
            # This URL exists at least from Centreon 22.x - if not accessible it must be legacy
            versions_raw = self.fetch_url(f'{conf.servers[self.get_name()].monitor_cgi_url}/api/latest/platform/versions', no_auth=True, giveback='raw')
            self.debug(server='[' + self.get_name() + ']', debug='Page retrieval to detect the version, status code : %s' % (str(versions_raw.status_code)))
            if versions_raw.status_code == 200:
                try:
                    data = json.loads(versions_raw.result)
                except Exception as e:
                    self.debug(server='[' + self.get_name() + ']', debug='Page retrieval to detect the version, ERROR when decoding JSON')
                    self.enable = False
                    self.isChecking = False
                    return None

                ver_major = int(data["web"]["major"])
                ver_minor = int(data["web"]["minor"])
                # API V2 is usable only after 21.04 (not tested), ressources endpoint is buggy in 20.10
                if ver_major >= 21:
                    self.debug(server='[' + self.get_name() + ']', debug='Loading class API, Centreon version : ' + str(ver_major) + '.' + str(ver_minor))
                    from .CentreonAPI import CentreonServer as CentreonServerReal
                elif ver_major < 21:
                    # Fallback to Legacy
                    self.debug(server='[' + self.get_name() + ']', debug='Loading class LEGACY, Centreon version : ' + str(ver_major) + '.' + str(ver_minor))
                    from .CentreonLegacy import CentreonServer as CentreonServerReal
                else:
                    self.debug(server='[' + self.get_name() + ']', debug='Something wrong happens with Centreon, version detected : ' + str(ver_major) + '.' + str(ver_minor))
                    self.enable = False
                    self.isChecking = False
                    return None
            else:
                # Try to check if only it’s a Centreon
                versions_raw = self.fetch_url(f'{server_conf.monitor_cgi_url}/main.php', no_auth=True, giveback='raw')
                if versions_raw.status_code == 200:
                    from .CentreonLegacy import CentreonServer as CentreonServerReal
                    self.debug(server='[' + self.get_name() + ']', debug='Loading class LEGACY, Centreon version will be checked later')
                else:
                    self.debug(server='[' + self.get_name() + ']', debug='The URL given is not a Centreon')
                    self.enable = False
                    self.isChecking = False
                    return None

            # kind of mad but helps the servers/__init__.py to detect if there is any other class to be used
            self.ClassServerReal = CentreonServerReal
