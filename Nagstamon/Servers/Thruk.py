# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
# Thruk additions copyright by dcec@Github
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

from collections import OrderedDict
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Config import conf
import sys
import json
import datetime
import copy
import urllib.parse

from Nagstamon.Helpers import HumanReadableDurationFromTimestamp
from Nagstamon.Helpers import webbrowser_open
from Nagstamon.Objects import (GenericHost, GenericService, Result)


class ThrukServer(GenericServer):
    """
        Thruk is derived from generic (Nagios) server
    """
    TYPE = 'Thruk'

    # dictionary to translate status bitmaps on webinterface into status flags
    # this are defaults from Nagios
    # "disabled.gif" is in Nagios for hosts the same as "passiveonly.gif" for services
    STATUS_MAPPING = { "ack.gif" : "acknowledged", \
                       "passiveonly.gif" : "passiveonly", \
                       "disabled.gif" : "passiveonly", \
                       "ndisabled.gif" : "notifications_disabled", \
                       "downtime.gif" : "scheduled_downtime", \
                       "flapping.gif" : "flapping"}

    # Entries for monitor default actions in context menu
    MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Submit check result", "Downtime"]

    # Arguments available for submitting check results
    SUBMIT_CHECK_RESULT_ARGS = ["check_output", "performance_data"]

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS = { "monitor": "$MONITOR$", \
                    "hosts": "$MONITOR-CGI$/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&page=1&entries=all", \
                    "services": "$MONITOR-CGI$/status.cgi?dfl_s0_value_sel=5&dfl_s0_servicestatustypes=29&dfl_s0_op=%3D&style=detail&dfl_s0_type=host&dfl_s0_serviceprops=0&dfl_s0_servicestatustype=4&dfl_s0_servicestatustype=8&dfl_s0_servicestatustype=16&dfl_s0_servicestatustype=1&hidetop=&dfl_s0_hoststatustypes=15&dfl_s0_val_pre=&hidesearch=2&dfl_s0_value=all&dfl_s0_hostprops=0&nav=&page=1&entries=all", \
                    "history": "$MONITOR-CGI$/history.cgi?host=all&page=1&entries=all"}

    STATES_MAPPING = {"hosts" : {0 : "OK", 1 : "DOWN", 2 : "UNREACHABLE"}, \
                      "services" : {0 : "OK", 1 : "WARNING", 2 : "CRITICAL", 3 : "UNKNOWN"}}


    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)


    def init_HTTP(self):
        """
            partly not constantly working Basic Authorization requires extra Autorization headers,
            different between various server types
        """
        if self.session is None:
            GenericServer.init_HTTP(self)

        # get cookie from login page via url retrieving as with other urls
        try:
            # login and get cookie
            if self.session is None or self.session.cookies.get('thruk_auth') is None:
                self.login()
        except:
            self.error(sys.exc_info())


    def init_config(self):
        """
            set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        # Thruk allows requesting only needed information to reduce traffic
        self.cgiurl_services = self.monitor_cgi_url + "/status.cgi?host=all&servicestatustypes=28&view_mode=json&"\
                                                      "entries=all&columns=host_name,description,state,last_check,"\
                                                      "last_state_change,plugin_output,current_attempt,"\
                                                      "max_check_attempts,active_checks_enabled,is_flapping,"\
                                                      "notifications_enabled,acknowledged,state_type,"\
                                                      "scheduled_downtime_depth,host_display_name,display_name"
        # hosts (up or down or unreachable)
        self.cgiurl_hosts = self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&"\
                                                    "dfl_s0_hoststatustypes=12&dfl_s1_hostprops=1&dfl_s2_hostprops=4&dfl_s3_hostprops=524288&&dfl_s4_hostprops=4096&dfl_s5_hostprop=16&"\
                                                    "view_mode=json&entries=all&"\
                                                    "columns=name,state,last_check,last_state_change,"\
                                                    "plugin_output,current_attempt,max_check_attempts,"\
                                                    "active_checks_enabled,notifications_enabled,is_flapping,"\
                                                    "acknowledged,scheduled_downtime_depth,state_type,host_display_name,display_name"

    def login(self):
        """
            use pure session instead of fetch_url to get Thruk session
        """
        if self.session is None:
            self.refresh_authentication = False
            GenericServer.init_HTTP(self)

        if self.use_autologin is True:
            req = self.session.post(self.monitor_cgi_url + '/user.cgi?', data={}, headers={'X-Thruk-Auth-Key':self.autologin_key.strip()})
            if conf.debug_mode:
                self.debug(server=self.get_name(), debug='Auto Login status: ' + req.url + ' http code : ' + str(req.status_code))
            if req.status_code != 200:
                self.refresh_authentication = True
                return Result(result=None, error="Login failed")
        else:
            # set thruk test cookie to in order to directly login
            self.session.cookies.set('thruk_test', '***')
            req = self.session.post(self.monitor_cgi_url + '/login.cgi?',
                            data={'login': self.get_username(),
                                    'password': self.get_password(),
                                    'submit': 'Login'})
            if conf.debug_mode:
                self.debug(server=self.get_name(), debug='Login status: ' + req.url + ' http code : ' + str(req.status_code))
            if req.status_code != 200:
                self.refresh_authentication = True
                return Result(result=None, error="Login failed")

        if self.disabled_backends is not None:
            self.session.cookies.set('thruk_backends', '&'.join((f"{v}=2" for v in self.disabled_backends.split(','))))
            print(self.session.cookies.get('thruk_backends'))

    def open_monitor(self, host, service=''):
        '''
            open monitor from tablewidget context menu
        '''
        # only type is important so do not care of service '' in case of host monitor
        if service == '':
            url = self.monitor_cgi_url + '/extinfo.cgi?type=1&' + urllib.parse.urlencode( { 'host': host })
        else:
            url = self.monitor_cgi_url + '/extinfo.cgi?type=2&' + urllib.parse.urlencode( { 'host': host, 'service': self.hosts[host].services[ service ].real_name })

        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='Open host/service monitor web page {0}'.format(url))
        webbrowser_open(url)

    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None):
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
            cgi_data['service'] = self.hosts[host].services[ service ].real_name
        cgi_data['com_author'] = author
        cgi_data['com_data'] = comment
        cgi_data['btnSubmit'] = 'Commit'
        if notify is True:
            cgi_data['send_notification'] = 'on'
        if persistent is True:
            cgi_data['persistent'] = 'on'
        if sticky is True:
            cgi_data['sticky_ack'] = 'on'

        self.fetch_url(url, giveback='raw', cgi_data=cgi_data)

        # acknowledge all services on a host
        if all_services:
            for s in all_services:
                cgi_data['cmd_typ'] = '34'
                cgi_data['service'] = self.hosts[host].services[ s ].real_name
                self.fetch_url(url, giveback='raw', cgi_data=cgi_data)

    def _set_recheck(self, host, service):
        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        if service != '':
            if self.hosts[host].services[ service ].is_passive_only():
                # Do not check passive only checks
                return
        try:
            # get start time from Nagios as HTML to use same timezone setting like the locally installed Nagios
            result = self.fetch_url(
                self.monitor_cgi_url + '/cmd.cgi?' + urllib.parse.urlencode({'cmd_typ': '96', 'host': host}))
            self.start_time = dict(result.result.find(attrs={'name': 'start_time'}).attrs)['value']
            # decision about host or service - they have different URLs
            if service == '':
                # host
                cmd_typ = '96'
                service_name = ''
            else:
                # service @ host
                cmd_typ = '7'
                service_name = self.hosts[host].services[ service ].real_name
            # ignore empty service in case of rechecking a host
            cgi_data = urllib.parse.urlencode([('cmd_typ', cmd_typ),
                                               ('cmd_mod', '2'),
                                               ('host', host),
                                               ('service', service_name),
                                               ('start_time', self.start_time),
                                               ('force_check', 'on'),
                                               ('btnSubmit', 'Commit')])
            # execute POST request
            self.fetch_url(self.monitor_cgi_url + '/cmd.cgi', giveback='raw', cgi_data=cgi_data)
        except:
            traceback.print_exc(file=sys.stdout)

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
            cgi_data['service'] = self.hosts[host].services[ service ].real_name
        cgi_data['com_author'] = author
        cgi_data['com_data'] = comment
        cgi_data['fixed'] = fixed
        cgi_data['start_time'] = start_time
        cgi_data['end_time'] = end_time
        cgi_data['hours'] = hours
        cgi_data['minutes'] = minutes
        cgi_data['btnSubmit'] = 'Commit'

        # running remote cgi command
        self.fetch_url(url, giveback='raw', cgi_data=cgi_data)

    def _get_status(self):
        """
            Get status from Thruk Server
        """
        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            # JSON experiments
            result = self.fetch_url(self.cgiurl_hosts, giveback='raw')
            jsonraw, error, status_code = copy.deepcopy(result.result),\
                                          copy.deepcopy(result.error),\
                                          result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(jsonraw, error, status_code)
            # if there are errors return them
            if errors_occured is not None:
                return(errors_occured)

            # in case basic auth did not work try form login cookie based login
            if jsonraw.startswith("<"):
                self.refresh_authentication = True
                return Result(result=None, error="Login failed")

            # in case JSON is not empty evaluate it
            elif not jsonraw == "[]":
                hosts = json.loads(jsonraw)

                for h in hosts:
                    if h["name"] not in self.new_hosts:
                        self.new_hosts[h["name"]] = GenericHost()
                        self.new_hosts[h["name"]].name = h["name"]
                        self.new_hosts[h["name"]].server = self.name
                        self.new_hosts[h["name"]].status = self.STATES_MAPPING["hosts"][h["state"]]
                        self.new_hosts[h["name"]].last_check = datetime.datetime.fromtimestamp(int(h["last_check"])).isoformat(" ")
                        self.new_hosts[h["name"]].duration = HumanReadableDurationFromTimestamp(h["last_state_change"])
                        self.new_hosts[h["name"]].attempt = "%s/%s" % (h["current_attempt"], h["max_check_attempts"])
                        self.new_hosts[h["name"]].status_information = h["plugin_output"].replace("\n", " ").strip()
                        self.new_hosts[h["name"]].passiveonly = not(bool(int(h["active_checks_enabled"])))
                        self.new_hosts[h["name"]].notifications_disabled = not(bool(int(h["notifications_enabled"])))
                        self.new_hosts[h["name"]].flapping = bool(int(h["is_flapping"]))
                        self.new_hosts[h["name"]].acknowledged = bool(int(h["acknowledged"]))
                        self.new_hosts[h["name"]].scheduled_downtime = bool(int(h["scheduled_downtime_depth"]))
                        self.new_hosts[h["name"]].status_type = {0: "soft", 1: "hard"}[h["state_type"]]
                    del h
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            # JSON experiments
            result = self.fetch_url(self.cgiurl_services, giveback="raw")
            jsonraw, error, status_code = copy.deepcopy(result.result),\
                                          copy.deepcopy(result.error),\
                                          result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(jsonraw, error, status_code)
            # if there are errors return them
            if errors_occured is not None:
                return(errors_occured)

            # in case basic auth did not work try form login cookie based login
            if jsonraw.startswith("<"):
                self.refresh_authentication = True
                return Result(result=None, error="Login failed")

            # in case JSON is not empty evaluate it
            elif not jsonraw == "[]":
                services = json.loads(jsonraw)

                for s in services:
                    # host objects contain service objects
                    if s["host_name"] not in self.new_hosts:
                        self.new_hosts[s["host_name"]] = GenericHost()
                        self.new_hosts[s["host_name"]].name = s["host_name"]
                        self.new_hosts[s["host_name"]].server = self.name
                        self.new_hosts[s["host_name"]].status = "UP"

                    if self.use_display_name_service:
                        entry = s["display_name"]
                    else:
                        entry = s["description"]

                    # if a service does not exist create its object
                    if entry not in self.new_hosts[s["host_name"]].services:
                        self.new_hosts[s["host_name"]].services[ entry ] = GenericService()
                        self.new_hosts[s["host_name"]].services[ entry ].host = s["host_name"]

                        self.new_hosts[s["host_name"]].services[ entry ].name = entry
                        self.new_hosts[s["host_name"]].services[ entry ].real_name = s["description"]

                        self.new_hosts[s["host_name"]].services[ entry ].server = self.name
                        self.new_hosts[s["host_name"]].services[ entry ].status = self.STATES_MAPPING["services"][s["state"]]
                        self.new_hosts[s["host_name"]].services[ entry ].last_check = datetime.datetime.fromtimestamp(int(s["last_check"])).isoformat(" ")
                        self.new_hosts[s["host_name"]].services[ entry ].duration = HumanReadableDurationFromTimestamp(s["last_state_change"])
                        self.new_hosts[s["host_name"]].services[ entry ].attempt = "%s/%s" % (s["current_attempt"], s["max_check_attempts"])
                        self.new_hosts[s["host_name"]].services[ entry ].status_information = s["plugin_output"].replace("\n", " ").strip()
                        self.new_hosts[s["host_name"]].services[ entry ].passiveonly = not(bool(int(s["active_checks_enabled"])))
                        self.new_hosts[s["host_name"]].services[ entry ].notifications_disabled = not(bool(int(s["notifications_enabled"])))
                        self.new_hosts[s["host_name"]].services[ entry ].flapping = not(bool(int(s["notifications_enabled"])))
                        self.new_hosts[s["host_name"]].services[ entry ] .acknowledged = bool(int(s["acknowledged"]))
                        self.new_hosts[s["host_name"]].services[ entry ].scheduled_downtime = bool(int(s["scheduled_downtime_depth"]))
                        self.new_hosts[s["host_name"]].services[ entry ].status_type = {0: "soft", 1: "hard"}[s["state_type"]]
                        del s
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # dummy return in case all is OK
        return Result()
