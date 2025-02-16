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

import urllib.request
import urllib.parse
import urllib.error
import socket
import sys
import re
import copy

from datetime import datetime, timedelta

from Nagstamon.Objects import *
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Config import conf
from Nagstamon.Helpers import webbrowser_open


class CentreonServer(GenericServer):

    def __init__(self, **kwds):

        GenericServer.__init__(self, **kwds)

        self.TYPE = 'Centreon'

        # centreon generic web interface uses a sid which is needed to ask for news
        self.SID = None

        # HARD/SOFT state mapping
        self.HARD_SOFT = {'(H)': 'hard', '(S)': 'soft'}

        # apparently necessesary because of non-english states as in https://github.com/HenriWahl/Nagstamon/issues/91 (Centeron 2.5)
        self.TRANSLATIONS = {'INDISPONIBLE': 'DOWN',
                        'INJOIGNABLE': 'UNREACHABLE',
                        'CRITIQUE': 'CRITICAL',
                        'INCONNU': 'UNKNOWN',
                        'ALERTE': 'WARNING'}

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ['Monitor', 'Recheck', 'Acknowledge', 'Downtime']

        # Centreon works better or at all with html.parser for BeautifulSoup
        self.PARSER = 'html.parser'

        # Needed to detect each Centreon's version
        self.centreon_version = None
        # Token that centreon use to protect the system
        self.centreon_token = None
        # To only detect broker once
        self.first_login = True
        # limit number of services retrived
        self.limit_services_number = 9999
        # default value, applies to version 2.2 and others
        self.XML_PATH = 'xml'

    def init_config(self):
        '''
        dummy init_config, called at thread start, not really needed here, just omit extra properties
        '''
        # set URLs here already
        self.init_HTTP()
        if not self.tls_error and self.centreon_version is not None:
            self._define_url()

    def init_HTTP(self):
        """
        initialize HTTP connection
        """
        if self.session is None:
            GenericServer.init_HTTP(self)

        if self.centreon_version is None:
            result_versioncheck = self.fetch_url(self.monitor_cgi_url + '/index.php', giveback='raw')
            raw_versioncheck, error_versioncheck = result_versioncheck.result, result_versioncheck.error
            if error_versioncheck == '':
                if re.search(r'2\.2\.[0-9]', raw_versioncheck):
                    self.centreon_version = 2.2
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version detected : 2.2')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?p=1',
                                        'hosts': '$MONITOR$/main.php?p=20103&o=hpb',
                                        'services': '$MONITOR$/main.php?p=20202&o=svcpb',
                                        'history': '$MONITOR$/main.php?p=203'}
                elif re.search(r'2\.[3-6]\.[0-5]', raw_versioncheck):
                    self.centreon_version = 2.3456
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version detected : 2.3 <=> 2.6.5')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?p=1',
                                        'hosts': '$MONITOR$/main.php?p=20103&o=hpb',
                                        'services': '$MONITOR$/main.php?p=20202&o=svcpb',
                                        'history': '$MONITOR$/main.php?p=203'}
                elif re.search(r'2\.6\.[6-9]', raw_versioncheck):
                    self.centreon_version = 2.66
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version detected : 2.6.6')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?p=1',
                                        'hosts': '$MONITOR$/main.php?p=20103&o=hpb',
                                        'services': '$MONITOR$/main.php?p=20202&o=svcpb',
                                        'history': '$MONITOR$/main.php?p=203'}
                elif re.search(r'2\.7\.[0-9]', raw_versioncheck):
                    # Centreon 2.7 only support C. Broker
                    self.centreon_version = 2.7
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version detected : 2.7')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?',
                                        'hosts': '$MONITOR$/main.php?p=20202&o=hpb',
                                        'services': '$MONITOR$/main.php?p=20201&o=svcpb',
                                        'history': '$MONITOR$/main.php?p=203'}
                elif re.search(r'2\.8\.[0-9]', raw_versioncheck):
                    # Centreon 2.8 only support C. Broker
                    self.centreon_version = 2.8
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version detected : 2.8')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?',
                                        'hosts': '$MONITOR$/main.php?p=20202',
                                        'services': '$MONITOR$/main.php?p=20201',
                                        'history': '$MONITOR$/main.php?p=203'}
                elif re.search(r'18\.10\.[0-9]', raw_versioncheck):
                    self.centreon_version = 18.10
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version detected : 18.10')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?',
                                        'hosts': '$MONITOR$/main.php?p=20202',
                                        'services': '$MONITOR$/main.php?p=20201',
                                        'history': '$MONITOR$/main.php?p=203'}
                elif re.search(r'19\.(04|10)\.[0-9]', raw_versioncheck) or re.search(r'20\.(04|10)\.[0-9]', raw_versioncheck):
                    self.centreon_version = 19.04
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version detected : 19.04 <=> 20.10')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?',
                                        'hosts': '$MONITOR$/main.php?p=20202',
                                        'services': '$MONITOR$/main.php?p=20201',
                                        'history': '$MONITOR$/main.php?p=203'}
                else:
                    # unsupported version or unable do determine
                    self.centreon_version = 19.04
                    if conf.debug_mode is True:
                        self.debug(server=self.get_name(), debug='Centreon version unknown : supposed to be >= 19.04')
                    # URLs for browser shortlinks/buttons on popup window
                    self.BROWSER_URLS = {'monitor': '$MONITOR$/main.php?',
                                        'hosts': '$MONITOR$/main.php?p=20202&o=hpb',
                                        'services': '$MONITOR$/main.php?p=20201&o=svcpb',
                                        'history': '$MONITOR$/main.php?p=203'}
            else:
                if conf.debug_mode is True:
                    self.debug(server=self.get_name(), debug='Error getting the home page : ' + error_versioncheck)

            if self.first_login:
                self.SID = self._get_sid().result
                self.first_login = False

            del result_versioncheck, raw_versioncheck, error_versioncheck

    def reset_HTTP(self):
        '''
        Centreon needs deletion of SID
        '''
        self.SID = None
        self.SID = self._get_sid().result

    def open_monitor(self, host, service=''):
        if self.use_autologin is True:
            auth = '&autologin=1&useralias=' + self.username + '&token=' + self.autologin_key
        else:
            auth = ''

        #  Meta
        if host == '_Module_Meta':
            # Centreon < 2.7
            if self.centreon_version < 2.7:
                webbrowser_open(self.urls_centreon['index'] + '?' + urllib.parse.urlencode({'p': 20206, 'o': 'meta'}) + auth )
            #  Centreon 2.7
            elif self.centreon_version == 2.7:
                webbrowser_open(self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p':20206, 'o':'meta'}) + auth )
            #  Centreon 2.8
            elif self.centreon_version == 2.8:
                m =  re.search(r'^.+ \((?P<rsd>.+)\)$', service)
                if m:
                    service = m.group('rsd')
                    webbrowser_open(self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p':20201,'o':'svcd','host_name':'_Module_Meta','service_description':service}) + auth )
            # Starting from Centreon 18.10
            else:
                m =  re.search(r'^.+ \((?P<rsd>.+)\)$', service)
                if m:
                    service = m.group('rsd')
                    webbrowser_open(self.urls_centreon['main_with_frames'] + '?' + urllib.parse.urlencode({'p':20201,'o':'svcd','host_name':'_Module_Meta','service_description':service}) + auth )

        # must be a host if service is empty
        elif service == '':
            if self.centreon_version < 2.7:
                webbrowser_open(self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p':201,'o':'hd', 'host_name':host}) + auth )
            elif self.centreon_version in [2.7, 2.8]:
                webbrowser_open(self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p':20202,'o':'hd', 'host_name':host}) + auth )
            else:
                webbrowser_open(self.urls_centreon['main_with_frames'] + '?' + urllib.parse.urlencode({'p':20202,'o':'hd', 'host_name':host}) + auth )

        # so it's a service
        else:
            if self.centreon_version < 2.7:
                webbrowser_open(self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p':202, 'o':'svcd',  'host_name':host, 'service_description':service}) + auth )
            elif self.centreon_version in [2.7, 2.8]:
                webbrowser_open(self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p':20201,'o':'svcd', 'host_name':host, 'service_description':service}) + auth )
            else:
                webbrowser_open(self.urls_centreon['main_with_frames'] + '?' + urllib.parse.urlencode({'p':20201,'o':'svcd', 'host_name':host, 'service_description':service}) + auth )


    def _get_sid(self):
        '''
        gets a shiny new SID for XML HTTP requests to Centreon cutting it out via .partition() from raw HTML
        additionally get php session cookie
        '''
        try:
            # Aulogin with key, BROWSER_URLS needs the key
            if self.use_autologin:
                auth = '&autologin=1&useralias=' + self.username + '&token=' + self.autologin_key
                self.BROWSER_URLS= { 'monitor': self.BROWSER_URLS['monitor'] + auth,\
                                    'hosts': self.BROWSER_URLS['hosts'] + auth,\
                                    'services': self.BROWSER_URLS['services'] + auth,\
                                    'history': self.BROWSER_URLS['history'] + auth}
                raw = self.fetch_url(self.monitor_cgi_url + '/index.php?p=101&autologin=1&useralias=' + self.username + '&token=' + self.autologin_key, giveback='raw')
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Autologin : ' + self.username + ' : ' + self.autologin_key)
                # Gathering of the token who will be used to interact with Centreon (start with 2.66)
                if  self.centreon_version >= 2.66 and self.centreon_version < 19.04:
                    page = self.fetch_url(self.monitor_cgi_url + '/main.get.php')
                    self.centreon_token = page.result.find('input', {'name': "centreon_token"})['value']

            # Password auth
            else:
                login = self.fetch_url(self.monitor_cgi_url + '/index.php')
                if login.error == '' and login.status_code == 200:
                    # Centreon >= 2.6.6 implement a token
                    if  self.centreon_version >= 2.66 and self.centreon_version <= 19.04:
                        form = login.result.find('form')
                        form_inputs = {}
                        # Need to catch the centreon_token for login to work
                        for form_input in ('centreon_token', 'submitLogin'):
                            form_inputs[form_input] = form.find('input', {'name': form_input})['value']
                        self.centreon_token = form_inputs['centreon_token']
                        form_inputs['useralias'] = self.username
                        form_inputs['password'] = self.password
                        # fire up login button with all needed data
                        raw = self.fetch_url(self.monitor_cgi_url + '/index.php', cgi_data=form_inputs)
                    else:
                        login_data = {"useralias" : self.username, "password" : self.password, "submit" : "Login"}
                        raw = self.fetch_url(self.monitor_cgi_url + "/index.php", cgi_data=login_data, giveback="raw")
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Password login : ' + self.username + ' : ' + self.password)

            sid = self.session.cookies.get('PHPSESSID', '')
            if conf.debug_mode:
                self.debug(server=self.get_name(), debug='SID : ' + sid)
                if  self.centreon_version >= 2.66 and self.centreon_version < 19.04:
                    self.debug(server=self.get_name(), debug='Centreon Token : ' + self.centreon_token)
            # those broker urls would not be changing too often so this check migth be done here
            if self.first_login:
                self._get_xml_path(sid)
                self.first_login = False
            return Result(result=sid)

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)


    def get_start_end(self, host):
        '''
        get start and end time for downtime from Centreon server
        '''
        try:
            # It's not possible since 18.10 to get date from the webinterface
            # because it's set in javascript
            if self.centreon_version < 18.10:
                cgi_data = {'o':'ah',\
                            'host_name':host}
                if self.centreon_version < 2.7:
                    cgi_data['p'] = '20106'
                elif self.centreon_version == 2.7:
                    cgi_data['p'] = '210'
                elif self.centreon_version == 2.8:
                    cgi_data['o'] = 'a'
                    cgi_data['p'] = '210'
                result = self.fetch_url(self.urls_centreon['main'], cgi_data = cgi_data, giveback='obj')

                html, error = result.result, result.error
                if error == '':
                    start_date = html.find(attrs={'name':'start'}).attrs['value']
                    start_hour = html.find(attrs={'name':'start_time'}).attrs['value']
                    start_time = start_date + ' ' + start_hour

                    end_date = html.find(attrs={'name':'end'}).attrs['value']
                    end_hour = html.find(attrs={'name':'end_time'}).attrs['value']
                    end_time = end_date + ' ' + end_hour
                    return start_time, end_time

            else:
                start_time = datetime.now().strftime("%m/%d/%Y %H:%M")
                end_time = datetime.now() + timedelta(hours=2)
                end_time = end_time.strftime("%m/%d/%Y %H:%M")
                return start_time, end_time

        except:
            self.error(sys.exc_info())
            return 'n/a', 'n/a'


    def get_host(self, host):
        '''
        Centreonified way to get host ip - attribute 'a' in down hosts xml is of no use for up
        hosts so we need to get ip anyway from web page
        '''
        # the fastest method is taking hostname as used in monitor
        if conf.connect_by_host == True or host == '':
            return Result(result=host)

        # do a web interface search limited to only one result - the hostname
        cgi_data = {'sid': self.SID,
                    'search': host,
                    'num': 0,
                    'limit': 1,
                    'sort_type':'hostname',
                    'order': 'ASC',
                    'date_time_format_status': 'd/m/Y H:i:s',
                    'o': 'h',
                    'p': 20102,
                    'time': 0}

        centreon_hosts = self.urls_centreon['xml_hosts'] + '?' + urllib.parse.urlencode(cgi_data)

        result = self.fetch_url(centreon_hosts, giveback='xml')
        xmlobj, error, status_code = result.result, result.error, result.status_code

        # initialize ip string
        ip = ''

        if len(xmlobj) != 0:
            ip = str(xmlobj.l.a.text)
            # when connection by DNS is not configured do it by IP
            try:
                if conf.connect_by_dns:
                   # try to get DNS name for ip (reverse DNS), if not available use ip
                    try:
                        address = socket.gethostbyaddr(ip)[0]
                    except:
                        if conf.debug_mode:
                            self.debug(server=self.get_name(), debug='Unable to do a reverse DNS lookup on IP: ' + ip)
                        address = ip
                else:
                    address = ip
            except:
                result, error = self.error(sys.exc_info())
                return Result(result=result, error=error)

        else:
            result, error = self.error(sys.exc_info())
            return Result(error=error)

        del xmlobj

        # print IP in debug mode
        if conf.debug_mode:
            self.debug(server=self.get_name(), debug='IP of %s:' % (host) + ' ' + address)

        # give back host or ip
        return Result(result=address)


    def _get_xml_path(self, sid):
        '''
        Find out where this instance of Centreon is publishing the status XMLs
        Centreon 2.6 + ndo/c.broker - /include/monitoring/status/Hosts/xml/{ndo,broker}/hostXML.php according to configuration
        Centreon 2.7 + c.broker - /include/monitoring/status/Hosts/xml/hostXML.php
        Centreon 2.8 + c.broker - /include/monitoring/status/Hosts/xml/hostXML.php
        regexping HTML for Javascript
        '''
        if self.centreon_version <= 2.66:
            # 2.6 support NDO and C. Broker, we must check which one is used
            cgi_data = {'p':201, 'sid':sid}
            result = self.fetch_url(self.monitor_cgi_url + '/main.php', cgi_data=cgi_data, giveback='raw')
            raw, error = result.result, result.error
            if error == '':
                if re.search(r'var _addrXML.*xml\/ndo\/host', raw):
                  self.XML_PATH = 'xml/ndo'
                  if conf.debug_mode:
                      self.debug(server=self.get_name(), debug='Detected broker : NDO')
                elif re.search(r'var _addrXML.*xml\/broker\/host', raw):
                    self.XML_PATH = 'xml/broker'
                    if conf.debug_mode:
                        self.debug(server=self.get_name(), debug='Detected broker : C. Broker')
                else:
                    if conf.debug_mode:
                        self.debug(server=self.get_name(), debug='Could not detect the broker for Centeron 2.[3-6]. Using Centreon Broker')
                    self.XML_PATH = 'xml/broker'
                del raw
            else:
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Unable to fetch the main page to detect the broker : ' + error)
            del result, error
        else:
            if conf.debug_mode:
                self.debug(server=self.get_name(), debug='Only Centreon Broker is supported in Centeon >= 2.7 -> XML_PATH=' + self.XML_PATH)


    def _define_url(self):
        urls_centreon_2_2 = {
            'main': self.monitor_cgi_url + '/main.php',
            'index': self.monitor_cgi_url + '/index.php',
            'xml_services': self.monitor_cgi_url + '/include/monitoring/status/Services/' + self.XML_PATH + '/serviceXML.php',
            'xml_hosts': self.monitor_cgi_url + '/include/monitoring/status/Hosts/' + self.XML_PATH + '/hostXML.php',
            'xml_meta': self.monitor_cgi_url + '/include/monitoring/status/Meta/' + self.XML_PATH + '/metaServiceXML.php',
            'xml_hostSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/hostSendCommand.php',
            'xml_serviceSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/serviceSendCommand.php',
            'external_cmd_cmdPopup': self.monitor_cgi_url + '/include/monitoring/external_cmd/cmdPopup.php',
            # no idea if this really exist in centreon < 2.7
            'autologoutXMLresponse': self.monitor_cgi_url + '/include/common/javascript/autologoutXMLresponse.php'
        }

        # inconsistant url in Centreon 2.7
        urls_centreon_2_7 = {
            'main': self.monitor_cgi_url + '/main.php',
            'index': self.monitor_cgi_url + '/index.php',
            'xml_services': self.monitor_cgi_url + '/include/monitoring/status/Services/' + self.XML_PATH + '/serviceXML.php',
            'xml_hosts': self.monitor_cgi_url + '/include/monitoring/status/Hosts/' + self.XML_PATH + '/broker/hostXML.php',
            'xml_meta': self.monitor_cgi_url + '/include/monitoring/status/Meta/' + self.XML_PATH + '/broker/metaServiceXML.php',
            'xml_hostSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/hostSendCommand.php',
            'xml_serviceSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/serviceSendCommand.php',
            'external_cmd_cmdPopup': self.monitor_cgi_url + '/include/monitoring/external_cmd/cmdPopup.php',
            'autologoutXMLresponse': self.monitor_cgi_url + '/include/common/javascript/autologoutXMLresponse.php'
        }

        urls_centreon_2_8 = {
            'main': self.monitor_cgi_url + '/main.php',
            'index': self.monitor_cgi_url + '/index.php',
            'xml_services': self.monitor_cgi_url + '/include/monitoring/status/Services/' + self.XML_PATH + '/serviceXML.php',
            'xml_hosts': self.monitor_cgi_url + '/include/monitoring/status/Hosts/' + self.XML_PATH + '/hostXML.php',
            'xml_hostSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/hostSendCommand.php',
            'xml_serviceSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/serviceSendCommand.php',
            'external_cmd_cmdPopup': self.monitor_cgi_url + '/include/monitoring/external_cmd/cmdPopup.php',
            'autologoutXMLresponse': self.monitor_cgi_url + '/include/core/autologout/autologoutXMLresponse.php'
        }

        urls_centreon_18_10 = {
            'main': self.monitor_cgi_url + '/main.get.php',
            # needed to get the frames around the page when opening the monitoring on a host/service
            'main_with_frames': self.monitor_cgi_url + '/main.php',
            'index': self.monitor_cgi_url + '/index.php',
            'xml_services': self.monitor_cgi_url + '/include/monitoring/status/Services/' + self.XML_PATH + '/serviceXML.php',
            'xml_hosts': self.monitor_cgi_url + '/include/monitoring/status/Hosts/' + self.XML_PATH + '/hostXML.php',
            'xml_hostSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/hostSendCommand.php',
            'xml_serviceSendCommand': self.monitor_cgi_url + '/include/monitoring/objectDetails/xml/serviceSendCommand.php',
            'external_cmd_cmdPopup': self.monitor_cgi_url + '/include/monitoring/external_cmd/cmdPopup.php',
            'keepAlive': self.monitor_cgi_url + '/api/internal.php?object=centreon_keepalive&action=keepAlive'
        }

        if self.centreon_version < 2.7:
            self.urls_centreon = urls_centreon_2_2
        elif self.centreon_version == 2.7:
            self.urls_centreon = urls_centreon_2_7
        elif self.centreon_version == 2.8:
            self.urls_centreon = urls_centreon_2_8
        # 18.10 and beyond
        elif self.centreon_version >= 18.10:
            self.urls_centreon = urls_centreon_18_10
        if conf.debug_mode:
            self.debug(server=self.get_name(), debug='URLs defined for Centreon %s' % (self.centreon_version))


    def _get_host_id(self, host):
        '''
        get host_id via parsing raw html
        '''
        if self.centreon_version < 2.7:
            cgi_data = {'p': 20102, 'o': 'hd', 'host_name': host, 'sid': self.SID}
        else:
            cgi_data = {'p': 20202, 'o': 'hd', 'host_name': host, 'sid': self.SID}

        url = self.urls_centreon['main'] + '?' + urllib.parse.urlencode(cgi_data)

        result = self.fetch_url(url, giveback='raw')
        raw, error = result.result, result.error

        if error == '':
            host_id = raw.partition("var host_id = '")[2].partition("'")[0]
            del raw
        else:
            if conf.debug_mode:
                self.debug(server=self.get_name(), debug='Host ID could not be retrieved.')

        # some cleanup
        del result, error

        # only if host_id is an usable integer return it
        try:
            if int(host_id):
                if conf.debug_mode:
                    self.debug(server=self.get_name(), host=host, debug='Host ID is ' + host_id)
                return host_id
            else:
                return ''
        except:
            return ''


    def _get_host_and_service_id(self, host, service):
        '''
        parse a ton of html to get a host and a service id...
        '''
        cgi_data = {'p':'20201',\
                    'host_name':host,\
                    'service_description':service,\
                    'o':'svcd'}

        # This request must be done in a GET, so just encode the parameters and fetch
        result = self.fetch_url(self.urls_centreon['main'] + '?' + urllib.parse.urlencode(cgi_data), giveback="raw")
        raw, error = result.result, result.error

        if error == '':
            host_id = raw.partition("var host_id = '")[2].partition("'")[0]
            svc_id = raw.partition("var svc_id = '")[2].partition("'")[0]
            del raw
            if conf.debug_mode:
                self.debug(server=self.get_name(), host=host, service=service, debug='- Get host/svc ID : ' + host_id + '/' + svc_id)
        else:
            if conf.debug_mode:
                self.debug(server=self.get_name(), host=host, service=service, debug='- IDs could not be retrieved.')

        # some cleanup
        del result, error

        # only if host_id is an usable integer return it
        try:
            if int(host_id) and int(svc_id):
                if conf.debug_mode:
                    self.debug(server=self.get_name(), host=host, service=service, debug='- Host & Service ID are valid (int)')
                return host_id,svc_id
            else:
                return '',''
        except:
            return '',''


    def _get_status(self):
        '''
        Get status from Centreon Server
        '''
        # Be sure that the session is still active
        result = self._check_session()
        if result is not None:
            if result.result == 'ERROR':
                if 'urls_centreon' in result.error:
                    result.error = 'Connection error'
                return result

        # services (unknown, warning or critical?)
        if self.centreon_version < 2.7:
            nagcgiurl_services = self.urls_centreon['xml_services'] + '?' + urllib.parse.urlencode({'num':0, 'limit':self.limit_services_number, 'o':'svcpb', 'sort_type':'status', 'sid':self.SID})
        else:
            nagcgiurl_services = self.urls_centreon['xml_services'] + '?' + urllib.parse.urlencode({'num':0, 'limit':self.limit_services_number, 'o':'svcpb', 'p':20201, 'nc':0, 'criticality':0, 'statusService':'svcpb', 'sSetOrderInMemory':1, 'sid':self.SID})

        # hosts (up or down or unreachable)
        # define hosts xml URL, because of inconsistant url
        if self.centreon_version < 2.7:
            nagcgiurl_hosts = self.urls_centreon['xml_hosts'] + '?' + urllib.parse.urlencode({'num':0, 'limit':self.limit_services_number, 'o':'hpb', 'sort_type':'status', 'sid':self.SID})
        elif self.centreon_version >= 2.7 and self.centreon_version < 19.04:
            nagcgiurl_hosts = self.urls_centreon['xml_hosts'] + '?' + urllib.parse.urlencode({'num':0, 'limit':self.limit_services_number, 'o':'hpb', 'p':20202, 'criticality':0, 'statusHost':'hpb', 'sSetOrderInMemory':1, 'sid':self.SID})
        else:
            nagcgiurl_hosts = self.urls_centreon['xml_hosts'] + '?' + urllib.parse.urlencode({'num':0, 'limit':self.limit_services_number, 'o':'hpb', 'p':20202, 'criticality':0, 'statusHost':'hpb', 'sSetOrderInMemory':1})

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            result = self.fetch_url(nagcgiurl_hosts, giveback='xml')
            xmlobj, error, status_code = result.result, result.error, result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(xmlobj, error, status_code)

            # if there are errors return them
            if errors_occured is not None:
                return(errors_occured)

            # Check if the result is not empty
            if len(xmlobj) == 0:
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Empty host XML result')
                return Result(result=None, error="Empty host XML result")

            # in case there are no children session ID is expired
            if xmlobj.text.lower() == 'bad session id':
                del xmlobj
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Bad session ID, retrieving new one...')

                # try again...
                self.SID = self._get_sid().result
                result = self.fetch_url(nagcgiurl_hosts, giveback='xml')
                xmlobj, error, status_code = result.result, result.error, result.status_code
                errors_occured = self.check_for_error(xmlobj, error, status_code)
                # if there are errors return them
                if errors_occured is not None:
                    return(errors_occured)

                # a second time a bad session id should raise an error
                if xmlobj.text.lower() == 'bad session id':
                    if conf.debug_mode:
                        self.debug(server=self.get_name(), debug='Even after renewing session ID, unable to get the XML')
                    return Result(result='ERROR',
                                  error='Bad session ID',
                                  status_code=status_code)

            for l in xmlobj.findAll('l'):
                try:
                    # host objects contain service objects
                    if not l.hn.text in self.new_hosts:
                        self.new_hosts[str(l.hn.text)] = GenericHost()
                        self.new_hosts[str(l.hn.text)].name =  str(l.hn.text)
                        self.new_hosts[str(l.hn.text)].server = self.name
                        self.new_hosts[str(l.hn.text)].status = str(l.cs.text)
                        # disgusting workaround for https://github.com/HenriWahl/Nagstamon/issues/91
                        if self.new_hosts[str(l.hn.text)].status in self.TRANSLATIONS:
                            self.new_hosts[str(l.hn.text)].status = self.TRANSLATIONS[self.new_hosts[str(l.hn.text)].status]
                        self.new_hosts[str(l.hn.text)].attempt, self.new_hosts[str(l.hn.text)].status_type  = str(l.tr.text).split(' ')
                        self.new_hosts[str(l.hn.text)].status_type = self.HARD_SOFT[self.new_hosts[str(l.hn.text)].status_type]
                        self.new_hosts[str(l.hn.text)].last_check = str(l.lc.text)
                        self.new_hosts[str(l.hn.text)].duration = str(l.lsc.text)
                        self.new_hosts[str(l.hn.text)].status_information = str(l.ou.text).replace('\n', ' ').strip()
                        if l.find('cih') != None:
                            self.new_hosts[str(l.hn.text)].criticality = str(l.cih.text)
                        else:
                            self.new_hosts[str(l.hn.text)].criticality = ''
                        self.new_hosts[str(l.hn.text)].acknowledged = bool(int(str(l.ha.text)))
                        self.new_hosts[str(l.hn.text)].scheduled_downtime = bool(int(str(l.hdtm.text)))
                        if l.find('is') != None:
                            self.new_hosts[str(l.hn.text)].flapping = bool(int(str(l.find('is').text)))
                        else:
                            self.new_hosts[str(l.hn.text)].flapping = False
                        self.new_hosts[str(l.hn.text)].notifications_disabled = not bool(int(str(l.ne.text)))
                        self.new_hosts[str(l.hn.text)].passiveonly = not bool(int(str(l.ace.text)))
                except:
                    import traceback
                    traceback.print_exc(file=sys.stdout)
                    # set checking flag back to False
                    self.isChecking = False
                    result, error = self.error(sys.exc_info())
                    return Result(result=result, error=error)

            del xmlobj

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            result = self.fetch_url(nagcgiurl_services, giveback='xml')
            xmlobj, error, status_code = result.result, result.error, result.status_code

            # check if any error occured
            errors_occured = self.check_for_error(xmlobj, error, status_code)
            # if there are errors return them
            if errors_occured is not None:
                return(errors_occured)

            # Check if the result is not empty
            if len(xmlobj) == 0:
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Empty service XML result')
                return Result(result=None, error="Empty service XML result")

            # in case there are no children session id is invalid
            if xmlobj.text.lower() == 'bad session id':
                # debug
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Bad session ID, retrieving new one...')
                # try again...
                self.SID = self._get_sid().result
                result = self.fetch_url(nagcgiurl_services, giveback='xml')
                xmlobj, error, status_code = result.result, result.error, result.status_code
                errors_occured = self.check_for_error(xmlobj, error, status_code)
                # if there are errors return them
                if errors_occured is not None:
                    return(errors_occured)

                # a second time a bad session id should raise an error
                if xmlobj.text.lower() == 'bad session id':
                    return Result(result='ERROR',
                                  error='Bad session ID',
                                  status_code=status_code)

            # In Centreon 2.8, Meta are merged with regular services
            if self.centreon_version < 2.8:
                # define meta-services xml URL
                if self.centreon_version == 2.7:
                    nagcgiurl_meta_services = self.urls_centreon['xml_meta'] + '?' + urllib.parse.urlencode({'num':0, 'limit':self.limit_services_number, 'o':'meta', 'sort_type':'status', 'sid':self.SID})
                else:
                    nagcgiurl_meta_services = self.urls_centreon['xml_meta'] + '?' + urllib.parse.urlencode({'num':0, 'limit':self.limit_services_number, 'o':'meta', 'sort_type':'status', 'sid':self.SID})

                # retrive meta-services xml STATUS
                result_meta = self.fetch_url(nagcgiurl_meta_services, giveback='xml')
                xmlobj_meta, error_meta, status_code_meta = result_meta.result, result_meta.error, result_meta.status_code

                # check if any error occured
                errors_occured = self.check_for_error(xmlobj_meta, error_meta, status_code_meta)

                # if there are errors return them
                if errors_occured is not None:
                    return(errors_occured)

                # a second time a bad session id should raise an error
                if xmlobj_meta.text.lower() == 'bad session id':
                    if conf.debug_mode:
                        self.debug(server=self.get_name(), debug='Even after renewing session ID, unable to get the XML')

                    return Result(result='ERROR',
                                  error='Bad session ID',
                                  status_code=status_code_meta)

                # INSERT META-services xml at the end of the services xml
                try:
                        xmlobj.append(xmlobj_meta.reponse)
                except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # set checking flag back to False
                        self.isChecking = False
                        result, error = self.error(sys.exc_info())
                        return Result(result=result, error=error)
                # do some cleanup
                del xmlobj_meta

            for l in xmlobj.findAll('l'):
                try:
                    # host objects contain service objects
                    ###if not self.new_hosts.has_key(str(l.hn.text)):
                    if not l.hn.text in self.new_hosts:
                        self.new_hosts[str(l.hn.text)] = GenericHost()
                        self.new_hosts[str(l.hn.text)].name = str(l.hn.text)
                        self.new_hosts[str(l.hn.text)].status = 'UP'
                    # if a service does not exist create its object
                    if not l.sd.text in self.new_hosts[str(l.hn.text)].services:
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)] = GenericService()
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].host = str(l.hn.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].name = str(l.sd.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].server = self.name
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status = str(l.cs.text)

                        if self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].host == '_Module_Meta':
                            # ajusting service name for Meta services
                            if self.centreon_version < 2.8:
                                self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].name = '{} ({})'.format(str(l.sd.text), l.rsd.text)
                                self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].attempt = str(l.ca.text)
                            else:
                                self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].name = '{} ({})'.format(str(l.sdn.text), l.sdl.text)
                                self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].attempt, \
                                self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type = str(l.ca.text).split(' ')
                        else:
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].attempt, \
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type = str(l.ca.text).split(' ')

                        # disgusting workaround for https://github.com/HenriWahl/Nagstamon/issues/91
                        # Still needed in Centreon 2.8 at least : https://github.com/HenriWahl/Nagstamon/issues/344
                        # Need enhancement, we can do service state matching with this field <sc>service_unknown</sc>
                        #if self.centreon_version < 2.66:
                        if self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status in self.TRANSLATIONS:
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status = self.TRANSLATIONS[\
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status]

                        if not (self.centreon_version < 2.8 and self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].host == '_Module_Meta'):
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type =\
                            self.HARD_SOFT[self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type]

                        if conf.debug_mode:
                            self.debug(server=self.get_name(), debug='Parsing service XML (Host/Service/Status_type) ' + self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].host + '/' + self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].name + '/' + self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].last_check = str(l.lc.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].duration = str(l.d.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_information = str(l.po.text).replace('\n', ' ').strip()

                        if l.find('cih') != None:
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].criticality = str(l.cih.text)
                        else:
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].criticality = ''

                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].acknowledged = bool(int(str(l.pa.text)))
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].notifications_disabled = not bool(int(str(l.ne.text)))

                        # for features not available in centreon < 2.8 and meta services
                        if not (self.centreon_version < 2.8 and self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].host == '_Module_Meta'):
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].scheduled_downtime = bool(int(str(l.dtm.text)))
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].flapping = bool(int(str(l.find('is').text)))
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].passiveonly = not bool(int(str(l.ac.text)))

                except:
                    import traceback
                    traceback.print_exc(file=sys.stdout)
                    # set checking flag back to False
                    self.isChecking = False
                    result, error = self.error(sys.exc_info())
                    return Result(result=result, error=error)

            # do some cleanup
            del xmlobj

        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            # set checking flag back to False
            self.isChecking = False
            result, error = self.error(sys.exc_info())
            return Result(result=result, error=error)

        # return True if all worked well
        return Result()


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=None):
        # decision about host or service - they have different URLs
        try:
            if service == '':
                # host
                cgi_data = {'cmd': '14',
                            'host_name': host,
                            'author': author,
                            'comment': comment,
                            'submit': 'Add',
                            'notify': int(notify),
                            'persistent': int(persistent),
                            'sticky': int(sticky),
                            'ackhostservice': '0',
                            'en': '1'}
                if self.centreon_version < 2.7:
                    cgi_data['p'] = '20105'
                    cgi_data['o'] = 'hpb'
                else:
                    cgi_data['p'] = '20202'
                    cgi_data['o'] = 'hpb'
                    cgi_data['centreon_token'] = self.centreon_token

                # Post
                raw = self.fetch_url(self.urls_centreon['main'], cgi_data=cgi_data, giveback='raw')
                del raw

            # if host is acknowledged and all services should be to or if a service is acknowledged
            # (and all other on this host too)
            if service != '' or all_services:
                # service(s) @ host
                # if all_services is empty only one service has to be checked - the one clicked
                # otherwise if there all services should be acknowledged
                if not all_services:
                    all_services = [service]

                # acknowledge all services on a host
                for s in all_services:
                    cgi_data = {'cmd': '15',
                                'host_name': host,
                                'author': author,
                                'comment': comment,
                                'submit': 'Add',
                                'notify': int(notify),
                                'service_description': s,
                                'force_check': '1',
                                'persistent': int(persistent),
                                # following not needed in 18.10, required in wich version ?
                                'persistant': int(persistent),
                                'sticky': int(sticky),
                                'o': 'svcd',
                                'en': '1'}
                    if self.centreon_version < 2.7:
                        cgi_data['p'] = '20215'
                    else:
                        cgi_data['p'] = '20201'
                        cgi_data['centreon_token'] = self.centreon_token

                    # in case of a meta-service, extract the 'rsd' field from the service name :
                    if host == '_Module_Meta':
                        m =  re.search(r'^.+ \((?P<rsd>.+)\)$', s)
                        if m:
                            rsd = m.group('rsd')
                            if self.centreon_version < 2.8:
                                cgi_data = {'p': '20206',
                                            'o': 'meta',
                                            'cmd': '70',
                                            'select[' + host + ';' + rsd + ']': '1',
                                            'limit': '0'}
                            elif self.centreon_version in [2.8, 18.10]:
                                cgi_data['service_description'] = rsd

                    # POST, for some strange reason only working if giveback is 'raw'
                    raw = self.fetch_url(self.urls_centreon['main'], cgi_data=cgi_data, giveback='raw')
                    del raw
        except:
            self.error(sys.exc_info())


    def _set_recheck(self, host, service):
        '''
        host and service ids are needed to tell Centreon what whe want
        '''
        try:
        # decision about host or service - they have different URLs
            #  Meta
            if host == '_Module_Meta':
                if conf.debug_mode:
                    self.debug(server=self.get_name(), debug='Recheck on a Meta service, more work to be done')
                m =  re.search(r'^.+ \((?P<rsd>.+)\)$', service)
                if m:
                    rsd = m.group('rsd')
                    if self.centreon_version < 2.8:
                        url = self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p': '20206','o': 'meta','cmd': '3','select[' + host + ';' + rsd + ']': '1','limit':'0'})
                    else:
                        url = self.urls_centreon['main'] + '?' + urllib.parse.urlencode({'p': '202','o': 'svc','cmd': '3','select[' + host + ';' + rsd + ']': '1','limit':'1','centreon_token':self.centreon_token})

            elif service == '':
                # ... it can only be a host, so check all his services and there is a command for that
                host_id = self._get_host_id(host)

                if self.centreon_version < 2.7:
                    url = self.urls_centreon['xml_hostSendCommand'] + '?' + urllib.parse.urlencode({'cmd':'host_schedule_check', 'actiontype':1,'host_id':host_id,'sid':self.SID})
                else:
                    url = self.urls_centreon['xml_hostSendCommand'] + '?' + urllib.parse.urlencode({'cmd':'host_schedule_check', 'actiontype':1,'host_id':host_id})
                del host_id

            else:
                # service @ host
                host_id, service_id = self._get_host_and_service_id(host, service)

                # Starting from 19.04 this must be in POST
                if self.centreon_version < 19.04:
                    # fill and encode URL data
                    cgi_data = urllib.parse.urlencode({'cmd':'service_schedule_check', 'actiontype':1,\
                                                 'host_id':host_id, 'service_id':service_id, 'sid':self.SID})

                    url = self.urls_centreon['xml_serviceSendCommand'] + '?' + cgi_data
                    del host_id, service_id
                else:
                    cgi_data = {'cmd': 'service_schedule_check',
                                'host_id': host_id,
                                'service_id': service_id,
                                'actiontype': '0'}
                    del host_id, service_id

            if self.centreon_version < 19.04:
                # execute GET request
                raw = self.fetch_url(url, giveback='raw')
                del raw
            else:
                # running remote cgi command with POST method, for some strange reason only working if
                # giveback is 'raw'
                raw = self.fetch_url(self.urls_centreon['xml_serviceSendCommand'], cgi_data=cgi_data, giveback='raw')
                del raw
        except:
            self.error(sys.exc_info())


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        '''
        gets actual host and service ids and apply them to downtime cgi
        '''
        try:
            # duration unit is minute
            duration = (hours * 60) + minutes
            # need cmdPopup.php needs boolean
            if fixed == 1:
                fixed = 'true'
            else:
                fixed = 'false'

            # Host downtime
            if service == '':
                if self.centreon_version < 19.04:
                    cgi_data = {'cmd':75,\
                                'duration':duration,\
                                'duration_scale':'m',\
                                'start':start_time,\
                                'end':end_time,\
                                'comment':comment,\
                                'fixed':fixed,\
                                'downtimehostservice':'true',\
                                'author':author,\
                                'sid':self.SID,\
                                'select['+host+']':1
                                }
                # Params has changed starting from 19.04
                else:
                    cgi_data = {'cmd':75,
                                'duration':duration,
                                'duration_scale':'m',
                                'comment':comment,
                                'start':start_time,
                                'end':end_time,
                                'host_or_centreon_time':0,
                                'fixed':fixed,
                                'downtimehostservice':'true',
                                'author':author,
                                'resources':'["'+host+'"]'
                                }

            # Service downtime
            else:
                # Centreon 2.8 only, in case of a meta-service, extract the 'rsd' field from the service name :
                if host == '_Module_Meta' and self.centreon_version in [2.8, 18.10]:
                    m =  re.search(r'^.+ \((?P<rsd>.+)\)$', service)
                    if m:
                        rsd = m.group('rsd')
                        service = rsd
                if self.centreon_version < 19.04:
                    cgi_data = {'cmd':74,\
                                'duration':duration,\
                                'duration_scale':'m',\
                                'start':start_time,\
                                'end':end_time,\
                                'comment':comment,\
                                'fixed':fixed,\
                                'downtimehostservice':0,\
                                'author':author,\
                                'sid':self.SID,\
                                'select['+host+';'+service+']':1
                                }

                # Params has changed starting from 19.04
                else:
                    cgi_data = {'cmd':74,
                                'duration':duration,
                                'duration_scale':'m',
                                'comment':comment,
                                'start':start_time,
                                'end':end_time,
                                'host_or_centreon_time':0,
                                'fixed':fixed,
                                'downtimehostservice':0,
                                'author':author,
                                'resources':'["'+host+'%3B'+service+'"]'
                                }

            if self.centreon_version < 19.04:
                # This request must be done in a GET, so just encode the parameters and fetch
                raw = self.fetch_url(self.urls_centreon['external_cmd_cmdPopup'] + '?' + urllib.parse.urlencode(cgi_data), giveback="raw")
                del raw
            # Starting from 19.04, must be POST
            else:
                # Do it in POST
                raw = self.fetch_url(self.urls_centreon['external_cmd_cmdPopup'], cgi_data=cgi_data, giveback='raw')
                del raw

        except:
            self.error(sys.exc_info())


    def _check_session(self):
        if conf.debug_mode:
            self.debug(server=self.get_name(), debug='Checking session status')
        if 'url_centreon' not in self.__dict__:
            self.init_config()
        if self.centreon_version:
            try:
                if self.centreon_version >= 18.10:
                    result = self.fetch_url(self.urls_centreon['keepAlive'], giveback='raw')
                    self.raw, self.error, self.status_code = result.result, result.error, result.status_code
                    # Return 200 & null a session is open
                    if conf.debug_mode:
                        self.debug(server=self.get_name(), debug='Session status : ' + self.raw + ', http code : ' + str(self.status_code))
                    # 401 if no valid session is present
                    if self.status_code == 401:
                        self.SID = self._get_sid().result
                        if conf.debug_mode:
                            self.debug(server=self.get_name(), debug='Session renewed')

                else:
                    result = self.fetch_url(self.urls_centreon['autologoutXMLresponse'], giveback='xml')
                    xmlobj, error, status_code = result.result, result.error, result.status_code
                    self.session_state = xmlobj.find("state").text.lower()
                    if conf.debug_mode:
                        self.debug(server=self.get_name(), debug='Session status : ' + self.session_state)
                    if self.session_state == "nok":
                        self.SID = self._get_sid().result
                        if conf.debug_mode:
                            self.debug(server=self.get_name(), debug='Session renewed')
            except:
                import traceback
                traceback.print_exc(file=sys.stdout)
                result, error = self.error(sys.exc_info())
                return Result(result=result, error=error)
        else:
            return Result(result='ERROR',
                          error='Cannot detect Centreon version')