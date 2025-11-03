# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Zabbix.py based on Checkmk Multisite.py
import base64
import json
import sys
import time
import datetime
import socket
from packaging import version

from Nagstamon.helpers import (human_readable_duration_from_timestamp,
                               webbrowser_open)
from Nagstamon.config import conf
from Nagstamon.objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.servers.Generic import GenericServer, BearerAuth


class ZabbixError(Exception):

    def __init__(self, terminate, result):
        self.terminate = terminate
        self.result = result


class ZabbixServer(GenericServer):
    """
       special treatment for Zabbix, taken from Check_MK Multisite JSON API
    """
    TYPE = 'Zabbix'

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
        self.api_version = ''
        self.auth_token = ''
        # Force authentication refresh by default until verified
        self.refresh_authentication = True
        self.monitor_path = '/api_jsonrpc.php'

    def init_http(self):
        """
        things to do if HTTP is not initialized
        Ensure a valid HTTP session exists before using it and handle re-auth flows.
        """
        # Let GenericServer manage refresh/session lifecycle
        super().init_http()

        # If refresh was requested, GenericServer cleared the session and returned False.
        # Create a fresh session explicitly so we can proceed with headers, version and auth checks.
        if self.session is None:
            self.session = self.create_session()

        # prepare for JSON
        if not hasattr(self.session, 'headers') or self.session.headers is None:
            # extremely defensive, but keeps AttributeError away
            self.session.headers = {}
        self.session.headers.update({'Accept': 'application/json',
                                     'Content-Type': 'application/json-rpc'})
        try:
            self.set_zabbix_version()
            self.check_authentication()
            if self.refresh_authentication:
                self.login()
        except Exception:
            self.error(sys.exc_info())
            return

    def api_request(self, cgi_data, no_auth=False):
        """
            Make a request to the Zabbix API
            Returns the response as a dictionary
        """
        url = self.monitor_url if self.monitor_url.endswith(self.monitor_path) else f"{self.monitor_url}{self.monitor_path}"
        result = self.fetch_url(url,
                                  headers=self.session.headers,
                                  cgi_data=cgi_data,
                                  giveback='json',
                                  no_auth=no_auth)
        # Check if the result is a valid JSON response
        data = result.result
        error = result.error
        status_code = result.status_code
        if error:
            raise ZabbixError(terminate=True, result=Result(result=False, error=error, status_code=status_code))
        return data

    def login(self):
        if conf.servers[self.get_name()].authentication == 'bearer':
            # In bearer mode the GUI stores the API token in the password field
            token = self.password
            if token:
                self.session.auth = BearerAuth(token)
                self.refresh_authentication = False
                return

        # check version to use the correct keyword for username which changed since 6.4
        if version.parse(self.api_version) < version.parse("6.4"):
            username_keyword = 'user'
        else:
            username_keyword = 'username'

        obj = self.generate_cgi_data('user.login', {username_keyword: self.username, 'password': self.password}, no_auth=True)
        result = self.api_request(obj)
        self.auth_token = result['result']  # Store the auth token for later use
        # For Zabbix >= 6.4 the server expects HTTP Bearer and no JSON-RPC auth field
        if version.parse(self.api_version) >= version.parse("6.4"):
            self.session.auth = BearerAuth(self.auth_token)
        self.refresh_authentication = False  # Reset the flag after successful login

    def check_authentication(self):
        try:
            # Build request depending on configured auth method
            if conf.servers[self.get_name()].authentication == 'bearer':
                obj = self.generate_cgi_data('user.checkAuthentication', {'token': self.auth_token}, no_auth=True)
            else:
                obj = self.generate_cgi_data('user.checkAuthentication', {'sessionid': self.auth_token}, no_auth=True)

            result = self.api_request(obj, no_auth=True)

            # Zabbix JSON-RPC: success responses contain 'result', errors contain 'error'.
            # Safely handle both without raising KeyError.
            if isinstance(result, dict) and result.get('error'):
                # Server explicitly reported an auth error
                self.refresh_authentication = True
                return

            res = result.get('result') if isinstance(result, dict) else None

            # Interpret common variants:
            # - {'result': True/False}
            # - {'result': {'authenticated': True/False}}
            if isinstance(res, bool):
                self.refresh_authentication = not res
            elif isinstance(res, dict) and 'authenticated' in res:
                self.refresh_authentication = not bool(res.get('authenticated'))
            else:
                # Unable to determine -> force refresh to be safe
                self.refresh_authentication = True
        except ZabbixError:
            # Treat any transport/API error as needing re-authentication
            self.refresh_authentication = True
        except Exception as e:
            raise RuntimeError(f"Authentication check failed: {str(e)}")

    def generate_cgi_data(self, method, params=None, no_auth=False):
        """
            Generate data for Zabbix API requests
        """
        if params is None:
            params = {}
        data = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': 1
        }
        # Only include auth parameter for Zabbix versions before 6.4
        if not no_auth and self.auth_token and version.parse(self.api_version) < version.parse("6.4"):
            data['auth'] = self.auth_token
        return json.dumps(data)

    def set_zabbix_version(self):
        """
            Set the Zabbix API version and other related attributes
        """
        try:
            obj = self.generate_cgi_data('apiinfo.version', no_auth=True)
            result = self.api_request(obj, no_auth=True)
            self.api_version = result['result']
        except Exception as e:
            raise RuntimeError(f"Failed to set Zabbix version: {str(e)}")

    def _get_status(self):
        """
            Get status from Zabbix Server
        """
        ret = Result()
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily

        # =========================================
        # Service
        # =========================================
        try:
            # Get a list of all issues (AKA tripped triggers)
            # add Pagination
            chunk_size = 200
            # services_ids will contain all trigger ids of active services
            results = self.api_request(
                self.generate_cgi_data('trigger.get',
                                       {
                                           'only_true': True,
                                           'skipDependent': True,
                                           'monitored': True,
                                           'active': True,
                                           'output': ['triggerid']
                                       }) )
            services_ids = results['result']
            services = []
            for i in range(0, len(services_ids), chunk_size):
                results = self.api_request(
                    self.generate_cgi_data('trigger.get',
                                           {
                                               'only_true': True,
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
                services.extend(results['result'])
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
                service_obj.duration = human_readable_duration_from_timestamp(service['lastEvent']['clock'])
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
        except ZabbixError as e:
            print(f"ZabbixError: {e.result.error}")
            return Result(result=e.result, error=e.result.error)
        except Exception:
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
                self.api_request(
                    self.generate_cgi_data('event.acknowledge',
                                           {
                                               'eventids': list(closable_events),
                                               'message': comment,
                                               'action': closable_actions
                                           }),
                )
                self.api_request(
                    self.generate_cgi_data('event.acknowledge',
                                           {
                                               'eventids': list(unclosable_events),
                                               'message': comment,
                                               'action': actions
                                           }),
                )
            else:
                if sticky:
                    actions |= 1
                try:
                    self.api_request(
                        self.generate_cgi_data('event.acknowledge',
                                               {
                                                   'eventids': list(eventids),
                                                   'message': comment,
                                                   'action': actions
                                               }),
                    )
                except RuntimeError as e:
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
            self.api_request(
                self.generate_cgi_data('maintenance.create', body)
            )
        except ValueError as e:
            if "already exists" in str(e).lower():
                self.debug(server=self.get_name(), debug=f"Maintanence with name {body['name']} already exists")
            else:
                raise e

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
