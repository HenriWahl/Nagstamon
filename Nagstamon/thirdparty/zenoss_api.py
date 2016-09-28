#!/usr/bin/python
# port from the zenstamon zenoss_api.py code into nagstamon:
# Zenoss-4.x JSON API Example (python)

# Copyright (C) 2016 Jake Murphy <jake.murphy@faredge.com.au> Far Edge Technology
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

# NOTES:
# Currently experimental version, only viewing and acknowledging works at present.

import os

import base64
import zlib

import hashlib
import logging
import string
import sys
import urllib

    
import re
from collections import deque


try:
    # Separate module or Python <2.6
    import simplejson as json
except ImportError:
    # Python >=2.6
    import json


ZENOSS_INSTANCE = ''
ZENOSS_USERNAME = ''
ZENOSS_PASSWORD = ''

ROUTERS = {'MessagingRouter': 'messaging',
           'EventsRouter': 'evconsole',
           'ProcessRouter': 'process',
           'ServiceRouter': 'service',
           'DeviceRouter': 'device',
           'NetworkRouter': 'network',
           'TemplateRouter': 'template',
           'DetailNavRouter': 'detailnav',
           'ReportRouter': 'report',
           'MibRouter': 'mib',
           'ZenPackRouter': 'zenpack'}

class ZenossAPI(object):

    def __init__(self, debug=False, Server=None):
        """
        Initialise the API connection, log in, and store authentication cookie
        """

        self.set_config_data(Server)
        self.urlOpener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        if debug: self.urlOpener.add_handler(urllib.request.HTTPHandler(debuglevel=1))
        self.reqCount = 1

        self._login() #login to the zenoss system

    def _login(self):
        # Construct POST parameters and submit login.
        loginParams = urllib.parse.urlencode(dict(
            __ac_name=self.ZENOSS_USERNAME,
            __ac_password=self.ZENOSS_PASSWORD,
            submitted='true',
            came_from=self.ZENOSS_INSTANCE + '/zport/dmd')).encode('ascii')
        self.urlOpener.open(self.ZENOSS_INSTANCE + '/zport/acl_users/cookieAuthHelper/login', loginParams)


    def set_config_data(self, Server):
        if True:
            self.ZENOSS_INSTANCE = 'http://' + Server.server_url + ':' + Server.server_port
            self.ZENOSS_USERNAME = Server.username
            self.ZENOSS_PASSWORD = Server.password
            
        else:
            pass

    def _router_request(self, router, method, data=[]):
        if router not in ROUTERS:
            raise Exception('Router "' + router + '" not available.')

        # Contruct a standard URL request for API calls
        req = urllib.request.Request(self.ZENOSS_INSTANCE + '/zport/dmd/' + ROUTERS[router] + '_router')

        # NOTE: Content-type MUST be set to 'application/json' for these requests
        req.add_header('Content-type', 'application/json; charset=utf-8')

        # Convert the request parameters into JSON
        reqData = json.dumps([dict(
            tid=self.reqCount,
            type='rpc',
            data=data,
            method=method,
            action=router)]).encode('ascii')

        # Increment the request count ('tid'). More important if sending multiple
        # calls in a single request
        self.reqCount += 1

        # Submit the request and convert the returned JSON to objects
        try:
            response = self.urlOpener.open(req, reqData)
        except:
            self._login()
            return {'result': {'events': []}} #return an empty object
        
        if response.code != 200:
            raise ZenossAPIException("HTTP ERROR %s: %s" % (response.status, response.reason))

        try:
            jsondata = response.read()
        except:
            raise ZenossAPIException("Couldn't read response data")
        
        if len(jsondata) == 0:
            raise ZenossAPIException("Received zero json data")

        try:
            jsonobj = json.loads(jsondata.decode('utf-8'))
        except ValueError as msg: 
            self._login()
            return {'result': {'events': []}} #return an 'empty' json object on failure
        
        return jsonobj

    '''
    The API
    '''
    def get_event(self, device=None, component=None, eventClass=None):
        data = dict(start=0, limit=500, dir='ASC', sort='severity')
        data['uid'] = '/zport/dmd'
        data['sort'] = 'device'
        data['keys'] = ['eventState', 'severity', 'device', 'component', 'eventClass', 'message', 'firstTime',
                        'lastTime', 'count', 'DevicePriority', 'evid', 'eventClassKey']
        data['params'] = dict(severity=[5, 4, 3], eventState=[0, 1], tags=[])

        if device: data['params']['device'] = device
        if component: data['params']['component'] = component
        if eventClass: data['params']['eventClass'] = eventClass

        return self._router_request('EventsRouter', 'query', [data])['result']

    def set_event_ack(self, evids):
        data = dict(limit=100)
        data['evids'] = [evids]
        return self._router_request('EventsRouter', 'acknowledge', [data])['result']

    def remove_event_ack(self, evids):
        data = dict(limit=100)
        data['evids'] = [evids]
        return self._router_request('EventsRouter', 'reopen', [data])['result']

    def remove_event(self, evids):
        data = dict(limit=100)
        data['evids'] = [evids]
        return self._router_request('EventsRouter', 'close', [data])['result']

class ZenossAPIException(Exception):
    """ generic zenoss api exception """
    pass