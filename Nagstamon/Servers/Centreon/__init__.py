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

import json

from . import CentreonAPI
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
        if server_conf and server_conf.enabled:
            # This URL exists on Centreon 22.x - if not accessible it must be legacy
            versions_raw = self.FetchURL(f'{server_conf.monitor_cgi_url}/api/latest/platform/versions', no_auth=True, giveback='raw')
            self.Debug(server='[' + self.get_name() + ']', debug='Status code %s' % (str(versions_raw.status_code)))
            if versions_raw.status_code == 200:
                # API V2 is usable only after 20.10
                data = json.loads(versions_raw.result)
                ver_major = int(data["web"]["major"])
                ver_minor = int(data["web"]["minor"])
                if (ver_major > 20) or (ver_major == 20 and ver_minor == 10):
                    self.Debug(server='[' + self.get_name() + ']', debug='>>>>>>>>>>>>>>>> API ' + str(ver_major) + ' ' + str(ver_minor))
                    from .CentreonAPI import CentreonServer as CentreonServerReal
                else:
                    self.Debug(server='[' + self.get_name() + ']', debug='>>>>>>>>>>>>>>>> LEGACY')
                    from .CentreonLegacy import CentreonServer as CentreonServerReal
            else:
                from .CentreonLegacy import CentreonServer as CentreonServerReal
                self.Debug(server='[' + self.get_name() + ']', debug='>>>>>>>>>>>>>>>> LEGACY')
            # kind of mad but helps the Servers/__init__.py to detect if there is any other class to be used
            self.ClassServerReal = CentreonServerReal
