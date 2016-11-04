# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Zabbix.py based on Check_MK Multisite.py

import sys
import urllib.request
import urllib.parse
import urllib.error
import time
# import socket  # never used

from Nagstamon.Helpers import (HumanReadableDurationFromTimestamp,
                               webbrowser_open)
from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.thirdparty.zabbix_api import (ZabbixAPI,
                                             ZabbixAPIException)


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

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Prepare all urls needed by nagstamon -
        self.urls = {}
        # self.statemap = {}
        self.statemap = {
            'UNREACH': 'UNREACHABLE',
            'CRIT': 'CRITICAL',
            'WARN': 'WARNING',
            'UNKN': 'UNKNOWN',
            'PEND': 'PENDING',
            '0': 'OK',
            '1': 'UNKNOWN',
            '2': 'WARNING',
            '5': 'CRITICAL',
            '3': 'WARNING',
            '4': 'CRITICAL'}

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Recheck", "Acknowledge", "Downtime"]
        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password

    def _login(self):
        try:
            self.zapi = ZabbixAPI(server=self.monitor_url, path="", log_level=0)
            self.zapi.login(self.username, self.password)
        except ZabbixAPIException:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

    """
    def init_HTTP(self):

        # not necessary to be initialized wit hevery HTTP request
        self.statemap = {
            'UNREACH': 'UNREACHABLE',
            'CRIT': 'CRITICAL',
            'WARN': 'WARNING',
            'UNKN': 'UNKNOWN',
            'PEND': 'PENDING',
            '0': 'OK',
            '1': 'UNKNOWN',
            '2': 'WARNING',
            '5': 'CRITICAL',
            '3': 'WARNING',
            '4': 'CRITICAL'}
        GenericServer.init_HTTP(self)
    """

    def _get_status(self):
        """
            Get status from Zabbix Server
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
            except (ZabbixError, ZabbixAPIException):
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)

            for host in hosts:
                # if host is disabled on server safely ignore it
                if host['available'] != '0':
                    n = {
                        'host': host['host'],
                        'status': self.statemap.get(host['status'], host['status']),
                        'last_check': 'n/a',
                        'duration': HumanReadableDurationFromTimestamp(host['errors_from']),
                        'status_information': host['error'],
                        'attempt': '1/1',
                        'site': '',
                        'address': host['host'],
                    }

                    # Zabbix shows OK hosts too - kick 'em!
                    if not n['status'] == 'OK':

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
        # groupids = [] # never used - probably old code
        zabbix_triggers = []
        try:
            api_version = self.zapi.api_version()
        except ZabbixAPIException:
            # FIXME Is there a cleaner way to handle this? I just borrowed
            # this code from 80 lines ahead. -- AGV
            # set checking flag back to False

            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            print(sys.exc_info())
            return Result(result=result, error=error)

        try:
            # response = [] # never used - probably old code
            try:
                triggers_list = []

                hostgroup_ids = [x['groupid'] for x in self.zapi.hostgroup.get(
                    {'output': 'extend', 'with_monitored_items': True})
                    if int(x['internal']) == 0]

                zabbix_triggers = self.zapi.trigger.get(
                    {'sortfield': 'lastchange', 'skipDependent': True, 'withLastEventUnacknowledged': True, 'groupids': hostgroup_ids,
                     'monitored': True, 'filter': {'value': 1}})

                triggers_list = []

                for trigger in zabbix_triggers:
                    triggers_list.append(trigger.get('triggerid'))
                this_trigger = self.zapi.trigger.get(
                    {'triggerids': triggers_list,
                     'expandDescription': True,
                     'output': 'extend',
                     'select_items': 'extend',  # thats for zabbix api 1.8
                     'selectItems': 'extend',  # thats for zabbix api 2.0+
                     'expandData': True}
                )
                if type(this_trigger) is dict:
                    for triggerid in list(this_trigger.keys()):
                        services.append(this_trigger[triggerid])
                        this_item = self.zapi.item.get(
                            {'itemids': [this_trigger[triggerid]['items'][0]['itemid']],
                             'selectApplications': 'extend'}
                        )
                        last_app = len(this_item[0]['applications']) - 1
                        this_trigger[triggerid]['application'] = this_item[0]['applications'][last_app]['name']
                elif type(this_trigger) is list:
                    for trigger in this_trigger:
                        services.append(trigger)
                        this_item = self.zapi.item.get(
                            {'itemids': trigger['items'][0]['itemid'],
                             'selectApplications': 'extend'}
                        )
                        # last_app = 0  # use it to get the first application name
                        last_app = len(this_item[0]['applications']) - 1  # use it to get the last application name
                        trigger['application'] = this_item[0]['applications'][last_app]['name']

            except ZabbixAPIException:
                # FIXME Is there a cleaner way to handle this? I just borrowed
                # this code from 80 lines ahead. -- AGV
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                print(sys.exc_info())
                return Result(result=result, error=error)

            except ZabbixError as e:
                if e.terminate:
                    return e.result
                else:
                    service = e.result.content
                    ret = e.result

            for service in services:
                # Zabbix probably shows OK services too - kick 'em!
                # UPDATE Zabbix api 3.0 doesn't but I didn't tried with older
                #        so I left it
                status = self.statemap.get(service['priority'], service['priority'])
                if not status == 'OK':
                    if not service['description'].endswith('...'):
                        state = service['description']
                    else:
                        state = service['items'][0]['lastvalue']
                    lastcheck = 0
                    for item in service['items']:
                        if int(item['lastclock']) > lastcheck:
                            lastcheck = int(item['lastclock'])
                    if len(service['comments']) == 0:
                        srvc = service['application']
                    else:
                        srvc = self.nagiosify_service(service['comments'])
                    n = {
                        'service': srvc,
                        'status': status,
                        # 1/1 attempt looks at least like there has been any attempt
                        'attempt': '1/1',
                        'duration': HumanReadableDurationFromTimestamp(service['lastchange']),
                        'status_information': state,
                        'passiveonly': 'no',
                        'last_check': time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(lastcheck)),
                        'notifications': 'yes',
                        'flapping': 'no',
                        'site': '',
                        'command': 'zabbix',
                        'triggerid': service['triggerid'],
                    }

                    if api_version >= '3.0':
                        n['host'] = self.zapi.host.get({"output": ["host"], "filter": {}, "triggerids": service['triggerid']})[0]['host']
                    else:
                        n['host'] = service['host']

                    nagitems["services"].append(n)
                    # after collection data in nagitems create objects of its informations
                    # host objects contain service objects
                    if n["host"] not in self.new_hosts:
                        self.new_hosts[n["host"]] = GenericHost()
                        self.new_hosts[n["host"]].name = n["host"]
                        self.new_hosts[n["host"]].status = "UP"
                        self.new_hosts[n["host"]].site = n["site"]
                        self.new_hosts[n["host"]].address = n["host"]
                        # if a service does not exist create its object
                    if n["service"] not in self.new_hosts[n["host"]].services:
                        # workaround for non-existing (or not found) host status flag
                        if n["service"] == "Host is down %s" % (n["host"]):
                            self.new_hosts[n["host"]].status = "DOWN"
                            # also take duration from "service" aka trigger
                            self.new_hosts[n["host"]].duration = n["duration"]
                        else:
                            new_service = n["service"]
                            self.new_hosts[n["host"]].services[new_service] = GenericService()
                            self.new_hosts[n["host"]].services[new_service].host = n["host"]
                            self.new_hosts[n["host"]].services[new_service].name = n["service"]
                            self.new_hosts[n["host"]].services[new_service].status = n["status"]
                            self.new_hosts[n["host"]].services[new_service].last_check = n["last_check"]
                            self.new_hosts[n["host"]].services[new_service].duration = n["duration"]
                            self.new_hosts[n["host"]].services[new_service].attempt = n["attempt"]
                            self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"]
                            self.new_hosts[n["host"]].services[new_service].passiveonly = False
                            self.new_hosts[n["host"]].services[new_service].flapping = False
                            self.new_hosts[n["host"]].services[new_service].site = n["site"]
                            self.new_hosts[n["host"]].services[new_service].address = n["host"]
                            self.new_hosts[n["host"]].services[new_service].command = n["command"]
                            self.new_hosts[n["host"]].services[new_service].triggerid = n["triggerid"]

        except (ZabbixError, ZabbixAPIException):
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            print(sys.exc_info())
            return Result(result=result, error=error)

        return ret

    def _open_browser(self, url):
        webbrowser_open(url)

        if conf.debug_mode is True:
            self.Debug(server=self.get_name(), debug="Open web page " + url)

    def open_services(self):
        self._open_browser(self.urls['human_services'])

    def open_hosts(self):
        self._open_browser(self.urls['human_hosts'])

    def open_monitor(self, host, service=""):
        """
            open monitor from treeview context menu
        """

        if service == "":
            url = self.urls['human_host'] + urllib.parse.urlencode(
                {'x': 'site=' + self.hosts[host].site + '&host=' + host}).replace('x=', '%26')
        else:
            url = self.urls['human_service'] + urllib.parse.urlencode(
                {'x': 'site=' + self.hosts[host].site + '&host=' + host + '&service=' + service}).replace('x=', '%26')

        if conf.debug_mode is True:
            self.Debug(server=self.get_name(), host=host, service=service,
                       debug="Open host/service monitor web page " + url)
        webbrowser_open(url)

    # def GetHost(self, host):
        # """
            # find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
            # have their ip saved in Nagios
        # """

        # # the fasted method is taking hostname as used in monitor
        # if conf.connect_by_host is True:
            # return Result(result=host)

        # ip = ""

        # try:
            # if host in self.hosts:
                # ip = self.hosts[host].address
            # if conf.debug_mode is True:
                # self.Debug(server=self.get_name(), host=host, debug="IP of %s:" % host + " " + ip)

            # if conf.connect_by_dns is True:
                # try:
                    # address = socket.gethostbyaddr(ip)[0]
                # except socket.herror:
                    # address = ip
            # else:
                # address = ip
        # except ZabbixError:
            # result, error = self.Error(sys.exc_info())
            # return Result(result=result, error=error)

        # return Result(result=address)

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

        if self.zapi is None:
            self._login()
        events = []
        for e in self.zapi.event.get({'triggerids': params['triggerids'],
                                      # from zabbix 2.2 should be used "objectids" that instead of "triggerids"
                                      'objectids': params['triggerids'],
                                      'hide_unknown': True,
                                      'sortfield': 'clock',
                                      'sortorder': 'DESC'}):
            # stop at first event in "OK" status
            if e['value'] == '0':
                break
            events.append(e['eventid'])
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

    def nagiosify_service(self, service):
        """
            next dirty workaround to get Zabbix events to look Nagios-esque
        """
        if (" on " or " is ") in service:
            for separator in [" on ", " is "]:
                service = service.split(separator)[0]
        return(service)
