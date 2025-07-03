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
        self.authentication = conf.servers[self.get_name()].authentication
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
        self.MENU_ACTIONS = ["Monitor", "Acknowledge", "Downtime"]
        # URLs for browser shortlinks/buttons on popup window
        self.BROWSER_URLS = {'monitor': '$MONITOR$',
                             'hosts': '$MONITOR-CGI$/hosts.php?ddreset=1',
                             'services': '$MONITOR-CGI$/zabbix.php?action=problem.view&fullscreen=0&page=1&filter_show=3&filter_set=1',
                             'history': '$MONITOR-CGI$/zabbix.php?action=problem.view&fullscreen=0&page=1&filter_show=2&filter_set=1'}

        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password
        self.timeout = conf.servers[self.get_name()].timeout
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
                                      validate_certs=self.validate_certs, timeout=self.timeout)
            # login if not yet logged in, or if login was refused previously
            if self.authentication == 'bearer':
                if not self.zapi.logged_in(bearer=True):
                    self.zapi.login(self.username, self.password, bearer=True)
            elif self.authentication == 'basic':
                if not self.zapi.logged_in():
                    self.zapi.login(self.username, self.password)
            else:
                raise Exception("Invalid authentication method")
        except ZabbixAPIException as e:
            raise e

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

        # Create URLs for the configured filters
        try:
            self._login()
        except Exception:
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)
        # =========================================
        # Service
        # =========================================
        try:
            try:
                # Get a list of all issues (AKA tripped triggers)
                # add Pagination
                chunk_size = 200
                services_ids = self.zapi.trigger.get({'only_true': True,
                                                      'skipDependent': True,
                                                      'monitored': True,
                                                      'active': True,
                                                      'output': ['triggerid']
                                                      })
                services = []
                for i in range(0, len(services_ids), chunk_size):
                    services.extend(self.zapi.trigger.get({'only_true': True,
                                                           'skipDependent': True,
                                                           'monitored': True,
                                                           'active': True,
                                                           'output': ['triggerid', 'description', 'lastchange', 'manual_close'],
                                                           # 'expandDescription': True,
                                                           # 'expandComment': True,
                                                           'triggerids': [trigger['triggerid'] for trigger in services_ids[i:i + chunk_size]],
                                                           'selectLastEvent': ['eventid', 'name', 'ns', 'clock', 'acknowledged',
                                                                               'value', 'severity'],
                                                           'selectHosts': ["hostid", "host", "name", "status", "available",
                                                                           "active_available", "maintenance_status", "maintenance_from"],
                                                           'selectItems': ['name', 'lastvalue', 'state', 'lastclock']
                                                        }))
                for service in services:
                    status_information = ", ".join(
                        [f"{item['name']}: {item['lastvalue']}" for item in service['items']])

                    # Add opdata to status information if available (from problem API)
                    if 'opdata' in service['lastEvent']:
                        if service['lastEvent']['opdata'] != "":
                            status_information = service['lastEvent']['name'] + " (" + service['lastEvent'][
                                'opdata'] + ")"

                    service_obj = GenericService()
                    service_obj.name = service['lastEvent']['name']
                    service_obj.status = self.statemap.get(service['lastEvent']['severity'], service['lastEvent']['severity'])
                    service_obj.last_check = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(max(int(item['lastclock']) for item in service['items'])))
                    service_obj.duration = HumanReadableDurationFromTimestamp(service['lastEvent']['clock'])
                    service_obj.status_information = status_information
                    service_obj.acknowledged = False if service['lastEvent']['acknowledged'] == '0' else True
                    #service_obj.address = ''  # Todo: check if address is available
                    service_obj.triggerid = service['triggerid']
                    service_obj.eventid = service['lastEvent']['eventid']
                    service_obj.allow_manual_close = False if str(service['manual_close']) == '0' else True

                    if service['hosts']:
                        # Get the first host only, because we only support one host per service
                        for host in service['hosts']:
                            self.new_hosts[host['name']] = GenericHost()
                            self.new_hosts[host['name']].name = host['name']
                            self.new_hosts[host['name']].server = self.name
                            self.new_hosts[host['name']].status = 'UP'
                            self.new_hosts[host['name']].scheduled_downtime = True if host["maintenance_status"] == '1' else False
                            # Map Stuff from Service to Host
                            self.new_hosts[host['name']].services[service["triggerid"]] = service_obj
                            self.new_hosts[host['name']].services[service["triggerid"]].host = host['name']
                            self.new_hosts[host['name']].services[service["triggerid"]].hostid = host['hostid']


            except ZabbixAPIException:
                # FIXME Is there a cleaner way to handle this? I just borrowed
                # this code from 80 lines ahead. -- AGV
                # set checking flag back to False
                self.isChecking = False
                result, error = self.error(sys.exc_info())
                print(sys.exc_info())
                return Result(result=result, error=error)
            except ZabbixError as e:
                if e.terminate:
                    return e.result
                else:
                    service = e.result.content
                    ret = e.result
            except Exception:
                result, error = self.error(sys.exc_info())
                print(sys.exc_info())
                return Result(result=result, error=error)

        except (ZabbixError, ZabbixAPIException):
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            print(sys.exc_info())
            return Result(result=result, error=error)
        return ret

    def _open_browser(self, url):
        webbrowser_open(url)

        if conf.debug_mode is True:
            self.debug(server=self.get_name(), debug="Open web page " + url)

    def open_services(self):
        self._open_browser(self.urls['human_services'])

    def open_hosts(self):
        self._open_browser(self.urls['human_hosts'])

    def open_monitor(self, host, service=""):
        """
            open monitor from treeview context menu
        """
        host_id = self.hosts[host].hostid
        url = f"{self.monitor_url}/zabbix.php?action=problem.view&hostids%5B%5D={host_id}&filter_set=1&show_suppressed=1"

        if conf.debug_mode is True:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="Open host/service monitor web page " + url)
        webbrowser_open(url)

    # Disable set_recheck (nosense in Zabbix)
    def set_recheck(self, info_dict):
        pass

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None):
        if conf.debug_mode is True:
            self.debug(server=self.get_name(),
                       debug="Set Acknowledge Host: " + host + " Service: " + service + " Sticky: " + str(
                           sticky) + " persistent:" + str(persistent) + " All services: " + str(all_services))
        try:
            self._login()
        except Exception:
            self.error(sys.exc_info())
            return
        eventids = set()
        unclosable_events = set()
        if all_services is None:
            all_services = []
        all_services.append(service)
        get_host = self.hosts[host]
        # Through all Services
        for s in all_services:
            # find Trigger ID
            for host_service in get_host.services:
                host_service = get_host.services[host_service]
                if host_service.name == s:
                    eventid = host_service.eventid
                    # https://github.com/HenriWahl/Nagstamon/issues/826 we may have set eventid = -1 earlier if there was no associated event
                    if eventid == -1:
                        continue
                    eventids.add(eventid)
                    if not host_service.allow_manual_close:
                        unclosable_events.add(eventid)

        # If events pending of acknowledge, execute ack
        if len(eventids) > 0:
            # actions is a bitmask with values:
            # 1 - close problem
            # 2 - acknowledge event
            # 4 - add message
            # 8 - change severity
            # 16 - unacknowledge event
            # 32 - suppress event;
            # 64 - unsuppress event;
            # 128 - change event rank to cause;
            # 256 - change event rank to symptom.
            # sticky = close problem  # TODO: make visible in GUI
            actions = 2
            if comment:
                actions |= 4
            if conf.debug_mode:
                self.debug(server=self.get_name(),
                           debug="Events to acknowledge: " + str(eventids) + " Close: " + str(actions))
            # If some events are not closable, we need to make 2 requests, 1 for the closable and one for the not closable
            if sticky and unclosable_events:
                closable_actions = actions | 1
                closable_events = set(e for e in eventids if e not in unclosable_events)
                self.zapi.event.acknowledge({'eventids': list(closable_events), 'message': comment, 'action': closable_actions})
                self.zapi.event.acknowledge({'eventids': list(unclosable_events), 'message': comment, 'action': actions})
            else:
                if sticky:
                    actions |= 1
                try:
                    self.zapi.event.acknowledge({'eventids': list(eventids), 'message': comment, 'action': actions})
                except ZabbixAPIException as e:
                    if "Incorrect user name or password or account is temporarily blocked" in str(e):
                        self.error(str(e))
                        return
                    else:
                        raise e

    def _set_downtime(self, hostname, service, author, comment, fixed, start_time, end_time, hours, minutes):
        # Check if there is an associated Application tag with this trigger/item
        triggerid = None
        for host_service in self.hosts[hostname].services:
            if self.hosts[hostname].services[host_service].name == service:
                triggerid = self.hosts[hostname].services[host_service].triggerid
                break
        if self.hosts[hostname].hostid is None:
            self.error("Host ID is None for " + hostname)
            return
        hostids = [self.hosts[hostname].hostid]

        if fixed == 1:
            start_date = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            end_date = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        else:
            start_date = datetime.datetime.now()
            end_date = start_date + datetime.timedelta(hours=hours, minutes=minutes)

        stime = int(time.mktime(start_date.timetuple()))
        etime = int(time.mktime(end_date.timetuple()))

        if conf.debug_mode is True:
            self.debug(server=self.get_name(),
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
            self.debug(server=self.get_name(), debug=f"Maintanence with name {body['name']} already exists")

    def get_start_end(self, host):
        return time.strftime("%Y-%m-%d %H:%M"), time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + 7200))

    def get_host(self, host):
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
                self.debug(server=self.get_name(), host=host, debug="IP of %s:" % host + " " + ip)

            if conf.connect_by_dns is True:
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except socket.herror:
                    address = ip
            else:
                address = ip
        except ZabbixError:
            result, error = self.error(sys.exc_info())
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
