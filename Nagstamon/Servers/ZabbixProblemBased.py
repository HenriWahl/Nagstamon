# encoding: utf-8

import sys
import time
import logging
import requests
from packaging import version

from Nagstamon.Helpers import HumanReadableDurationFromTimestamp
from Nagstamon.Config import conf
from Nagstamon.Objects import GenericHost, GenericService, Result
from Nagstamon.Servers.Generic import GenericServer

class ZabbixLightApi():

    logger = None
    server_name = "Zabbix"
    monitor_url = "http://127.0.0.1/api_jsonrpc.php"
    validate_certs = False
    r_session = None

    zbx_auth = None
    zbx_req_id = 0

    def __init__(self, server_name, monitor_url, validate_certs):

        self.server_name = server_name
        self.monitor_url = monitor_url + "/api_jsonrpc.php"
        self.validate_certs = validate_certs

        #persistent connections
        self.r_session = requests.Session()

        #configure logging
        self.logger = logging.getLogger('ZabbixLightApi_'+server_name)
        console_logger = logging.StreamHandler()
        console_logger_formatter = logging.Formatter('[%(name)s] %(levelname)s - %(message)s')
        console_logger.setFormatter(console_logger_formatter)
        self.logger.addHandler(console_logger)
        if conf.debug_mode is True:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        self.logger.debug("ZabbixLightApi START!")
        self.logger.debug("monitor_url = " + self.monitor_url)

    def do_request(self, method, params={}, no_auth=False):
        zabbix_rpc_obj = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.zbx_req_id
        }

        if not no_auth:
            zabbix_rpc_obj["auth"] = self.zbx_auth

        self.zbx_req_id += 1

        self.logger.debug("ZBX: > " + str(zabbix_rpc_obj))

        try:

            response = self.r_session.post(self.monitor_url, json=zabbix_rpc_obj, verify=self.validate_certs)

            #we didnt get HTTP code 200
            if response.status_code != 200:
                raise ZabbixLightApiException("Got return code - " + str(response.status_code))

            #parse response json
            response_json = response.json()
            self.logger.debug("ZBX: < " + str(response_json))

            #there was some kind of error during processing our request
            if "error" in response_json.keys():
                raise ZabbixLightApiException("ZBX: < " + response_json["error"]["data"])

            #zabbix returned garbage
            if "result" not in response_json.keys():
                raise ZabbixLightApiException("ZBX: < no result object in response")

        #all other network related errors
        except Exception as e:
            raise ZabbixLightApiException(e)

        return response_json['result']

    def api_version(self, **options):
        obj = self.do_request('apiinfo.version', options, no_auth=True)
        return obj

    def logged_in(self):
        if self.zbx_auth is None:
            return False
        else:
            is_auth=self.do_request("user.checkAuthentication", {"sessionid": self.zbx_auth}, no_auth=True)
            if is_auth:
                return True
            else:
                self.zbx_auth = None
                return False

    def login(self, username, password):
        self.logger.debug("Login in as " + username)
        # see issue https://github.com/HenriWahl/Nagstamon/issues/1018
        if self.api_version() < '6.4':
            self.zbx_auth = self.do_request('user.login', {'user': username, 'password': password})
        else:
            self.zbx_auth = self.do_request('user.login', {'username': username, 'password': password})

class ZabbixLightApiException(Exception):
    pass

class ZabbixProblemBasedServer(GenericServer):

    TYPE = 'ZabbixProblemBased'
    zlapi = None
    zbx_version = ""

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        self.statemap = {
            '0': 'OK',
            '1': 'INFORMATION',
            '2': 'WARNING',
            '3': 'AVERAGE',
            '4': 'HIGH',
            '5': 'DISASTER'}

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = []
        # URLs for browser shortlinks/buttons on popup window
        self.BROWSER_URLS = {'monitor': '$MONITOR$',
                             'hosts': '$MONITOR-CGI$/hosts.php?ddreset=1',
                             'services': '$MONITOR-CGI$/zabbix.php?action=problem.view&fullscreen=0&page=1&filter_show=3&filter_set=1',
                             'history':  '$MONITOR-CGI$/zabbix.php?action=problem.view&fullscreen=0&page=1&filter_show=2&filter_set=1'}

        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password
        self.validate_certs = not conf.servers[self.get_name()].ignore_cert

    def _get_status(self):
        """
            Get status from Zabbix Server
        """
        # =========================================
        # problems
        # =========================================
        problems = []
        try:
            #Are we logged in?
            if self.zlapi is None:
                self.zlapi = ZabbixLightApi(server_name=self.name, monitor_url=self.monitor_url, validate_certs=self.validate_certs)

            #zabbix could get an upgrade between checks, we need to check version each time
            self.zbx_version = self.zlapi.do_request("apiinfo.version", {}, no_auth=True)

            #check are we still logged in, if not, relogin
            if not self.zlapi.logged_in():
                self.zlapi.login(self.username, self.password)

            #Get all current problems (trigger based), no need to check acknowledged problems if they are filtered out (load reduce)
            if conf.filter_acknowledged_hosts_services:
                # old versions doesnt support suppressed problems
                if version.parse(self.zbx_version) < version.parse("6.2.0"):
                    problems = self.zlapi.do_request("problem.get", {'recent': False, 'acknowledged': False})
                else:
                    problems = self.zlapi.do_request("problem.get", {'recent': False, 'acknowledged': False, 'suppressed': False})
            else:
                problems = self.zlapi.do_request("problem.get", {'recent': False})

            for problem in problems:

                #get trigger which rose current problem
                trigger = self.zlapi.do_request("trigger.get", {'triggerids': problem['objectid'],
                                                'monitored': True,
                                                'active': True,
                                                'skipDependent': True,
                                                'selectHosts': ['hostid', 'name', 'maintenance_status',
                                                                'available', 'error', 'errors_from',
                                                                'ipmi_available', 'ipmi_error', 'ipmi_errors_from',
                                                                'jmx_available', 'jmx_error', 'jmx_errors_from',
                                                                'snmp_available', 'snmp_error', 'snmp_errors_from'],
                                                'selectItems': ['key_', 'lastclock']})


                #problems on disabled/maintenance/deleted hosts don't have triggers
                #have to do that because of how zabbix housekeeping service work
                #API reports past problems for hosts that no longer exist
                if not trigger:
                    continue

                service_id = problem['eventid']
                host_id = trigger[0]['hosts'][0]['hostid']

                #new host to report, we only need to do that at first problem for that host
                if host_id not in self.new_hosts:
                    self.new_hosts[host_id] = GenericHost()
                    self.new_hosts[host_id].name = trigger[0]['hosts'][0]['name']

                    #host has active maintenance period
                    if trigger[0]['hosts'][0]['maintenance_status'] == "1":
                        self.new_hosts[host_id].scheduled_downtime = True

                    #old api shows host interfaces status in host object
                    if version.parse(self.zbx_version) < version.parse("5.4.0"):

                        #host not available via agent
                        if trigger[0]['hosts'][0].get('available', '0') == "2":
                            self.new_hosts[host_id].status = "DOWN"
                            self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['error']
                            self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['errors_from'])

                        #host not available via ipmi
                        if trigger[0]['hosts'][0].get('ipmi_available', '0') == "2":
                            self.new_hosts[host_id].status = "DOWN"
                            self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['ipmi_error']
                            self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['ipmi_errors_from'])

                        #host not available via jmx
                        if trigger[0]['hosts'][0].get('jmx_available', '0') == "2":
                            self.new_hosts[host_id].status = "DOWN"
                            self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['jmx_error']
                            self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['jmx_errors_from'])

                        #host not available via snmp
                        if trigger[0]['hosts'][0].get('snmp_available', '0') == "2":
                            self.new_hosts[host_id].status = "DOWN"
                            self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['snmp_error']
                            self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['snmp_errors_from'])

                    #new api shows host interfaces status in hostinterfaces object
                    else:

                        #get all host interfaces
                        hostinterfaces = self.zlapi.do_request("hostinterface.get", {"hostids": host_id})

                        #check them all and mark host as DOWN on first not available interface
                        for hostinterface in hostinterfaces:
                            if hostinterface.get('available', '0') == "2":
                                self.new_hosts[host_id].status = "DOWN"
                                self.new_hosts[host_id].status_information = hostinterface['error']
                                self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(hostinterface['errors_from'])
                                #we stop checking rest of interfaces
                                break

                #service to report
                self.new_hosts[host_id].services[service_id] = GenericService()
                self.new_hosts[host_id].services[service_id].host = trigger[0]['hosts'][0]['name']
                self.new_hosts[host_id].services[service_id].status = self.statemap.get(problem['severity'], problem['severity'])
                self.new_hosts[host_id].services[service_id].duration = HumanReadableDurationFromTimestamp(problem['clock'])
                self.new_hosts[host_id].services[service_id].name = trigger[0]['items'][0]['key_']
                self.new_hosts[host_id].services[service_id].last_check = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(int(trigger[0]['items'][0]['lastclock'])))

                #we add opdata to status information just like in zabbix GUI
                if problem["opdata"] != "":
                    self.new_hosts[host_id].services[service_id].status_information = problem['name'] + " (" + problem["opdata"] + ")"
                else:
                    self.new_hosts[host_id].services[service_id].status_information = problem['name']

                #service is acknowledged
                if problem['acknowledged'] == "1":
                    self.new_hosts[host_id].services[service_id].acknowledged = True

        except ZabbixLightApiException:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        return Result()

    # Disable set_recheck (nosense in Zabbix)
    def set_recheck(self, info_dict):
        pass
