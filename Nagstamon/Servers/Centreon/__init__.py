# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2022 Henri Wahl <henri@nagstamon.de> et al.
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


from ..Generic import GenericServer
from Nagstamon.Config import conf


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
        if server_conf:
            # This URL exists on Centreon 22x - if not accessiblie it must be legacy
            versions_raw = self.FetchURL(f'{server_conf.monitor_cgi_url}/api/latest/platform/versions', no_auth=True)
            if versions_raw.status_code == 200:
                from .CentreonAPI import CentreonServer as CentreonServerReal
            else:
                from .CentreonLegacy import CentreonServer as CentreonServerReal
            CentreonServerReal.__init__(self, name=kwds.get('name'))
