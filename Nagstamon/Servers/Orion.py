# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2014 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

# Important: 
# ==================
# * Install the Orion python SDK - https://github.com/solarwinds/orionsdk-python
# * Install demjson (json.loads didn't work well here)

import arrow
import logging
import sys
import urllib3
import orionsdk
from demjson import decode
import re

from Nagstamon.Helpers import (webbrowser_open)

from Nagstamon.Config import conf
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Objects import (GenericHost, GenericService, Result)

log = logging.getLogger('Orion.py')
urllib3.disable_warnings()


class OrionServer(GenericServer):
    """
        object of Solarwinds Orion API
    """
    TYPE = 'Orion'

    #
    MENU_ACTIONS = ['Monitor', 'Acknowledge']    
    
    # services: Should be reworked. I think not all installations have APM licensed
    BROWSER_URLS = {'monitor': '$MONITOR$',
                    'hosts': '$MONITOR$',
                    'services': '$MONITOR$/Orion/Apm/Summary.aspx',
                    'history': '$MONITOR$/orion/netperfmon/events.aspx'}
           

    # Helpers
    SERVICE_SEVERITY_CODE_TEXT_MAP = dict()
    HOST_SEVERITY_CODE_TEXT_MAP = dict()

    def __init__(self, **kwds):
        """
        Prepare all urls needed by nagstamon and Orion
        """
        GenericServer.__init__(self, **kwds)

        self.url = conf.servers[self.get_name()].monitor_cgi_url
        self.username = conf.servers[self.get_name()].username
        self.password = conf.servers[self.get_name()].password
        self.swisConnection = None

        self.SERVICE_SEVERITY_CODE_TEXT_MAP = {
            0: 'INFORMATIONAL',
            1: 'WARNING',
            2: 'CRITICAL',
            3: 'UNKNOWN'
        }
        self.HOST_SEVERITY_CODE_TEXT_MAP = {
            0: 'UP',
            1: 'DOWN',
            2: 'UNREACHABLE',
            9: 'UNKNOWN' # in Orion: unmanaged?
        }


    def _orionlogin(self):
        """
        Initialize HTTP connection to Orion api (using the Orion python SDK - https://github.com/solarwinds/orionsdk-python )
        """
        try:                        
            self.swisConnection = orionsdk.SwisClient(self.url,self.username,self.password)        
        except Exception as e:
            log.exception(e)
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

    def _insert_service_to_hosts(self, service: GenericService):
        """
        We want to create hosts for faulty services as GenericService requires
        that logic.
        """
        service_host = service.get_host_name()
        if service_host not in self.new_hosts:
            self.new_hosts[service_host] = GenericHost()
            self.new_hosts[service_host].name = service_host
            self.new_hosts[service_host].site = service.site

        self.new_hosts[service_host].services[service.alertID] = service
        

    def _get_status(self):
        """
            Get status from Solarwinds Orion Server and translate it into Nagstamon logic
            generic array
        """
        # new_hosts dictionary
        self.new_hosts = dict()

        # Orion has a host status - BUT there is no option to acknowledge a host state because these informations are not treated as alerts
        # Because of that:
        # Skip hosts lookup. Rely on alerts (use #DOWN# tag in alert name to identify a host down alert)
        # self._get_host_status()

        if self.swisConnection is None:
            self._orionlogin()
        
        # get list of all alerts from Orion (SWIS Query)
        try:
            nodeList = self.swisConnection.query(''' 
             SELECT [AA].[AlertActiveID], [AO].[EntityCaption], [AO].[EntityDetailsUrl], [AC].[Name] AS [Alert], [AC].[Severity], [AA].[TriggeredDateTime], 
            [AA].[TriggeredMessage],  [AA].[Acknowledged], [AO].[EntityType], [AO].[Node].[NodeID], [AO].[Node].[Caption],
            [AO].[RelatedNodeId], [AO].[RelatedNodeCaption], [AC].[Name] AS [AlertName], [ON].[Status], [ORN].[Status] AS [RelatedNodeStatus]
                FROM [Orion].[AlertActive] AS [AA] 
                LEFT JOIN [Orion].[AlertObjects] AS [AO] ON [AA].[AlertObjectID] = [AO].[AlertObjectID] 
                LEFT JOIN [Orion].[AlertConfigurations] AS [AC] ON [AO].[AlertID] = [AC].[AlertID]
                LEFT JOIN [Orion].[Nodes] AS [ON] ON [AO].[Node].[NodeID] = [ON].NodeID  
                LEFT JOIN [Orion].[Nodes] AS [ORN] ON [AO].[Node].[NodeID] = [ORN].NodeID                 
                order by [ON].NodeID                
            ''')

            # do some bugfixes to the result and convert to json object
            # Escape : None and : True to : "None" and : "True"
            # Otherweise the decode operation fails            
            x=str(nodeList)
            x = x.replace(': None',': "None"')
            x = x.replace(': True',': "True"')            
            x = decode(x)            
            
            # add all alerts
            for alert in x['results']:                
                self._add_alert(alert)
                                                
        except Exception as e:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            log.exception(e)
            return Result(result=result, error=error)
        
        return Result()

    def removeLinebreaks(self, message):
        mystring = message.replace('\n', ' ').replace('\r', '')        
        #mystring = mystring[0:120]
        return mystring 

    def _add_alert(self,alert):          
        host_name = alert['Caption']

        # Not all alerts have an assiciated hostname, so try to find a meaningful replacements, if no hostname is available
        # Candidates:
        #  - EntityCaption
        #  - RelationNodeCaption

        if host_name == 'None':            
            if alert['RelatedNodeCaption'] == 'None':
                host_name = alert['EntityCaption']
            else:
                host_name = alert['RelatedNodeCaption']

        # host already known / in new_hosts array?
        if host_name in self.new_hosts:
            pass
        else:            
            self.new_hosts[host_name] = GenericHost()
            self.new_hosts[host_name].services = dict()
            self.new_hosts[host_name].name = host_name
            self.new_hosts[host_name].site = self.name
            self.new_hosts[host_name].status = 'UNKNOWN'

            try:
                self.new_hosts[host_name].status = self.HOST_SEVERITY_CODE_TEXT_MAP[0] # 0 = UP
            except KeyError:
                self.new_hosts[host_name].status = 'UNKNOWN'
            self.new_hosts[host_name].attempt = "{}/{}".format( int(1), int(1))

        if alert['Acknowledged'] == 'True':
            acknowledged = True
        else:
            acknowledged = False

        # if the messages contains the keyword "#DOWN" consider the host down
        if "#DOWN#" in alert['TriggeredMessage']:
            self.new_hosts[host_name].status = self.HOST_SEVERITY_CODE_TEXT_MAP[1] # 0 = UP, 1=DOWN
            self.new_hosts[host_name].status_information = self.removeLinebreaks(alert['TriggeredMessage'])
            self.new_hosts[host_name].acknowledged = acknowledged
            self.new_hosts[host_name].duration = arrow.get(alert['TriggeredDateTime']).humanize()
            self.new_hosts[host_name].name = '[' + "{:08d}".format(alert['AlertActiveID']) + '] ' + host_name
            self.new_hosts[host_name].server =  self.name

        else:        
            new_service = GenericService()
            new_service.host = host_name
            new_service.name = '[' + "{:08d}".format(alert['AlertActiveID']) + ']  ' + alert['AlertName']             
            new_service.alertID = str(alert['AlertActiveID'])
            try:
                new_service.status = self.SERVICE_SEVERITY_CODE_TEXT_MAP.get(alert['Severity'])                
            except KeyError:
                new_service.status = 'UNKNOWN'                
                new_service.attempt = "{}/{}".format(1,1)
            
            new_service.status_type = {0: "soft", 1: "hard"}[int(1)]
            new_service.duration = arrow.get(alert['TriggeredDateTime']).humanize()
            new_service.status_information = alert['TriggeredMessage'] # + "  [" + alert['AlertName'] + "]"
            new_service.status_information = self.removeLinebreaks(alert['TriggeredMessage'])
            new_service.acknowledged = acknowledged        

            if new_service.status == None:
                pass # no status? do not add the node!
            else:
                self._insert_service_to_hosts(new_service)        


    def open_monitor(self, host, service=''):
        '''
            open monitor from tablewidget context menu
        '''
        # only type is important so do not care of service '' in case of host monitor
        if service == '':
            self._open_node_monitor(host)
        else:
            self._open_alert_monitor(host,service)

    
    def _open_node_monitor(self, host):
        '''
            open monitor from tablewidget context menu
        '''
        if self.swisConnection is None:
            self._orionlogin()        
        
        # test for prefixed with AlertID, if regexp matches, use hostname from regex parser
        m= re.split(r'^\[(.*)\] (.*)$', host)
        
        if (len(m[2])> 0 ):
            host = m[2]

        nodeList = self.swisConnection.query('SELECT Caption, DetailsUrl FROM Orion.Nodes where Status = 2 and [Caption] =' "'" + host + "'")

        # do some bugfixes to result and convert to json object
        x=str(nodeList)
        x = x.replace(': None',': "None"')
        x = x.replace(': True',': "True"')
        hostlist = decode(x)
            
        itemUrl=''
        if 'results' in hostlist:
            if len(hostlist['results']) >0 :
                itemUrl = hostlist['results'][0]['DetailsUrl']

        if len(itemUrl) >0:
            webbrowser_open(self.monitor_url + itemUrl)
    

    def _get_alertid(self, host,service):
        # get alertID from service name
        alertID= '' 
        m= re.split(r'^\[(.*)\] .*$', service)        
        if len(m) > 1:
            alertID = m[1]
        else:
            # maybe the id is stored in the hostname? (=host down alerts, there is no service information available)
            m= re.split(r'^\[(.*)\] .*$', host)
            if len(m) > 1:
                alertID = m[1]

        return alertID
    
    def _open_alert_monitor(self, host, service=''):
        '''
            open monitor from tablewidget context menu
        '''
        if self.swisConnection is None:
            self._orionlogin()            

        alertID = self._get_alertid(host,service)        
        alertList = self.swisConnection.query(''' 
        SELECT [AA].[AlertActiveID], [AO].[EntityCaption], [AO].[EntityDetailsUrl], [AA].[TriggeredDateTime], 
        [AA].[TriggeredMessage],  [AA].[Acknowledged], [AO].[EntityType], [AO].[Node].[NodeID], [AO].[Node].[Caption],
        [AO].[RelatedNodeId], [AO].[RelatedNodeCaption]
            FROM [Orion].[AlertActive] AS [AA] 
            LEFT JOIN [Orion].[AlertObjects] AS [AO] ON [AA].[AlertObjectID] = [AO].[AlertObjectID]                  
            ''' +
            'where [AA].[AlertActiveID] = ' + alertID )

        # do some bugfixes to result and convert to json object
        x=str(alertList)
        x = x.replace(': None',': "None"')
        x = x.replace(': True',': "True"')
        activeAlertList = decode(x)
            
        itemUrl=''
        if 'results' in activeAlertList:
            if len(activeAlertList['results']) >0 :
                itemUrl = activeAlertList['results'][0]['EntityDetailsUrl']

        if len(itemUrl) >0:
            webbrowser_open(self.monitor_url + itemUrl)
            

    def _set_recheck(self, host, service):
        """
        Please check again Icinga!
        """
        pass

    def _set_acknowledge(self, host, service, author, comment, sticky,
                         notify, persistent, all_services=[]):
        '''
        Send acknowledge to monitor server
        '''

        # only type is important so do not care of service '' in case of host monitor
        if service == '':
            self._set_acknowledge_node(host, service, author, comment, sticky,
                         notify, persistent, all_services=[])
        else:
            self._set_acknowledge_alert(host, service, author, comment, sticky,
                         notify, persistent, all_services=[])


    def _set_acknowledge_node(self, host, service, author, comment, sticky,
                         notify, persistent, all_services=[]):
        '''
        Send acknowledge to monitor server
        '''

        if self.swisConnection is None:
            self._orionlogin()
        
        alertID = self._get_alertid(host,service)

        nodeList = self.swisConnection.query(''' 
            SELECT [AA].[AlertActiveID], [AO].[EntityCaption], [AO].[EntityDetailsUrl], [AA].[TriggeredDateTime], 
            [AA].[TriggeredMessage],  [AA].[Acknowledged], [AO].[EntityType], [AO].[Node].[NodeID], [AO].[Node].[Caption],
            [AO].[RelatedNodeId], [AO].[RelatedNodeCaption], [AO].[AlertObjectID]
                FROM [Orion].[AlertActive] AS [AA] 
                LEFT JOIN [Orion].[AlertObjects] AS [AO] ON [AA].[AlertObjectID] = [AO].[AlertObjectID]                  
                ''' +
                'where [AA].[AlertActiveID] = ' + alertID )

        # do some bugfixes to result and convert to json object
        x=str(nodeList)
        x = x.replace(': None',': "None"')
        x = x.replace(': True',': "True"')
        hostlist = decode(x)

        alertObjectID=0
        if 'results' in hostlist:
            if len(hostlist['results']) >0 :
                alertObjectID = hostlist['results'][0]['AlertObjectID']

        if alertObjectID >0:            
            self.swisConnection.invoke('Orion.AlertActive','Acknowledge', [alertObjectID], comment)
        pass
        
        # I think it is not possible to acknowledge a "host down state" - maybe we shoud create an alert for that instead?
    

    def _set_acknowledge_alert(self, host, service, author, comment, sticky,
                         notify, persistent, all_services=[]):
        '''
        Send acknowledge to monitor server
        '''

        if self.swisConnection is None:
            self._orionlogin()

        alertID = self._get_alertid(host,service)

        nodeList = self.swisConnection.query(''' 
            SELECT [AA].[AlertActiveID], [AO].[EntityCaption], [AO].[EntityDetailsUrl], [AA].[TriggeredDateTime], 
            [AA].[TriggeredMessage],  [AA].[Acknowledged], [AO].[EntityType], [AO].[Node].[NodeID], [AO].[Node].[Caption],
            [AO].[RelatedNodeId], [AO].[RelatedNodeCaption], [AO].[AlertObjectID]
                FROM [Orion].[AlertActive] AS [AA] 
                LEFT JOIN [Orion].[AlertObjects] AS [AO] ON [AA].[AlertObjectID] = [AO].[AlertObjectID]                  
                ''' +
                'where [AA].[AlertActiveID] = ' + alertID )

        # do some bugfixes to result and convert to json object
        x=str(nodeList)
        x = x.replace(': None',': "None"')
        x = x.replace(': True',': "True"')
        hostlist = decode(x)

        alertObjectID=0
        if 'results' in hostlist:
            if len(hostlist['results']) >0 :
                alertObjectID = hostlist['results'][0]['AlertObjectID']

        if alertObjectID >0:            
            self.swisConnection.invoke('Orion.AlertActive','Acknowledge', [alertObjectID], comment)
        pass

    # not applicable (as far as I know a check result can not be submitted manually)    
    def _set_submit_check_result(self, host, service, state, comment,
                                 check_output, performance_data):
        '''
        Submit check results
        '''
        pass

    # not implemented yet, could be used to unmanage a host/application?
    def _set_downtime(self, host, service, author, comment, fixed, start_time,
                      end_time, hours, minutes):
        """
        Submit downtime
        """
        pass

0
