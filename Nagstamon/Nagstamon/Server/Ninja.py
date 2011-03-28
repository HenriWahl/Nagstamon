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

from urllib2 import urlopen, Request, build_opener, HTTPCookieProcessor, install_opener
from Nagstamon import Actions
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer


class NinjaServer(GenericServer):
    """
        Ninja plugin for Nagstamon
    """

    TYPE = 'Ninja'

    # Ninja variables to be used later
    #commit_url = False
    #login_url = False
    #time_url = False
    #headers = False

    # Session Cookies
    ###cj = cookielib.LWPCookieJar()

    # used in Nagios _get_status() method
    HTML_BODY_TABLE_INDEX = 2
    
    
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        GenericServer.__init__(self, **kwds)
        
        # Ninja Settings
        self.commit_url = self.nagios_url + '/index.php/command/commit'
        self.login_url = self.nagios_url + '/index.php/default/do_login'
        self.time_url = self.nagios_url + '/index.php/extinfo/show_process_info'
    

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

        check_time = self.send_http_command("time")

        if not check_time:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="Recheck failed, didn't got any 'time' from server")
            return

        values.update({"cmd_param[check_time]": check_time})
        values.update({"cmd_param[_force]": "1"})

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Sending Recheck")

        if self.send_http_command("commit", values):
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="Recheck Success")


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

        values.update({"cmd_param[sticky]": sticky})
        values.update({"cmd_param[notify]": notify})
        values.update({"cmd_param[persistent]": persistent})
        values.update({"cmd_param[author]": self.get_username()})
        values.update({"cmd_param[comment]": comment})

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Sending ACKNOWLEDGE Values: " + str(values) )

        self.send_http_command("commit", values)

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

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Sending DOWNTIME Values: " + str(values) )

        self.send_http_command("commit", values)
        

    def init_HTTP(self):
        # add default auth for monitor.old 
        GenericServer.init_HTTP(self)

        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), debug="Enter _init_HTTP" )

        #if self.cj != None:
        #    self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
        #    urllib2.install_opener(self.opener)

        try:
            # Try to login
            login_values = {'username': self.get_username(), 'password': self.get_password()}
            login_data = urllib.urlencode(login_values)
            #req = Request(self.login_url, login_data, self.headers)
            req = Request(self.login_url, login_data)            
            handle = urlopen(req)

        except IOError, e:
            print 'We failed to open "%s".' % self.login_url
            if hasattr(e, 'code'):
                print 'We failed with error code - %s.' % e.code
                return False
        else:
            if handle.geturl() == self.login_url:
                # If we get back to show_login somethings wrong, prob username/password
                #while (1):
                #    if self._init_HTTP():
                #       return True
                #    if str(self.conf.debug_mode) == "True":
                #       self.Debug(server=self.get_name(), debug="Failed login, retrying...")
                return False
            else:
                # Cookie should be set by now lets return ok.
                return True
            

    def send_http_command(self, mode, values=False):
        #if not self.login_url:
        #    self._init_HTTP()

        if mode == "commit" and not values:
            return False

        # Lets send the commit string
        if mode == "commit":
            data = urllib.urlencode(values)
            req = Request(self.commit_url, data, self.headers)
            handle = urlopen(req)
            return True

        if mode == "time":
            data = None
            remote_time = None
            req = Request(self.time_url, data, self.headers)
            handle = urlopen(req)

            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="Url: " + handle.geturl())

            #if handle.geturl() == self.login_url:
            #    self._init_HTTP()
            #    remote_time = self.send_http_command(mode, values)
            #    if remote_time != False:
            #        return remote_time

            content = handle.read()
            pos = content.find('<span id="page_last_updated">')
            remote_time = content[pos+len('<span id="page_last_updated">'):content.find('<', pos+1)]
            if remote_time:
                magic_tuple = datetime.datetime.strptime(str(remote_time), "%Y-%m-%d %H:%M:%S")
                time_diff = datetime.timedelta(0, 10)
                remote_time = magic_tuple + time_diff

            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="Get Remote time: " + str(remote_time))

            if not remote_time:
                return False
            else:
                return str(remote_time)

        return False