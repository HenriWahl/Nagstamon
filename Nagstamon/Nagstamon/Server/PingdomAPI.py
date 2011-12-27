# The MIT License
#
# Copyright (c) 2010 Daniel R. Craig
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from urlparse import urljoin
from urllib import urlencode
import urllib2
import json
import time

API_URL = 'https://api.pingdom.com/api/2.0/'

class Pingdom(object):
    def __init__(self, url=API_URL, username=None, password=None, appkey=None):
        self.url = url
        self.appkey= appkey
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, url, username, password)
        auth_handler = urllib2.HTTPBasicAuthHandler(password_manager)
        self.opener = urllib2.build_opener(auth_handler)
        
    class RequestWithMethod(urllib2.Request):
        def __init__(self, url, data=None, headers={},
                     origin_req_host=None, unverifiable=False, http_method=None):
           urllib2.Request.__init__(self, url, data, headers, origin_req_host, unverifiable)
           if http_method:
               self.method = http_method

        def get_method(self):
            if self.method:
                return self.method
            return urllib2.Request.get_method(self)
    
    def method(self, url, method="GET", parameters=None):
        if parameters:
            data = urlencode(parameters)
        else:
            data = None
        method_url = urljoin(self.url, url)
        if method == "GET" and data:
            method_url = method_url+'?'+data
            req = self.RequestWithMethod(method_url, http_method=method, data=None)
        else:
            req = self.RequestWithMethod(method_url, http_method=method, data=data)
        req.add_header('App-Key', self.appkey)
        response = self.opener.open(req).read()
        return json.loads(response)
        
    def check_by_name(self, name):
        resp = self.method('checks')
        checks = [check for check in resp['checks'] if check['name'] == name]
        return checks
        
    def check_status(self, name):
        checks = self.check_by_name(name)
        for check in checks:
            print '%s check %s' % (check['name'], check['status'])

    def modify_check(self, name, parameters={}):
        checks = self.check_by_name(name)
        if not checks:
            print "No checks for %s" % name
            return
        for check in checks:
            id_ = check['id']
            response = self.method('checks/%s/' % id_, method='PUT', parameters=parameters)
            print response['message']
            
    def pause_check(self, name):
        self.modify_check(name, parameters={'paused': True})
        self.check_status(name)
        
    def unpause_check(self, name):
        self.modify_check(name, parameters={'paused': False})
        self.check_status(name)
        
    def avg_response(self, check_id, minutes_back=None, country=None):
        parameters = {}
        if minutes_back:
            from_time = "%.0f" % (time.time() - 60*minutes_back)
            parameters['from'] = from_time
        if country:
            parameters['bycountry'] = 'true'

        summary = self.method('summary.average/%s/' % check_id, parameters=parameters)['summary']
        avgresponse = summary['responsetime']['avgresponse']

        if country:
            response_time = None
            for c in avgresponse:
                countryiso = c['countryiso']
                countryresponse = c['avgresponse']
                if countryiso == country:
                    response_time = countryresponse
        else:
           response_time = avgresponse
        return response_time
