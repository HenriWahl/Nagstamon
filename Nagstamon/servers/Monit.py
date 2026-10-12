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

"""Read service status from Monit's built-in HTTP server."""

from datetime import datetime
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

from Nagstamon.helpers import webbrowser_open
from Nagstamon.objects import GenericHost, GenericService, Result
from Nagstamon.servers.Generic import GenericServer


class MonitServer(GenericServer):
    TYPE = 'Monit'
    MENU_ACTIONS = ['Monitor']
    BROWSER_URLS = dict.fromkeys(
        ('monitor', 'hosts', 'services', 'history'), '$MONITOR$')

    # Bit positions in Monit's XML status/status_hint (EventClass_T).
    EVENT_NAMES = (
        'Checksum', 'Resource', 'Timeout', 'Timestamp', 'Size', 'Connection',
        'Permission', 'UID', 'GID', 'Does not exist', 'Invalid type', 'Data',
        'Execution', 'Filesystem flags', 'ICMP', 'Content', 'Instance',
        'Action', 'PID', 'Parent PID', 'Heartbeat', 'Exit status', 'Uptime',
        'Link', 'Speed', 'Saturation', 'Download bytes', 'Upload bytes',
        'Download packets', 'Upload packets', 'Exists',
    )

    def init_config(self):
        """Monit uses the monitor URL directly, without a CGI URL."""

    @classmethod
    def _state(cls, node):
        monitor = int(node.findtext('monitor'))
        if monitor == 0:
            return 'UNKNOWN', 'Not monitored'
        if monitor & 4:
            return 'UNKNOWN', 'Waiting'
        if monitor & 2:
            return 'UNKNOWN', 'Initializing'
        if monitor != 1:
            return 'UNKNOWN', 'Unknown monitoring state: {}'.format(monitor)

        status = int(node.findtext('status'))
        hint = int(node.findtext('status_hint', '0'))
        if status < 0 or hint < 0:
            raise ValueError('Negative Monit status bitmask')
        if status == 0:
            return 'OK', 'OK'
        messages = [
            '{} {}'.format(name, 'changed' if hint & (1 << bit) else 'failed')
            for bit, name in enumerate(cls.EVENT_NAMES) if status & (1 << bit)
        ]
        unknown = status & ~((1 << len(cls.EVENT_NAMES)) - 1)
        if unknown:
            messages.append('Unknown event bits: {:#x}'.format(unknown))
        return ('CRITICAL' if status & ~hint else 'WARNING'), ' | '.join(messages)

    def _get_status(self):
        self.new_hosts = {}
        response = self.fetch_url(
            self.monitor_url.rstrip('/') + '/_status?format=xml', giveback='raw')
        if response.error or response.status_code >= 400:
            return response
        try:
            root = ElementTree.fromstring(response.result)
            if root.tag != 'monit' or root.find('server') is None:
                raise ValueError('Expected a Monit XML status response')
            hostname = (root.findtext('server/localhostname') or
                        urlsplit(self.monitor_url).hostname or self.name)
            host = GenericHost()
            host.name = hostname
            host.server = self.name
            host.status = 'UP'
            # All Monit checks, including system resource checks, are services.
            # A resource failure does not mean that the machine is down.
            for node in root.findall('service'):
                name = node.findtext('name')
                if not name:
                    raise ValueError('Monit service has no name')
                service = GenericService()
                service.name = name
                service.host = hostname
                service.server = self.name
                service.status, service.status_information = self._state(node)
                service.status_type = 'hard'
                # In Monit, passive mode still runs checks, but disables repair.
                service.passiveonly = int(node.findtext('monitor')) == 0
                collected = node.findtext('collected_sec')
                if collected:
                    service.last_check = datetime.fromtimestamp(int(collected)).isoformat(' ')
                service.attempt = '1/1'
                host.services[name] = service
            self.new_hosts = {hostname: host}
        except (ElementTree.ParseError, ValueError, TypeError, OverflowError, OSError) as error:
            return Result(result='ERROR', error='Invalid Monit status: {}'.format(error))
        return Result()

    def open_monitor(self, host, service=''):
        url = self.monitor_url.rstrip('/') + '/'
        if service:
            url += quote(service, safe='')
        webbrowser_open(url)
