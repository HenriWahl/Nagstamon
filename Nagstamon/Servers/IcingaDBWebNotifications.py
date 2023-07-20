# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2023 Henri Wahl <henri@nagstamon.de> et al.
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

# Initial implementation by Marcus Mönnig
#
# This Server class connects against IcingaWeb2. The monitor URL in the setup should be
# something like http://icinga2/icingaweb2
#
# Status/TODOs:
#
# * The IcingaWeb2 API is not implemented yet, so currently this implementation uses
#   two HTTP requests per action. The first fetches the HTML, then the form data is extracted and
#   then a second HTTP POST request is made which actually executed the action.
#   Once IcingaWeb2 has an API, it's probably the better choice.


from Nagstamon.Servers.Generic import GenericServer
import urllib.parse
import sys
import json
import datetime
import socket

from bs4 import BeautifulSoup
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Config import (conf,
                              AppInfo)
from Nagstamon.Helpers import webbrowser_open
from Nagstamon.Servers.IcingaDBWeb import IcingaDBWebServer


def strfdelta(tdelta, fmt):
    d = {'days': tdelta.days}
    d['hours'], rem = divmod(tdelta.seconds, 3600)
    d['minutes'], d['seconds'] = divmod(rem, 60)
    return fmt.format(**d)


class IcingaDBWebNotificationsServer(IcingaDBWebServer):

    """Read data from IcingaDB in IcingaWeb via the Notification endpoint."""

    TYPE = 'IcingaDBWebNotifications'

    def _get_status(self) -> Result:
        """Update internal status variables.

        This method updates self.new_host. It will not return any status.
        It will return an empty Result object on success or a Result with an error on error.
        """
        try:
            return self._update_new_host_content()
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

    def _update_new_host_content(self) -> Result:
        """Update self.new_host based on icinga notifications."""
        notification_url = "{}/icingadb/notifications?{}&history.event_time>{} ago&format=json".format(
            self.monitor_cgi_url, self.notification_filter, self.notification_lookback)
        health_url = '{}/health?format=json'.format(self.monitor_cgi_url)
        result = self.FetchURL(notification_url, giveback='raw')

        # check if any error occurred
        potential_error = self.check_for_error(result.result, result.error, result.status_code)
        if potential_error:
            return potential_error

        # HEALTH CHECK
        health_result = self.FetchURL(health_url, giveback='raw')
        if health_result.status_code == 200:
            # we already got check results so icinga is unlikely down. do not break it without need.
            monitoring_health_results = json.loads(health_result.result)
            if monitoring_health_results["status"] != "success":
                errors = [e["message"] for e in monitoring_health_results["data"] if e["state"] != 0]
                return Result(result="UNKNOWN",
                              error='Icinga2 not healthy: {}'.format("; ".join(errors)))

        self.new_hosts = {}

        notifications = json.loads(result.result)

        for notification in reversed(notifications):
            if notification["object_type"] == "host":
                # host
                if not self.use_display_name_host:
                    # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                    # better be name instead of display_name
                    host_name = notification['host']['name']
                else:
                    # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                    # problems with that so here we go with extra display_name option
                    host_name = notification['host']['display_name']

                status_type = notification['host']["state_type"]

                if status_type == 'hard':
                    status_numeric = int(notification['host']['state']['hard_state'])
                else:
                    status_numeric = int(notification['host']['state']['soft_state'])

                if status_numeric not in (1, 2):
                    try:
                        del self.new_hosts[host_name]
                    except KeyError:
                        pass
                    continue

                self.new_hosts[host_name] = GenericHost()
                self.new_hosts[host_name].name = host_name
                self.new_hosts[host_name].server = self.name
                self.new_hosts[host_name].status_type = status_type

                self.new_hosts[host_name].status = self.STATES_MAPPING['hosts'][status_numeric]
                self.new_hosts[host_name].last_check = datetime.datetime.fromtimestamp(int(float(notification['host']['state']['last_update'])))
                self.new_hosts[host_name].attempt = "{}/{}".format(notification['host']['state']['check_attempt'],notification['host']['max_check_attempts'])
                self.new_hosts[host_name].status_information = BeautifulSoup(notification['host']['state']['output'].replace('\n', ' ').strip(), 'html.parser').text
                self.new_hosts[host_name].passiveonly = not int(notification['host'].get('active_checks_enabled') or '0')
                self.new_hosts[host_name].notifications_disabled = not int(notification['host'].get('notifications_enabled') or '0')
                self.new_hosts[host_name].flapping = bool(int(notification['host']['state']['is_flapping'] or 0))
                #s['state']['is_acknowledged'] can be null, 0, 1, or 'sticky'
                self.new_hosts[host_name].acknowledged = bool(int(notification['host']['state']['is_acknowledged'].replace('sticky', '1') or 0))
                self.new_hosts[host_name].scheduled_downtime = bool(int(notification['host']['state']['in_downtime'] or 0))

                # extra Icinga properties to solve https://github.com/HenriWahl/Nagstamon/issues/192
                # acknowledge needs host_description and no display name
                self.new_hosts[host_name].real_name = notification['host']['name']

                # Icinga only updates the attempts for soft states. When hard state is reached, a flag is set and
                # attemt is set to 1/x.
                if status_type == 'hard':
                    try:
                        self.new_hosts[host_name].attempt = "{0}/{0}".format(notification['host']['max_check_attempts'])
                    except Exception:
                        self.new_hosts[host_name].attempt = "HARD"

                # extra duration needed for calculation
                if notification['host']['state']['last_state_change'] is not None and notification['host']['state']['last_state_change'] != 0:
                    duration = datetime.datetime.now() - datetime.datetime.fromtimestamp(int(float(notification['host']['state']['last_state_change'])))
                    self.new_hosts[host_name].duration = strfdelta(duration,'{days}d {hours}h {minutes}m {seconds}s')
                else:
                    self.new_hosts[host_name].duration = 'n/a'
            elif notification["object_type"] == "service":
                if not self.use_display_name_host:
                    # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                    # better be name instead of display_name
                    host_name = notification['host']['name']
                else:
                    # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                    # problems with that so here we go with extra display_name option
                    host_name = notification['host']['display_name']

                status_type = notification['service']["state"]["state_type"]
                service_name = notification['service']['display_name']

                if status_type == 'hard':
                    status_numeric = int(notification['service']['state']['hard_state'])
                else:
                    status_numeric = int(notification['service']['state']['soft_state'])

                if status_numeric not in (1, 2, 3):
                    try:
                        del self.new_hosts[host_name].services[service_name]
                        if not self.new_hosts[host_name].services:
                            del self.new_hosts[host_name]
                    except KeyError:
                        pass
                    continue

                # host objects contain service objects
                if not host_name in self.new_hosts:
                    self.new_hosts[host_name] = GenericHost()
                    self.new_hosts[host_name].name = host_name
                    self.new_hosts[host_name].status = 'UP'
                    # extra Icinga properties to solve https://github.com/HenriWahl/Nagstamon/issues/192
                    # acknowledge needs host_description and no display name
                    self.new_hosts[host_name].real_name = notification['host']['name']

                # if a service does not exist create its object
                self.new_hosts[host_name].services[service_name] = GenericService()
                self.new_hosts[host_name].services[service_name].host = host_name
                self.new_hosts[host_name].services[service_name].name = service_name
                self.new_hosts[host_name].services[service_name].server = self.name
                self.new_hosts[host_name].services[service_name].status_type = status_type

                self.new_hosts[host_name].services[service_name].status = self.STATES_MAPPING['services'][status_numeric]

                self.new_hosts[host_name].services[service_name].last_check = datetime.datetime.fromtimestamp(int(float(notification['service']['state']['last_update'])))
                self.new_hosts[host_name].services[service_name].status_information = BeautifulSoup(notification['service']['state']['output'].replace('\n', ' ').strip(), 'html.parser').text
                self.new_hosts[host_name].services[service_name].passiveonly = not int(notification['service'].get('active_checks_enabled') or '0')
                self.new_hosts[host_name].services[service_name].notifications_disabled = not int(notification['service'].get('notifications_enabled') or '0')
                self.new_hosts[host_name].services[service_name].flapping = bool(int(notification['service']['state']['is_flapping'] or 0))
                #s['state']['is_acknowledged'] can be null, 0, 1, or 'sticky'
                self.new_hosts[host_name].services[service_name].acknowledged = bool(int(notification['service']['state']['is_acknowledged'].replace('sticky', '1') or 0))
                self.new_hosts[host_name].services[service_name].scheduled_downtime = bool(int(notification['service']['state']['in_downtime'] or 0))
                self.new_hosts[host_name].services[service_name].unreachable = not bool(int(notification['service']['state']['is_reachable'] or 0))

                if self.new_hosts[host_name].services[service_name].unreachable:
                    self.new_hosts[host_name].services[service_name].status_information += " (SERVICE UNREACHABLE)"

                # extra Icinga properties to solve https://github.com/HenriWahl/Nagstamon/issues/192
                # acknowledge needs service_description and no display name
                self.new_hosts[host_name].services[service_name].real_name = notification['service']['name']

                if status_type == 'hard':
                    # Icinga only updates the attempts for soft states. When hard state is reached, a flag is set and
                    # attempt is set to 1/x.
                    self.new_hosts[host_name].services[service_name].attempt = "{0}/{0}".format(
                        notification['service']['max_check_attempts'])
                else:
                    self.new_hosts[host_name].services[service_name].attempt = "{}/{}".format(
                        notification['service']['state']['check_attempt'],
                        notification['service']['max_check_attempts'])

                # extra duration needed for calculation
                if notification['service']['state']['last_state_change'] is not None and notification['service']['state']['last_state_change'] != 0:
                    duration = datetime.datetime.now() - datetime.datetime.fromtimestamp(int(float(notification['service']['state']['last_state_change'])))
                    self.new_hosts[host_name].services[service_name].duration = strfdelta(duration, '{days}d {hours}h {minutes}m {seconds}s')
                else:
                    self.new_hosts[host_name].services[service_name].duration = 'n/a'

        # return success
        return Result()