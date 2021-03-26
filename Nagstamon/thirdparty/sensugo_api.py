import json
import logging
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

class SensuGoAPIException(Exception):
    pass

class SensuGoAPI(object):
    _base_api_url = ''
    _refresh_token = ''
    _session = None

    GOOD_RESPONSE_CODES = (200, 201, 202, 204)

    SEVERITY_CHECK_STATUS = {
        0: 'OK',
        1: 'WARNING',
        2: 'CRITICAL',
        3: 'UNKNOWN'
    }

    def __init__(self, base_api_url):
        self._base_api_url = base_api_url
        self._session = requests.Session()

    def auth(self, username, password, verify):
        response = self._session.get(
            f'{self._base_api_url}/auth',
            verify=verify,
            auth=HTTPBasicAuth(username, password))

        self._update_local_tokens(response)

    def _refresh_access_token(self):
        response = self._session.post(
            f'{self._base_api_url}/auth/token',
            json={'refresh_token': self._refresh_token})

        self._update_local_tokens(response)

    def _update_local_tokens(self, response):
        if response.status_code in SensuGoAPI.GOOD_RESPONSE_CODES:
            access_token = response.json()['access_token']
            self._session.headers.update({
                'Authorization': f'Bearer {access_token}'})

            self._refresh_token = response.json()['refresh_token']
        else:
            logger.error(f'Response code: {response.status_code} {response.text}')
            raise SensuGoAPIException('API returned bad request')

    def get_all_events(self):
        self._refresh_access_token()
        response = self._session.get(f'{self._base_api_url}/api/core/v2/events')
        return (response.status_code, response.json())

    def has_acquired_token(self):
        return self._refresh_token != ''

    @staticmethod
    def parse_check_status(status_code):
        status = SensuGoAPI.SEVERITY_CHECK_STATUS[3]
        if status_code in SensuGoAPI.SEVERITY_CHECK_STATUS:
            status = SensuGoAPI.SEVERITY_CHECK_STATUS[status_code]
        return status

    def create_or_update_silence(self, kwargs):
        namespace = kwargs['metadata']['namespace']
        check = kwargs['metadata']['name']
        silence_api = f'/api/core/v2/namespaces/{namespace}/silenced/{check}'
        self._session.put(self._base_api_url + silence_api, json=kwargs)

