# encoding: utf-8
import json
# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
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

# The initial implementation was contributed to the Nagstamon project
# by tribe29 GmbH.

import sys
import urllib.request, urllib.parse, urllib.error
import time
import copy
import html
import tzlocal
from datetime import datetime

from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Helpers import webbrowser_open
from Nagstamon.Config import conf

class MultisiteError(Exception):
    def __init__(self, terminate, result):
        self.terminate = terminate
        self.result    = result


class MultisiteServer(GenericServer):
    """
       special treatment for Checkmk Multisite JSON API
    """
    TYPE = 'Checkmk Multisite'

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS= { 'monitor': '$MONITOR$',
                    'hosts': '$MONITOR$/index.py?start_url=view.py?view_name=hostproblems',
                    'services': '$MONITOR$/index.py?start_url=view.py?view_name=svcproblems',
                    'history': '$MONITOR$/index.py?start_url=view.py?view_name=events'}

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Prepare all urls needed by nagstamon -
        self.urls = {}
        self.statemap = {}

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ['Monitor', 'Recheck', 'Acknowledge', 'Downtime']

        # flag for newer cookie authentication
        self.CookieAuth = False


    def init_HTTP(self):
        # general initialization
        if not self.session:
            GenericServer.init_HTTP(self)

        # Fix eventually missing tailing '/' in url
        if self.monitor_url.endswith('/'):
            self.monitor_url.rstrip('/')

        # Add /check_mk if not already existent - makes setting URL simpler
        if not self.monitor_url.endswith('/check_mk'):
            self.monitor_url += '/check_mk'

        # Prepare all urls needed by nagstamon if not yet done
        if len(self.urls) == len(self.statemap):
            self.urls = {
              'api_services':    self.monitor_url + '/view.py?view_name={0}&output_format=python&lang=&limit=hard'.\
                                                                          format(self.checkmk_view_services),
              'human_services':  self.monitor_url + '/index.py?%s' % \
                                                   urllib.parse.urlencode({'start_url': 'view.py?view_name={0}'.\
                                                                          format(self.checkmk_view_services)}),
              'human_service':   self.monitor_url + '/index.py?%s' %
                                                   urllib.parse.urlencode({'start_url': 'view.py?view_name=service'}),

              'api_hosts':       self.monitor_url + '/view.py?view_name={0}&output_format=python&lang=&limit=hard'.\
                                                                          format(self.checkmk_view_hosts),
              'human_hosts':     self.monitor_url + '/index.py?%s' %
                                                   urllib.parse.urlencode({'start_url': 'view.py?view_name={0}'.\
                                                                           format(self.checkmk_view_services)}),
              'human_host':      self.monitor_url + '/index.py?%s' %
                                                   urllib.parse.urlencode({'start_url': 'view.py?view_name=hoststatus'}),
              # URLs do not need pythonic output because since werk #0766 API does not work with transid=-1 anymore
              # thus access to normal webinterface is used
              'api_host_act':    self.monitor_url + '/view.py?_transid=-1&_do_actions=yes&_do_confirm=Yes!&view_name=hoststatus&filled_in=actions&lang=',
              'api_service_act': self.monitor_url + '/view.py?_transid=-1&_do_actions=yes&_do_confirm=Yes!&view_name=service&filled_in=actions&lang=',
              'api_svcprob_act': self.monitor_url + '/view.py?_transid=-1&_do_actions=yes&_do_confirm=Yes!&view_name=svcproblems&filled_in=actions&lang=',
              'human_events':    self.monitor_url + '/index.py?%s' %
                                                   urllib.parse.urlencode({'start_url': 'view.py?view_name=events'}),
              'omd_host_downtime': self.monitor_url + '/api/1.0/domain-types/downtime/collections/host',
              'omd_svc_downtime': self.monitor_url + '/api/1.0/domain-types/downtime/collections/service',
              'recheck':         self.monitor_url + '/ajax_reschedule.py?_ajaxid=0',
              'omd_version':         self.monitor_url + '/api/1.0/version',
              'transid':         self.monitor_url + '/view.py?actions=yes&filled_in=actions&host=$HOST$&service=$SERVICE$&view_name=service'
            }

            self.statemap = {
                'UNREACH': 'UNREACHABLE',
                'CRIT':    'CRITICAL',
                'WARN':    'WARNING',
                'UNKN':    'UNKNOWN',
                'PEND':    'PENDING',
            }

        # Function overrides for Checkmk 2.3+
        version = self._omd_get_version()
        if version >= [2, 3]:
            self._set_downtime = self._omd_set_downtime
            self._set_recheck = self._omd_set_recheck

        if self.CookieAuth and not self.refresh_authentication:
            # get cookie to access Checkmk web interface
            if 'cookies' in dir(self.session):
                if len(self.session.cookies) == 0:
                    # if no cookie yet login
                    self._get_cookie_login()
            elif self.session == None:
                # if no cookie yet login
                self._get_cookie_login()
        elif self.CookieAuth and self.refresh_authentication:
            #if self.session is None:
            self.session = self.create_session()

            # force re-auth
            self._get_cookie_login()


    def init_config(self):
        """
            dummy init_config, called at thread start, not really needed here, just omit extra properties
        """
        pass


    def _is_auth_in_cookies(self):
        """
            check if there is any valid auth session in cookies which has the name 'auth_<monitor_name>'
        """
        if self.session:
            for cookie in self.session.cookies:
                if cookie.name.startswith('auth_'):
                    return True
        return False

    def _get_url(self, url):
        result = self.fetch_url(url, 'raw')
        content, error, status_code = result.result, result.error, result.status_code

        if error != '' or status_code >= 400:
            raise MultisiteError(True, Result(result=content,
                                              error=error,
                                              status_code=status_code))

        if content.startswith('WARNING:'):
            c = content.split('\n')

            # Print non ERRORS to the log in debug mode
            self.debug(server=self.get_name(), debug=c[0])

            raise MultisiteError(False, Result(result='\n'.join(c[1:]),
                                               error=c[0],
                                               status_code=status_code))

        elif content.startswith('ERROR:'):
            raise MultisiteError(True, Result(result=content,
                                              error=content,
                                              status_code=status_code))

        # in case of auth problem enable GUI auth part in popup
        #if self.CookieAuth and self.session is not None:
        #    if not self._is_auth_in_cookies():
        #        self.refresh_authentication = True
        #        return ''

        # looks like cookieauth
        elif content.startswith('<') or\
                '<!DOCTYPE html>' in content:
            self.CookieAuth = True
            # if first attempt login and then try to get data again
            if not self._is_auth_in_cookies():
                self._get_cookie_login()
                result = self.fetch_url(url, 'raw')
                content, error = result.result, result.error
                if content.startswith('<') or\
                '<!DOCTYPE html>' in content:
                    return ''

        # if finally still some <HTML> is sent this looks like a new login due to password change
        if content.startswith('<') or\
                '<!DOCTYPE html>' in content:
            self.refresh_authentication = True
            return ''

        return eval(content)

    def _get_cookie_login(self):
        """
            login on cookie monitor site
        """
        # put all necessary data into url string
        login_data = {'_username': self.get_username(),
                     '_password': self.get_password(),
                     '_login': '1',
                     '_origtarget' : '',
                     'filled_in' :' login'}
        # get cookie from login page via url retrieving as with other urls
        try:
            # login and get cookie
            self.fetch_url(self.monitor_url + '/login.py', cgi_data=login_data, multipart=True)
        except:
            self.error(sys.exc_info())


    def _get_status(self):
        """
            Get status from Checkmk Server
        """

        ret = Result()

        # Create URLs for the configured filters
        url_params = ''

        if self.force_authuser:
            url_params += "&force_authuser=1"

        url_params += '&is_host_acknowledged=-1&is_service_acknowledged=-1'
        url_params += '&is_host_notifications_enabled=-1&is_service_notifications_enabled=-1'
        url_params += '&is_host_active_checks_enabled=-1&is_service_active_checks_enabled=-1'
        url_params += '&host_scheduled_downtime_depth=-1&is_in_downtime=-1'

        try:
            response = []
            try:
                response = self._get_url(self.urls['api_hosts'] + url_params)
            except MultisiteError as e:
                if e.terminate:
                    return e.result

            if response == '':
                return Result(result='',
                              error='Login failed',
                              status_code=401)

            for row in response[1:]:
                host= dict(list(zip(copy.deepcopy(response[0]), copy.deepcopy(row))))
                n = {
                    'host':               host['host'],
                    'status':             self.statemap.get(host['host_state'], host['host_state']),
                    'last_check':         host['host_check_age'],
                    'duration':           host['host_state_age'],
                    'status_information': html.unescape(host['host_plugin_output'].replace('\n', ' ')),
                    'attempt':            host['host_attempt'],
                    'site':               host['sitename_plain'],
                    'address':            host['host_address']
                }

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
                    self.new_hosts[new_host].status_information= html.unescape(n['status_information'].replace('\n', ' '))
                    self.new_hosts[new_host].site = n['site']
                    self.new_hosts[new_host].address = n['address']

                    # transisition to Checkmk 1.1.10p2
                    if 'host_in_downtime' in host:
                        if host['host_in_downtime'] == 'yes':
                            self.new_hosts[new_host].scheduled_downtime = True
                    if 'host_acknowledged' in host:
                        if host['host_acknowledged'] == 'yes':
                            self.new_hosts[new_host].acknowledged = True
                    if 'host_notifications_enabled' in host:
                        if host['host_notifications_enabled'] == 'no':
                            self.new_hosts[new_host].notifications_disabled = True

                    # hard/soft state for later filter evaluation
                    real_attempt, max_attempt = self.new_hosts[new_host].attempt.split('/')
                    if real_attempt != max_attempt:
                        self.new_hosts[new_host].status_type = 'soft'
                    else:
                        self.new_hosts[new_host].status_type = 'hard'

            del response

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # Add filters to the url which should only be applied to the service request
        if conf.filter_services_on_unreachable_hosts:
            # thanks to https://github.com/HenriWahl/Nagstamon/issues/510
            url_params += '&hst0=On&hst1=On'

        # services
        try:
            response = []
            try:
                response = self._get_url(self.urls['api_services'] + url_params)
            except MultisiteError as e:
                if e.terminate:
                    return e.result
                else:
                    response = copy.deepcopy(e.result.content)
                    ret = copy.deepcopy(e.result)

            for row in response[1:]:
                service = dict(list(zip(copy.deepcopy(response[0]), copy.deepcopy(row))))
                n = {
                    'host':               service['host'],
                    'service':            service['service_description'],
                    'status':             self.statemap.get(service['service_state'], service['service_state']),
                    'last_check':         service['svc_check_age'],
                    'duration':           service['svc_state_age'],
                    'attempt':            service['svc_attempt'],
                    'status_information': html.unescape(service['svc_plugin_output'].replace('\n', ' ')),
                    # Checkmk passive services can be re-scheduled by using the Checkmk service
                    'passiveonly':        service['svc_is_active'] == 'no' and not service['svc_check_command'].startswith('check_mk'),
                    'flapping':           service['svc_flapping'] == 'yes',
                    'site':               service['sitename_plain'],
                    'address':            service['host_address'],
                    'command':            service['svc_check_command'],
                }

                # host objects contain service objects
                if n['host'] not in self.new_hosts:
                    self.new_hosts[n['host']] = GenericHost()
                    self.new_hosts[n['host']].name = n['host']
                    self.new_hosts[n['host']].status = 'UP'
                    self.new_hosts[n['host']].site = n['site']
                    self.new_hosts[n['host']].address = n['address']
                # if a service does not exist create its object
                if n['service'] not in self.new_hosts[n['host']].services:
                    new_service = n['service']
                    self.new_hosts[n['host']].services[new_service] = GenericService()
                    self.new_hosts[n['host']].services[new_service].host = n['host']
                    self.new_hosts[n['host']].services[new_service].server = self.name
                    self.new_hosts[n['host']].services[new_service].name = n['service']
                    self.new_hosts[n['host']].services[new_service].status = n['status']
                    self.new_hosts[n['host']].services[new_service].last_check = n['last_check']
                    self.new_hosts[n['host']].services[new_service].duration = n['duration']
                    self.new_hosts[n['host']].services[new_service].attempt = n['attempt']
                    self.new_hosts[n['host']].services[new_service].status_information = n['status_information'].strip()
                    self.new_hosts[n['host']].services[new_service].passiveonly = n['passiveonly']
                    self.new_hosts[n['host']].services[new_service].flapping = n['flapping']
                    self.new_hosts[n['host']].services[new_service].site = n['site']
                    self.new_hosts[n['host']].services[new_service].address = n['address']
                    self.new_hosts[n['host']].services[new_service].command = n['command']

                    # transition to Checkmk 1.1.10p2
                    if 'svc_in_downtime' in service:
                        if service['svc_in_downtime'] == 'yes':
                            self.new_hosts[n['host']].services[new_service].scheduled_downtime = True
                    if 'svc_acknowledged' in service:
                        if service['svc_acknowledged'] == 'yes':
                            self.new_hosts[n['host']].services[new_service].acknowledged = True
                    if 'svc_flapping' in service:
                        if service['svc_flapping'] == 'yes':
                            self.new_hosts[n['host']].services[new_service].flapping = True
                    if 'svc_notifications_enabled' in service:
                        if service['svc_notifications_enabled'] == 'no':
                            self.new_hosts[n['host']].services[new_service].notifications_disabled = True
                    if 'host_in_downtime' in service:
                        if service['host_in_downtime'] == 'yes':
                            self.new_hosts[n['host']].scheduled_downtime = True

                    # hard/soft state for later filter evaluation
                    real_attempt, max_attempt = self.new_hosts[n['host']].services[new_service].attempt.split('/')
                    if real_attempt != max_attempt:
                        self.new_hosts[n['host']].services[new_service].status_type = 'soft'
                    else:
                        self.new_hosts[n['host']].services[new_service].status_type = 'hard'

            del response

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=copy.deepcopy(result), error=copy.deepcopy(error))

        del url_params

        return ret


    def open_monitor(self, host, service=''):
        """
            open monitor from treeview context menu
        """

        if service == '':
            url = self.urls['human_host'] + urllib.parse.urlencode({'x': 'site='+self.hosts[host].site+'&host='+host}).replace('x=', '%26')
        else:
            url = self.urls['human_service'] + urllib.parse.urlencode({'x': 'site='+self.hosts[host].site+'&host='+host+'&service='+service}).replace('x=', '%26')

        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service, debug='Open host/service monitor web page ' + url)
        webbrowser_open(url)


    def get_host(self, host):
        """
            find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
            have their ip saved in Nagios
        """

        # the fastest method is taking hostname as used in monitor
        if conf.connect_by_host == True or host == '':
            return Result(result=host)

        ip = ''

        try:
            if host in self.hosts:
                ip = self.hosts[host].address

            if conf.debug_mode:
                self.debug(server=self.get_name(), host=host, debug ='IP of %s:' % (host) + ' ' + ip)

            if conf.connect_by_dns:
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except:
                    address = ip
            else:
                address = ip
        except:
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        return Result(result=address)


    def get_start_end(self, host):
        return time.strftime('%Y-%m-%d %H:%M'), time.strftime('%Y-%m-%d %H:%M', time.localtime(time.time() + 7200))


    def _action(self, site, host, service, specific_params):
        params = {
            'site':    self.hosts[host].site,
            'host':    host,
        }
        params.update(specific_params)

        # decide about service or host url
        if service != '':
            url = self.urls['api_service_act']
        else:
            url = self.urls['api_host_act']

        # set service
        params['service'] = service

        # get current transid
        transid = self._get_transid(host, service)
        url = url.replace('?_transid=-1&', '?_transid=%s&' % (transid))

        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, debug ='Submitting action: ' + url + '&' + urllib.parse.urlencode(params))

        # apply action
        self.fetch_url(url + '&' + urllib.parse.urlencode(params))


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        try:
            # might be more sophisticated, especially if there is a localized Checkmk web interface
            from_date, from_time = start_time.split(' ')
            from_year, from_month, from_day = from_date.split('-')
            from_hour, from_min = from_time.split(':')
            to_date, to_time = end_time.split(' ')
            to_year, to_month, to_day = to_date.split('-')
            to_hour, to_min = to_time.split(':')

            # let's try to push downtime info in all variants to server - somewhat holzhammery but well...
            params = {
                '_down_comment': author == self.username and comment or '%s: %s' % (author, comment),
                '_down_flexible': fixed == 0 and 'on' or '',
                '_down_custom': 'Custom+time+range',
                '_down_from_date': from_date,
                '_down_from_time': from_time,
                '_down_to_date': to_date,
                '_down_to_time': to_time,
                '_down_duration': '%s:%s' % (hours, minutes),
                '_down_from_year': from_year,
                '_down_from_month': from_month,
                '_down_from_day': from_day,
                '_down_from_hour': from_hour,
                '_down_from_min': from_min,
                '_down_from_sec': '00',
                '_down_to_year': to_year,
                '_down_to_month': to_month,
                '_down_to_day': to_day,
                '_down_to_hour': to_hour,
                '_down_to_min': to_min,
                '_down_to_sec': '00',
                'actions': 'yes'
            }
            # service needs extra parameter
            if service:
                params['_do_confirm_service_downtime'] = 'Schedule+downtime+for+1+service'
            self._action(self.hosts[host].site, host, service, params)
        except:
            if conf.debug_mode:
                self.debug(server=self.get_name(), host=host,
                           debug='Invalid start/end date/time given')


    def _omd_set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        """
           _set_downtime function for Checkmk version 2.3+
        """
        try:
            # Headers required for Checkmk API
            headers = {
                "Authorization": f"Bearer {self.username} {self.password}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Only timezone aware dates are allowed
            iso_start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M").replace(tzinfo=tzlocal.get_localzone()).isoformat()
            iso_end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M").replace(tzinfo=tzlocal.get_localzone()).isoformat()
            # Set parameters for host downtimes
            url = self.urls["omd_host_downtime"]
            params = {
                "start_time": iso_start_time,
                "end_time": iso_end_time,
                "comment": author == self.username and comment or "%s: %s" % (author, comment),
                "downtime_type": "host",
                "host_name": host,
            }

            # Downtime type is "flexible" if "duration" is set
            if fixed == 0:
                params['duration'] = hours * 60 + minutes
            # Parameter overrides for service downtimes
            if service:
                url = self.urls['omd_svc_downtime']
                params['downtime_type'] = 'service'
                params['service_descriptions'] = [service]
            self.fetch_url(url, headers=headers, cgi_data=json.dumps(params))
        except Exception as error:
            if conf.debug_mode:
                self.debug(server=self.get_name(), host=host,
                           debug='Invalid start/end date/time given')


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None):
        p = {
            '_acknowledge':    'Acknowledge',
            '_ack_sticky':     sticky == 1 and 'on' or '',
            '_ack_notify':     notify == 1 and 'on' or '',
            '_ack_persistent': persistent == 1 and 'on' or '',
            '_ack_comment':    author == self.username and comment or '%s: %s' % (author, comment)
        }
        self._action(self.hosts[host].site, host, service, p)

        # acknowledge all services on a host when told to do so
        if all_services:
            for s in all_services:
                self._action(self.hosts[host].site, host, s, p)


    def _set_recheck(self, host, service):
        p = {
            '_resched_checks': 'Reschedule active checks',
            '_resched_pread':  '0'
        }
        self._action(self.hosts[host].site, host, service, p)


    def _omd_set_recheck(self, host, service):
        """
           _set_recheck function for Checkmk version 2.3+
        """
        csrf_token = self._get_csrf_token(host, service)
        data = {
            "site": self.hosts[host].site,
            "host": host,
            "service": service,
            "wait_svc": service,
            "csrf_token": csrf_token,
        }
        self.fetch_url(self.urls["recheck"], cgi_data=data)


    def recheck_all(self):
        """
            special method for Checkmk as there is one URL for rescheduling all problems to be checked
        """
        params = dict()
        params['_resched_checks'] = 'Reschedule active checks'
        url = self.urls['api_svcprob_act']

        if conf.debug_mode:
            self.debug(server=self.get_name(), debug ='Rechecking all action: ' + url + '&' + urllib.parse.urlencode(params))

        result = self.fetch_url(url + '&' + urllib.parse.urlencode(params), giveback ='raw')


    def _get_transid(self, host, service):
        """
            get transid for an action
        """
        # since Checkmk 2.0 it seems to be a problem if service is empty so fill it with a definitively existing one
        if not service:
            service = 'PING'
        transid = self.fetch_url(self.urls['transid'].replace('$HOST$', host).replace('$SERVICE$', service.replace(' ', '+')),
                                'obj').result.find(attrs={'name' : '_transid'})['value']
        return transid


    def _get_csrf_token(self, host, service):
        """
           get csrf token for the session
        """
        # since Checkmk 2.0 it seems to be a problem if service is empty so fill it with a definitively existing one
        if not service:
            service = "PING"
        csrf_token = self.fetch_url(self.urls["transid"].replace("$HOST$", host).replace("$SERVICE$", service.replace(" ", "+")),
                                    "obj").result.find(attrs={"name": ["csrf_token", "_csrf_token"]})["value"]
        return csrf_token


    def _omd_get_version(self):
        """
           get version of OMD Checkmk as [major_version, minor_version]
        """
        try:
            version = [int(x) for x in self.fetch_url(self.urls['omd_version'], 'json').result['versions']['checkmk'].split('.')[:2]]
        # If /version api is not supported, return the lowest non-negative pair
        except:
            version = [0, 0]
        return version
