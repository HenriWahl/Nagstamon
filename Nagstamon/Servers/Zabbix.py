# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# Zabbix.py based on Check_MK Multisite.py

import sys
import urllib.request
import urllib.parse
import urllib.error
import time
import logging
import datetime
# import socket  # never used

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

    # Store indexed host information
    hostinfo = dict()

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
                             'history':  '$MONITOR-CGI$/zabbix.php?action=problem.view&fullscreen=0&page=1&filter_show=2&filter_set=1'}

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
            self.zapi = ZabbixAPI(server=self.monitor_url, path="", log_level=self.log_level,
                                  validate_certs=self.validate_certs)
            self.zapi.login(self.username, self.password)
        except ZabbixAPIException:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

    def getLastApp(self, this_item):
        if len(this_item) > 0:
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
        if self.zapi is None:
            self._login()

        try:
            # Hosts Zabbix API data
            hosts = []
            try:
                hosts = self.zapi.host.get({"output": ["hostid", "host", "name", "status", \
                                                       "available",      "error",      "errors_from", \
                                                       "snmp_available", "snmp_error", "snmp_errors_from", \
                                                       "ipmi_available", "ipmi_error", "ipmi_errors_from", \
                                                       "jmx_available",  "jmx_error",  "jmx_errors_from", \
                                                       "maintenance_status", "maintenance_from"], "selectInterfaces": ["ip"], "filter": {}})
            except (ZabbixError, ZabbixAPIException, APITimeout, Already_Exists):
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)

            #sys.exit(0)
# Enabled no-ZBX
#{'hostid': '10156', 'host': 'p720',                                 'status': '0', 'error': '',                                                                                               'available': '0', 'ipmi_available': '0', 'snmp_available': '0', 'maintenance_status': '0', 'maintenance_from': '0',          'ipmi_errors_from': '0', 'snmp_errors_from': '0',           'ipmi_error': '', 'snmp_error': '',                                                  'jmx_available': '0', 'jmx_errors_from': '0', 'jmx_error': '', 'name': 'p720',            'description': 'Vmware Server hosting Mustang VMs', 'interfaces': [{'ip': '192.168.0.12'}]}
# Enabled    ZBX-Error
#{'hostid': '10152', 'host': 'p710',                                 'status': '0', 'error': 'Get value from agent failed: cannot connect to [[192.168.0.11]:10050]: [113] No route to host',  'available': '2', 'ipmi_available': '0', 'snmp_available': '0', 'maintenance_status': '0', 'maintenance_from': '0',          'ipmi_errors_from': '0', 'snmp_errors_from': '0',           'ipmi_error': '', 'snmp_error': '',                                                  'jmx_available': '0', 'jmx_errors_from': '0', 'jmx_error': '', 'name': 'p710',            'description': '',                                  'interfaces': [{'ip': '192.168.0.11'}]}
# Disabled   ZBX-Error
#{'hostid': '10363', 'host': '564d64fe-fbe0-f6fc-77bf-ae917aae0069', 'status': '1', 'error': 'Get value from agent failed: cannot connect to [[192.168.1.129]:10050]: [113] No route to host', 'available': '2', 'ipmi_available': '0', 'snmp_available': '0', 'maintenance_status': '1', 'maintenance_from': '1513042200', 'ipmi_errors_from': '0', 'snmp_errors_from': '0',           'ipmi_error': '', 'snmp_error': '',                                                  'jmx_available': '0', 'jmx_errors_from': '0', 'jmx_error': '', 'name': 'p720[cloudsrv1]', 'description': 'Eurofims',                          'interfaces': [{'ip': '192.168.1.129'}]}
# Enabled,   No-ZBX, SMTP Error
#{'hostid': '10146', 'host': 'cam4',                                 'status': '0', 'error': '',                                                                                               'available': '0', 'ipmi_available': '0', 'snmp_available': '2', 'maintenance_status': '0', 'maintenance_from': '0',          'ipmi_errors_from': '0', 'snmp_errors_from': '1513770779',  'ipmi_error': '', 'snmp_error': 'Timeout while connecting to "192.168.10.214:161".', 'jmx_available': '0', 'jmx_errors_from': '0', 'jmx_error': '', 'name': 'cam4',            'description': '',                                  'interfaces': [{'ip': '192.168.10.214'}]}
# Enabled,  ZBX OK, JMX OK
#{'hostid': '10108', 'host': '40f4859a-7649-4e1b-8e9c-bb278508335e', 'status': '0', 'error': '',                                                                                               'available': '1', 'ipmi_available': '0', 'snmp_available': '0', 'maintenance_status': '0', 'maintenance_from': '0',          'ipmi_errors_from': '0', 'snmp_errors_from': '0',           'ipmi_error': '', 'snmp_error': '',                                                  'jmx_available': '1', 'jmx_errors_from': '0', 'jmx_error': '', 'name': 'web1',            'description': '', 'interfaces': [{'ip': '192.168.10.14'}, {'ip': '192.168.10.14'}]}
# Enabled   ZBX OK  JMX OK - In maintenance
#{'hostid': '10108', 'host': '40f4859a-7649-4e1b-8e9c-bb278508335e', 'status': '0', 'error': '',                                                                                               'available': '1', 'ipmi_available': '0', 'snmp_available': '0', 'maintenance_status': '1', 'maintenance_from': '1527288840', 'ipmi_errors_from': '0', 'snmp_errors_from': '0',           'ipmi_error': '', 'snmp_error': '',                                                  'jmx_available': '1', 'jmx_errors_from': '0', 'jmx_error': '', 'name': 'web1',            'description': '',  'interfaces': [{'ip': '192.168.10.14'}, {'ip': '192.168.10.14'}]}
            # get All Hosts.
            # 1. Store data in cache (to be used in events
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
                    'status': 'UP', # Host is OK by default
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
                    'address': host['interfaces'][0]['ip'],
                }


                if host['maintenance_status'] == '1':
                    n['scheduled_downtime'] = True

                if host['status'] == '1':
                    # filter services and hosts by "filter_hosts_services_disabled_notifications"
                    n['notifications_disabled'] = True
                    # Filter only hosts by filter "Host & services with disabled checks"
                    n['passiveonly']           = True
                    # This is just to put an icon on host
                    #n['acknowledged']           = True
                    # This is just to put an icon on host
                    #n['flapping']           = True

                if host['available'] == '0' and host['snmp_available'] == '0' and host['ipmi_available'] == '0' and host['jmx_available'] == '0':
                    n['status']             = 'UNREACHABLE'
                    n['status_information'] = 'Host agents in unknown state'
                    n['duration']           = 'Unknown'
                    
                if host['ipmi_available'] == '2':
                    n['status']             = 'DOWN'
                    n['status_information'] = host['ipmi_error']
                    n['duration']           = HumanReadableDurationFromTimestamp(host['ipmi_errors_from'])
                if host['snmp_available'] == '2':
                    n['status']             = 'DOWN'
                    n['status_information'] = host['snmp_error']
                    n['duration']           = HumanReadableDurationFromTimestamp(host['snmp_errors_from'])
                if host['jmx_available'] == '2':
                    n['status']             = 'DOWN'
                    n['status_information'] = host['jmx_error']
                    n['duration']           = HumanReadableDurationFromTimestamp(host['jmx_errors_from'])
                if host['available'] == '2':
                    n['status']             = 'DOWN'
                    n['status_information'] = host['error']
                    n['duration']           = HumanReadableDurationFromTimestamp(host['errors_from'])
                
                # TODO: Try to remove hostinfo             
                self.hostinfo[host['host']] = n

                # Zabbix shows OK hosts too - kick 'em!
                if not n['status'] == 'UP':
                    # add dictionary full of information about this host item to nagitems
                    nagitems["hosts"].append(n)

                # after collection data in nagitems create objects from its informations
                # host objects contain service objects
                new_host = n["host"]
                if new_host not in self.new_hosts:
                    self.new_hosts[new_host] = GenericHost()
                    self.new_hosts[new_host].hostid = n["hostid"]
                    self.new_hosts[new_host].host = n["host"]
                    self.new_hosts[new_host].name = n["name"]
                    self.new_hosts[new_host].status = n["status"]
                    self.new_hosts[new_host].last_check = n["last_check"]
                    self.new_hosts[new_host].duration = n["duration"]
                    self.new_hosts[new_host].attempt = n["attempt"]
                    self.new_hosts[new_host].status_information = n["status_information"]
                    self.new_hosts[new_host].site = n["site"]
                    self.new_hosts[new_host].address = n["address"]
                    self.new_hosts[new_host].notifications_disabled = n["notifications_disabled"]
                    self.new_hosts[new_host].scheduled_downtime = n["scheduled_downtime"]
                    self.new_hosts[new_host].passiveonly = n["passiveonly"]
                    self.new_hosts[new_host].acknowledged = n["acknowledged"]
                    self.new_hosts[new_host].flapping = n["flapping"]
                    
                    
        except ZabbixError:
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        services = []
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

                # value = 1 filters only triggers in "problem status"
                zabbix_triggers = self.zapi.trigger.get(
                    {'sortfield': 'lastchange', 'skipDependent': True, 'groupids': hostgroup_ids,
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
                     'expandData': True,
                     'selectHosts': 'extend'}
                )
                if type(this_trigger) is dict:
                    for triggerid in list(this_trigger.keys()):
                        services.append(this_trigger[triggerid])
                        # get Application name for the trigger
                        this_item = self.zapi.item.get(
                            {'itemids': [this_trigger[triggerid]['items'][0]['itemid']],
                             'selectApplications': 'extend'}
                        )

                        this_trigger[triggerid]['application'] = self.getLastApp(this_item)

                        # get Last Event Information
                        this_event = self.zapi.event.get(
                            {'objectids': [triggerid],
                             "output": "extend",
                             'value': '1'}
                        )
                        this_trigger[triggerid]['acknowledged'] = this_event['acknowledged']

                elif type(this_trigger) is list:
                    for trigger in this_trigger:
                        services.append(trigger)
                        # get Application name for the trigger
                        this_item = self.zapi.item.get(
                            {'itemids': trigger['items'][0]['itemid'],
                             'selectApplications': 'extend'}
                        )

                        trigger['application'] = self.getLastApp(this_item)

                        # get Last Event Information
                        this_event = self.zapi.event.get(
                            {'objectids': [trigger['triggerid']],
                             "output": "extend",
                             'value': '1'}
                        )
                        trigger['acknowledged'] = this_event[0]['acknowledged']

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
                # self.Debug(server=self.get_name(), debug="SERVICE (" + service['application'] + ") STATUS: **" + status + "** PRIORITY: #" + service['priority'])
                # self.Debug(server=self.get_name(), debug="-----======== SERVICE " + str(service))
                if not status == 'OK':
                    if not service['description'].endswith('...'):
                        state = service['description']
                    else:
                        state = service['items'][0]['lastvalue']
                    lastcheck = 0
                    for item in service['items']:
                        if int(item['lastclock']) > lastcheck:
                            lastcheck = int(item['lastclock'])
                    if self.use_description_name_service and \
                            len(service['comments']) != 0:
                        srvc = self.nagiosify_service(service['comments'])
                    else:
                        srvc = service['application']
                    n = {
                        'service': srvc,
                        'status': status,
                        # Putting service in attempt column allow to see it in GUI
                        # 'attempt': '1/1',
                        'attempt': srvc,
                        'duration': HumanReadableDurationFromTimestamp(service['lastchange']),
                        'status_information': state,
                        'last_check': time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(lastcheck)),
                        'site': '',
                        'command': 'zabbix',
                        'triggerid': service['triggerid'],
                        # status flags
                        'passiveonly': False,
                        'notifications_disabled': False,
                        'flapping': False,
                        'acknowledged' : False,
                        'scheduled_downtime': False,
                    }
                    if api_version >= '3.0':
                        n['host'] = service['hosts'][0]['host']
                        n['name'] = service['hosts'][0]['name']
                    else:
                        n['host'] = service['host']
                        n['name'] = service['name']

                    if service['acknowledged'] == '1':
                        n['acknowledged'] = True
                    if self.hostinfo[n['host']]['scheduled_downtime'] == True:
                        n['scheduled_downtime'] = True

                    nagitems["services"].append(n)
                    # after collection data in nagitems create objects of its informations
                    # host objects contain service objects
                    # if not created previously, host should be created with proper data
                    #key = n["host"];
                    key = n["name"];
                    if key not in self.new_hosts:
                        self.new_hosts[key] = GenericHost()
                        self.new_hosts[key].host = n["host"]
                        self.new_hosts[key].name = n["name"]
                        self.new_hosts[key].status = "UP"
                        self.new_hosts[key].site = n["site"]
                        self.new_hosts[key].address = n["host"]

                        ## hosts already got all hosts from Zabbix API
                        for host in hosts:
                            if host['host'] == n["host"]:
                                self.new_hosts[key].address = host['interfaces'][0]['ip']

                    # if a service does not exist create its object
                    if n["service"] not in self.new_hosts[key].services:
                        # workaround for non-existing (or not found) host status flag
                        if n["service"] == "Host is down %s" % (key):
                            self.new_hosts[key].status = "DOWN"
                            # also take duration from "service" aka trigger
                            self.new_hosts[key].duration = n["duration"]
                            if conf.debug_mode is True:
                                self.Debug(server=self.get_name(), debug="Adding Host[" + key + "]")
                        else:
                            new_service = n["triggerid"]
                            self.new_hosts[key].services[new_service] = GenericService()
                            # VSC 
                            if len(n['name']) != 0:
                                self.new_hosts[key].services[new_service].host = n["name"]
                            else:
                                self.new_hosts[key].services[new_service].host = n["host"]

                            # self.new_hosts[key].services[new_service].name = n["service"]
                            # Setting triggerid as service name is not so nice but allow
                            # to acknowledge events properlly
                            self.new_hosts[key].services[new_service].name = n["triggerid"]
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
                            # VSCself.new_hosts[key].services[new_service].address = n["host"]
                            self.new_hosts[key].services[new_service].address = self.new_hosts[key].address
                            self.new_hosts[key].services[new_service].command = n["command"]
                            self.new_hosts[key].services[new_service].triggerid = n["triggerid"]
                            if conf.debug_mode is True:
                                self.Debug(server=self.get_name(), debug="Adding new service[" + new_service + "] **" + n['service'] + "**")

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
            self.Debug(server=self.get_name(), debug="Set Acknowledge Host: " + host + " Service: " + service + " Sticky: " + sticky + " persistent:" + persistent)

        # Service column is storing current trigger id
        triggerid  = service
        p = {
            'message': '%s: %s' % (author, comment),
            'triggerids': [triggerid],
        }
        self._action(self.hosts[host].site, host, service, p)

        # TODO: Currently not working. This should acknowledge all problems from same host
        # acknowledge all services on a host when told to do so
        for s in all_services:
            self._action(self.hosts[host].site, host, s, p)

    def _set_downtime(self, hostname, service, author, comment, fixed, start_time, end_time, hours, minutes):
        hostsids = [0]
        for hostcode in self.hostinfo:
            if self.hostinfo[hostcode]['name'] == hostname:
                hostids = [ self.hostinfo[hostcode]['hostid'] ]
        
        date  = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        stime = time.mktime(date.timetuple())

        date  = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        etime = time.mktime(date.timetuple())
        
        if conf.debug_mode is True:
            self.Debug(server=self.get_name(), debug="Downtime for " + hostname + "[" + str(hostids[0]) + "] stime:" + str(stime) + " etime:" + str(etime))
            
        self.zapi.maintenance.create({'hostids': hostids, 'name': comment, 'description': author, 'active_since': stime, 'active_till': etime, 'maintenance_type' : 0, "timeperiods": [
            { "timeperiod_type": 0, "start_date": stime, "period": etime - stime }
        ]})

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
        address = host;

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


    # ======================================================
    # Special Zabbix implementation functions
    # ======================================================
    def _action(self, site, host, service, specific_params):
        params = {
            'site': self.hosts[host].site,
            'host': self.hosts[host].host,
        }
        params.update(specific_params)

        if self.zapi is None:
            self._login()
        events = []
        for e in self.zapi.event.get({'triggerids': params['triggerids'],
                                      # from zabbix 2.2 should be used "objectids" instead of "triggerids"
                                      'objectids': params['triggerids'],
                                      'hide_unknown': True,  # zabbix 1.8
                                      'acknowledged': False,
                                      'sortfield': 'clock',
                                      'sortorder': 'DESC'}):
            # stop at first event in "OK" status
            if e['value'] == '0':
                break
            events.append(e['eventid'])
        self.zapi.event.acknowledge({'eventids': events, 'message': params['message'], 'action': 0})

    def nagiosify_service(self, service):
        """
            next dirty workaround to get Zabbix events to look Nagios-esque
        """
        if (" on " or " is ") in service:
            for separator in [" on ", " is "]:
                service = service.split(separator)[0]
        return(service)