# encoding: utf-8

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

# Initial implementation by Marcus Mönnig
#
# This Server class connects against IcingaWeb2. The monitor URL in the setup should be
# something like http://icinga2/icingaweb2
#
# Status/TODOs:
#
# * The IcingaWeb2 API is not implemented yet, so currently this implementation uses
#   two HTTP requests per action. The first fetches the HTML, then the form data is extracted and
#   then a second HTTP POST request is made which actually executed the action.
#   Once IcingaWeb2 has an API, it's probably the better choice.


from Nagstamon.Servers.Generic import GenericServer
import urllib.parse
import sys
import copy
import json
import datetime
from datetime import timezone
import socket

from bs4 import BeautifulSoup
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)
from Nagstamon.Config import (conf,
                              AppInfo)
from Nagstamon.Helpers import webbrowser_open


def strfdelta(tdelta, fmt):
    d = {'days': tdelta.days}
    d['hours'], rem = divmod(tdelta.seconds, 3600)
    d['minutes'], d['seconds'] = divmod(rem, 60)
    return fmt.format(**d)


class IcingaDBWebServer(GenericServer):
    """
        object of Icinga server
    """
    TYPE = 'IcingaDBWeb'
    MENU_ACTIONS = ['Monitor', 'Recheck', 'Acknowledge', 'Submit check result', 'Downtime']
    STATES_MAPPING = {'hosts' : {0 : 'UP', 1 : 'DOWN', 2 : 'UNREACHABLE'},
                     'services' : {0 : 'OK', 1 : 'WARNING', 2 : 'CRITICAL', 3 : 'UNKNOWN'}}
    STATES_MAPPING_REV = {'hosts' : { 'UP': 0, 'DOWN': 1, 'UNREACHABLE': 2},
                     'services' : {'OK': 0, 'WARNING': 1, 'CRITICAL': 2, 'UNKNOWN': 3}}
    BROWSER_URLS = { 'monitor': '$MONITOR-CGI$/dashboard',
                    'hosts': '$MONITOR-CGI$/icingadb/hosts',
                    'services': '$MONITOR-CGI$/icingadb/services',
                    'history': '$MONITOR-CGI$/icingadb/history'}


    def init_config(self):
        """
            set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # dummy default empty cgi urls - get filled later when server version is known
        self.cgiurl_services = None
        self.cgiurl_hosts = None
        self.cgiurl_monitoring_health = None

        # https://github.com/HenriWahl/Nagstamon/issues/400
        # The displayed name for host and service is the Icinga2 "internal" name and not the display_name from host/service configuration
        # This name is stored in host/service dict under key 'name' but is also used as dict key for dict containing all hosts/services
        # The "internal" name must still be used to query IcingaWeb2 and is in dict under key 'real_name' since https://github.com/HenriWahl/Nagstamon/issues/192
        self.use_display_name_host = True
        self.use_display_name_service = True

    def init_HTTP(self):
        """
            initializing of session object
        """
        GenericServer.init_HTTP(self)

        if self.session and not 'Referer' in self.session.headers:
            self.session.headers['Referer'] = self.monitor_cgi_url

        # normally cookie auth will be used
        if not self.no_cookie_auth:
            if 'cookies' not in dir(self.session) or len(self.session.cookies) == 0:
                # get login page, thus automatically a cookie
                login = self.fetch_url('{0}/authentication/login'.format(self.monitor_url))
                if login.error == '' and login.status_code == 200:
                    form = login.result.find('form')
                    form_inputs = {}
                    for form_input in ('redirect', 'formUID', 'CSRFToken', 'btn_submit'):
                        if form is not None and not form.find('input', {'name': form_input}) is None:
                            form_inputs[form_input] = form.find('input', {'name': form_input})['value']
                        else:
                            form_inputs[form_input] = ''
                    form_inputs['username'] = self.username
                    form_inputs['password'] = self.password

                    # fire up login button with all needed data
                    self.fetch_url('{0}/authentication/login'.format(self.monitor_url), cgi_data=form_inputs)


    def _get_status(self):
        """
            Get status from Icinga Server - only JSON
        """
        # define CGI URLs for hosts and services
        if self.cgiurl_hosts is None and self.cgiurl_services is None and self.cgiurl_monitoring_health is None:
            # services (unknown, warning or critical?)
            self.cgiurl_services = {'hard': self.monitor_cgi_url + '/icingadb/services?service.state.is_problem=y&service.state.state_type=hard&columns=service.state.last_update,service.state.is_reachable&format=json', \
                                    'soft': self.monitor_cgi_url + '/icingadb/services?service.state.is_problem=y&service.state.state_type=soft&columns=service.state.last_update,service.state.is_reachable&format=json'}
            # hosts (up or down or unreachable)
            self.cgiurl_hosts = {'hard': self.monitor_cgi_url + '/icingadb/hosts?host.state.is_problem=y&host.state.state_type=hard&columns=host.state.last_update&format=json', \
                                 'soft': self.monitor_cgi_url + '/icingadb/hosts?host.state.is_problem=y&host.state.state_type=soft&columns=host.state.last_update&format=json'}
            # monitoring health
            self.cgiurl_monitoring_health = self.monitor_cgi_url + '/health?format=json'

        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # now using JSON output from Icinga
        try:
            for status_type in 'hard', 'soft':
                # first attempt
                result = self.fetch_url(self.cgiurl_hosts[status_type], giveback='raw')
                # authentication errors get a status code 200 too back because its
                # HTML works fine :-(
                if result.status_code < 400 and\
                   result.result.startswith('<'):
                    # in case of auth error reset HTTP session and try again
                    self.reset_HTTP()
                    result = self.fetch_url(self.cgiurl_hosts[status_type], giveback='raw')
                    # if it does not work again tell GUI there is a problem
                    if result.status_code < 400 and\
                       result.result.startswith('<'):
                        self.refresh_authentication = True
                        return Result(result=result.result,
                                      error='Authentication error',
                                      status_code=result.status_code)

                # purify JSON result of unnecessary control sequence \n
                jsonraw, error, status_code = copy.deepcopy(result.result.replace('\n', '')),\
                                              copy.deepcopy(result.error),\
                                              result.status_code

                # check if any error occured
                potential_error = self.check_for_error(jsonraw, error, status_code)
                if potential_error is not None:
                    return potential_error

                # Check if the backend is running
                # If it isn't running the last values stored in the database are returned/shown
                # Unfortunately we need to make a extra request for this and only, if monitoring health is possible
                if self.cgiurl_monitoring_health:
                    pass
                    # TODO: Health checks for IcingaDB and icinga-redis
                    # try:
                    #     result = self.fetch_url(self.cgiurl_monitoring_health, giveback='raw')
                    #     monitoring_health = json.loads(result.result)[0]
                    #     if (monitoring_health['is_currently_running'] == '0'):
                    #         return Result(result=monitoring_health,
                    #                       error='Icinga2 backend not running')
                    # except json.decoder.JSONDecodeError:
                    #     # https://github.com/HenriWahl/Nagstamon/issues/619
                    #     # Icinga2 monitoring health status query does not seem to work (on older version?)
                    #     self.cgiurl_monitoring_health = None

                hosts = json.loads(jsonraw)

                for host in hosts:
                    # make dict of tuples for better reading
                    h = dict(host.items())

                    # host
                    if not self.use_display_name_host:
                        # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                        # better be name instead of display_name
                        host_name = h['name']
                    else:
                        # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                        # problems with that so here we go with extra display_name option
                        host_name = h['display_name']

                    # host objects contain service objects
                    if not host_name in self.new_hosts:
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].server = self.name
                        self.new_hosts[host_name].status_type = status_type
                        if (status_type == 'hard'):
                            self.new_hosts[host_name].status = self.STATES_MAPPING['hosts'][int(h['state']['hard_state'])]
                        else:
                            self.new_hosts[host_name].status = self.STATES_MAPPING['hosts'][int(h['state']['soft_state'])]

                        if h['state']['last_update'].replace(".", "").isnumeric(): # new version of icingadb doesnt return unix timestamp
                            #self.new_hosts[host_name].last_check = datetime.datetime.fromtimestamp(int(float(h['state']['last_update'])))
                            utc_time = datetime.datetime.fromtimestamp(int(float(h['state']['last_update'])), tz=timezone.utc)
                        else:
                            #self.new_hosts[host_name].last_check = datetime.datetime.fromisoformat(h['state']['last_update'])
                            utc_time = datetime.datetime.fromisoformat(h['state']['last_update'])

                        local_time = utc_time.astimezone()
                        self.new_hosts[host_name].last_check = local_time.strftime("%Y-%m-%d %H:%M:%S")  # format without microseconds and tz
                        
                        self.new_hosts[host_name].attempt = "{}/{}".format(h['state']['check_attempt'],h['max_check_attempts'])
                        self.new_hosts[host_name].status_information = BeautifulSoup(str(h['state']['output']).replace('\n', ' ').strip(), 'html.parser').text
                        self.new_hosts[host_name].passiveonly = not int(h.get('active_checks_enabled') or '0')
                        self.new_hosts[host_name].notifications_disabled = not int(h.get('notifications_enabled') or '0')
                        self.new_hosts[host_name].flapping = bool(int(h['state']['is_flapping'] or 0))
                        #s['state']['is_acknowledged'] can be null, 0, 1, or 'sticky'
                        self.new_hosts[host_name].acknowledged = h['state']['is_acknowledged'] if isinstance(h['state']['is_acknowledged'], bool) else bool(int(h['state']['is_acknowledged'].replace('sticky', '1') or 0))
                        self.new_hosts[host_name].scheduled_downtime = bool(int(h['state']['in_downtime'] or 0))

                        # extra Icinga properties to solve https://github.com/HenriWahl/Nagstamon/issues/192
                        # acknowledge needs host_description and no display name
                        self.new_hosts[host_name].real_name = h['name']

                        # Icinga only updates the attempts for soft states. When hard state is reached, a flag is set and
                        # attemt is set to 1/x.
                        if (status_type == 'hard'):
                            try:
                                self.new_hosts[host_name].attempt = "{0}/{0}".format(h['max_check_attempts'])
                            except Exception:
                                self.new_hosts[host_name].attempt = "HARD"

                        # extra duration needed for calculation
                        self.new_hosts[host_name].duration = 'n/a'
                        if h['state']['last_state_change'] is not None:
                            if h['state']['last_state_change'].replace(".", "").isnumeric(): # new version of icingadb doesnt return unix timestamp
                                duration = datetime.datetime.now() - datetime.datetime.fromtimestamp(int(float(h['state']['last_state_change'])))
                            else:
                                last_state_change = datetime.datetime.fromisoformat(h['state']['last_state_change'])
                                duration = datetime.datetime.now(timezone.utc).astimezone() - last_state_change
                            
                            if duration.total_seconds() > 0:
                                self.new_hosts[host_name].duration = strfdelta(duration,'{days}d {hours}h {minutes}m {seconds}s')

                    del h, host_name
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            for status_type in 'hard', 'soft':
                result = self.fetch_url(self.cgiurl_services[status_type], giveback='raw')
                # purify JSON result of unnecessary control sequence \n
                jsonraw, error, status_code = copy.deepcopy(result.result.replace('\n', '')),\
                                              copy.deepcopy(result.error),\
                                              result.status_code

                if error != '' or status_code >= 400:
                    return Result(result=jsonraw,
                                  error=error,
                                  status_code=status_code)

                # check if any error occured
                self.check_for_error(jsonraw, error, status_code)

                services = copy.deepcopy(json.loads(jsonraw))

                for service in services:
                    # make dict of tuples for better reading
                    s = dict(service.items())

                    if not self.use_display_name_host:
                        # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                        # better be name instead of display_name
                        host_name = s['host']['name']
                    else:
                        # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                        # problems with that so here we go with extra display_name option
                        host_name = s['host']['display_name']

                    # host objects contain service objects
                    if not host_name in self.new_hosts:
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].status = 'UP'
                        # extra Icinga properties to solve https://github.com/HenriWahl/Nagstamon/issues/192
                        # acknowledge needs host_description and no display name
                        self.new_hosts[host_name].real_name = s['host']['name']

                    service_name = s['display_name']

                    # if a service does not exist create its object
                    if not service_name in self.new_hosts[host_name].services:
                        self.new_hosts[host_name].services[service_name] = GenericService()
                        self.new_hosts[host_name].services[service_name].host = host_name
                        self.new_hosts[host_name].services[service_name].name = service_name
                        self.new_hosts[host_name].services[service_name].server = self.name
                        self.new_hosts[host_name].services[service_name].status_type = status_type
                        if (status_type == 'hard'):
                            self.new_hosts[host_name].services[service_name].status = self.STATES_MAPPING['services'][int(s['state']['hard_state'])]
                        else:
                            self.new_hosts[host_name].services[service_name].status = self.STATES_MAPPING['services'][int(s['state']['soft_state'])]

                        if s['state']['last_update'].replace(".", "").isnumeric(): # new version of icingadb doesnt return unix timestamp
                            #self.new_hosts[host_name].services[service_name].last_check = datetime.datetime.fromtimestamp(int(float(s['state']['last_update'])))
                            utc_time = datetime.datetime.fromtimestamp(int(float(s['state']['last_update'])), tz=timezone.utc)
                        else:
                            #self.new_hosts[host_name].services[service_name].last_check = datetime.datetime.fromisoformat(s['state']['last_update'])
                            utc_time = datetime.datetime.fromisoformat(s['state']['last_update'])

                        local_time = utc_time.astimezone()
                        self.new_hosts[host_name].services[service_name].last_check = local_time.strftime("%Y-%m-%d %H:%M:%S")  # format without microseconds and tz

                        self.new_hosts[host_name].services[service_name].attempt = "{}/{}".format(s['state']['check_attempt'],s['max_check_attempts'])
                        self.new_hosts[host_name].services[service_name].status_information = BeautifulSoup(str(s['state']['output']).replace('\n', ' ').strip(), 'html.parser').text
                        self.new_hosts[host_name].services[service_name].passiveonly = not int(s.get('active_checks_enabled') or '0')
                        self.new_hosts[host_name].services[service_name].notifications_disabled = not int(s.get('notifications_enabled') or '0')
                        self.new_hosts[host_name].services[service_name].flapping = bool(int(s['state']['is_flapping'] or 0))
                        #s['state']['is_acknowledged'] can be null, 0, 1, or 'sticky'
                        self.new_hosts[host_name].services[service_name].acknowledged = s['state']['is_acknowledged'] if isinstance(s['state']['is_acknowledged'], bool) else bool(int(s['state']['is_acknowledged'].replace('sticky', '1') or 0))
                        self.new_hosts[host_name].services[service_name].scheduled_downtime = bool(int(s['state']['in_downtime'] or 0))
                        self.new_hosts[host_name].services[service_name].unreachable = not bool(int(s['state']['is_reachable'] or 0))

                        if self.new_hosts[host_name].services[service_name].unreachable:
                            self.new_hosts[host_name].services[service_name].status_information += " (SERVICE UNREACHABLE)"

                        # extra Icinga properties to solve https://github.com/HenriWahl/Nagstamon/issues/192
                        # acknowledge needs service_description and no display name
                        self.new_hosts[host_name].services[service_name].real_name = s['name']

                        # Icinga only updates the attempts for soft states. When hard state is reached, a flag is set and
                        # attemt is set to 1/x.
                        if (status_type == 'hard'):
                            try:
                                self.new_hosts[host_name].services[service_name].attempt = "{0}/{0}".format(s['max_check_attempts'])
                            except Exception:
                                self.new_hosts[host_name].services[service_name].attempt = "HARD"

                        # extra duration needed for calculation
                        self.new_hosts[host_name].services[service_name].duration = 'n/a'
                        if s['state']['last_state_change'] is not None:
                            if s['state']['last_update'].replace(".", "").isnumeric(): # new version of icingadb doesnt return unix timestamp
                                duration = datetime.datetime.now() - datetime.datetime.fromtimestamp(int(float(s['state']['last_state_change'])))
                            else:
                                last_state_change = datetime.datetime.fromisoformat(s['state']['last_state_change'])
                                duration = datetime.datetime.now(timezone.utc).astimezone() - last_state_change
                            
                            if duration.total_seconds() > 0:
                                self.new_hosts[host_name].services[service_name].duration = strfdelta(duration, '{days}d {hours}h {minutes}m {seconds}s')

                    del s, host_name, service_name
        except:

            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # some cleanup
        del jsonraw, error, hosts, services

        # dummy return in case all is OK
        return Result()


    def _set_recheck(self, host, service):
        # Set correct headers
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        # First retrieve the info page for this host/service
        if service == '':
            url = '{0}/icingadb/host?name={1}'.format(self.monitor_cgi_url, self.hosts[host].real_name)
        else:
            url = '{0}/icingadb/service?name={1}&host.name={2}'.format(self.monitor_cgi_url,
                                                                                           self.hosts[host].services[service].real_name,
                                                                                           self.hosts[host].real_name
                                                                                           )
        result = self.fetch_url(url, giveback='raw')

        if result.error != '':
            return result
        else:
            pageraw = result.result

        pagesoup = BeautifulSoup(pageraw, 'html.parser')
        print(pagesoup.prettify())

        # Extract the relevant form element values
        formtag = pagesoup.select_one('form[action*="check-now"]')

        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='[Recheck] Retrieve html form from {0}: \n{1}'.format(url,formtag.prettify()))

        btn_submit = formtag.findNext('button', {'name':'btn_submit'})['value']
        CSRFToken = formtag.findNext('input', {'name':'CSRFToken'})['value']

        # Pass these values to the check-now URL as cgi_data
        cgi_data = {}
        cgi_data['CSRFToken'] = CSRFToken
        cgi_data['btn_submit'] = btn_submit

        if service == '':
            url = '{0}/icingadb/host/check-now?name={1}'.format(self.monitor_cgi_url, self.hosts[host].real_name)
        else:
            url = '{0}/icingadb/service/check-now?name={1}&host.name={2}'.format(self.monitor_cgi_url,
                                                                                           self.hosts[host].services[service].real_name,
                                                                                           self.hosts[host].real_name
                                                                                           )
        
        response = self.fetch_url(url, giveback='raw', cgi_data=cgi_data)

        # Some debug data
        data = response.result
        error = response.error
        status_code = response.status_code
        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='Recheck response')
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- response: {0}".format(response))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- data: {0}".format(data))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- error: {0}".format(error))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- status_code: {0}".format(status_code))


    # Overwrite function from generic server to add expire_time value
    def set_acknowledge(self, info_dict):
        '''
            different monitors might have different implementations of _set_acknowledge
        '''
        if info_dict['acknowledge_all_services'] is True:
            all_services = info_dict['all_services']
        else:
            all_services = []

        # Make sure expire_time is set
        #if not info_dict['expire_time']:
        #    info_dict['expire_time'] = None

        try:
            self._set_acknowledge(info_dict['host'],
                                  info_dict['service'],
                                  info_dict['author'],
                                  info_dict['comment'],
                                  info_dict['sticky'],
                                  info_dict['notify'],
                                  info_dict['persistent'],
                                  all_services,
                                  info_dict['expire_time'])
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None, expire_time=None):
        # Set correct headers
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        # First retrieve the info page for this host/service
        if service == '':
            url = '{0}/icingadb/host/acknowledge?name={1}&showCompact=1'.format(self.monitor_cgi_url,
                                                                            self.hosts[host].real_name)
        else:
            url = '{0}/icingadb/service/acknowledge?name={1}&host.name={2}&showCompact=1'.format(self.monitor_cgi_url,
                                                                                           self.hosts[host].services[service].real_name,
                                                                                           self.hosts[host].real_name
                                                                                           )

        result = self.fetch_url(url, giveback='raw')

        if result.error != '':
            return result
        else:
            pageraw = result.result

        pagesoup = BeautifulSoup(pageraw, 'html.parser')

        # Extract the relevant form element values
        formtag = pagesoup.select_one('form[action*="acknowledge"]')
        #print('-----------------')
        #print(formtag.prettify())
        #print('-----------------')

        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='[Acknowledge] Retrieve html form from {0}: \n{1}'.format(url,formtag.prettify()))
                
        btn_submit = formtag.findNext('input', {'name':'btn_submit'})['value']
        CSRFToken = formtag.findNext('input', {'name':'CSRFToken'})['value']

        # Pass these values to the same URL as cgi_data
        cgi_data = {}
        cgi_data['CSRFToken'] = CSRFToken
        cgi_data['btn_submit'] = btn_submit
        cgi_data['comment'] = comment
        cgi_data['persistent'] = str(persistent).replace('True', 'y').replace('False', 'n')
        cgi_data['sticky'] = str(sticky).replace('True', 'y').replace('False', 'n')
        cgi_data['notify'] = str(notify).replace('True', 'y').replace('False', 'n')
        if expire_time:
            cgi_data['expire'] = 'y'
            cgi_data['expire_time'] = expire_time
        else:
            cgi_data['expire'] = 'n'

        response = self.fetch_url(url, giveback='raw', cgi_data=cgi_data)

        # Some debug data
        data = response.result
        error = response.error
        status_code = response.status_code
        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='Achnowledgement response')
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- response: {0}".format(response))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- data: {0}".format(data))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- error: {0}".format(error))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- status_code: {0}".format(status_code))

        if len(all_services) > 0:
            for s in all_services:
                # cheap, recursive solution...
                self._set_acknowledge(host, s, author, comment, sticky, notify, persistent, [], expire_time)


    def _set_submit_check_result(self, host, service, state, comment, check_output, performance_data):
        # Set correct headers
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        # First retrieve the info page for this host/service
        if service == '':
            url = '{0}/icingadb/host/process-checkresult?name='.format(self.monitor_cgi_url,
                                                                            self.hosts[host].real_name)
            status = self.STATES_MAPPING_REV['hosts'][state.upper()]
        else:
            url = '{0}/icingadb/service/process-checkresult?name={1}&host.name={2}'.format(self.monitor_cgi_url,
                                                                                           self.hosts[host].services[service].real_name,
                                                                                           self.hosts[host].real_name
                                                                                           )
            status = self.STATES_MAPPING_REV['services'][state.upper()]

        result = self.fetch_url(url, giveback='raw')

        if result.error != '':
            return result
        else:
            pageraw = result.result

        pagesoup = BeautifulSoup(pageraw, 'html.parser')

        # Extract the relevant form element values
        formtag = pagesoup.select_one('form[action*="process-checkresult"]')
        #print('-----------------')
        #print(formtag.prettify())
        #print('-----------------')
        
        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='[Submit check result] Retrieve html form from {0}: \n{1}'.format(url,formtag.prettify()))

        btn_submit = formtag.findNext('input', {'name':'btn_submit'})['value']
        CSRFToken = formtag.findNext('input', {'name':'CSRFToken'})['value']
        
        # Pass these values to the same URL as cgi_data
        cgi_data = {}
        cgi_data['CSRFToken'] = CSRFToken
        cgi_data['btn_submit'] = btn_submit

        cgi_data['status'] = status
        cgi_data['output'] = check_output
        cgi_data['perfdata'] = performance_data

        response = self.fetch_url(url, giveback='raw', cgi_data=cgi_data)

        # Some debug data
        data = response.result
        error = response.error
        status_code = response.status_code
        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='Achnowledgement response')
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- response: {0}".format(response))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- data: {0}".format(data))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- error: {0}".format(error))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- status_code: {0}".format(status_code))


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        # Set correct headers
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        # First retrieve the info page for this host/service
        if service == '':
            url = '{0}/icingadb/host/schedule-downtime?name={1}'.format(self.monitor_cgi_url,
                                                                            self.hosts[host].real_name)
        else:
            url = '{0}/icingadb/service/schedule-downtime?name={1}&host.name={2}&showCompact=1'.format(self.monitor_cgi_url,
                                                                                           self.hosts[host].services[service].real_name,
                                                                                           self.hosts[host].real_name
                                                                                           )
                    
        result = self.fetch_url(url, giveback='raw')

        if result.error != '':
            return result
        else:
            pageraw = result.result

        pagesoup = BeautifulSoup(pageraw, 'html.parser')

        # Extract the relevant form element values
        formtag = pagesoup.select_one('form[action*="schedule-downtime"]')
        #print('-----------------')
        #print(formtag.prettify())
        #print('-----------------')
        
        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='[Set downtime] Retrieve html form from {0}: \n{1}'.format(url,formtag.prettify()))
        
        btn_submit = formtag.findNext('input', {'name':'btn_submit'})['value']
        CSRFToken = formtag.findNext('input', {'name':'CSRFToken'})['value']

        # Pass these values to the same URL as cgi_data
        cgi_data = {}
        cgi_data['CSRFToken'] = CSRFToken
        cgi_data['btn_submit'] = btn_submit
        cgi_data['comment'] = comment
        if fixed:
            cgi_data['flexible'] = 'n'
        else:
            cgi_data['flexible'] = 'y'
            cgi_data['hours'] = hours
            cgi_data['minutes'] = minutes
        if start_time == '' or start_time == 'n/a':
            start = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        else:
            start = start_time
        if end_time == '' or end_time == 'n/a':
            end = (datetime.datetime.now() + datetime.timedelta(hours=hours, minutes=minutes)).strftime('%Y-%m-%dT%H:%M:%S')
        else:
            end = end_time

        cgi_data['start'] = start
        cgi_data['end'] = end

        response = self.fetch_url(url, giveback='raw', cgi_data=cgi_data)

        # Some debug data
        data = response.result
        error = response.error
        status_code = response.status_code
        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='Achnowledgement response')
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- response: {0}".format(response))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- data: {0}".format(data))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- error: {0}".format(error))
            self.debug(server=self.get_name(), host=host, service=service,
                       debug="- status_code: {0}".format(status_code))


    def get_start_end(self, host):
        '''
            for GUI to get actual downtime start and end from server - they may vary so it's better to get
            directly from web interface
        '''
        # Set correct headers
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        try:
            url = '{0}/icingadb/host/schedule-downtime?name={1}'.format(self.monitor_cgi_url, self.hosts[host].real_name)
            downtime = self.fetch_url(url, giveback='raw')

            if downtime.error != '':
                return 'n/a', 'n/a'
            else:
                pageraw = downtime.result
    
            pagesoup = BeautifulSoup(pageraw, 'html.parser')

            #print('-----------------')
            #print(pagesoup.prettify())
            #print('-----------------')
        
            # Super debug
            if conf.debug_mode:
                self.debug(server=self.get_name(), host=host, service='',
                           debug='[Get downtime start/end] Retrieve html from {0}: {1}'.format(url,pagesoup.prettify()))

            start = pagesoup.find('input', {'name': 'start'})['value']
            end = pagesoup.find('input', {'name': 'end'})['value']
            # give values back as tuple
            return start, end
        except:
            self.error(sys.exc_info())
            return 'n/a', 'n/a'


    def open_monitor(self, host, service=''):
        """Open monitor from tablewidget context menu."""
        if host not in self.hosts:
            print("Cannot find {}. Skipping!".format(host))
            return
        if service and service not in self.hosts[host].services:
            print("Cannot find {}::{}. Skipping!".format(host, service))
            return

        # Generate the base path for the URL
        base_path = urllib.parse.urlparse(self.monitor_url).path

        # Handle URL for host monitoring
        if service == '':
            url = '{0}/icingadb/hosts?host.state.is_problem=y&sort=host.state.severity#!{1}/icingadb/host?{2}'.format(
                self.monitor_url,
                base_path,
                urllib.parse.urlencode({'name': self.hosts[host].real_name}, quote_via=urllib.parse.quote)
            )
        else:
            # Handle URL for service monitoring
            url = '{0}/icingadb/services?service.state.is_problem=y&sort=service.state.severity%20desc#!{1}/icingadb/service?{2}'.format(
                self.monitor_url,
                base_path,
                urllib.parse.urlencode({
                    'name': self.hosts[host].services[service].real_name,
                    'host.name': self.hosts[host].real_name
                }, quote_via=urllib.parse.quote)
            )
        if conf.debug_mode:
            self.debug(server=self.get_name(), host=host, service=service,
                       debug='[Open monitor] Open host/service monitor web page {0}'.format(url))
        webbrowser_open(url)

    def get_host(self, host):
        '''
            find out ip or hostname of given host to access hosts/devices which do not appear in DNS but
            have their ip saved in Icinga
        '''
        # Host is the display name as in the GUI
        # but we need the FQDN not the display name
        host = self.hosts[host].real_name

        # the fasted method is taking hostname as used in monitor
        if conf.connect_by_host is True or host == '':
            return Result(result=host)

        # initialize ip string
        ip = ''
        address = ''

        # glue nagios cgi url and hostinfo
        cgiurl_host = self.monitor_cgi_url + '/icingadb/hosts?name={0}&columns=host.address&format=json'.format(host)

        # get host info
        hostobj = self.fetch_url(cgiurl_host, giveback='raw')
        jsonhost = hostobj.result

        try:
            # take ip from json output
            result = json.loads(jsonhost)[0]
            ip = result["host_address"]

            # print IP in debug mode
            if conf.debug_mode is True:
                self.debug(server=self.get_name(), host=host, debug='IP of %s:' % (host) + ' ' + ip)

            # when connection by DNS is not configured do it by IP
            if conf.connect_by_dns is True:
                # try to get DNS name for ip, if not available use ip
                try:
                    address = socket.gethostbyaddr(ip)[0]
                except socket.error:
                    address = ip
            else:
                address = ip
        except Exception:
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # do some cleanup
        del hostobj

        # give back host or ip
        return Result(result=address)
