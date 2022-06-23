from Nagstamon.Servers.Generic import GenericServer
import requests
import sys
import datetime as dt
from Nagstamon.Objects import (GenericHost,
                               GenericService,
                               Result)

def _calc_duration(agtlastcheck,agtlastok):
        agtfaultS = (agtlastcheck - agtlastok).total_seconds()
        # If the SMHUB agent has not received the data (agent offline)
        if agtfaultS == 0:
            agtlastok = dt.datetime.now()
            agtfaultS = (agtlastcheck - agtlastok).total_seconds()
        agtfaultM, agtfaultS = divmod(agtfaultS, 60)
        agtfaultH, agtfaultM = divmod(agtfaultM, 60)
        agtfaultD, agtfaultH = divmod(agtfaultH, 24)
        agtfaultW, agtfaultD = divmod(agtfaultH, 7)
        agtduration = str(round(agtfaultW)) + "w " + str(round(agtfaultD)) + "d " + str(round(agtfaultH)) + "h " + str(round(agtfaultM)) + "m " + str(round(agtfaultS)) + "s"
        return agtduration
class SMHubServer(GenericServer):
    """
        SMHUB (SAP Monitor Hub)
	Powerful modular and secure monitoring tool ideal for systems that deliver 
	SAP applications: local and/or remote agents monitor the system, using owned 
	schedulers, communicating anomalies via non permanent connections and/or remote
	 monitoring. All communications to SMHUB are via HTTP/HTTPS protocol, allowing 
	a controlled traffic management from small to large companies. No sensitive data 
	is sent/stored. No usenrame/pssword required.
    """

    TYPE = u'SMHUB'
    SERVICE_SEVERITY_CODE_TEXT_MAP = dict()
    MENU_ACTIONS = []
    BROWSER_URLS = {'monitor': '$MONITOR$',
                        'hosts': '$MONITOR$', \
                    'services': '$MONITOR$', \
                    'history': '$MONITOR$'}


    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)
        self.username = 'nouser'
        self.password = 'nouser'
        self.STATES_MAPPING = {
            'operating': 'OK',
            'warning': 'WARNING',
            'critical': 'CRITICAL',
            'unknow': 'UNKNOWN'
        }


    def _get_status(self):
        '''Get status from SMHub SERVER'''
        # new_hosts dictionary
        self.new_hosts = dict()
        try:
            result = requests.get(url=self.monitor_url)
            if(result.status_code==200):
                json_res = result.json()
                agents = {k:v for (k,v) in json_res['agents'].items() if v['status'] not in ['disabled','operating']}
                host_name = json_res['summary']['label'].upper()
                self.new_hosts[host_name] = GenericHost()
                for agent in agents:
                    service_name = f"{agents[agent]['name'].upper()} ({agents[agent]['component'].upper()})"
                    service_status = agents[agent]["status"]
                    service_status_info = agents[agent]["notes"].upper()
                    last_check = dt.datetime.strptime(agents[agent]["lastcheck"], "%H:%M:%S %d/%m/%Y")
                    last_ok = dt.datetime.strptime(agents[agent]["lastok"], "%H:%M:%S %d/%m/%Y")
                    duration = _calc_duration(last_check,last_ok)
                    if not service_name in self.new_hosts[host_name].services:
                        self.new_hosts[host_name].services[service_name] = GenericService()
                        self.new_hosts[host_name].services[service_name].host = host_name
                        self.new_hosts[host_name].services[service_name].name = service_name
                        self.new_hosts[host_name].services[service_name].server = self.name
                        self.new_hosts[host_name].services[service_name].last_check = last_check.strftime('%Y-%m-%d %H:%M:%S')
                        self.new_hosts[host_name].services[service_name].status = self.STATES_MAPPING[service_status]
                        self.new_hosts[host_name].services[service_name].status_information = service_status_info
                        self.new_hosts[host_name].services[service_name].duration = duration
                        
            return Result()
                        


        except:
            import traceback
            traceback.print_exc(file=sys.stdout)

            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)
    

    def init_HTTP(self):
        self.session = requests.Session()
        self.session.auth = NoAuth()
        return True

class NoAuth(requests.auth.AuthBase):
    """
        Override to avoid auth headers
        Needed for LDAP login
    """

    def __call__(self, r):
        return r
