# encoding: utf-8

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

import sys
import json
import urllib
import datetime
import time

from datetime import datetime

from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer, not_empty


def human_duration(start):
    """
    transform timestamp to human readable
    some changes necessary due to https://github.com/HenriWahl/Nagstamon/issues/93
    - move definition of stop out of def() statement because it kept static
    """
    stop = time.time()
    if stop <= start:
        return "n/a"
    else:
        ret = ''
    first = True
    secs = stop - start
    units = 'wdhms'
    divisors = {'w': 86400 * 7, 'd': 86400, 'h': 3600, 'm': 60, 's': 1}
    for unit in units:
        divisor = divisors[unit]
        if secs < divisor:
            continue
        amount = int(secs / divisor)
        secs %= divisor
        if not first:
            ret += ' '
        ret += "%d%c" % (amount, unit)
        first = False
    return ret


class Op5MonitorServer(GenericServer):
    """
        object of Nagios server - when nagstamon will be able to poll various servers this
        will be useful
        As Nagios is the default server type all its methods are in GenericServer
    """

    TYPE = 'op5Monitor'
    api_count='/api/filter/count/?query='
    api_query='/api/filter/query/?query='
    api_cmd='/api/command'

    api_svc_col = []
    api_host_col = []
    api_host_col.append('acknowledged')
    api_host_col.append('active_checks_enabled')
    api_host_col.append('alias')
    api_host_col.append('current_attempt')
    api_host_col.append('is_flapping')
    api_host_col.append('last_check')
    api_host_col.append('last_state_change')
    api_host_col.append('max_check_attempts')
    api_host_col.append('name')
    api_host_col.append('notifications_enabled')
    api_host_col.append('plugin_output')
    api_host_col.append('scheduled_downtime_depth')
    api_host_col.append('state')

    api_svc_col.append('acknowledged')
    api_svc_col.append('active_checks_enabled')
    api_svc_col.append('current_attempt')
    api_svc_col.append('description')
    api_svc_col.append('host.name')
    api_svc_col.append('host.state')
    api_svc_col.append('host.active_checks_enabled')
    api_svc_col.append('is_flapping')
    api_svc_col.append('last_check')
    api_svc_col.append('last_state_change')
    api_svc_col.append('max_check_attempts')
    api_svc_col.append('notifications_enabled')
    api_svc_col.append('plugin_output')
    api_svc_col.append('scheduled_downtime_depth')
    api_svc_col.append('state')

    api_default_svc_query='[services] state !=0'
    api_default_svc_query+=' or host.state != 0'
    api_default_svc_query+='&columns=%s' % (','.join(api_svc_col))
    api_default_svc_query+='&format=json'

    api_default_host_query='[hosts] state !=0'
    api_default_host_query+='&columns=%s' % (','.join(api_host_col))
    api_default_host_query+='&format=json'

    api_default_host_query = api_default_host_query.replace(" ", "%20")
    api_default_svc_query = api_default_svc_query.replace(" ", "%20")

    # autologin is used only by Centreon
    DISABLED_CONTROLS = ["label_monitor_cgi_url",
                         "input_entry_monitor_cgi_url",
                         "input_checkbutton_use_autologin",
                         "label_autologin_key",
                         "input_entry_autologin_key",
                         "input_checkbutton_use_display_name_host",
                         "input_checkbutton_use_display_name_service"]

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS = { "monitor": "$MONITOR$/monitor",\
                    "hosts": "$MONITOR$/monitor/index.php/listview?q=%s" % '[hosts] all and state != 0'.replace(" ", "%20"),\
                    "services": "$MONITOR$/monitor/index.php/listview?q=%s" % '[services] all and state != 0'.replace(" ", "%20"),\
                    "history": "$MONITOR$/monitor/index.php/alert_history/generate"}

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Downtime"]
        self.STATUS_SVC_MAPPING = {'0':'OK', '1':'WARNING', '2':'CRITICAL', '3':'UNKNOWN'}
        self.STATUS_HOST_MAPPING = {'0':'UP', '1':'DOWN', '2':'UNREACHABLE'}


    def _get_status(self):
        """
        Get status from op5 Monitor Server
        """
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"hosts":[], "services":[]}

        # new_hosts dictionary
        self.new_hosts = dict()

        # Fetch api listview with filters
        try:

            # Fetch Host info
            result = self.FetchURL(self.monitor_url + self.api_count + self.api_default_host_query, giveback="raw")
            data = json.loads(result.result)
            if data['count']:
                count = data['count']
                result = self.FetchURL(self.monitor_url + self.api_query + self.api_default_host_query + '&limit=' + str(count), giveback="raw")
                data = json.loads(result.result)
                n = dict()
                for api in data:
                    n['host'] = api['name']
                    n["acknowledged"] = api['acknowledged']
                    n["flapping"] = api['is_flapping']
                    n["notifications_disabled"] = 0 if api['notifications_enabled'] else 1
                    n["passiveonly"] = 0 if api['active_checks_enabled'] else 1
                    n["scheduled_downtime"] = 1 if api['scheduled_downtime_depth'] else 0
                    n['attempt'] = "%s/%s" % (str(api['current_attempt']), str(api['max_check_attempts']))
                    n['duration'] = human_duration(api['last_state_change'])
                    n['last_check'] = datetime.fromtimestamp(int(api['last_check'])).strftime('%Y-%m-%d %H:%M:%S')
                    n['status'] = self.STATUS_HOST_MAPPING[str(api['state'])]
                    n['status_information'] = api['plugin_output']
                    n['status_type'] = api['state']

                    if not self.new_hosts.has_key(n['host']):
                        self.new_hosts[n['host']] = GenericHost()
                        self.new_hosts[n['host']].name = n['host']
                        self.new_hosts[n['host']].acknowledged = n["acknowledged"]
                        self.new_hosts[n['host']].attempt = n['attempt']
                        self.new_hosts[n['host']].duration = n['duration']
                        self.new_hosts[n['host']].flapping = n["flapping"]
                        self.new_hosts[n['host']].last_check = n['last_check']
                        self.new_hosts[n['host']].notifications_disabled = n["notifications_disabled"]
                        self.new_hosts[n['host']].passiveonly = n["passiveonly"]
                        self.new_hosts[n['host']].scheduled_downtime = n["scheduled_downtime"]
                        self.new_hosts[n['host']].status = n['status']
                        self.new_hosts[n['host']].status_information = n['status_information'].replace("\n", " ").strip()
                        self.new_hosts[n['host']].status_type = n['status_type']
                    nagitems['hosts'].append(n)
                del n


            # Fetch services info
            result = self.FetchURL(self.monitor_url + self.api_count + self.api_default_svc_query, giveback="raw")
            data = json.loads(result.result)
            if data['count']:
                count = data['count']
                result = self.FetchURL(self.monitor_url + self.api_query + self.api_default_svc_query + '&limit=' + str(count), giveback="raw")
                data = json.loads(result.result)
                for api in data:
                    n = dict()
                    n['host'] = api['host']['name']
                    n['status'] = self.STATUS_HOST_MAPPING[str(api['host']['state'])]
                    n["passiveonly"] = 0 if api['host']['active_checks_enabled'] else 1

                    if not self.new_hosts.has_key(n['host']):
                        self.new_hosts[n['host']] = GenericHost()
                        self.new_hosts[n['host']].name = n['host']
                        self.new_hosts[n['host']].status = n['status']
                        self.new_hosts[n['host']].passiveonly = n["passiveonly"]

                    n['service'] = api['description']
                    n["acknowledged"] = api['acknowledged']
                    n["flapping"] = api['is_flapping']
                    n["notifications_disabled"] = 0 if api['notifications_enabled'] else 1
                    n["passiveonly"] = 0 if api['active_checks_enabled'] else 1
                    n["scheduled_downtime"] = 1 if api['scheduled_downtime_depth'] else 0
                    n['attempt'] = "%s/%s" % (str(api['current_attempt']), str(api['max_check_attempts']))
                    n['duration'] = human_duration(api['last_state_change'])
                    n['last_check'] = datetime.fromtimestamp(int(api['last_check'])).strftime('%Y-%m-%d %H:%M:%S')
                    n['status_information'] = api['plugin_output']

                    if not self.new_hosts.has_key(n['host']):
                        self.new_hosts[n['host']] = GenericHost()
                        self.new_hosts[n['host']].name = n['host']
                        self.new_hosts[n['host']].status = n['status']

                    if not self.new_hosts[n['host']].services.has_key(n['service']):
                        n['status'] = self.STATUS_SVC_MAPPING[str(api['state'])]

                        self.new_hosts[n['host']].services[n['service']] = GenericService()
                        self.new_hosts[n['host']].services[n['service']].acknowledged = n['acknowledged']
                        self.new_hosts[n['host']].services[n['service']].attempt = n['attempt']
                        self.new_hosts[n['host']].services[n['service']].duration = n['duration']
                        self.new_hosts[n['host']].services[n['service']].flapping = n['flapping']
                        self.new_hosts[n['host']].services[n['service']].host = n['host']
                        self.new_hosts[n['host']].services[n['service']].last_check = n['last_check']
                        self.new_hosts[n['host']].services[n['service']].name = n['service']
                        self.new_hosts[n['host']].services[n['service']].notifications_disabled = n["notifications_disabled"]
                        self.new_hosts[n['host']].services[n['service']].passiveonly = n['passiveonly']
                        self.new_hosts[n['host']].services[n['service']].scheduled_downtime = n['duration']
                        self.new_hosts[n['host']].services[n['service']].scheduled_downtime = n['scheduled_downtime']
                        self.new_hosts[n['host']].services[n['service']].status = n['status']
                        self.new_hosts[n['host']].services[n['service']].status_information = n['status_information'].replace("\n", " ").strip()

                    nagitems['services'].append(n)
                return Result()
        except:
            print "========================================== b0rked =========================================="
            self.isChecking = False
            result,error = self.Error(sys.exc_info())
            print error
            return Result(result=result, error=error)

        return Result()


    def open_tree_view(self, host, service):
        if not service:
            url = "%s/monitor/index.php/extinfo/details?host=%s" % (self.monitor_url, host)
        else:
            url = "%s/monitor/index.php/extinfo/details?host=%s&service=%s" % (self.monitor_url, host, service)
        action = Actions.Action(type="browser", string=url, conf=self.conf, server=self, host=host, service=service)
        action.run()

    def get_start_end(self, host):
        return time.strftime("%Y-%m-%d %H:%M"), time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + 7200))


    def send_command(self, command, params=False):
        url = self.monitor_url + self.api_cmd + '/' + command
        if 'service_description' in params.keys():
            action = Actions.Action(
                type="url-post",
                string=url,
                cgi_data=urllib.urlencode(params),
                conf=self.conf,
                server=self,
                host=params["host_name"],
                service=params["service_description"],
            )
        else:
            action = Actions.Action(
                type="url-post",
                string=url,
                cgi_data=urllib.urlencode(params),
                conf=self.conf,
                server=self,
                host=params["host_name"],
            )
        action.run()


    def _set_recheck(self, host, service):
        params = {'host_name': host, 'check_time': int(time.time())}
        if not service:
            command = 'SCHEDULE_HOST_CHECK'
        else:
            if self.hosts[host].services[service].is_passive_only():
                return
            command = 'SCHEDULE_SVC_CHECK'
            params['service_description'] = service
        self.send_command(command, params)


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services):
        params = {'host_name': host, 'sticky': int(sticky),
                  'notify': int(notify), 'persistent': int(persistent),
                  'comment': comment}
        if not service:
            command = 'ACKNOWLEDGE_HOST_PROBLEM'
        else:
            params['service_description'] = service
            command = 'ACKNOWLEDGE_SVC_PROBLEM'
        self.send_command(command, params)


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        start_time = int(time.mktime(time.strptime(start_time, "%Y-%m-%d %H:%M")))
        end_time = int(time.mktime(time.strptime(end_time, "%Y-%m-%d %H:%M")))
        duration = end_time - start_time
        params = {'host_name': host, 'comment': comment,
                  'fixed': fixed, 'trigger_id': '0', 'start_time': start_time,
                  'end_time': end_time, 'duration': duration}
        if not service:
            command = 'SCHEDULE_HOST_DOWNTIME'
        else:
            command = 'SCHEDULE_SVC_DOWNTIME'
            params['service_description'] = service
        self.send_command(command, params)
