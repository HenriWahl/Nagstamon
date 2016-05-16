#!/usr/bin/python
# adapted from the zabbix.py code

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

import sys
import urllib
import base64
import time
import copy
import datetime
import traceback
from datetime import datetime

from Nagstamon.Config import conf
from Nagstamon.Objects import (GenericHost, GenericService, Result)
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.thirdparty.zenoss_api import ZenossAPI

class ZenossServer(GenericServer):
    
    TYPE = 'Zenoss'
    zapi = None

    SEVERITY_MAP = {0: 'OK',
                1: 'UNKNOWN',
                2: 'UNKNOWN',
                3: 'WARNING',
                4: 'CRITICAL',
                5: 'CRITICAL'}

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # Prepare all urls needed by nagstamon 
        self.urls = {}
        self.statemap = {}

        self.MENU_ACTIONS = ["Recheck", "Acknowledge", "Downtime"]

        self.server = Server()
        self.server.server_url, self.server.server_port = conf.servers[self.get_name()].monitor_url.split(':')
        self.server.username = conf.servers[self.get_name()].username
        self.server.password = conf.servers[self.get_name()].password
        
        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Recheck", "Acknowledge", "Downtime"]
    
    def _zlogin(self):
        self.zapi = ZenossAPI(Server=self.server)
    
    def _get_status(self):
        nagitems = {"services":[], "hosts":[]}

        self.new_hosts = dict()

        try:
            hosts = self._get_all_events()['events']
            for host in hosts:
                n = dict()
                n['host'] = host['device']['text']
                n['service'] = host['eventClass']['text']

                n['status'] = self.SEVERITY_MAP.get(host['severity'])
                n['last_check'] = host['lastTime']
                
                n['duration'] = self._calc_duration(host['firstTime'], host['lastTime'])
                
                n["status_information"] = host['message']
                n["attempt"] = str(host['count'])+"/1"# TODO:

                n["passiveonly"] = False
                n["notifications_disabled"] = False
                n["flapping"] = False
                n["acknowledged"] = False
                n["scheduled_downtime"] = False
              
                nagitems["hosts"].append(n)

                new_host = n["host"]
                if not new_host in self.new_hosts:
                    self.new_hosts[new_host] = GenericHost()
                    self.new_hosts[new_host].name = new_host
                    
                    
                if not new_host in self.new_hosts[new_host].services:
                        
                    new_service = new_host
                    self.new_hosts[new_host].services[new_service] = GenericService()
                    self.new_hosts[new_host].services[new_service].host = new_host
                    self.new_hosts[new_host].services[new_service].name = n["service"]
                    
                    self.new_hosts[new_host].services[new_service].server = self.name
                    self.new_hosts[new_host].services[new_service].status = n["status"]
                    self.new_hosts[new_host].services[new_service].last_check = n["last_check"]
                    
                    self.new_hosts[new_host].services[new_service].duration = n["duration"]
                    self.new_hosts[new_host].services[new_service].status_information= n["status_information"].encode("utf-8")
                    self.new_hosts[new_host].services[new_service].attempt = n["attempt"]

                    self.new_hosts[new_host].services[new_service].passiveonly = n["passiveonly"]
                    self.new_hosts[new_host].services[new_service].notifications_disabled = n["notifications_disabled"]
                    self.new_hosts[new_host].services[new_service].flapping = n["flapping"]
                    self.new_hosts[new_host].services[new_service].acknowledged = n["acknowledged"]
                    self.new_hosts[new_host].services[new_service].scheduled_downtime = n["scheduled_downtime"]
                del n
                
        except:
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            print(traceback.format_exc())
            return Result(result=result, error=error)

        
        del nagitems
        return Result(error="")

    
    def _get_all_events(self):
        if self.zapi is None:
            self._zlogin()

        events = self.zapi.get_event()
        return events

    ##http://stackoverflow.com/questions/538666/python-format-timedelta-to-string
    def _calc_duration(self, startStr, endStr): # like: '2016-10-2213: 53: 43' (that day/hour gap..)
        start = datetime.strptime(startStr, '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(endStr, '%Y-%m-%d %H:%M:%S')
        
        sec = (int)((end - start).total_seconds())
        days, rem = divmod(sec, 60*60*24)
        hours, rem = divmod(rem, 60*60)
        mins, sec = divmod(rem, 60)
        return '%sd %sh %sm %ss' % (days,hours,mins,sec)
        

class Server(object):
    #server object for configuration reasons

    def __init__(self):
        self.server_url = ""
        self.server_port = ""
        self.username = ""
        self.password = ""