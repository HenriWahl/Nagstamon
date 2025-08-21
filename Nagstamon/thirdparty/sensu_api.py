# This is part of Sangoma's pysensu library found here: https://github.com/sangoma/pysensu
# and licensed under the MIT License
#
# The MIT License (MIT)

# Copyright (c) 2015 Sangoma Technologies

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import json
import logging

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class SensuAPIException(Exception):
    pass


class SensuAPI:
    def __init__(self, url_base, username=None, password=None, verify=None):
        self._url_base = url_base
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'PySensu Client v0.9.0'
        })
        self._session.verify = verify
        self.good_status = (200, 201, 202, 204)

        if username and password:
            self._session.auth = HTTPBasicAuth(username, password)
        elif password and not username:
            self._session.headers.update({
                'Authorization': 'token {}'.format(password)
            })

    def _request(self, method, path, **kwargs):
        url = '{}{}'.format(self._url_base, path)
        logger.debug('{} -> {} with {}'.format(method, url, kwargs))

        if method == 'GET':
            resp = self._session.get(url, **kwargs)

        elif method == 'POST':
            resp = self._session.post(url, **kwargs)

        elif method == 'PUT':
            resp = self._session.put(url, **kwargs)

        elif method == 'DELETE':
            resp = self._session.delete(url, **kwargs)
        else:
            raise SensuAPIException(
                'Method {} not implemented'.format(method)
            )

        if resp.status_code in self.good_status:
            logger.debug('{}: {}'.format(
                resp.status_code,
                ''.join(resp.text.split('\n'))[0:80]
            ))
            return resp

        elif resp.status_code == 400:
            logger.error('{}: {}'.format(
                resp.status_code,
                resp.text
            ))
            raise SensuAPIException('API returned "Bad Request"')

        else:
            logger.warning('{}: {}'.format(
                resp.status_code,
                resp.text
            ))
            raise SensuAPIException('API bad response {}: {}'.format(resp.status_code, resp.text))

    """
    Clients ops
    """
    def get_clients(self, limit=None, offset=None):
        """
        Returns a list of clients.
        """
        data = {}
        if limit:
            data['limit'] = limit
        if offset:
            data['offset'] = offset
        result = self._request('GET', '/clients', data=json.dumps(data))
        return result.json()

    def get_client_data(self, client):
        """
        Returns a client.
        """
        data = self._request('GET', '/clients/{}'.format(client))
        return data.json()

    def get_client_history(self, client):
        """
        Returns the history for a client.
        """
        data = self._request('GET', '/clients/{}/history'.format(client))
        return data.json()

    def delete_client(self, client):
        """
        Removes a client, resolving its current events. (delayed action)
        """
        self._request('DELETE', '/clients/{}'.format(client))
        return True

    """
    Events ops
    """
    def get_events(self):
        """
        Returns the list of current events.
        """
        data = self._request('GET', '/events')
        return data.json()

    def get_all_client_events(self, client):
        """
        Returns the list of current events for a given client.
        """
        data = self._request('GET', '/events/{}'.format(client))
        return data.json()

    def get_event(self, client, check):
        """
        Returns an event for a given client & check name.
        """
        data = self._request('GET', '/events/{}/{}'.format(client, check))
        return data.json()

    def delete_event(self, client, check):
        """
        Resolves an event for a given check on a given client. (delayed action)
        """
        self._request('DELETE', '/events/{}/{}'.format(client, check))
        return True

    def post_event(self, client, check):
        """
        Resolves an event. (delayed action)
        """
        self._request('POST', '/resolve', json={'client': client, 'check': check})
        return True

    """
    Checks ops
    """
    def get_checks(self):
        """
        Returns the list of checks.
        """
        data = self._request('GET', '/checks')
        return data.json()

    def get_check(self, check):
        """
        Returns a check.
        """
        data = self._request('GET', '/checks/{}'.format(check))
        return data.json()

    def post_check_request(self, check, subscribers, dc=None):
        """
        Issues a check execution request.
        """
        data = {
            'check': check,
            'subscribers': [subscribers]
        }
        if dc is not None:
            data['dc'] = dc
        self._request('POST', '/request', json=data)
        return True

    """
    Silenced API ops
    """
    def get_silenced(self, limit=None, offset=None):
        """
        Returns a list of silence entries.
        """
        data = {}
        if limit:
            data['limit'] = limit
        if offset:
            data['offset'] = offset
        result = self._request('GET', '/silenced', json=data)
        return result.json()

    def post_silence_request(self, kwargs):
        """
        Create a silence entry.
        """
        self._request('POST', '/silenced', json=kwargs)
        return True

    def clear_silence(self, kwargs):
        """
        Clear a silence entry.
        """
        self._request('POST', '/silenced/clear', json=kwargs)
        return True

    """
    Aggregates ops
    """
    def get_aggregates(self):
        """
        Returns the list of named aggregates.
        """
        data = self._request('GET', '/aggregates')
        return data.json()

    def get_aggregate_check(self, check, age=None):
        """
        Returns the list of aggregates for a given check
        """
        data = {}
        if age:
            data['max_age'] = age

        result = self._request('GET', '/aggregates/{}'.format(check), json=data)
        return result.json()

    def delete_aggregate(self, check):
        """
        Deletes all aggregate data for a named aggregate
        """
        self._request('DELETE', '/aggregates/{}'.format(check))
        return True

    """
    Status ops
    """
    def get_info(self):
        """
        Returns information on the API.
        """
        data = self._request('GET', '/info')
        return data.json()

    def get_health(self, consumers=2, messages=100):
        """
        Returns health information on transport & Redis connections.
        """
        data = {'consumers': consumers, 'messages': messages}

        try:
            self._request('GET', '/health', json=data)
            return True
        except SensuAPIException:
            return False

    """
    Results ops
    """
    def get_all_client_results(self):
        """
        Returns the list of results.
        """
        data = self._request('GET', '/results')
        return data.json()

    def get_results(self, client):
        """
        Returns a result.
        """
        data = self._request('GET', '/results/{}'.format(client))
        return data.json()

    def get_result(self, client, check):
        """
        Returns an event for a given client & result name.
        """
        data = self._request('GET', '/results/{}/{}'.format(client, check))
        return data.json()

    def delete_result(self, client, check):
        """
        Deletes an check result data for a given check on a given client.
        """
        self._request('DELETE', '/results/{}/{}'.format(client, check))
        return True

    def post_result_data(self, client, check, output, status):
        """
        Posts check result data.
        """
        data = {
            'source': client,
            'name': check,
            'output': output,
            'status': status,
        }
        self._request('POST', '/results', json=data)
        return True

    """
    Stashes ops
    """
    def get_stashes(self):
        """
        Returns a list of stashes.
        """
        data = self._request('GET', '/stashes')
        return data.json()

    def create_stash(self, payload, path=None):
        """
        Create a stash. (JSON document)
        """
        if path:
            self._request('POST', '/stashes/{}'.format(path),
                          json=payload)
        else:
            self._request('POST', '/stashes', json=payload)
        return True

    def delete_stash(self, path):
        """
        Delete a stash. (JSON document)
        """
        self._request('DELETE', '/stashes/{}'.format(path))
        return True

    """
    Subscriptions ops (not directly in the Sensu API)
    """
    def get_subscriptions(self, nodes=[]):
        """
        Returns all the channels where (optionally specified) nodes are subscribed
        """
        if len(nodes) > 0:
            data = [node for node in self.get_clients() if node['name'] in nodes]
        else:
            data = self.get_clients()
        channels = []
        for client in data:
            if 'subscriptions' in client:
                if isinstance(client['subscriptions'], list):
                    for channel in client['subscriptions']:
                        if channel not in channels:
                            channels.append(channel)
                else:
                    if client['subscriptions'] not in channels:
                        channels.append(client['subscriptions'])
        return channels

    def get_subscriptions_channel(self, search_channel):
        """
        Return all the nodes that are subscribed to the specified channel
        """
        data = self.get_clients()
        clients = []
        for client in data:
            if 'subscriptions' in client:
                if isinstance(client['subscriptions'], list):
                    if search_channel in client['subscriptions']:
                        clients.append(client['name'])
                else:
                    if search_channel == client['subscriptions']:
                        clients.append(client['name'])
        return clients
