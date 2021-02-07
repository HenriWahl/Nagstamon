# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Zabbix.py based on Checkmk Multisite.py

import sys
import urllib.parse
import time
import logging
import datetime

from Nagstamon.Helpers import (HumanReadableDurationFromTimestamp,
                               webbrowser_open)
from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.thirdparty.zabbix_api import (ZabbixAPI,
                                             ZabbixAPIException)

class ZabbixProblemBasedServer(GenericServer):

    TYPE = 'ZabbixProblemBased'
    zapi = None

    if conf.debug_mode is True:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING

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
        self.ignore_cert = conf.servers[self.get_name()].ignore_cert
        self.validate_certs = not self.ignore_cert


    def _login(self):
        try:
            # create ZabbixAPI if not yet created
            if self.zapi is None:
                self.zapi = ZabbixAPI(server=self.monitor_url, path="", log_level=self.log_level, validate_certs=self.validate_certs)
            # login if not yet logged in, or if login was refused previously
            if not self.zapi.logged_in():
                self.zapi.login(self.username, self.password)
        except ZabbixAPIException:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

    def _get_status(self):
        """
            Get status from Zabbix Server
        """

        # Create URLs for the configured filters
        self._login()

        # =========================================
        # problems
        # =========================================
        problems = []
        try:
            #Get all current problems (trigger based)
            problems = self.zapi.problem.get({'recent': "False"})

            for problem in problems:

                #get trigger which rose current problem
                trigger = self.zapi.trigger.get({'triggerids': problem['objectid'],
                                                'monitored': True,
                                                'active': True,
                                                'selectHosts': ['hostid', 'name', 'maintenance_status',
                                                                'available', 'error', 'errors_from',
                                                                'ipmi_available', 'ipmi_error', 'ipmi_errors_from',
                                                                'jmx_available', 'jmx_error', 'jmx_errors_from',
                                                                'snmp_available', 'snmp_error', 'snmp_errors_from'],
                                                'selectItems': ['key_', 'lastclock']})


                #problems on disabled/maintenanced/deleted hosts don't have triggers
                #have to to that becouse of how zabbix houesekeeping service worke
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

                    #host not available via agent
                    if trigger[0]['hosts'][0]['available'] == "2":
                        self.new_hosts[host_id].status = "DOWN"
                        self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['error']
                        self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['errors_from'])

                    #host not available via ipmi
                    if trigger[0]['hosts'][0]['ipmi_available'] == "2":
                        self.new_hosts[host_id].status = "DOWN"
                        self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['ipmi_error']
                        self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['ipmi_errors_from'])

                    #host not available via jmx
                    if trigger[0]['hosts'][0]['jmx_available'] == "2":
                        self.new_hosts[host_id].status = "DOWN"
                        self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['jmx_error']
                        self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['jmx_errors_from'])

                    #host not available via snmp
                    if trigger[0]['hosts'][0]['snmp_available'] == "2":
                        self.new_hosts[host_id].status = "DOWN"
                        self.new_hosts[host_id].status_information = trigger[0]['hosts'][0]['snmp_error']
                        self.new_hosts[host_id].duration = HumanReadableDurationFromTimestamp(trigger[0]['hosts'][0]['snmp_errors_from'])

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

        except (ZabbixAPIException):
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            print(sys.exc_info())
            return Result(result=result, error=error)

        return Result()

    # Disable set_recheck (nosense in Zabbix)
    def set_recheck(self, info_dict):
        pass
