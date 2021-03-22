import sys
import traceback
from Nagstamon.Servers.Generic import GenericServer
from Nagstamon.Objects import (GenericHost, GenericService, Result)
from Nagstamon.Config import conf
from Nagstamon.thirdparty.sensugo_api import SensuGoAPI, SensuGoAPIException
from Nagstamon.Helpers import HumanReadableDurationFromTimestamp
from time import time
from datetime import datetime

NAMESPACE_SEPARATOR = ' ||| '
class SensuGoServer(GenericServer):
    TYPE = 'SensuGo'
    MENU_ACTIONS = ['Acknowledge']

    _authentication = 'basic'
    _api_url = ''
    _sensugo_api = None

    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)
        self._api_url = conf.servers[self.get_name()].monitor_cgi_url
        self.reset_HTTP()

    def init_HTTP(self):
        GenericServer.init_HTTP(self)
        self._setup_sensugo_api()

    def reset_HTTP(self):
        self._sensugo_api = SensuGoAPI(self._api_url)

    def _setup_sensugo_api(self):
        if not self._sensugo_api.has_acquired_token():
            if self.custom_cert_use:
                verify = self.custom_cert_ca_file
            else:
                verify = not self.ignore_cert

            try:
                self._sensugo_api.auth(self.username, self.password, verify)
            except Exception:
                self.Error(sys.exc_info())

    def _get_status(self):
        try:
            response_code, events = self._sensugo_api.get_all_events()
            self._create_services(events)
        except Exception:
            result, error = self.Error(sys.exc_info())
            print(traceback.format_exc())
            return Result(result=result, error=error)
        return Result()

    def _create_services(self, events):
        for event in events:
            service = self._parse_event_to_service(event)
            self._insert_service_to_hosts(service)

    def _parse_event_to_service(self, event):
        service = GenericService()
        namespace_host = event['entity']['metadata']['namespace'] + NAMESPACE_SEPARATOR + event['entity']['metadata']['name']
        service.hostid = namespace_host
        service.host = namespace_host
        service.name = event['check']['metadata']['name']
        service.status = SensuGoAPI.parse_check_status(event['check']['status'])
        service.last_check = datetime.fromtimestamp(int(event['timestamp'])).strftime('%Y-%m-%d %H:%M:%S')
        service.duration = self._duration_since(event['check']['last_ok'])
        service.status_information = event['check']['output']
        service.acknowledged = event['check']['is_silenced']
        service.notifications_disabled = event['check']['is_silenced']
        service.attempt = str(event['check']['occurrences']) + '/1'
        service.passiveonly = event['check']['publish']
        service.flapping = False
        service.scheduled_downtime = False
        return service

    def _insert_service_to_hosts(self, service: GenericService):
        service_host = service.get_host_name()
        if service_host not in self.new_hosts:
            self.new_hosts[service_host] = GenericHost()
            self.new_hosts[service_host].name = service_host
            self.new_hosts[service_host].site = service.site

        self.new_hosts[service_host].services[service.name] = service

    def _duration_since(self, timestamp):
        if (timestamp == 0) or (timestamp > time()):
            duration_text = 'n/a'
        else:
            duration_text = HumanReadableDurationFromTimestamp(timestamp)
        return duration_text

    def set_acknowledge(self, info_dict):
        namespace = self._extract_namespace(info_dict['host'])

        silenece_args = {
            'metadata': {
                'name': info_dict['service'],
                'namespace': namespace
            },
            'expire': -1,
            'expire_on_resolve': True,
            'creator': info_dict['author'],
            'reason': info_dict['comment'],
            'check': info_dict['service']
        }
        self._sensugo_api.create_or_update_silence(silenece_args)

    def _extract_namespace(self, host_column: str):
        return host_column.split(NAMESPACE_SEPARATOR)[0]

