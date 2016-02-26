#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Zabbix.py based on Check_MK Multisite.py
#
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2010             mk@mathias-kettner.de |
# |                                            lm@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# ails.  You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

# hax0rized by: lm@mathias-kettner.de

import sys
import urllib
import webbrowser
import base64
import time
import datetime

from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer
from Nagstamon.thirdparty.zabbix_api import ZabbixAPI, ZabbixAPIException


class ZabbixError(Exception):
    def __init__(self, terminate, result):
        self.terminate = terminate
        self.result = result


class ZabbixServer(GenericServer):
    """
       special treatment for Zabbix, taken from Check_MK Multisite JSON API
    """
    TYPE = 'Zabbix'
    zapi = None

    # A Monitor CGI URL is not necessary so hide it in settings
    # autologin is used only by Centreon
    DISABLED_CONTROLS = ["label_monitor_cgi_url",
                         "input_entry_monitor_cgi_url",
                         "input_checkbutton_use_autologin",
                         "label_autologin_key",
                         "input_entry_autologin_key",
                         "input_checkbutton_use_display_name_host",
                         "input_checkbutton_use_display_name_service"]


    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Prepare all urls needed by nagstamon - 
        self.urls = {}
        self.statemap = {}

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Recheck", "Acknowledge", "Downtime"]
        self.username = self.conf.servers[self.get_name()].username
        self.password = self.conf.servers[self.get_name()].password


    def _login(self):
        try:
            self.zapi = ZabbixAPI(server=self.monitor_url, path="", log_level=0)
            self.zapi.login(self.username, self.password)
        except ZabbixAPIException:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


    def init_HTTP(self):

        self.statemap = {
            'UNREACH': 'UNREACHABLE',
            'CRIT': 'CRITICAL',
            'WARN': 'WARNING',
            'UNKN': 'UNKNOWN',
            'PEND': 'PENDING',
            '0': 'OK',
            '1': 'INFORMATION',
            '2': 'WARNING',
            '5': 'CRITICAL',
            '3': 'AVERAGE',
            '4': 'HIGH'}
        GenericServer.init_HTTP(self)


    def _get_status(self):
        """
        Get status from Nagios Server
        """
        ret = Result()
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services": [], "hosts": []}

        # Create URLs for the configured filters
        if self.zapi is None:
            self._login()

        try:
            hosts = []
            try:
                hosts = self.zapi.host.get(
                    {"output": ["host", "ip", "status", "available", "error", "errors_from"], "filter": {}})
            except:
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)

            for host in hosts:
                n = {
                    'host': host['host'],
                    'status': self.statemap.get(host['available'], host['available']),
                    'last_check': 'n/a',
                    'duration': Actions.HumanReadableDurationFromTimestamp(host['errors_from']),
                    'status_information': host['error'],
                    'attempt': '1/1',
                    'site': '',
                    'address': host['host'],
                }

                # add dictionary full of information about this host item to nagitems
                nagitems["hosts"].append(n)
                # after collection data in nagitems create objects from its informations
                # host objects contain service objects
                if n["host"] not in self.new_hosts:
                    new_host = n["host"]
                    self.new_hosts[new_host] = GenericHost()
                    self.new_hosts[new_host].name = n["host"]
                    self.new_hosts[new_host].status = n["status"]
                    self.new_hosts[new_host].last_check = n["last_check"]
                    self.new_hosts[new_host].duration = n["duration"]
                    self.new_hosts[new_host].attempt = n["attempt"]
                    self.new_hosts[new_host].status_information = n["status_information"]
                    self.new_hosts[new_host].site = n["site"]
                    self.new_hosts[new_host].address = n["address"]
        except ZabbixError:
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        services = []
        groupids = []
        zabbix_triggers = []
        try:
            api_version = self.zapi.api_version()
        except ZabbixAPIException:
            # FIXME Is there a cleaner way to handle this? I just borrowed
            # this code from 80 lines ahead. -- AGV
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            print sys.exc_info()
            return Result(result=result, error=error)

        try:
            response = []
            try:
                #service = self.zapi.trigger.get({"select_items":"extend","monitored":1,"only_true":1,"min_severity":3,"output":"extend","filter":{}})

                triggers_list = []
                if self.monitor_cgi_url:
                    group_list = self.monitor_cgi_url.split(',')

                    #hostgroup_ids = [x['groupid'] for x in self.zapi.hostgroup.get(
                    #    {'output': 'extend',
                    #     'with_monitored_items': True,
                    #     'filter': {"name": group_list}}) if int(x['internal']) == 0]

                    # only without filter there is anything shown at all
                    hostgroup_ids = [x['groupid'] for x in self.zapi.hostgroup.get(
                                    {'output': 'extend', 'with_monitored_items': True})
                                    if int(x['internal']) == 0]

                    zabbix_triggers = self.zapi.trigger.get(
                        {'sortfield': 'lastchange', 'withLastEventUnacknowledged': 0, 'groupids': hostgroup_ids,
                         "monitored": True, "filter": {'value': 1}})
                else:
                    zabbix_triggers = self.zapi.trigger.get(
                        {'sortfield': 'lastchange', 'withLastEventUnacknowledged': 0, "monitored": True,
                         "filter": {'value': 1}})
                triggers_list = []

                for trigger in zabbix_triggers:
                    triggers_list.append(trigger.get('triggerid'))
                this_trigger = self.zapi.trigger.get(
                    {'triggerids': triggers_list,
                     'expandDescription': True,
                     'output': 'extend',
                     'select_items': 'extend',
                     'expandData': True,
                     'selectHosts': 'extend',
                     'selectGroups': 'extend'}
                )
                if type(this_trigger) is dict:
                    for triggerid in this_trigger.keys():
                        services.append(this_trigger[triggerid])
                elif type(this_trigger) is list:
                    for trigger in this_trigger:
                        services.append(trigger)

            except ZabbixAPIException:
                # FIXME Is there a cleaner way to handle this? I just borrowed
                # this code from 80 lines ahead. -- AGV
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                print sys.exc_info()
                return Result(result=result, error=error)

            except ZabbixError, e:
                #print "------------------------------------"
                #print "%s" % e.result.error
                if e.terminate:
                    return e.result
                else:
                    service = e.result.content
                    ret = e.result

            for service in services:
                if api_version > '1.8':
                    state = '%s' % service['description']
                else:
                    state = '%s=%s' % (service['items'][0]['key_'], service['items'][0]['lastvalue']) 
                n = {
                    'host': service['hosts'][0]['host'],
                    'service': service['description'],
                    'status': self.statemap.get(service['priority'], service['priority']),
                    # 1/1 attempt looks at least like there has been any attempt
                    'attempt': service['groups'][0]['name'] + ' /',
                    'duration': Actions.HumanReadableDurationFromTimestamp(service['lastchange']),
                    'status_information': state,
                    'passiveonly': 'no',
                    'last_check': service['priority'],
                    'notifications': 'yes',
                    'flapping': 'no',
                    'site': '',
                    'command': 'zabbix',
                    'triggerid': service['triggerid'],
                }
                #print service
                nagitems["services"].append(n)
                # after collection data in nagitems create objects of its informations
                # host objects contain service objects
                if n["host"] not in  self.new_hosts:
                    self.new_hosts[n["host"]] = GenericHost()
                    self.new_hosts[n["host"]].name = n["host"]
                    self.new_hosts[n["host"]].status = "UP"
                    self.new_hosts[n["host"]].site = n["site"]
                    self.new_hosts[n["host"]].address = n["host"]
                    # if a service does not exist create its object
                if n["service"] not in  self.new_hosts[n["host"]].services:
                    # workaround for non-existing (or not found) host status flag
                    if n["service"] == "Host is down %s" % (n["host"]):
                        self.new_hosts[n["host"]].status = "DOWN"
                        # also take duration from "service" aka trigger
                        self.new_hosts[n["host"]].duration = n["duration"]
                    else:
                        new_service = n["service"]
                        self.new_hosts[n["host"]].services[new_service] = GenericService()
                        self.new_hosts[n["host"]].services[new_service].host = n["host"]

                        # next dirty workaround to get Zabbix events to look Nagios-esque
                        if (" on " or " is ") in n["service"]:
                            for separator in [" on ", " is "]:
                                n["service"] = n["service"].split(separator)[0]
                        self.new_hosts[n["host"]].services[new_service].name = n["service"]

                        self.new_hosts[n["host"]].services[new_service].status = n["status"]
                        self.new_hosts[n["host"]].services[new_service].last_check = n["last_check"]
                        self.new_hosts[n["host"]].services[new_service].duration = n["duration"]
                        self.new_hosts[n["host"]].services[new_service].attempt = n["attempt"]
                        self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"]
                        #self.new_hosts[n["host"]].services[new_service].passiveonly = n["passiveonly"]
                        self.new_hosts[n["host"]].services[new_service].passiveonly = False
                        #self.new_hosts[n["host"]].services[new_service].flapping = n["flapping"]
                        self.new_hosts[n["host"]].services[new_service].flapping = False
                        self.new_hosts[n["host"]].services[new_service].site = n["site"]
                        self.new_hosts[n["host"]].services[new_service].address = n["host"]
                        self.new_hosts[n["host"]].services[new_service].command = n["command"]
                        self.new_hosts[n["host"]].services[new_service].triggerid = n["triggerid"]
        except (ZabbixError, ZabbixAPIException):
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            print sys.exc_info()
            return Result(result=result, error=error)

        return ret

    def _open_browser(self, url):
        webbrowser.open(url)

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Open web page " + url)

    def open_services(self):
        self._open_browser(self.urls['human_services'])

    def open_hosts(self):
        self._open_browser(self.urls['human_hosts'])

    def open_tree_view(self, host, service=""):
        """
        open monitor from treeview context menu
        """

        if service == "":
            url = self.urls['human_host'] + urllib.urlencode(
                {'x': 'site=' + self.hosts[host].site + '&host=' + host}).replace('x=', '%26')
        else:
            url = self.urls['human_service'] + urllib.urlencode(
                {'x': 'site=' + self.hosts[host].site + '&host=' + host + '&service=' + service}).replace('x=', '%26')

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), host=host, service=service,
                       debug="Open host/service monitor web page " + url)
        webbrowser.open(url)

    def GetHost(self, host):
        """
        find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
        have their ip saved in Nagios
        """

        # the fasted method is taking hostname as used in monitor
        if str(self.conf.connect_by_host) == "True":
            return Result(result=host)

        ip = ""

        try:
            if host in self.hosts:
                ip = self.hosts[host].address

            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), host=host, debug="IP of %s:" % host + " " + ip)

            if str(self.conf.connect_by_dns) == "True":
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except:
                    address = ip
            else:
                address = ip
        except ZabbixError:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        return Result(result=address)

    def _set_recheck(self, host, service):
        pass

    def get_start_end(self, host):
        return time.strftime("%Y-%m-%d %H:%M"), time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + 7200))

    def _action(self, site, host, service, specific_params):
        params = {
            'site': self.hosts[host].site,
            'host': host,
        }
        params.update(specific_params)
        #print params
        if self.zapi is None:
            self._login()
        events = []
        for e in self.zapi.event.get({'objectids': params['triggerids'],
                                      'acknowledged': False,
                                      'sortfield': 'clock',
                                      'sortorder': 'DESC',
                                      'limit': 1}):
            events.append(e['eventid'])
            #print events
        self.zapi.event.acknowledge({'eventids': events, 'message': params['message']})

    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        pass

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        triggerid = self.hosts[host].services[service].triggerid
        p = {
            'message': '%s: %s' % (author, comment),
            'triggerids': [triggerid],
        }
        self._action(self.hosts[host].site, host, service, p)

        # acknowledge all services on a host when told to do so
        for s in all_services:
            self._action(self.hosts[host].site, host, s, p)
