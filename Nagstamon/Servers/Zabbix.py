# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Zabbix.py based on Checkmk Multisite.py

import sys
import urllib.request
import urllib.parse
import urllib.error
import time
import logging
import datetime
import socket

from Nagstamon.Helpers import (HumanReadableDurationFromTimestamp,
                               webbrowser_open)
from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.thirdparty.zabbix_api import (ZabbixAPI,
                                             ZabbixAPIException,
                                             APITimeout,
                                             Already_Exists)

log = logging.getLogger('Zabbix')


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
    if conf.debug_mode is True:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING
    log.setLevel(log_level)

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
            '1': 'INFORMATION',
            '2': 'WARNING',
            '3': 'AVERAGE',
            '4': 'HIGH',
            '5': 'DISASTER'}

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Acknowledge", "Downtime"]
        # URLs for browser shortlinks/buttons on popup window
        self.BROWSER_URLS = {'monitor': '$MONITOR$',
                             'hosts': '$MONITOR-CGI$/hosts.php?ddreset=1',
                             'services': '$MONITOR-CGI$/zabbix.php?action=problem.view&fullscreen=0&page=1&filter_show=3&filter_set=1',
                             'history': '$MONITOR-CGI$/zabbix.php?action=problem.view&fullscreen=0&page=1&filter_show=2&filter_set=1'}

        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password
        self.ignore_cert = conf.servers[self.get_name()].ignore_cert
        self.use_description_name_service = conf.servers[self.get_name()].use_description_name_service
        if self.ignore_cert is True:
            self.validate_certs = False
        else:
            self.validate_certs = True

    def _login(self):
        try:
            # create ZabbixAPI if not yet created
            if self.zapi is None:
                self.zapi = ZabbixAPI(server=self.monitor_url, path="", log_level=self.log_level,
                                      validate_certs=self.validate_certs)
            # login if not yet logged in, or if login was refused previously
            if not self.zapi.logged_in():
                self.zapi.login(self.username, self.password)
        except ZabbixAPIException:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

    def getLastApp(self, this_item):
        if len(this_item) > 0:
            if "applications" not in this_item[0]:
                if 'tags' in this_item[0]:
                    app = "NO APP"
                    for tag in this_item[0]['tags']:
                        if tag['tag'] == 'Application':
                            app = tag['value']
                    return app
                else:
                    return "NO APP"
            last_app = len(this_item[0]['applications']) - 1  # use it to get the last application name
            if last_app > -1:
                return "%s" % this_item[0]['applications'][last_app]['name']
            else:
                return "NO APP"
        else:
            return "Web scenario"

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
        self._login()
        # print(self.name)

        # =========================================
        # Service
        # =========================================
        services = []
        try:
            api_version = int(''.join(self.zapi.api_version().split('.')[:-1])) # Make API Version smaller
        except ZabbixAPIException:
            # FIXME Is there a cleaner way to handle this? I just borrowed
            # this code from 80 lines ahead. -- AGV
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            print(sys.exc_info())
            return Result(result=result, error=error)

        try:
            try:
                # Get a list of all issues (AKA tripped triggers)
                # Zabbix 3+ returns array of objects
                services = self.zapi.trigger.get({'only_true': True,
                                                  'skipDependent': True,
                                                  'monitored': True,
                                                  'active': True,
                                                  'output': ['triggerid', 'description', 'lastchange'],
                                                  # 'expandDescription': True,
                                                  # 'expandComment': True,
                                                  'selectLastEvent': ['eventid', 'name', 'ns', 'clock', 'acknowledged',
                                                                      'value', 'severity'],
                                                  'selectHosts': ["hostid", "host", "name", "status", "available",
                                                                  "maintenance_status", "maintenance_from"],
                                                  'selectItems': ['name', 'lastvalue', 'state', 'lastclock'],
                                                  # thats for zabbix api 2.0+
                                                  'filter': {'value': 1},
                                                  })

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

            # =========================================
            # Hosts Zabbix API data
            # =========================================
            # Create Hostids for shorten Query
            try:
                hosts = []
                if api_version >= 54:  # For Version 5.4 and higher
                    # Some performance improvement for 5.4
                    hostids = []
                    # get just involved Hosts.
                    for service in services:
                        for host in service["hosts"]:
                            hostids.append(host["hostid"])

                    try:
                        hosts = self.zapi.host.get({"output": ["hostid", "host", "name", "status", "available",
                                                               "maintenance_status", "maintenance_from"],
                                                    "hostids": hostids,
                                                    "selectInterfaces": ["ip"],
                                                    "filter": {}
                                                    })
                    except (ZabbixError, ZabbixAPIException, APITimeout, Already_Exists):
                        # set checking flag back to False
                        self.isChecking = False
                        result, error = self.Error(sys.exc_info())
                        return Result(result=result, error=error)
                else:
                    try:
                        # TODO: This Query can be removed when Zabbix Version 4 Support is dropped.
                        hosts = self.zapi.host.get({"output": ["hostid", "host", "name", "status", "available",
                                                               "error", "errors_from", # dropped in Version 5.4
                                                               "snmp_available", "snmp_error", "snmp_errors_from", # dropped in Version 5.4
                                                               "ipmi_available", "ipmi_error", "ipmi_errors_from", # dropped in Version 5.4
                                                               "jmx_available", "jmx_error", "jmx_errors_from", # dropped in Version 5.4
                                                               "maintenance_status", "maintenance_from"],
                                                    "selectInterfaces": ["ip"],
                                                    "filter": {}
                                                    })
                    except (ZabbixError, ZabbixAPIException, APITimeout, Already_Exists):
                        # set checking flag back to False
                        self.isChecking = False
                        result, error = self.Error(sys.exc_info())
                        return Result(result=result, error=error)
                # get All Hosts.
                # 1. Store data in cache (to be used by events)
                # 2. We store as faulty two kinds of hosts incidences:
                #    - Disabled hosts
                #    - Hosts with issues trying to connect to agent/service
                #    - In maintenance
                # status = 1 -> Disabled
                # available ZBX: 0 -> No agents 1 -> available 2-> Agent access error
                # ipmi_available IPMI: 0 -> No agents 1 -> available 2-> Agent access error
                # maintenance_status = 1 In maintenance
                for host in hosts:
                    n = {
                        'host': host['host'],
                        'name': host['name'],
                        'server': self.name,
                        'status': 'UP',  # Host is OK by default
                        'last_check': 'n/a',
                        'duration': '',
                        'attempt': 'N/A',
                        'status_information': '',
                        # status flags
                        'passiveonly': False,
                        'notifications_disabled': False,
                        'flapping': False,
                        'acknowledged': False,
                        'scheduled_downtime': False,
                        # Zabbix backend data
                        'hostid': host['hostid'],
                        'site': '',
                        # 'address': host['interfaces'][0]['ip'],
                    }

                    # try to fix https://github.com/HenriWahl/Nagstamon/issues/687
                    #
                    n['address'] = host['interfaces'][0]['ip'] if len(host['interfaces']) > 0 else ''

                    if host['maintenance_status'] == '1':
                        n['scheduled_downtime'] = True

                    if host['status'] == '1':
                        # filter services and hosts by "filter_hosts_services_disabled_notifications"
                        n['notifications_disabled'] = True
                        # Filter only hosts by filter "Host & services with disabled checks"
                        n['passiveonly'] = True
                    # attempt to fix https://github.com/HenriWahl/Nagstamon/issues/535
                    # TODO: This can be simplified if Zabbix Version 5.0 Support is dropped.
                    # if host['available'] == '0' and host['snmp_available'] == '0' and host['ipmi_available'] == '0' and host['jmx_available'] == '0':
                    #     n['status']             = 'UNREACHABLE'
                    #     n['status_information'] = 'Host agents in unknown state'
                    #     n['duration']           = 'Unknown'
                    if host.get('ipmi_available', '0') == '2':
                        n['status'] = 'DOWN'
                        n['status_information'] = host['ipmi_error']
                        n['duration'] = HumanReadableDurationFromTimestamp(host['ipmi_errors_from'])
                    if host.get('snmp_available', '0') == '2':
                        n['status'] = 'DOWN'
                        n['status_information'] = host['snmp_error']
                        n['duration'] = HumanReadableDurationFromTimestamp(host['snmp_errors_from'])
                    if host.get('jmx_available', '0') == '2':
                        n['status'] = 'DOWN'
                        n['status_information'] = host['jmx_error']
                        n['duration'] = HumanReadableDurationFromTimestamp(host['jmx_errors_from'])
                    if host.get('available', '0') == '2':
                        n['status'] = 'DOWN'
                        n['status_information'] = host['error']
                        n['duration'] = HumanReadableDurationFromTimestamp(host['errors_from'])
                    # Zabbix shows OK hosts too - kick 'em!
                    if not n['status'] == 'UP':
                        # add dictionary full of information about this host item to nagitems
                        nagitems["hosts"].append(n)

                    # after collection data in nagitems create objects from its informations
                    # host objects contain service objects
                    # key_host = n["host"]
                    key_host = n["name"] if len(n['name']) != 0 else n["host"]

                    # key_host = n["hostid"]
                    if key_host not in self.new_hosts:
                        self.new_hosts[key_host] = GenericHost()
                        self.new_hosts[key_host].hostid = n["hostid"]
                        self.new_hosts[key_host].host = n["host"]
                        self.new_hosts[key_host].name = n["name"]
                        self.new_hosts[key_host].status = n["status"]
                        self.new_hosts[key_host].last_check = n["last_check"]
                        self.new_hosts[key_host].duration = n["duration"]
                        self.new_hosts[key_host].attempt = n["attempt"]
                        self.new_hosts[key_host].status_information = n["status_information"]
                        self.new_hosts[key_host].site = n["site"]
                        self.new_hosts[key_host].address = n["address"]
                        self.new_hosts[key_host].notifications_disabled = n["notifications_disabled"]
                        self.new_hosts[key_host].scheduled_downtime = n["scheduled_downtime"]
                        self.new_hosts[key_host].passiveonly = n["passiveonly"]
                        self.new_hosts[key_host].acknowledged = n["acknowledged"]
                        self.new_hosts[key_host].flapping = n["flapping"]

            except ZabbixError:
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)
            ###
            for service in services:
                # Zabbix probably shows OK services too - kick 'em!
                # UPDATE Zabbix api 3.0 doesn't but I didn't tried with older
                #        so I left it
                # print(service)
                status = self.statemap.get(service['lastEvent']['severity'], service['lastEvent']['severity'])
                # self.Debug(server=self.get_name(), debug="SERVICE (" + service['application'] + ") STATUS: **" +
                # status + "** PRIORITY: #" + service['priority']) self.Debug(server=self.get_name(),
                # debug="-----======== SERVICE " + str(service))
                if not status == 'OK':
                    # if not service['description'].endswith('...'):
                    #     state = service['description']
                    # else:
                    #     state = service['items'][0]['lastvalue']
                    # A trigger can be triggered by multiple items
                    # Get last checking date of any of the items involved
                    lastcheck = 0
                    for item in service['items']:
                        if int(item['lastclock']) > lastcheck:
                            lastcheck = int(item['lastclock'])

                    # if self.use_description_name_service and \
                    #         len(service['comments']) != 0:
                    #     srvc = self.nagiosify_service(service['comments'])
                    # else:
                    #     srvc = "Not Implemented"
                    status_information = ""
                    for item in service['items']:
                        status_information = item['name'] + ": " + item['lastvalue'] + ", " + status_information
                    n = {
                        'host': '',
                        'hostname': '',
                        'service': service['lastEvent']['name'],
                        'server': self.name,
                        'status': status,
                        # Putting service in attempt column allow to see it in GUI
                        'attempt': '',
                        'duration': HumanReadableDurationFromTimestamp(service['lastchange']),
                        'status_information': status_information,
                        'last_check': time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(lastcheck)),
                        'site': '',
                        'command': 'zabbix',
                        # status flags
                        'passiveonly': False,
                        'notifications_disabled': False,
                        'flapping': False,
                        'acknowledged': bool(int(service['lastEvent']['acknowledged'])),
                        'scheduled_downtime': False,
                        # Zabbix data
                        'triggerid': service['triggerid'],
                        'eventid': service['lastEvent']['eventid'],
                    }

                    n['hostid'] = service['hosts'][0]['hostid']
                    n['host'] = service['hosts'][0]['host']
                    n['hostname'] = service['hosts'][0]['name']

                    key = n["hostname"] if len(n['hostname']) != 0 else n["host"]
                    # key = n["hostid"];

                    if self.new_hosts[key].scheduled_downtime:
                        n['scheduled_downtime'] = True

                    nagitems["services"].append(n)

                    # after collection data in nagitems create objects of its informations
                    # host objects contain service objects
                    # if not created previously, host should be created with proper data
                    if key not in self.new_hosts:
                        # This should never happen, because we've stored all hosts in new_hosts array
                        print("================================")
                        print("Host " + key + "Not found in host cache")
                        if conf.debug_mode is True:
                            self.Debug(server=self.get_name(), debug="Host not found [" + key + "]")

                    # if a service does not exist create its object
                    new_service = n["triggerid"]
                    if new_service not in self.new_hosts[key].services:
                        self.new_hosts[key].services[new_service] = GenericService()
                        self.new_hosts[key].services[new_service].host = n["hostname"] if len(n['hostname']) != 0 else \
                            n["host"]
                        self.new_hosts[key].services[new_service].name = n["service"]
                        self.new_hosts[key].services[new_service].status = n["status"]
                        self.new_hosts[key].services[new_service].last_check = n["last_check"]
                        self.new_hosts[key].services[new_service].duration = n["duration"]
                        self.new_hosts[key].services[new_service].attempt = n["attempt"]
                        self.new_hosts[key].services[new_service].status_information = n["status_information"]
                        self.new_hosts[key].services[new_service].passiveonly = n["passiveonly"]
                        self.new_hosts[key].services[new_service].notifications_disabled = n["notifications_disabled"]
                        self.new_hosts[key].services[new_service].flapping = n["flapping"]
                        self.new_hosts[key].services[new_service].acknowledged = n["acknowledged"]
                        self.new_hosts[key].services[new_service].scheduled_downtime = n["scheduled_downtime"]
                        self.new_hosts[key].services[new_service].site = n["site"]
                        self.new_hosts[key].services[new_service].address = self.new_hosts[key].address
                        self.new_hosts[key].services[new_service].command = n["command"]
                        self.new_hosts[key].services[new_service].hostid = n["hostid"]
                        self.new_hosts[key].services[new_service].triggerid = n["triggerid"]
                        self.new_hosts[key].services[new_service].eventid = n["eventid"]
                        if conf.debug_mode is True:
                            self.Debug(server=self.get_name(),
                                       debug="Adding new service[" + new_service + "] **" + n['service'] + "**")

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

    # Disable set_recheck (nosense in Zabbix)
    def set_recheck(self, info_dict):
        pass

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        if conf.debug_mode is True:
            self.Debug(server=self.get_name(),
                       debug="Set Acknowledge Host: " + host + " Service: " + service + " Sticky: " + str(
                           sticky) + " persistent:" + str(persistent) + " All services: " + str(all_services))
        # print("Set Acknowledge Host: " + host + " Service: " + service + " Sticky: " + str(
        #                     sticky) + " persistent:" + str(persistent) + " All services: " + str(all_services))
        # Service column is storing current trigger id
        services = []
        services.append(service)

        # acknowledge all problems (column services) on a host when told to do so
        for s in all_services:
            services.append(s)

        self._login()
        eventids=[]
        get_host = self.hosts[host]
        # Through all Services
        for service in services:
            # find Trigger ID
            for host_service in get_host.services:
                host_service = get_host.services[host_service]
                if host_service.name == service:
                    eventids.append(host_service.eventid)
                    break

        #for e in self.zapi.event.get({'triggerids': [triggerid],
        #                              # from zabbix 2.2 should be used "objectids" instead of "triggerids"
        #                              'objectids': [triggerid],
        #                              # 'acknowledged': False,
        #                              'sortfield': 'clock',
        #                              'sortorder': 'DESC'}):
        #    # Get only current event status, but retrieving first row ordered by clock DESC
        #    # If event status is not "OK" (Still is an active problem), mark event to acknowledge/close
        #    if e['value'] != '0':
        #        events.append(e['eventid'])
        #    # Only take care of newest event, discard all next
        #    break

        # If events pending of acknowledge, execute ack
        if len(eventids) > 0:
            # actions is a bitmask with values:
            # 1 - close problem
            # 2 - acknowledge event
            # 4 - add message
            # 8 - change severity
            # 16 - unacknowledge event
            actions = 2
            # If sticky is set then close only current event
            # if triggerid == service and sticky:
            #     # do not send the "Close" flag if this event does not allow manual closing
            #     triggers = self.zapi.trigger.get({
            #         'output': ['triggerid', 'manual_close'],
            #         'filter': {'triggerid': triggerid}})
            #     if not triggers or 'manual_close' not in triggers[0] or str(triggers[0]['manual_close']) == '1':
            #         actions |= 1
            # The current Nagstamon menu items don't match up too well with the Zabbix actions,
            # but perhaps "Persistent comment" is the closest thing to acknowledgement
            # if persistent:
            #     actions |= 2
            if comment:
                actions |= 4
            if conf.debug_mode is True:
                self.Debug(server=self.get_name(),
                           debug="Events to acknowledge: " + str(eventids) + " Close: " + str(actions))
            # print("Events to acknowledge: " + str(eventids) + " Close: " + str(actions))
            self.zapi.event.acknowledge({'eventids': eventids, 'message': comment, 'action': actions})

    def _set_downtime(self, hostname, service, author, comment, fixed, start_time, end_time, hours, minutes):
        # Check if there is an associated Application tag with this trigger/item
        triggerid = None
        for host_service in self.hosts[hostname].services:
            if self.hosts[hostname].services[host_service].name == service:
                triggerid = self.hosts[hostname].services[host_service].triggerid
                break
        # triggers = self.zapi.trigger.get({
        #     'selectItems': ['itemid'],
        #     'output': ['triggerid'],
        #     'filter': {'triggerid': service}})
        # if triggers and triggers[0]['items']:
        #     items = self.zapi.item.get({
        #         'itemids': [triggers[0]['items'][0]['itemid']],
        #         'output': ['itemid'],
        #         'selectTags': 'extend'})
        #     if items and items[0]['tags']:
        #         for tag in items[0]['tags']:
        #             if tag['tag'] == 'Application':
        #                 app = tag['value']

        hostids = [self.hosts[hostname].hostid]

        date = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        stime = time.mktime(date.timetuple())

        date = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        etime = time.mktime(date.timetuple())

        if conf.debug_mode is True:
            self.Debug(server=self.get_name(),
                       debug="Downtime for " + hostname + "[" + str(hostids) + "] stime:" + str(
                           stime) + " etime:" + str(etime))
        # print("Downtime for " + hostname + "[" + str(hostids) + "] stime:" + str(stime) + " etime:" + str(etime))
        body = {'hostids': hostids, 'name': comment, 'description': author, 'active_since': stime, 'active_till': etime,
                'maintenance_type': 0, "timeperiods": [
                        {"timeperiod_type": 0, "start_date": stime, "period": etime - stime}
                    ]
                }
        if triggerid:
            body['tags'] = [{'tag': 'triggerid', 'operator': 0, 'value': triggerid}]
            body['description'] = body['description'] + '(Nagstamon): ' + comment
            body['name'] = f'{hostname}: {service}'
        try:
            self.zapi.maintenance.create(body)
        except Already_Exists:
            self.Debug(server=self.get_name(), debug=f"Maintanence with name {body['name']} already exists")

    def get_start_end(self, host):
        return time.strftime("%Y-%m-%d %H:%M"), time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + 7200))

    def GetHost(self, host):
        """
            find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
            have their ip saved in Nagios
        """

        # the fasted method is taking hostname as used in monitor
        if conf.connect_by_host is True:
            return Result(result=host)

        ip = ""
        address = host

        try:
            if host in self.hosts:
                ip = self.hosts[host].address
            if conf.debug_mode is True:
                self.Debug(server=self.get_name(), host=host, debug="IP of %s:" % host + " " + ip)

            if conf.connect_by_dns is True:
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except socket.herror:
                    address = ip
            else:
                address = ip
        except ZabbixError:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        return Result(result=address)

    def nagiosify_service(self, service):
        """
            next dirty workaround to get Zabbix events to look Nagios-esque
        """
        if (" on " or " is ") in service:
            for separator in [" on ", " is "]:
                service = service.split(separator)[0]
        return service
