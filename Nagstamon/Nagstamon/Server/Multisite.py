#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
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
import traceback
import base64
import time

from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer


class MultisiteError(Exception):
    def __init__(self, terminate, result):
        self.terminate = terminate
        self.result    = result


class LastCheckColumnMultisite(Column):
    """
    because Check_MK has a pretty different date format (much better readable) it has to
    be treaten differently

    This is a custom version of LastCheckColumn to be used in list COLUMNS in class Multisite
    """

    ATTR_NAME = 'last_check'

    @classmethod
    def sort_function(cls, model, iter1, iter2, column):
        """ Overrides default sorting behaviour """
        data1, data2 = [model.get_value(x, column) for x in (iter1, iter2)]
        try:
            first = Actions.MachineSortableDateMultisite(data1)
            second = Actions.MachineSortableDateMultisite(data2)
        except ValueError, err:
            print err
            return cmp(first, second)
        return first - second


class DurationColumnMultisite(CustomSortingColumn):
    ATTR_NAME = 'duration'

    @classmethod
    def sort_function(cls, model, iter1, iter2, column):
        """ Overrides default sorting behaviour """
        data1, data2 = [model.get_value(x, column) for x in (iter1, iter2)]
        try:
            first = Actions.MachineSortableDateMultisite(data1)
            second = Actions.MachineSortableDateMultisite(data2)
        except ValueError, err:
            print err
            return cmp(first, second)
        return first - second


class MultisiteServer(GenericServer):
    """
       special treatment for Check_MK Multisite JSON API
    """
    TYPE = 'Check_MK Multisite'

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS= { "monitor": "$MONITOR$",\
                    "hosts": "$MONITOR$/index.py?start_url=view.py?view_name=nagstamon_hosts",\
                    "services": "$MONITOR$/index.py?start_url=view.py?view_name=nagstamon_svc",\
                    "history": '$MONITOR$/index.py?start_url=view.py?view_name=events'}

    # A Monitor CGI URL is not necessary so hide it in settings
    # autologin is used only by Centreon
    DISABLED_CONTROLS = ["label_monitor_cgi_url", "input_entry_monitor_cgi_url", "input_checkbutton_use_autologin", "label_autologin_key", "input_entry_autologin_key"]

    COLUMNS = [
        HostColumn,
        ServiceColumn,
        StatusColumn,
        LastCheckColumnMultisite,
        DurationColumnMultisite,
        AttemptColumn,
        StatusInformationColumn
    ]


    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Prepare all urls needed by nagstamon -
        self.urls = {}
        self.statemap = {}

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Downtime"]

        # flag fo newer cookie authentication
        self.CookieAuth = False


    def init_HTTP(self):
        # Fix eventually missing tailing "/" in url
        if self.monitor_url[-1] != '/':
            self.monitor_url += '/'

        # Prepare all urls needed by nagstamon if not yet done
        if len(self.urls) == len(self.statemap):
            self.urls = {
              'api_services':    self.monitor_url + "view.py?view_name=nagstamon_svc&output_format=python",
              'human_services':  self.monitor_url + "index.py?%s" % \
                                                   urllib.urlencode({'start_url': 'view.py?view_name=nagstamon_svc'}),
              'human_service':   self.monitor_url + "index.py?%s" %
                                                   urllib.urlencode({'start_url': 'view.py?view_name=service'}),

              'api_hosts':       self.monitor_url + "view.py?view_name=nagstamon_hosts&output_format=python",
              'human_hosts':     self.monitor_url + "index.py?%s" %
                                                   urllib.urlencode({'start_url': 'view.py?view_name=nagstamon_hosts'}),
              'human_host':      self.monitor_url + "index.py?%s" %
                                                   urllib.urlencode({'start_url': 'view.py?view_name=hoststatus'}),

              'api_reschedule':  self.monitor_url + 'nagios_action.py?action=reschedule',
              'api_host_act':    self.monitor_url + 'view.py?_transid=-1&_do_actions=yes&_do_confirm=Yes!&output_format=python&view_name=hoststatus',
              'api_service_act': self.monitor_url + 'view.py?_transid=-1&_do_actions=yes&_do_confirm=Yes!&output_format=python&view_name=service',
              'human_events':    self.monitor_url + "index.py?%s" %
                                                   urllib.urlencode({'start_url': 'view.py?view_name=events'}),
            }

            self.statemap = {
                'UNREACH': 'UNREACHABLE',
                'CRIT':    'CRITICAL',
                'WARN':    'WARNING',
                'UNKN':    'UNKNOWN',
                'PEND':    'PENDING',
            }

        if self.CookieAuth:
            # get cookie to access Check_MK web interface
            if len(self.Cookie) == 0:
                # put all necessary data into url string
                logindata = urllib.urlencode({"_username":self.get_username(),\
                                 "_password":self.get_password(),\
                                 "_login":"1",\
                                 "_origtarget": "",\
                                 "filled_in":"login"})

                # the following is necessary for Opsview servers
                # get cookie from login page via url retrieving as with other urls
                try:
                    # login and get cookie
                    urlcontent = self.urlopener.open(self.monitor_url + "/login.py", logindata)
                    urlcontent.close()
                except:
                    self.Error(sys.exc_info())

        GenericServer.init_HTTP(self)


    def init_config(self):
        """
        dummy init_config, called at thread start, not really needed here, just omit extra properties
        """
        pass


    def _get_url(self, url):
        result = self.FetchURL(url, 'raw')
        content, error = result.result, result.error

        if error != "":
            #raise MultisiteError(True, Result(result = copy.deepcopy(content), error = error))
            raise MultisiteError(True, Result(result = content, error = error))

        if content.startswith('WARNING:'):
            c = content.split("\n")

            # Print non ERRORS to the log in debug mode
            self.Debug(server=self.get_name(), debug=c[0])

            raise MultisiteError(False, Result(result = "\n".join(c[1:]),
                                               content = eval("\n".join(c[1:])),
                                               error = c[0]))
        elif content.startswith('ERROR:'):
            raise MultisiteError(True, Result(result = content,
                                               error = content))

        # looks like cookieauth
        elif content.startswith('<'):
            self.CookieAuth = True
            return ""

        return eval(content)


    def _get_status(self):
        """
        Get status from Check_MK Server
        """
        ret = Result()
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        nagitems = {"services":[], "hosts":[]}

        # Create URLs for the configured filters
        url_params = ''

        url_params += '&is_host_acknowledged=-1&is_service_acknowledged=-1'
        url_params += '&is_host_notifications_enabled=-1&is_service_notifications_enabled=-1'
        url_params += '&is_host_active_checks_enabled=-1&is_service_active_checks_enabled=-1'
        url_params += '&host_scheduled_downtime_depth=-1&is_in_downtime=-1'


        try:
            response = []
            try:
                response = self._get_url(self.urls['api_hosts'] + url_params)
            except MultisiteError, e:
                if e.terminate:
                    return e.result

            for row in response[1:]:
                host= dict(zip(response[0], row))
                n = {
                    'host':               host['host'],
                    'status':             self.statemap.get(host['host_state'], host['host_state']),
                    'last_check':         host['host_check_age'],
                    'duration':           host['host_state_age'],
                    'status_information': host['host_plugin_output'],
                    'attempt':            host['host_attempt'],
                    'site':               host['sitename_plain'],
                    'address':            host['host_address'],
                }

                # add dictionary full of information about this host item to nagitems
                nagitems["hosts"].append(n)
                # after collection data in nagitems create objects from its informations
                # host objects contain service objects
                if not self.new_hosts.has_key(n["host"]):
                    new_host = n["host"]
                    self.new_hosts[new_host] = GenericHost()
                    self.new_hosts[new_host].name = n["host"]
                    self.new_hosts[new_host].status = n["status"]
                    self.new_hosts[new_host].last_check = n["last_check"]
                    self.new_hosts[new_host].duration = n["duration"]
                    self.new_hosts[new_host].attempt = n["attempt"]
                    self.new_hosts[new_host].status_information= n["status_information"]
                    self.new_hosts[new_host].site    = n["site"]
                    self.new_hosts[new_host].address = n["address"]
                    # transisition to Check_MK 1.1.10p2
                    if host.has_key('host_in_downtime'):
                        if host['host_in_downtime'] == 'yes':
                            self.new_hosts[new_host].scheduled_downtime = True
                    if host.has_key('host_acknowledged'):
                        if host['host_acknowledged'] == 'yes':
                            self.new_hosts[new_host].acknowledged = True

                    # hard/soft state for later filter evaluation
                    real_attempt, max_attempt = self.new_hosts[new_host].attempt.split("/")
                    if real_attempt <> max_attempt:
                        self.new_hosts[new_host].status_type = "soft"
                    else:
                        self.new_hosts[new_host].status_type = "hard"

        except:
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # Add filters to the url which should only be applied to the service request
        if str(self.conf.filter_services_on_unreachable_hosts) == "True":
            url_params += '&hst2=0'

        # services
        try:
            response = []
            try:
                response = self._get_url(self.urls['api_services'] + url_params)
            except MultisiteError, e:
                if e.terminate:
                    return e.result
                else:
                    response = e.result.content
                    ret = e.result

            for row in response[1:]:
                service = dict(zip(response[0], row))
                n = {
                    'host':               service['host'].encode("utf-8"),
                    'service':            service['service_description'].encode("utf-8"),
                    'status':             self.statemap.get(service['service_state'], service['service_state']),
                    'last_check':         service['svc_check_age'],
                    'duration':           service['svc_state_age'],
                    'attempt':            service['svc_attempt'],
                    'status_information': service['svc_plugin_output'].encode("utf-8"),
                    # Check_MK passive services can be re-scheduled by using the Check_MK service
                    'passiveonly':        service['svc_is_active'] == 'no' and not service['svc_check_command'].startswith('check_mk'),
                    'notifications':      service['svc_notifications_enabled'] == 'yes',
                    'flapping':           service['svc_flapping'] == 'yes',
                    'site':               service['sitename_plain'],
                    'address':            service['host_address'],
                    'command':            service['svc_check_command'],
                }

            # add dictionary full of information about this service item to nagitems - only if service
                nagitems["services"].append(n)
                # after collection data in nagitems create objects of its informations
                # host objects contain service objects
                if not self.new_hosts.has_key(n["host"]):
                    self.new_hosts[n["host"]] = GenericHost()
                    self.new_hosts[n["host"]].name    = n["host"]
                    self.new_hosts[n["host"]].status  = "UP"
                    self.new_hosts[n["host"]].site    = n["site"]
                    self.new_hosts[n["host"]].address = n["address"]
                # if a service does not exist create its object
                if not self.new_hosts[n["host"]].services.has_key(n["service"]):
                    new_service = n["service"]
                    self.new_hosts[n["host"]].services[new_service] = GenericService()
                    self.new_hosts[n["host"]].services[new_service].host = n["host"]
                    self.new_hosts[n["host"]].services[new_service].name = n["service"]
                    self.new_hosts[n["host"]].services[new_service].status = n["status"]
                    self.new_hosts[n["host"]].services[new_service].last_check = n["last_check"]
                    self.new_hosts[n["host"]].services[new_service].duration = n["duration"]
                    self.new_hosts[n["host"]].services[new_service].attempt = n["attempt"]
                    self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"]
                    self.new_hosts[n["host"]].services[new_service].passiveonly = n["passiveonly"]
                    self.new_hosts[n["host"]].services[new_service].flapping = n["flapping"]
                    self.new_hosts[n["host"]].services[new_service].site = n["site"]
                    self.new_hosts[n["host"]].services[new_service].address = n["address"]
                    self.new_hosts[n["host"]].services[new_service].command = n["command"]
                    # transistion to Check_MK 1.1.10p2
                    if service.has_key('svc_in_downtime'):
                        if service['svc_in_downtime'] == 'yes':
                            self.new_hosts[n["host"]].services[new_service].scheduled_downtime = True
                    if service.has_key('svc_acknowledged'):
                        if service['svc_acknowledged'] == 'yes':
                            self.new_hosts[n["host"]].services[new_service].acknowledged = True
                    # the following lead to wrong "passive" P sign in status window
                    #if service.has_key('svc_is_active'):
                    #    if service['svc_is_active'] == 'no' and not service['svc_check_command'].startswith('check_mk'):
                    #        self.new_hosts[n["host"]].services[new_service].passiveonly = True
                    #if service.has_key('svc_flapping'):
                    #    if service['svc_flapping'] == 'yes':
                    #        self.new_hosts[n["host"]].services[new_service].flapping = True

                    # hard/soft state for later filter evaluation
                    real_attempt, max_attempt = self.new_hosts[n["host"]].services[new_service].attempt.split("/")
                    if real_attempt <> max_attempt:
                        self.new_hosts[n["host"]].services[new_service].status_type = "soft"
                    else:
                        self.new_hosts[n["host"]].services[new_service].status_type = "hard"

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        return ret


    def open_tree_view(self, host, service=""):
        """
        open monitor from treeview context menu
        """

        if service == "":
            url = self.urls['human_host'] + urllib.urlencode({'x': 'site='+self.hosts[host].site+'&host='+host}).replace('x=', '%26')
        else:
            url = self.urls['human_service'] + urllib.urlencode({'x': 'site='+self.hosts[host].site+'&host='+host+'&service='+service}).replace('x=', '%26')

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), host=host, service=service, debug="Open host/service monitor web page " + url)
        webbrowser.open(url)


    def GetHost(self, host):
        """
        find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
        have their ip saved in Nagios
        """

        # the fastest method is taking hostname as used in monitor
        if str(self.conf.connect_by_host) == "True" or host == "":
            return Result(result=host)

        ip = ""

        try:
            if host in self.hosts:
                ip = self.hosts[host].address

            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), host=host, debug ="IP of %s:" % (host) + " " + ip)

            if str(self.conf.connect_by_dns) == "True":
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except:
                    address = ip
            else:
                address = ip
        except:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        return Result(result=address)


    def _set_recheck(self, host, service):
        if service != "":
            if self.hosts[host].services[service].is_passive_only() and not service['Service check command'].startswith('check_mk'):
                # Do not check passive only checks
                return

            if self.hosts[host].services[service].command.startswith('check_mk'):
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), host=host, debug ="This is a passive child of Check_MK. Re-schedule the Check_MK service")

                service = 'Check_MK'

        result = self.FetchURL(self.urls['api_reschedule'] + '&' + urllib.urlencode({'site': self.hosts[host].site,
                                                                                     'host': host,
                                                                                     'service': service}), giveback='raw')


    def get_start_end(self, host):
        return time.strftime("%Y-%m-%d %H:%M"), time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + 7200))


    def _action(self, site, host, service, specific_params):
        params = {
            'site':           self.hosts[host].site,
            'host':           host,
        }
        params.update(specific_params)

        url = self.urls['api_host_act']

        if service != "":
            params['service'] = service
            url = self.urls['api_service_act']

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), host=host, debug ="Adding downtime: " + url + '&' + urllib.urlencode(params))

        result = self.FetchURL(url + '&' + urllib.urlencode(params), giveback = 'raw')


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        self._action(self.hosts[host].site, host, service, {
            '_down_comment':  author == self.username and comment or '%s: %s' % (author, comment),
            '_down_flexible': fixed == 0 and 'on' or '',
            '_down_custom':   'Custom+time+range',
            '_down_from_date': start_time.split(' ')[0],
            '_down_from_time': start_time.split(' ')[1],
            '_down_to_date':   end_time.split(' ')[0],
            '_down_to_time':   end_time.split(' ')[1],
            '_down_duration':  '%s:%s' % (hours, minutes),
        })


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        p = {
            '_acknowledge':    'Acknowledge',
            '_ack_sticky':     sticky == 1 and 'on' or '',
            '_ack_notify':     notify == 1 and 'on' or '',
            '_ack_persistent': persistent == 1 and 'on' or '',
            '_ack_comment':    author == self.username and comment or '%s: %s' % (author, comment)
        }
        self._action(self.hosts[host].site, host, service, p)

        # acknowledge all services on a host when told to do so
        for s in all_services:
            self._action(self.hosts[host].site, host, s, p)




