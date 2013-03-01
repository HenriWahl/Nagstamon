# encoding: utf-8

import sys
import urllib2
import webbrowser
import base64
import datetime
import time
import os.path
import urllib
import cookielib

from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer, not_empty

# to let Linux distributions use their own BeautifulSoup if existent try importing local BeautifulSoup first
# see https://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3302612&group_id=236865
try:
    from BeautifulSoup import BeautifulSoup
except:
    from Nagstamon.BeautifulSoup import BeautifulSoup


class NinjaServer(GenericServer):
    """
        Ninja plugin for Nagstamon
    """
    TYPE = "Ninja"

    bitmasks = {
        1: 'acknowledged',
        2: 'notifications_disabled',
        4: 'passiveonly',
        8: 'scheduled_downtime',
        16: 'down_or_unreachable',
        32: 'flapping'
    }
    commit_path = '/index.php/command/commit'
    show_login_path =  '/index.php/default/show_login'
    login_path ='/index.php/default/do_login'
    time_path = '/index.php/extinfo/show_process_info'
    services_path = "/index.php/status/service/all?servicestatustypes=78&hoststatustypes=71&items_per_page=10000"
    hosts_path = "/index.php/status/host/?host=all&hoststatustypes=6&items_per_page=999999"

    # A Monitor CGI URL is not necessary so hide it in settings
    DISABLED_CONTROLS = ["label_monitor_cgi_url", "input_entry_monitor_cgi_url"]


    def __init__(self, **kwds):
        GenericServer.__init__(self, **kwds)

        # dictionary to translate status bitmaps on webinterface into status flags
        # this are defaults from Nagios

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Downtime"]


    def init_config(self):
        """
        dummy init_config, called at thread start, not really needed here, just omit extra properties
        """
        pass


    def get_start_end(self, host):
        #try to get ninja3 style update field first
        last_update = self.FetchURL(self.time_url).result.find("a", {"id": "page_last_updated"})
        if not last_update:
            #maybe ninja2?
            last_update = self.FetchURL(self.time_url).result.find("span", {"id": "page_last_updated"})

        if not last_update:
            #I don't even ...
            raise Exception("Failed to get page update time!")

        start_time = last_update.contents[0]
        magic_tuple = datetime.datetime.strptime(str(start_time), "%Y-%m-%d %H:%M:%S")
        start_diff = datetime.timedelta(0, 10)
        end_diff = datetime.timedelta(0, 7210)
        start_time = magic_tuple + start_diff
        end_time = magic_tuple + end_diff
        return str(start_time), str(end_time)


    def init_HTTP(self):
        # add default auth for monitor.old
        GenericServer.init_HTTP(self)

        # self.Cookie is a CookieJar which is a list of cookies - if 0 then emtpy
        if len(self.Cookie) == 0:
            try:
                # Ninja Settings
                # get a Ninja cookie via own method
                self.urlopener.add_handler(urllib2.HTTPDefaultErrorHandler())
                self.urlopener.open(self.login_url, urllib.urlencode({'username': self.get_username(), 'password': self.get_password(), 'csrf_token': self.csrf()}))

                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), debug="Cookie:" + str(self.Cookie))

            except:
                self.Error(sys.exc_info())

    def csrf(self):
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.Cookie))
        response = opener.open(self.show_login_url)
        soup = BeautifulSoup(response.read())
        return soup.find('input', {'name': 'csrf_token'})['value']

    def open_tree_view(self, host, service):
        if not service:
            webbrowser.open('%s/index.php/extinfo/details/host/%s' % (self.monitor_url, host))
        else:
            webbrowser.open('%s/index.php/extinfo/details/service/%s?service=%s' % (self.monitor_url, host, service))

    def open_services(self):
        webbrowser.open('%s/index.php/status/service/all?servicestatustypes=14' % (self.monitor_url))

    def open_hosts(self):
        webbrowser.open('%s/index.php/status/host/all/6' % (self.monitor_url))

    @property
    def time_url(self):
        return self.monitor_url + self.time_path

    @property
    def login_url(self):
        return self.monitor_url + self.login_path

    @property
    def show_login_url(self):
        return self.monitor_url + self.show_login_path

    @property
    def commit_url(self):
        return self.monitor_url + self.commit_path

    @property
    def hosts_url(self):
        return self.monitor_url + self.hosts_path

    @property
    def services_url(self):
        return self.monitor_url + self.services_path

    def _set_recheck(self, host, service):
        if not service:
            values = {"requested_command": "SCHEDULE_HOST_CHECK"}
            values.update({"cmd_param[host_name]": host})
        else:
            if self.hosts[host].services[service].is_passive_only():
                return
            values = {"requested_command": "SCHEDULE_SVC_CHECK"}
            values.update({"cmd_param[service]": host + ";" + service})

        content = self.FetchURL(self.time_url, giveback="raw").result
        pos = content.find('<span id="page_last_updated">')
        remote_time = content[pos+len('<span id="page_last_updated">'):content.find('<', pos+1)]
        if remote_time:
            magic_tuple = datetime.datetime.strptime(str(remote_time), "%Y-%m-%d %H:%M:%S")
            time_diff = datetime.timedelta(0, 10)
            remote_time = magic_tuple + time_diff

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Get Remote time: " + str(remote_time))

        values.update({"cmd_param[check_time]": remote_time})
        values.update({"cmd_param[_force]": "1"})

        self.FetchURL(self.commit_url, cgi_data=urllib.urlencode(values), giveback="raw")


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services):
        if not service:
            values = {"requested_command": "ACKNOWLEDGE_HOST_PROBLEM"}
            values.update({"cmd_param[host_name]": host})
        else:
            values = {"requested_command": "ACKNOWLEDGE_SVC_PROBLEM"}
            values.update({"cmd_param[service]": host + ";" + service})

        values.update({"cmd_param[sticky]": int(sticky)})
        values.update({"cmd_param[notify]": int(notify)})
        values.update({"cmd_param[persistent]": int(persistent)})
        values.update({"cmd_param[author]": self.get_username()})
        values.update({"cmd_param[comment]": comment})

        self.FetchURL(self.commit_url, cgi_data=urllib.urlencode(values), giveback="raw")


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        if not service:
            values = {"requested_command": "SCHEDULE_HOST_DOWNTIME"}
            values.update({"cmd_param[host_name]": host})
        else:
            values = {"requested_command": "SCHEDULE_SVC_DOWNTIME"}
            values.update({"cmd_param[service]": host + ";" + service})

        values.update({"cmd_param[author]": author})
        values.update({"cmd_param[comment]": comment})
        values.update({"cmd_param[fixed]": fixed})
        values.update({"cmd_param[trigger_id]": "0"})
        values.update({"cmd_param[start_time]": start_time})
        values.update({"cmd_param[end_time]": end_time})
        values.update({"cmd_param[duration]": str(hours) + "." + str(minutes)})

        self.FetchURL(self.commit_url, cgi_data=urllib.urlencode(values), giveback="raw")

    def get_host_status(self):
        htobj = self.FetchURL(self.hosts_url).result
        table = htobj.find('table', {'id': 'host_table'})
        trs = table.findAll('tr')
        trs.pop(0)

        for tr in [tr for tr in table('tr') if len(tr('td')) > 1]:
            n = self.parse_host_row(tr)

            # after collection data in nagitems create objects from its informations
            # host objects contain service objects
            if n["name"] not in self.new_hosts:
                new_host = GenericHost()
                for attr, val in n.iteritems():
                    setattr(new_host, attr, val)
                self.new_hosts[new_host.name] = new_host

        del trs, table, htobj

    def get_service_status(self):
        htobj = self.FetchURL(self.services_url).result
        table = htobj.find('table', {'id': 'service_table'})
        trs = table('tr')
        trs.pop(0)
        lasthost = ""

        for tr in [tr for tr in table('tr') if len(tr('td')) > 1]:
            n, host_bitmask = self.parse_service_row(tr)

            if n["host"] not in self.new_hosts:
                # the hosts that we just fetched were on a list only containing
                # those in a non-OK state, thus, we just found a not-yet seen host
                # and we have to fake it 'til we make it
                new_host = GenericHost()
                new_host.name = n["host"]
                new_host.status = "UP"
                new_host.visible = False

                # trying to fix https://sourceforge.net/tracker/index.php?func=detail&aid=3299790&group_id=236865&atid=1101370
                # if host is not down but in downtime or any other flag this should be evaluated too
                if host_bitmask:
                    for number, name in self.bitmasks.iteritems():
                        setattr(new_host, name, bool(int(host_bitmask) & number))
                self.new_hosts[n["host"]] = new_host

            # if a service does not exist create its object
            if n["name"] not in self.new_hosts[n["host"]].services:
                new_service = GenericService()
                for attr, val in n.iteritems():
                    setattr(new_service, attr, val)
                self.new_hosts[n["host"]].services[n["name"]] = new_service

        del trs, table, htobj


    def _get_status(self):
        """
        Get status from Ninja Server
        """

        try:
            self.get_host_status()
            self.get_service_status()
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        return Result()

    def parse_host_row(self, tr):
        tds = tr('td')
        n = {}
        n["name"] = tds[0]['id'].split('|')[-1]
        n["status"] = tds[0]['title']
        n["last_check"] = str(tds[5].contents[0])
        n["duration"] = str(tds[6].contents[0])
        n["attempt"] = "N/A"
        n["status_information"] = str(tds[7].contents[0]).strip()
        n["visible"] = True

        # the last, hidden, span always contains an integer
        bitmask = tds[2].findAll('span')[-1]

        for number, name in self.bitmasks.iteritems():
            n[name] = bool(int(bitmask.contents[0]) & number)

        return n

    def parse_service_row(self, tr):
        tds = tr('td')
        n = {}
        n["status"] = tds[2]['title']

        host_bitmask = tds[1].findAll('span')
        if host_bitmask:
            # we got at least one hit, pick the last
            host_bitmask = host_bitmask[-1].contents[0]
        n["host"] = tds[0]['id'].split('|')[-1]
        n["name"] = tds[2]['id'].split('|')[-1]
        n["last_check"] = str(tds[6].contents[0])
        n["duration"] = str(tds[7].contents[0])
        n["attempt"] = str(tds[8].contents[0])
        n["status_information"] = str(tds[9].contents[0]).strip()
        n["visible"] = True

        # the last, hidden, span always contains an integer
        bitmask = tds[4].findAll('span')[-1]
        for number, name in self.bitmasks.iteritems():
            n[name] = bool(int(bitmask.contents[0]) & number)

        return n, host_bitmask
