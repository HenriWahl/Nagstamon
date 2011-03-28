# encoding: utf-8

from Nagstamon.Server.Generic import GenericServer

import sys
import urllib2
import webbrowser
import base64
import datetime
import time
import os.path
import urllib
import cookielib

#from urllib2 import urlopen, Request, build_opener, HTTPCookieProcessor, install_opener
from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer


class NinjaServer(GenericServer):
    """
        Ninja plugin for Nagstamon
    """

    TYPE = 'Ninja'

    # Ninja variables to be used later
    commit_url = False
    login_url = False
    time_url = False

    # used in Nagios _get_status() method
    HTML_BODY_TABLE_INDEX = 2
    

    def init_HTTP(self):
        # add default auth for monitor.old 
        GenericServer.init_HTTP(self)

        # self.Cookie is a CookieJar which is a list of cookies - if 0 then emtpy
        if len(self.Cookie) == 0: 
            try:
                # Ninja Settings
                self.commit_url = self.nagios_url + '/index.php/command/commit'
                self.login_url = self.nagios_url + '/index.php/default/do_login'
                self.time_url = self.nagios_url + '/index.php/extinfo/show_process_info'
                # get a Ninja cookie via own method
                self.urlopener.open(self.login_url, urllib.urlencode({'username': self.get_username(), 'password': self.get_password()}))

                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), debug="Cookie:" + str(self.Cookie))

            except:
                self.Error(sys.exc_info())
      

    def open_tree_view(self, host, service):
        if not service:
            webbrowser.open('%s/index.php/extinfo/details/host/%s' % (self.nagios_url, host))
        else:
            webbrowser.open('%s/index.php/extinfo/details/service/%s?service=%s' % (self.nagios_url, host, service))

    def open_services(self):
        webbrowser.open('%s/index.php/status/service/all?servicestatustypes=14' % (self.nagios_url))

    def open_hosts(self):
        webbrowser.open('%s/index.php/status/host/all/6' % (self.nagios_url))

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
        if sticky == True:
            sticky = "1"
        else:
            sticky = "0"

        if notify == True:
            notify = "1"
        else:
            notify = "0"

        if persistent == True:
            persistent = "1"
        else:
            persistent = "0"

        if not service:
            values = {"requested_command": "ACKNOWLEDGE_HOST_PROBLEM"}
            values.update({"cmd_param[service]": host})
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
        
            