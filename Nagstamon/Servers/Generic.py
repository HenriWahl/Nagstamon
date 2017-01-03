# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2016 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

import requests
import requests_kerberos
# disable annoying InsecureRequestWarning warnings
try:
    requests.packages.urllib3.disable_warnings()
except:
    # older requests version might not have the packages submodule
    # for example the one in Ubuntu 14.04
    pass

import sys
import socket
import copy
import datetime
import traceback
import platform
import urllib.parse
from bs4 import BeautifulSoup

from Nagstamon.Helpers import (host_is_filtered_out_by_re,
                               ServiceIsFilteredOutByRE,
                               StatusInformationIsFilteredOutByRE,
                               CriticalityIsFilteredOutByRE,
                               not_empty,
                               webbrowser_open,
                               STATES)

from Nagstamon.Objects import (GenericService,
                               GenericHost,
                               Result)

from Nagstamon.Config import (conf,
                              AppInfo,
                              debug_queue)

from collections import OrderedDict


class GenericServer(object):
    '''
        Abstract server which serves as template for all other types
        Default values are for Nagios servers
    '''

    TYPE = 'Generic'

    # dictionary to translate status bitmaps on webinterface into status flags
    # this are defaults from Nagios
    # 'disabled.gif' is in Nagios for hosts the same as 'passiveonly.gif' for services
    STATUS_MAPPING = {'ack.gif': 'acknowledged', \
                      'passiveonly.gif': 'passiveonly', \
                      'disabled.gif': 'passiveonly', \
                      'ndisabled.gif': 'notifications_disabled', \
                      'downtime.gif': 'scheduled_downtime', \
                      'flapping.gif': 'flapping'}

    # Entries for monitor default actions in context menu
    MENU_ACTIONS = ['Monitor', 'Recheck', 'Acknowledge', 'Submit check result', 'Downtime']

    # Arguments available for submitting check results
    SUBMIT_CHECK_RESULT_ARGS = ['check_output', 'performance_data']

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS = {'monitor': '$MONITOR$', \
                    'hosts': '$MONITOR-CGI$/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12', \
                    'services': '$MONITOR-CGI$/status.cgi?host=all&servicestatustypes=253', \
                    'history': '$MONITOR-CGI$/history.cgi?host=all'}

    USER_AGENT = '{0}/{1}/{2}'.format(AppInfo.NAME, AppInfo.VERSION, platform.system())

    # needed to check return code of monitor server in case of false authentication
    STATUS_CODES_NO_AUTH = [401, 403]

    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        self.enabled = False
        self.type = ''
        self.monitor_url = ''
        self.monitor_cgi_url = ''
        self.username = ''
        self.password = ''
        self.use_proxy = False
        self.use_proxy_from_os = False
        self.proxy_address = ''
        self.proxy_username = ''
        self.proxy_password = ''
        self.auth_type = ''
        self.hosts = dict()
        self.new_hosts = dict()
        self.isChecking = False
        self.CheckingForNewVersion = False
        # store current and difference of worst state for notification
        self.worst_status_diff = self.worst_status_current = 'UP'
        self.nagitems_filtered_list = list()
        self.nagitems_filtered = {'services': {'CRITICAL': [], 'WARNING': [], 'UNKNOWN': []},
                                  'hosts': {'DOWN': [], 'UNREACHABLE': []}}
        # number of filtered items
        self.nagitems_filtered_count = 0
        self.down = 0
        self.unreachable = 0
        self.unknown = 0
        self.critical = 0
        self.warning = 0
        self.all_ok = True
        self.status = ''
        self.status_description = ''
        self.status_code = 0
        self.has_error = False
        self.timeout = 10

        # The events_* are recycled from GUI.py
        # history of events to track status changes for notifications
        # events that came in
        self.events_current = {}
        # events that had been already displayed in popwin and need no extra mark
        self.events_history = {}
        # events to be given to custom notification, maybe to desktop notification too
        self.events_notification = {}

        # needed for looping server thread
        self.thread_counter = 0
        # needed for RecheckAll - save start_time once for not having to get it for every recheck
        self.start_time = None

        # Requests-based connections
        self.session = None

        # flag which decides if authentication has to be renewed
        self.refresh_authentication = False
        # to handle Icinga versions this information is necessary, might be of future use for others too
        self.version = ''

        # Special FX
        # Centreon
        self.use_autologin = False
        self.autologin_key = ''
        # Icinga
        self.use_display_name_host = False
        self.use_display_name_service = False
        # Check_MK Multisite
        self.force_authuser = False

        # OP5 api filters
        self.host_filter = 'state !=0'
        self.service_filter = 'state !=0 or host.state != 0'

    def init_config(self):
        '''
            set URLs for CGI - they are static and there is no need to set them with every cycle
        '''
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        #
        # the following variables are not necessary anymore as with 'new' filtering
        #
        # hoststatus
        # hoststatustypes = 12
        # servicestatus
        # servicestatustypes = 253
        # serviceprops & hostprops both have the same values for the same states so I
        # group them together
        # hostserviceprops = 0

        # services (unknown, warning or critical?) as dictionary, sorted by hard and soft state type
        self.cgiurl_services = {
        'hard': self.monitor_cgi_url + '/status.cgi?host=all&servicestatustypes=253&serviceprops=262144&limit=0', \
        'soft': self.monitor_cgi_url + '/status.cgi?host=all&servicestatustypes=253&serviceprops=524288&limit=0'}
        # hosts (up or down or unreachable)
        self.cgiurl_hosts = {
        'hard': self.monitor_cgi_url + '/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=262144&limit=0', \
        'soft': self.monitor_cgi_url + '/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=524288&limit=0'}


    def init_HTTP(self):
        '''
            partly not constantly working Basic Authorization requires extra Authorization headers,
            different between various server types
        '''
        if self.session == None:
            self.session = requests.Session()
            self.session.headers['User-Agent'] = self.USER_AGENT

            # support for different authentication types
            if self.authentication == 'basic':
                # basic authentication
               #self.session.auth = (self.username, self.password)
                self.session.auth = requests.auth.HTTPBasicAuth(self.username, self.password)
            elif self.authentication == 'digest':
                self.session.auth = requests.auth.HTTPDigestAuth(self.username, self.password)
            elif self.authentication == 'kerberos':
                self.session.auth = requests_kerberos.HTTPKerberosAuth()

            # default to not check TLS validity
            self.session.verify = False

            # add proxy information
            self.proxify(self.session)


    def proxify(self, requester):
        '''
            add proxy information to session or single request
        '''
        # check if proxies have to be used
        if self.use_proxy == True:
            if self.use_proxy_from_os == True:
                # if .trust_enf is true the system environment will be evaluated
                requester.trust_env = True
                requester.proxies = dict()
            else:
                # check if username and password are given and provide credentials if needed
                if self.proxy_username == self.proxy_password == '':
                    user_pass = ''
                else:
                    user_pass = '{0}:{1}@'.format(self.proxy_username, self.proxy_password)

                # split and analyze proxy URL
                proxy_address_parts = self.proxy_address.split('//')
                scheme = proxy_address_parts[0]
                host_port = ''.join(proxy_address_parts[1:])

                # use only valid schemes
                if scheme.lower() in ('http:', 'https:'):
                    # merge proxy URL
                    proxy_url = '{0}//{1}{2}'.format(scheme, user_pass, host_port)
                    # fill session.proxies for both protocols
                    requester.proxies = {'http': proxy_url, 'https': proxy_url}
        else:
            # disable evaluation of environment variables
            requester.trust_env = False
            requester.proxies = None


    def reset_HTTP(self):
        '''
            if authentication fails try to reset any HTTP session stuff - might be different for different monitors
        '''
        self.session = None


    def get_name(self):
        '''
        return stringified name
        '''
        return str(self.name)


    def get_username(self):
        '''
        return stringified username
        '''
        return str(self.username)


    def get_password(self):
        '''
        return stringified password
        '''
        return str(self.password)


    def get_server_version(self):
        '''
        dummy function, at the moment only used by Icinga
        '''
        pass


    def set_recheck(self, info_dict):
        self._set_recheck(info_dict['host'], info_dict['service'])


    def _set_recheck(self, host, service):
        if service != '':
            if self.hosts[host].services[service].is_passive_only():
                # Do not check passive only checks
                return
        # get start time from Nagios as HTML to use same timezone setting like the locally installed Nagios
        result = self.FetchURL(
            self.monitor_cgi_url + '/cmd.cgi?' + urllib.parse.urlencode({'cmd_typ': '96', 'host': host}))
        self.start_time = dict(result.result.find(attrs={'name': 'start_time'}).attrs)['value']
        # decision about host or service - they have different URLs
        if service == '':
            # host
            cmd_typ = '96'
        else:
            # service @ host
            cmd_typ = '7'
        # ignore empty service in case of rechecking a host
        cgi_data = urllib.parse.urlencode([('cmd_typ', cmd_typ), \
                                           ('cmd_mod', '2'), \
                                           ('host', host), \
                                           ('service', service), \
                                           ('start_time', self.start_time), \
                                           ('force_check', 'on'), \
                                           ('btnSubmit', 'Commit')])
        # execute POST request
        self.FetchURL(self.monitor_cgi_url + '/cmd.cgi', giveback='raw', cgi_data=cgi_data)


    def set_acknowledge(self, info_dict):
        '''
            different monitors might have different implementations of _set_acknowledge
        '''
        if info_dict['acknowledge_all_services'] == True:
            all_services = info_dict['all_services']
        else:
            all_services = []
        self._set_acknowledge(info_dict['host'],
                              info_dict['service'],
                              info_dict['author'],
                              info_dict['comment'],
                              info_dict['sticky'],
                              info_dict['notify'],
                              info_dict['persistent'],
                              all_services)

        # refresh immediately according to https://github.com/HenriWahl/Nagstamon/issues/86
        # ##self.thread.doRefresh = True


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        '''
            send acknowledge to monitor server - might be different on every monitor type
        '''

        url = self.monitor_cgi_url + '/cmd.cgi'

        # the following flags apply to hosts and services
        #
        # according to sf.net bug #3304098 (https://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3304098&group_id=236865)
        # the send_notification-flag must not exist if it is set to 'off', otherwise
        # the Nagios core interpretes it as set, regardless its real value
        #
        # for whatever silly reason Icinga depends on the correct order of submitted form items...
        # see sf.net bug 3428844
        #
        # Thanks to Icinga ORDER OF ARGUMENTS IS IMPORTANT HERE!
        #
        cgi_data = OrderedDict()
        if service == '':
            cgi_data['cmd_typ'] = '33'
        else:
            cgi_data['cmd_typ'] = '34'
        cgi_data['cmd_mod'] = '2'
        cgi_data['host'] = host
        if service != '':
            cgi_data['service'] = service
        cgi_data['com_author'] = author
        cgi_data['com_data'] = comment
        cgi_data['btnSubmit'] = 'Commit'
        if notify == True:
            cgi_data['send_notification'] = 'on'
        if persistent == True:
            cgi_data['persistent'] = 'on'
        if sticky == True:
            cgi_data['sticky_ack'] = 'on'

        self.FetchURL(url, giveback='raw', cgi_data=cgi_data)

        # acknowledge all services on a host
        if len(all_services) > 0:
            for s in all_services:
                cgi_data['cmd_typ'] = '34'
                cgi_data['service'] = s
                self.FetchURL(url, giveback='raw', cgi_data=cgi_data)


    def set_downtime(self, info_dict):
        '''
            different monitors might have different implementations of _set_downtime
        '''
        self._set_downtime(info_dict['host'],
                           info_dict['service'],
                           info_dict['author'],
                           info_dict['comment'],
                           info_dict['fixed'],
                           info_dict['start_time'],
                           info_dict['end_time'],
                           info_dict['hours'],
                           info_dict['minutes'])


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        '''
            finally send downtime command to monitor server
        '''
        url = self.monitor_cgi_url + '/cmd.cgi'

        # for some reason Icinga is very fastidiuos about the order of CGI arguments, so please
        # here we go... it took DAYS :-(
        cgi_data = OrderedDict()
        if service == '':
            cgi_data['cmd_typ'] = '55'
        else:
            cgi_data['cmd_typ'] = '56'
        cgi_data['cmd_mod'] = '2'
        cgi_data['trigger'] = '0'
        cgi_data['host'] = host
        if service != '':
            cgi_data['service'] = service
        cgi_data['com_author'] = author
        cgi_data['com_data'] = comment
        cgi_data['fixed'] = fixed
        cgi_data['start_time'] = start_time
        cgi_data['end_time'] = end_time
        cgi_data['hours'] = hours
        cgi_data['minutes'] = minutes
        cgi_data['btnSubmit'] = 'Commit'

        # running remote cgi command
        self.FetchURL(url, giveback='raw', cgi_data=cgi_data)


    def set_submit_check_result(self, info_dict):
        """
            start specific submission part
        """
        self._set_submit_check_result(info_dict['host'],
                                      info_dict['service'],
                                      info_dict['state'],
                                      info_dict['comment'],
                                      info_dict['check_output'],
                                      info_dict['performance_data'])


    def _set_submit_check_result(self, host, service, state, comment, check_output, performance_data):
        '''
            worker for submitting check result
        '''
        url = self.monitor_cgi_url + '/cmd.cgi'

        # decision about host or service - they have different URLs
        if service == '':
            # host
            cgi_data = urllib.parse.urlencode([('cmd_typ', '87'), ('cmd_mod', '2'), ('host', host), \
                                               ('plugin_state', {'up': '0', 'down': '1', 'unreachable': '2'}[state]), \
                                               ('plugin_output', check_output), \
                                               ('performance_data', performance_data), ('btnSubmit', 'Commit')])
            self.FetchURL(url, giveback='raw', cgi_data=cgi_data)

        if service != '':
            # service @ host
            cgi_data = urllib.parse.urlencode(
                [('cmd_typ', '30'), ('cmd_mod', '2'), ('host', host), ('service', service), \
                 ('plugin_state', {'ok': '0', 'warning': '1', 'critical': '2', 'unknown': '3'}[state]),
                 ('plugin_output', check_output), \
                 ('performance_data', performance_data), ('btnSubmit', 'Commit')])
            # running remote cgi command
            self.FetchURL(url, giveback='raw', cgi_data=cgi_data)


    def get_start_end(self, host):
        '''
            for GUI to get actual downtime start and end from server - they may vary so it's better to get
            directly from web interface
        '''
        try:
            result = self.FetchURL(
                self.monitor_cgi_url + '/cmd.cgi?' + urllib.parse.urlencode({'cmd_typ': '55', 'host': host}))
            start_time = dict(result.result.find(attrs={'name': 'start_time'}).attrs)['value']
            end_time = dict(result.result.find(attrs={'name': 'end_time'}).attrs)['value']
            # give values back as tuple
            return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return 'n/a', 'n/a'


    def open_monitor(self, host, service=''):
        '''
            open monitor from tablewidget context menu
        '''
        # only type is important so do not care of service '' in case of host monitor
        if service == '':
            typ = 1
        else:
            typ = 2
        if conf.debug_mode:
            self.Debug(server=self.get_name(), host=host, service=service,
                       debug='Open host/service monitor web page ' + self.monitor_cgi_url + '/extinfo.cgi?' + urllib.parse.urlencode(
                           {'type': typ, 'host': host, 'service': service}))
        webbrowser_open(self.monitor_cgi_url + '/extinfo.cgi?' + urllib.parse.urlencode(
            {'type': typ, 'host': host, 'service': service}))


    def open_monitor_webpage(self):
        '''
            open monitor from systray/toparea context menu
        '''

        if conf.debug_mode:
            self.Debug(server=self.get_name(),
                       debug='Open monitor web page ' + self.monitor_cgi_url)
        webbrowser_open(self.monitor_url)


    def _get_status(self):
        '''
            Get status from Nagios Server
        '''
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {'services': [], 'hosts': []}

        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            for status_type in 'hard', 'soft':
                result = self.FetchURL(self.cgiurl_hosts[status_type])               
                htobj, error, status_code = result.result, result.error, result.status_code
                
                # check if any error occured
                errors_occured = self.check_for_error(htobj, error, status_code)
                # if there are errors return them
                if errors_occured != False:
                    return(errors_occured)

                # put a copy of a part of htobj into table to be able to delete htobj
                # too mnuch copy.deepcopy()s here give recursion crashs
                table = htobj('table', {'class': 'status'})[0]

                # access table rows
                # some Icinga versions have a <tbody> tag in cgi output HTML which
                # omits the <tr> tags being found
                if len(table('tbody')) == 0:
                    trs = table('tr', recursive=False)
                else:
                    tbody = table('tbody')[0]
                    trs = tbody('tr', recursive=False)

                # do some cleanup
                del result, error

                # kick out table heads
                trs.pop(0)

                # dummy tds to be deleteable
                tds = []

                for tr in trs:
                    try:
                        # ignore empty <tr> rows
                        if len(tr('td', recursive=False)) > 1:
                            n = dict()
                            # get tds in one tr
                            tds = tr('td', recursive=False)
                            # host
                            try:
                                n['host'] = str(tds[0].table.tr.td.table.tr.td.a.text)
                            except:
                                n['host'] = str(nagitems[len(nagitems) - 1]['host'])
                            # status
                            n['status'] = str(tds[1].text)
                            # last_check
                            n['last_check'] = str(tds[2].text)
                            # duration
                            n['duration'] = str(tds[3].text)
                            # division between Nagios and Icinga in real life... where
                            # Nagios has only 5 columns there are 7 in Icinga 1.3...
                            # ... and 6 in Icinga 1.2 :-)
                            if len(tds) < 7:
                                # the old Nagios table
                                # status_information
                                if len(tds[4](text=not_empty)) == 0:
                                    n['status_information'] = ''
                                else:
                                    n['status_information'] = str(tds[4].text).replace('\n', ' ').strip()
                                # attempts are not shown in case of hosts so it defaults to 'n/a'
                                n['attempt'] = 'n/a'
                            else:
                                # attempts are shown for hosts
                                # to fix http://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3280961&group_id=236865 .attempt needs
                                # to be stripped
                                n['attempt'] = str(tds[4].text).strip()
                                # status_information
                                if len(tds[5](text=not_empty)) == 0:
                                    n['status_information'] = ''
                                else:
                                    n['status_information'] = str(tds[5].text).replace('\n',' ').strip()
                            # status flags
                            n['passiveonly'] = False
                            n['notifications_disabled'] = False
                            n['flapping'] = False
                            n['acknowledged'] = False
                            n['scheduled_downtime'] = False

                            # map status icons to status flags
                            icons = tds[0].findAll('img')
                            for i in icons:
                                icon = i['src'].split('/')[-1]
                                if icon in self.STATUS_MAPPING:
                                    n[self.STATUS_MAPPING[icon]] = True
                            # cleaning
                            del icons

                            # add dictionary full of information about this host item to nagitems
                            nagitems['hosts'].append(n)
                            # after collection data in nagitems create objects from its informations
                            # host objects contain service objects
                            if n['host'] not in self.new_hosts:
                                new_host = n['host']
                                self.new_hosts[new_host] = GenericHost()
                                self.new_hosts[new_host].name = n['host']
                                self.new_hosts[new_host].server = self.name
                                self.new_hosts[new_host].status = n['status']
                                self.new_hosts[new_host].last_check = n['last_check']
                                self.new_hosts[new_host].duration = n['duration']
                                self.new_hosts[new_host].attempt = n['attempt']
                                # ##self.new_hosts[new_host].status_information = n['status_information'].encode('utf-8')
                                self.new_hosts[new_host].status_information = n['status_information']
                                self.new_hosts[new_host].passiveonly = n['passiveonly']
                                self.new_hosts[new_host].notifications_disabled = n['notifications_disabled']
                                self.new_hosts[new_host].flapping = n['flapping']
                                self.new_hosts[new_host].acknowledged = n['acknowledged']
                                self.new_hosts[new_host].scheduled_downtime = n['scheduled_downtime']
                                self.new_hosts[new_host].status_type = status_type
                            del tds, n
                    except:
                        self.Error(sys.exc_info())

                # do some cleanup
                htobj.decompose()
                del htobj, trs, table

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            for status_type in 'hard', 'soft':
                result = self.FetchURL(self.cgiurl_services[status_type])
                htobj, error, status_code = result.result, result.error, result.status_code

                # check if any error occured
                errors_occured = self.check_for_error(htobj, error, status_code)
                # if there are errors return them
                if errors_occured != False:
                    return(errors_occured)

                # too much copy.deepcopy()s here give recursion crashs
                table = htobj('table', {'class': 'status'})[0]

                # some Icinga versions have a <tbody> tag in cgi output HTML which
                # omits the <tr> tags being found
                if len(table('tbody')) == 0:
                    trs = table('tr', recursive=False)
                else:
                    tbody = table('tbody')[0]
                    trs = tbody('tr', recursive=False)

                del result, error

                # kick out table heads
                trs.pop(0)

                # dummy tds to be deleteable
                tds = []

                for tr in trs:
                    try:
                        # ignore empty <tr> rows - there are a lot of them - a Nagios bug?
                        tds = tr('td', recursive=False)
                        if len(tds) > 1:
                            n = dict()
                            # host
                            # the resulting table of Nagios status.cgi table omits the
                            # hostname of a failing service if there are more than one
                            # so if the hostname is empty the nagios status item should get
                            # its hostname from the previuos item - one reason to keep 'nagitems'
                            try:
                                n['host'] = str(tds[0](text=not_empty)[0])
                            except:
                                n['host'] = str(nagitems['services'][len(nagitems['services']) - 1]['host'])
                            # service
                            n['service'] = str(tds[1](text=not_empty)[0])
                            # status
                            n['status'] = str(tds[2](text=not_empty)[0])
                            # last_check
                            n['last_check'] = str(tds[3](text=not_empty)[0])
                            # duration
                            n['duration'] = str(tds[4](text=not_empty)[0])
                            # attempt
                            # to fix http://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3280961&group_id=236865 .attempt needs
                            # to be stripped
                            n['attempt'] = str(tds[5](text=not_empty)[0]).strip()
                            # status_information
                            if len(tds[6](text=not_empty)) == 0:
                                n['status_information'] = ''
                            else:
                                n['status_information'] = str(tds[6].text).replace('\n',  '').strip()
                            # status flags
                            n['passiveonly'] = False
                            n['notifications_disabled'] = False
                            n['flapping'] = False
                            n['acknowledged'] = False
                            n['scheduled_downtime'] = False

                            # map status icons to status flags
                            icons = tds[1].findAll('img')
                            for i in icons:
                                icon = i['src'].split('/')[-1]
                                if icon in self.STATUS_MAPPING:
                                    n[self.STATUS_MAPPING[icon]] = True
                            # cleaning
                            del icons

                            # add dictionary full of information about this service item to nagitems - only if service
                            nagitems['services'].append(n)
                            # after collection data in nagitems create objects of its informations
                            # host objects contain service objects
                            if n['host'] not in self.new_hosts:
                                self.new_hosts[n['host']] = GenericHost()
                                self.new_hosts[n['host']].name = n['host']
                                self.new_hosts[n['host']].status = 'UP'
                                # trying to fix https://sourceforge.net/tracker/index.php?func=detail&aid=3299790&group_id=236865&atid=1101370
                                # if host is not down but in downtime or any other flag this should be evaluated too
                                # map status icons to status flags
                                icons = tds[0].findAll('img')
                                for i in icons:
                                    icon = i['src'].split('/')[-1]
                                    if icon in self.STATUS_MAPPING:
                                        self.new_hosts[n['host']].__dict__[self.STATUS_MAPPING[icon]] = True

                            # if a service does not exist create its object
                            if n['service'] not in self.new_hosts[n['host']].services:
                                new_service = n['service']
                                self.new_hosts[n['host']].services[new_service] = GenericService()
                                self.new_hosts[n['host']].services[new_service].host = n['host']
                                self.new_hosts[n['host']].services[new_service].name = n['service']
                                self.new_hosts[n['host']].services[new_service].server = self.name
                                self.new_hosts[n['host']].services[new_service].status = n['status']
                                self.new_hosts[n['host']].services[new_service].last_check = n['last_check']
                                self.new_hosts[n['host']].services[new_service].duration = n['duration']
                                self.new_hosts[n['host']].services[new_service].attempt = n['attempt']
                                self.new_hosts[n['host']].services[new_service].status_information = n['status_information']
                                self.new_hosts[n['host']].services[new_service].passiveonly = n['passiveonly']
                                self.new_hosts[n['host']].services[new_service].notifications_disabled = n[
                                    'notifications_disabled']
                                self.new_hosts[n['host']].services[new_service].flapping = n['flapping']
                                self.new_hosts[n['host']].services[new_service].acknowledged = n['acknowledged']
                                self.new_hosts[n['host']].services[new_service].scheduled_downtime = n['scheduled_downtime']
                                self.new_hosts[n['host']].services[new_service].status_type = status_type
                            del tds, n
                    except:
                        self.Error(sys.exc_info())

                # do some cleanup
                htobj.decompose()
                del htobj, trs, table

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # some cleanup
        del(nagitems)

        # dummy return in case all is OK
        return Result()


    def GetStatus(self, output=None):
        '''
            get nagios status information from cgiurl and give it back
            as dictionary
            output parameter is needed in case authentication failed so that popwin might ask for credentials
        '''

        # set checking flag to be sure only one thread cares about this server
        self.isChecking = True

        # check if server is enabled, if not, do not get any status
        if self.enabled == False:
            self.worst_status_diff = 'UP'
            self.isChecking = False
            return Result()

        # initialize HTTP first
        self.init_HTTP()

        # get all trouble hosts/services from server specific _get_status()
        status = self._get_status()

        if status != None:
            self.status = status.result
            self.status_description = status.error
            self.status_code = status.status_code
        else:
            return Result()

        # some monitor server seem to have a problem with too short intervals
        # and sometimes send a bad status line which would result in a misleading
        # ERROR display - it seems safe to ignore these errors
        # see https://github.com/HenriWahl/Nagstamon/issues/207
        # Update: Another strange error to ignore is ConnectionResetError
        # see https://github.com/HenriWahl/Nagstamon/issues/295       
        if 'BadStatusLine' in self.status_description or\
           'ConnectionResetError' in self.status_description:
            self.status_description = ''
            self.isChecking = False
            return Result(result=self.status,
                          error=self.status_description,
                          status_code=self.status_code)

        if (self.status == 'ERROR' or
            self.status_description != '' or
            self.status_code >= 400):

            # ask for password if authorization failed
            if 'HTTP Error 401' in self.status_description or \
               'HTTP Error 403' in self.status_description or \
               'HTTP Error 500' in self.status_description or \
               'bad session id' in self.status_description.lower() or \
               'login failed' in self.status_description.lower() or \
               self.status_code in self.STATUS_CODES_NO_AUTH:
                if conf.servers[self.name].enabled == True:
                    # needed to get valid credentials
                    self.refresh_authentication = True
                    # clean existent authentication
                    self.reset_HTTP()
                    self.init_HTTP()
                    status = self._get_status()
                    self.status = status.result
                    self.status_description = status.error
                    self.status_code = status.status_code
                    return(status)
            else:
                self.isChecking = False
                return Result(result=self.status,
                              error=self.status_description,
                              status_code=self.status_code)

        # no new authentication needed
        self.refresh_authentication = False

        # this part has been before in GUI.RefreshDisplay() - wrong place, here it needs to be reset
        self.nagitems_filtered = {'services': {'CRITICAL': [], 'WARNING': [], 'UNKNOWN': []},
                                  'hosts': {'DOWN': [], 'UNREACHABLE': []}}

        # initialize counts for various service/hosts states
        # count them with every miserable host/service respective to their meaning
        self.down = 0
        self.unreachable = 0
        self.unknown = 0
        self.critical = 0
        self.warning = 0

        for host in self.new_hosts.values():
            # Don't enter the loop if we don't have a problem. Jump down to your problem services
            if not host.status == 'UP':
                # add hostname for sorting
                host.host = host.name
                # Some generic filters
                if host.acknowledged == True and conf.filter_acknowledged_hosts_services == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug='Filter: ACKNOWLEDGED ' + str(host.name))
                    host.visible = False

                if host.notifications_disabled == True and\
                        conf.filter_hosts_services_disabled_notifications == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug='Filter: NOTIFICATIONS ' + str(host.name))
                    host.visible = False

                if host.passiveonly == True and conf.filter_hosts_services_disabled_checks == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug='Filter: PASSIVEONLY ' + str(host.name))
                    host.visible = False

                if host.scheduled_downtime == True and conf.filter_hosts_services_maintenance == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug='Filter: DOWNTIME ' + str(host.name))
                    host.visible = False

                if host.flapping == True and conf.filter_all_flapping_hosts == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug='Filter: FLAPPING HOST ' + str(host.name))
                    host.visible = False

                # Check_MK and OP5 do not show the status_type so their host.status_type will be empty
                if host.status_type != '':
                    if conf.filter_hosts_in_soft_state == True and host.status_type == 'soft':
                        if conf.debug_mode:
                            self.Debug(server=self.get_name(), debug='Filter: SOFT STATE ' + str(host.name))
                        host.visible = False

                if host_is_filtered_out_by_re(host.name, conf) == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug='Filter: REGEXP ' + str(host.name))
                    host.visible = False

                if StatusInformationIsFilteredOutByRE(host.status_information, conf) == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(), debug='Filter: REGEXP ' + str(host.name))
                    host.visible = False

                # The Criticality filter can be used only with centreon objects. Other objects don't have the criticality attribute.
                if self.type == 'Centreon':
                    if CriticalityIsFilteredOutByRE(host.criticality, conf):
                        if conf.debug_mode:
                            self.Debug(server=self.get_name(), debug='Filter: REGEXP Criticality ' + str(host.name))
                        host.visible = False

                # Finegrain for the specific state
                if host.status == 'DOWN':
                    if conf.filter_all_down_hosts == True:
                        if conf.debug_mode:
                            self.Debug(server=self.get_name(), debug='Filter: DOWN ' + str(host.name))
                        host.visible = False

                    if host.visible:
                        self.nagitems_filtered['hosts']['DOWN'].append(host)
                        self.down += 1

                if host.status == 'UNREACHABLE':
                    if conf.filter_all_unreachable_hosts == True:
                        if conf.debug_mode:
                            self.Debug(server=self.get_name(), debug='Filter: UNREACHABLE ' + str(host.name))
                        host.visible = False

                    if host.visible:
                        self.nagitems_filtered['hosts']['UNREACHABLE'].append(host)
                        self.unreachable += 1

                # Add host flags for status icons in treeview
                if host.acknowledged:
                    host.host_flags += 'A'
                if host.scheduled_downtime:
                    host.host_flags += 'D'
                if host.flapping:
                    host.host_flags += 'F'
                if host.passiveonly:
                    host.host_flags += 'P'

            for service in host.services.values():
                # add service name for sorting
                service.service = service.name
                # Some generic filtering
                if service.acknowledged == True and conf.filter_acknowledged_hosts_services == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: ACKNOWLEDGED ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                if service.notifications_disabled == True and\
                        conf.filter_hosts_services_disabled_notifications == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: NOTIFICATIONS ' + str(host.name) + ';' + str(service.name))
                    
                    service.visible = False

                if service.passiveonly == True and conf.filter_hosts_services_disabled_checks == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: PASSIVEONLY ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                if service.scheduled_downtime == True and conf.filter_hosts_services_maintenance == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: DOWNTIME ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                if service.flapping == True and conf.filter_all_flapping_services == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: FLAPPING SERVICE ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                if host.scheduled_downtime == True and conf.filter_services_on_hosts_in_maintenance == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: Service on host in DOWNTIME ' + str(host.name) + ';' + str(
                                       service.name))
                    service.visible = False

                if host.acknowledged == True and conf.filter_services_on_acknowledged_hosts == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: Service on acknowledged host' + str(host.name) + ';' + str(
                                       service.name))
                    service.visible = False

                if host.status == 'DOWN' and conf.filter_services_on_down_hosts == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: Service on host in DOWN ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                if host.status == 'UNREACHABLE' and conf.filter_services_on_unreachable_hosts == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: Service on host in UNREACHABLE ' + str(host.name) + ';' + str(
                                       service.name))
                    service.visible = False

                # Check_MK and OP5 do not show the status_type so their host.status_type will be empty
                if service.status_type != '':
                    if conf.filter_services_in_soft_state == True and service.status_type == 'soft':
                        if conf.debug_mode:
                            self.Debug(server=self.get_name(),
                                       debug='Filter: SOFT STATE ' + str(host.name) + ';' + str(service.name))
                        service.visible = False
                else:
                    if len(service.attempt) < 3:
                        service.visible = True
                    elif len(service.attempt) == 3:                    
                        # the old, actually wrong, behaviour
                        real_attempt, max_attempt = service.attempt.split('/')
                        if real_attempt != max_attempt and conf.filter_services_in_soft_state == True:
                            if conf.debug_mode:
                                self.Debug(server=self.get_name(),
                                           debug='Filter: SOFT STATE ' + str(host.name) + ';' + str(service.name))
                            service.visible = False

                if host_is_filtered_out_by_re(host.name, conf) == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: REGEXP ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                if ServiceIsFilteredOutByRE(service.get_name(), conf) == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: REGEXP ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                if StatusInformationIsFilteredOutByRE(service.status_information, conf) == True:
                    if conf.debug_mode:
                        self.Debug(server=self.get_name(),
                                   debug='Filter: REGEXP ' + str(host.name) + ';' + str(service.name))
                    service.visible = False

                # The Criticality filter can be used only with centreon objects. Other objects don't have the criticality attribute.
                if self.type == 'Centreon':
                    if CriticalityIsFilteredOutByRE(service.criticality, conf):
                        if conf.debug_mode:
                            self.Debug(server=self.get_name(), debug='Filter: REGEXP Criticality %s;%s %s' % (
                            (str(host.name), str(service.name), str(service.criticality))))
                        service.visible = False

                # Finegrain for the specific state
                if service.visible:
                    if service.status == 'CRITICAL':
                        if conf.filter_all_critical_services == True:
                            if conf.debug_mode:
                                self.Debug(server=self.get_name(),
                                           debug='Filter: CRITICAL ' + str(host.name) + ';' + str(service.name))
                            service.visible = False
                        else:
                            self.nagitems_filtered['services']['CRITICAL'].append(service)
                            self.critical += 1

                    if service.status == 'WARNING':
                        if conf.filter_all_warning_services == True:
                            if conf.debug_mode:
                                self.Debug(server=self.get_name(),
                                           debug='Filter: WARNING ' + str(host.name) + ';' + str(service.name))
                            service.visible = False
                        else:
                            self.nagitems_filtered['services']['WARNING'].append(service)
                            self.warning += 1

                    if service.status == 'UNKNOWN':
                        if conf.filter_all_unknown_services == True:
                            if conf.debug_mode:
                                self.Debug(server=self.get_name(),
                                           debug='Filter: UNKNOWN ' + str(host.name) + ';' + str(service.name))
                            service.visible = False
                        else:
                            self.nagitems_filtered['services']['UNKNOWN'].append(service)
                            self.unknown += 1
                            
                # Add service flags for status icons in treeview
                if service.acknowledged:
                    service.service_flags += 'A'
                if service.scheduled_downtime:
                    service.service_flags += 'D'
                if service.flapping:
                    service.service_flags += 'F'
                if service.passiveonly:
                    service.service_flags += 'P'
                    
                # Add host of service flags for status icons in treeview
                if host.acknowledged:
                    service.host_flags += 'A'
                if host.scheduled_downtime:
                    service.host_flags += 'D'
                if host.flapping:
                    service.host_flags += 'F'
                if host.passiveonly:
                    service.host_flags += 'P'

        # find out if there has been some status change to notify user
        # compare sorted lists of filtered nagios items
        new_nagitems_filtered_list = []

        for i in self.nagitems_filtered['hosts'].values():
            for h in i:
                new_nagitems_filtered_list.append((h.name, h.status))
        for i in self.nagitems_filtered['services'].values():
            for s in i:
                new_nagitems_filtered_list.append((s.host, s.name, s.status))

        # sort for better comparison
        new_nagitems_filtered_list.sort()

        # in the following lines worst_status_diff only changes from UP to another value if there was some change in the
        # worst status - if it is the same as before it will just keep UP
        # if both lists are identical there was no status change
        if (self.nagitems_filtered_list == new_nagitems_filtered_list):
            self.worst_status_diff = 'UP'
        else:
            # if the new list is shorter than the first and there are no different hosts
            # there one host/service must have been recovered, which is not worth a notification
            diff = []
            for i in new_nagitems_filtered_list:
                if not i in self.nagitems_filtered_list:
                    # collect differences
                    diff.append(i)
            if len(diff) == 0:
                self.worst_status_diff = 'UP'
            else:
                # if there are different hosts/services in list of new hosts there must be a notification
                # get list of states for comparison
                diff_states = []
                for d in diff:
                    diff_states.append(d[-1])
                # temporary worst state index
                worst = 0
                for d in diff_states:
                    # only check worst state if it is valid
                    if d in STATES:
                        if STATES.index(d) > worst:
                            worst = STATES.index(d)

                # final worst state is one of the predefined states
                self.worst_status_diff = STATES[worst]

        # get the current worst state, needed at least for systraystatusicon
        self.worst_status_current = 'UP'
        if self.down > 0:
            self.worst_status_current = 'DOWN'
        elif self.unreachable > 0:
            self.worst_status_current = 'UNREACHABLE'
        elif self.critical > 0:
            self.worst_status_current = 'CRITICAL'
        elif self.warning > 0:
            self.worst_status_current = 'WARNING'
        elif self.unknown > 0:
            self.worst_status_current = 'UNKNOWN'

        # when everything is OK set this flag for GUI to evaluate
        if self.down == 0 and\
           self.unreachable == 0 and\
           self.unknown == 0 and\
           self.critical == 0 and\
           self.warning == 0:
            self.all_ok = True
        else:
            self.all_ok = False

        # copy of listed nagitems for next comparison
        self.nagitems_filtered_list = copy.deepcopy(new_nagitems_filtered_list)
        del new_nagitems_filtered_list

        # put new informations into respective dictionaries
        self.hosts = copy.deepcopy(self.new_hosts)
        self.new_hosts.clear()

        # taken from GUI.RefreshDisplay() - get event history for notification
        # first clear current events
        self.events_current.clear()
        # get all nagitems
        for host in self.hosts.values():
            if not host.status == 'UP':
                # only if host is not filtered out add it to current events
                # the boolean is meaningless for current events
                if host.visible:
                    self.events_current[host.get_hash()] = True
            for service in host.services.values():
                # same for services of host
                if service.visible:
                    self.events_current[service.get_hash()] = True

        # check if some cached event still is relevant - kick it out if not
        for event in list(self.events_history.keys()):
            if not event in self.events_current.keys():
                self.events_history.pop(event)
                self.events_notification.pop(event)

        # if some current event is not yet in event cache add it and mark it as fresh (=True)
        for event in list(self.events_current.keys()):
            if not event in self.events_history.keys() and conf.highlight_new_events:
                self.events_history[event] = True
                self.events_notification[event] = True

        # after all checks are done unset checking flag
        self.isChecking = False

        # return True if all worked well
        return Result()


    def FetchURL(self, url, giveback='obj', cgi_data=None, no_auth=False, multipart=False):
        '''
            get content of given url, cgi_data only used if present
            'obj' FetchURL gives back a dict full of miserable hosts/services,
            'xml' giving back as objectified xml
            'raw' it gives back pure HTML - useful for finding out IP or new version
            existence of cgi_data forces urllib to use POST instead of GET requests
            NEW: gives back a list containing result and, if necessary, a more clear error description
        '''

        # run this method which checks itself if there is some action to take for initializing connection
        # if no_auth is true do not use Auth headers, used by check for new version
        try:
            try:
                # debug
                if conf.debug_mode == True:
                    self.Debug(server=self.get_name(), debug='FetchURL: ' + url + ' CGI Data: ' + str(cgi_data))

                # use session only for connections to monitor servers, other requests like looking for updates
                # should go out without credentials
                if no_auth == False:
                    # most requests come without multipart/form-data
                    if multipart == False:
                        if cgi_data == None:
                            #response = self.session.get(url, timeout=30)
                            response = self.session.get(url, timeout=self.timeout)
                        else:
                            #response = self.session.post(url, data=cgi_data, timeout=30)
                            response = self.session.post(url, data=cgi_data, timeout=self.timeout)
                    else:
                        # Check_MK and Opsview need multipart/form-data encoding
                        # http://stackoverflow.com/questions/23120974/python-requests-post-multipart-form-data-without-filename-in-http-request#23131823
                        form_data = dict()
                        for key in cgi_data:
                            form_data[key] = (None, cgi_data[key])

                        # get response with cgi_data encodes as files
                        response = self.session.post(url, files=form_data, timeout=self.timeout)                   
                else:
                    # send request without authentication data
                    temporary_session = requests.Session()
                    temporary_session.headers['User-Agent'] = self.USER_AGENT

                    # add proxy information if necessary
                    self.proxify(temporary_session)

                    # default to not check TLS validity for temporary sessions
                    temporary_session.verify = False

                    # most requests come without multipart/form-data
                    if multipart == False:
                        if cgi_data == None:
                            #response = temporary_session.get(url, timeout=30)
                            response = temporary_session.get(url, timeout=self.timeout)
                        else:
                            #response = temporary_session.post(url, data=cgi_data, timeout=30)
                            response = temporary_session.post(url, data=cgi_data, timeout=self.timeout)
                    else:
                        # Check_MK and Opsview nees multipart/form-data encoding
                        # http://stackoverflow.com/questions/23120974/python-requests-post-multipart-form-data-without-filename-in-http-request#23131823
                        form_data = dict()
                        for key in cgi_data:
                            form_data[key] = (None, cgi_data[key])
                        # get response with cgi_data encodes as files
                        #response = temporary_session.post(url, files=form_data, timeout=30)
                        response = temporary_session.post(url, files=form_data, timeout=self.timeout)

                    # cleanup
                    del temporary_session

            except Exception as err:               
                traceback.print_exc(file=sys.stdout)
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error, status_code=-1)

            # give back pure HTML or XML in case giveback is 'raw'
            if giveback == 'raw':
                # .text gives content in unicode
                return Result(result=response.text,
                              status_code=response.status_code)

            # objectified HTML
            if giveback == 'obj':
                yummysoup = BeautifulSoup(response.text, 'html.parser')
                return Result(result=yummysoup, status_code=response.status_code)

            # objectified generic XML, valid at least for Opsview and Centreon
            elif giveback == 'xml':
                xmlobj = BeautifulSoup(response.text, 'html.parser')
                return Result(result=xmlobj,
                              status_code=response.status_code)

        except:
            traceback.print_exc(file=sys.stdout)

            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error, status_code=response.status_code)

        result, error = self.Error(sys.exc_info())

        return Result(result=result, error=error, status_code=response.status_code)


    def GetHost(self, host):
        '''
            find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
            have their ip saved in Nagios
        '''

        # the fasted method is taking hostname as used in monitor
        if conf.connect_by_host == True or host == '':
            return Result(result=host)

        # initialize ip string
        ip = ''

        # glue nagios cgi url and hostinfo
        cgiurl_host = self.monitor_cgi_url + '/extinfo.cgi?type=1&host=' + host

        # get host info
        result = self.FetchURL(cgiurl_host, giveback='obj')
        htobj = result.result

        try:
            # take ip from html soup
            ip = htobj.findAll(name='div', attrs={'class': 'data'})[-1].text

            # workaround for URL-ified IP as described in SF bug 2967416
            # https://sourceforge.net/tracker/?func=detail&aid=2967416&group_id=236865&atid=1101370
            if '://' in ip: ip = ip.split('://')[1]

            # last-minute-workaround for https://github.com/HenriWahl/Nagstamon/issues/48
            if ',' in ip: ip = ip.split(',')[0]

            # print IP in debug mode
            if conf.debug_mode == True:
                self.Debug(server=self.get_name(), host=host, debug='IP of %s:' % (host) + ' ' + ip)
            # when connection by DNS is not configured do it by IP
            if conf.connect_by_dns == True:
                # try to get DNS name for ip, if not available use ip
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except:
                    address = ip
            else:
                address = ip
        except:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # do some cleanup
        del htobj

        # give back host or ip
        return Result(result=address)


    def GetItemsGenerator(self):
        '''
            Generator for plain listing of all filtered items, used in QUI for tableview
        '''

        # reset number of filtered items
        self.nagitems_filtered_count = 0

        for state in self.nagitems_filtered['hosts'].values():
            for host in state:
                # increase number of items for use in table
                self.nagitems_filtered_count += 1
                yield (host)

        for state in self.nagitems_filtered['services'].values():
            for service in state:
                # increase number of items for use in table
                self.nagitems_filtered_count += 1
                yield (service)


    def Hook(self):
        '''
            allows to add some extra actions for a monitor server to be executed in RefreshLoop
            inspired by Centreon and its seemingly Alzheimer disease regarding session ID/Cookie/whatever
        '''
        pass


    def Error(self, error):
        '''
            Handle errors somehow - print them or later log them into not yet existing log file
        '''
        if conf.debug_mode:
            debug = ''
            for line in traceback.format_exception(error[0], error[1], error[2], 5):
                debug += line
            self.Debug(server=self.get_name(), debug=debug, head='ERROR')

        return ['ERROR', traceback.format_exception_only(error[0], error[1])[0]]


    def Debug(self, server='', host='', service='', debug='', head='DEBUG'):
        '''
            centralized debugging
        '''

        # initialize items in line to be logged
        log_line = [head + ':', str(datetime.datetime.now())]
        if server != '':
            log_line.append(server)
        if host != '':
            log_line.append(host)
        if service != '':
            log_line.append(service)
        if debug != '':
            log_line.append(debug)

        # put debug info into debug queue
        debug_queue.append(' '.join(log_line))


    def get_events_history_count(self):
        """
            return number of unseen events - those which are set True as unseen
        """
        return(len(list((e for e in self.events_history if self.events_history[e] == True))))

    
    def check_for_error(self, result, error, status_code):
        """
            check if any error occured - if so, return error
        """
        if error != '' or status_code > 400:
            return(Result(result=copy.deepcopy(result),
                          error=copy.deepcopy(error),
                          status_code=copy.deepcopy(status_code)))
        else:
            return(False)

