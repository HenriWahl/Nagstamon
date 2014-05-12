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

from Nagstamon.Server.Generic import GenericServer
import urllib
import sys
import copy
# this seems to be necessary for json to be packaged by pyinstaller
from encodings import hex_codec
import json
import base64

# to let Linux distributions use their own BeautifulSoup if existent try importing local BeautifulSoup first
# see https://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3302612&group_id=236865
try:
    from BeautifulSoup import BeautifulSoup
except:
    from Nagstamon.thirdparty.BeautifulSoup import BeautifulSoup

from Nagstamon.Objects import *
from Nagstamon.Actions import *


class IcingaServer(GenericServer):
    """
        object of Incinga server
    """
    TYPE = 'Icinga'
    # flag to handle JSON or HTML correctly - checked by get_server_version()
    json = None

    # autologin is used only by Centreon
    DISABLED_CONTROLS = ["input_checkbutton_use_autologin",
                         "label_autologin_key",
                         "input_entry_autologin_key"]


    def init_config(self):
        """
        set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # dummy default empty cgi urls - get filled later when server version is known
        self.cgiurl_services = None
        self.cgiurl_hosts = None


    def init_HTTP(self):
        """
        Icinga 1.11 needs extra Referer header for actions
        """
        GenericServer.init_HTTP(self)

        if not "Referer" in self.HTTPheaders:
            # to execute actions since Icinga 1.11 a Referer Header is necessary
            for giveback in ["raw", "obj"]:
                self.HTTPheaders[giveback]["Referer"] = self.monitor_cgi_url + "/cmd.cgi"


    def get_server_version(self):
        """
        Try to get Icinga version for different URLs and JSON capabilities
        """
        result = self.FetchURL("%s/tac.cgi?jsonoutput" % (self.monitor_cgi_url), giveback="raw")

        if result.error != "":
            return result
        else:
            tacraw = result.result

        if tacraw.startswith("<"):
            self.json = False
            tacsoup = BeautifulSoup(tacraw)
            self.version = tacsoup.find("a", { "class" : "homepageURL" })
            # only extract version if HTML seemed to be OK
            if self.version.__dict__.has_key("contents"):
                self.version = self.version.contents[0].split("Icinga ")[1]
        elif tacraw.startswith("{"):
            # there seem to be problems with Icinga < 1.6
            # in case JSON parsing crashes fall back to HTML
            try:
                jsondict = json.loads(tacraw)
                self.version = jsondict["cgi_json_version"]
                self.json = True
            except:
                self.version = "1.6"
                self.json = False


    def _get_status(self):
        """
        Get status from Icinga Server, prefer JSON if possible
        """
        try:
            if self.json == None:
                # we need to get the server version and its JSONability
                result = self.get_server_version()

            if self.version != "":
                # define CGI URLs for hosts and services depending on JSON-capable server version
                if self.cgiurl_hosts == self.cgiurl_services == None:
                    if self.version < "1.7":
                        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
                        # services (unknown, warning or critical?) as dictionary, sorted by hard and soft state type
                        self.cgiurl_services = {"hard": self.monitor_cgi_url + "/status.cgi?host=all&servicestatustypes=253&serviceprops=262144",\
                                                "soft": self.monitor_cgi_url + "/status.cgi?host=all&servicestatustypes=253&serviceprops=524288"}
                        # hosts (up or down or unreachable)
                        self.cgiurl_hosts = {"hard": self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=262144",\
                                             "soft": self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=524288"}
                    else:
                        # services (unknown, warning or critical?)
                        self.cgiurl_services = {"hard": self.monitor_cgi_url + "/status.cgi?style=servicedetail&servicestatustypes=253&serviceprops=262144",\
                                                "soft": self.monitor_cgi_url + "/status.cgi?style=servicedetail&servicestatustypes=253&serviceprops=524288"}
                        # hosts (up or down or unreachable)
                        self.cgiurl_hosts = {"hard": self.monitor_cgi_url + "/status.cgi?style=hostdetail&hoststatustypes=12&hostprops=262144",\
                                             "soft": self.monitor_cgi_url + "/status.cgi?style=hostdetail&hoststatustypes=12&hostprops=524288"}
                    if self.json == True:
                        for status_type in "hard", "soft":
                           self.cgiurl_services[status_type] += "&jsonoutput"
                           self.cgiurl_hosts[status_type] += "&jsonoutput"

                # get status depending on JSONablility
                if self.json == True:
                    self._get_status_JSON()
                else:
                    self._get_status_HTML()
            else:
                # error result in case version still was ""
                return result
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()


    def _get_status_JSON(self):
        """
        Get status from Icinga Server - the JSON way
        """
        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # now using JSON output from Icinga
        try:
            for status_type in "hard", "soft":
                result = self.FetchURL(self.cgiurl_hosts[status_type], giveback="raw")
                # purify JSON result of unnecessary control sequence \n
                jsonraw, error = copy.deepcopy(result.result.replace("\n", "")), copy.deepcopy(result.error)

                if error != "": return Result(result=jsonraw, error=error)

                jsondict = json.loads(jsonraw)
                hosts = copy.deepcopy(jsondict["status"]["host_status"])

                for host in hosts:
                    # make dict of tuples for better reading
                    h = dict(host.items())

                    # host
                    if str(self.use_display_name_host) == "False":
                        # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                        # better be host_name instead of host_display_name
                        # legacy Icinga adjustments
                        if h.has_key("host_name"): host_name = h["host_name"]
                        elif h.has_key("host"): host_name = h["host"]
                    else:
                        # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                        # problems with that so here we go with extra display_name option
                        host_name = h["host_display_name"]

                    # host objects contain service objects
                    if not self.new_hosts.has_key(host_name):
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].server = self.name
                        self.new_hosts[host_name].status = h["status"]
                        self.new_hosts[host_name].last_check = h["last_check"]
                        self.new_hosts[host_name].duration = h["duration"]
                        self.new_hosts[host_name].attempt = h["attempts"]
                        self.new_hosts[host_name].status_information= h["status_information"].encode("utf-8").replace("\n", " ").strip()
                        self.new_hosts[host_name].passiveonly = not(h["active_checks_enabled"])
                        self.new_hosts[host_name].notifications_disabled = not(h["notifications_enabled"])
                        self.new_hosts[host_name].flapping = h["is_flapping"]
                        self.new_hosts[host_name].acknowledged = h["has_been_acknowledged"]
                        self.new_hosts[host_name].scheduled_downtime = h["in_scheduled_downtime"]
                        self.new_hosts[host_name].status_type = status_type
                    del h, host_name
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            for status_type in "hard", "soft":
                result = self.FetchURL(self.cgiurl_services[status_type], giveback="raw")
                # purify JSON result of unnecessary control sequence \n
                jsonraw, error = copy.deepcopy(result.result.replace("\n", "")), copy.deepcopy(result.error)

                if error != "": return Result(result=jsonraw, error=error)

                jsondict = json.loads(jsonraw)
                services = copy.deepcopy(jsondict["status"]["service_status"])

                for service in services:
                    # make dict of tuples for better reading
                    s = dict(service.items())

                    if str(self.use_display_name_host) == "False":
                        # according to http://sourceforge.net/p/nagstamon/bugs/83/ it might
                        # better be host_name instead of host_display_name
                        # legacy Icinga adjustments
                        if s.has_key("host_name"): host_name = s["host_name"]
                        elif s.has_key("host"): host_name = s["host"]
                    else:
                        # https://github.com/HenriWahl/Nagstamon/issues/46 on the other hand has
                        # problems with that so here we go with extra display_name option
                        host_name = s["host_display_name"]

                    # host objects contain service objects
                    if not self.new_hosts.has_key(host_name):
                        self.new_hosts[host_name] = GenericHost()
                        self.new_hosts[host_name].name = host_name
                        self.new_hosts[host_name].status = "UP"

                    if str(self.use_display_name_host) == "False":
                        # legacy Icinga adjustments
                        if s.has_key("service_description"): service_name = s["service_description"]
                        elif s.has_key("description"): service_name = s["description"]
                        elif s.has_key("service"): service_name = s["service"]
                    else:
                        service_name = s["service_display_name"]

                    # if a service does not exist create its object
                    if not self.new_hosts[host_name].services.has_key(service_name):
                        self.new_hosts[host_name].services[service_name] = GenericService()
                        self.new_hosts[host_name].services[service_name].host = host_name
                        self.new_hosts[host_name].services[service_name].name = service_name
                        self.new_hosts[host_name].services[service_name].server = self.name
                        self.new_hosts[host_name].services[service_name].status = s["status"]
                        self.new_hosts[host_name].services[service_name].last_check = s["last_check"]
                        self.new_hosts[host_name].services[service_name].duration = s["duration"]
                        self.new_hosts[host_name].services[service_name].attempt = s["attempts"]
                        self.new_hosts[host_name].services[service_name].status_information = s["status_information"].encode("utf-8").replace("\n", " ").strip()
                        self.new_hosts[host_name].services[service_name].passiveonly = not(s["active_checks_enabled"])
                        self.new_hosts[host_name].services[service_name].notifications_disabled = not(s["notifications_enabled"])
                        self.new_hosts[host_name].services[service_name].flapping = s["is_flapping"]
                        self.new_hosts[host_name].services[service_name].acknowledged = s["has_been_acknowledged"]
                        self.new_hosts[host_name].services[service_name].scheduled_downtime = s["in_scheduled_downtime"]

                        self.new_hosts[host_name].services[service_name].status_type = status_type
                    del s, host_name, service_name
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # some cleanup
        del jsonraw, jsondict, error, hosts, services

        #dummy return in case all is OK
        return Result()


    def _get_status_HTML(self):
        """
        Get status from Nagios Server - the oldschool CGI HTML way
        """
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
        ###global icons
        nagitems = {"services":[], "hosts":[]}

        # new_hosts dictionary
        self.new_hosts = dict()

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            for status_type in "hard", "soft":
                result = self.FetchURL(self.cgiurl_hosts[status_type])
                htobj, error = result.result, result.error

                if error != "": return Result(result=htobj, error=error)

                # put a copy of a part of htobj into table to be able to delete htobj
                table = htobj('table', {'class': 'status'})[0]

                # do some cleanup
                del result, error

                # access table rows
                # some Icinga versions have a <tbody> tag in cgi output HTML which
                # omits the <tr> tags being found
                if len(table('tbody')) == 0:
                    trs = table('tr', recursive=False)
                else:
                    tbody = table('tbody')[0]
                    trs = tbody('tr', recursive=False)

                # kick out table heads
                trs.pop(0)

                for tr in trs:
                    try:
                        # ignore empty <tr> rows
                        if len(tr('td', recursive=False)) > 1:
                            n = {}
                            # get tds in one tr
                            tds = tr('td', recursive=False)
                            # host
                            try:
                                n["host"] = str(tds[0].table.tr.td.table.tr.td.a.string)
                            except:
                                n["host"] = str(nagitems[len(nagitems)-1]["host"])
                                # status
                            n["status"] = str(tds[1].string)
                            # last_check
                            n["last_check"] = str(tds[2].string)
                            # duration
                            n["duration"] = str(tds[3].string)
                            # division between Nagios and Icinga in real life... where
                            # Nagios has only 5 columns there are 7 in Icinga 1.3...
                            # ... and 6 in Icinga 1.2 :-)
                            if len(tds) < 7:
                                # the old Nagios table
                                # status_information
                                if len(tds[4](text=not_empty)) == 0:
                                    n["status_information"] = ""
                                else:
                                    n["status_information"] = str(tds[4].string).encode("utf-8")
                                    # attempts are not shown in case of hosts so it defaults to "N/A"
                                n["attempt"] = "N/A"
                            else:
                                # attempts are shown for hosts
                                # to fix http://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3280961&group_id=236865 .attempt needs
                                # to be stripped
                                n["attempt"] = str(tds[4].string).strip()
                                # status_information
                                if len(tds[5](text=not_empty)) == 0:
                                    n["status_information"] = ""
                                else:
                                    n["status_information"] = str(tds[5].string).encode("utf-8")

                            # status flags
                            n["passiveonly"] = False
                            n["notifications_disabled"] = False
                            n["flapping"] = False
                            n["acknowledged"] = False
                            n["scheduled_downtime"] = False

                            # map status icons to status flags
                            icons = tds[0].findAll('img')
                            for i in icons:
                                icon = i["src"].split("/")[-1]
                                if icon in self.STATUS_MAPPING:
                                    n[self.STATUS_MAPPING[icon]] = True
                            # cleaning
                            del icons

                            # add dictionary full of information about this host item to nagitems
                            nagitems["hosts"].append(n)
                            # after collection data in nagitems create objects from its informations
                            # host objects contain service objects
                            if not self.new_hosts.has_key(n["host"]):
                                new_host = n["host"]
                                self.new_hosts[new_host] = GenericHost()
                                self.new_hosts[new_host].name = n["host"]
                                self.new_hosts[new_host].server = self.name
                                self.new_hosts[new_host].status = n["status"]
                                self.new_hosts[new_host].last_check = n["last_check"]
                                self.new_hosts[new_host].duration = n["duration"]
                                self.new_hosts[new_host].attempt = n["attempt"]
                                self.new_hosts[new_host].status_information= n["status_information"].encode("utf-8").replace("\n", " ").strip()
                                self.new_hosts[new_host].passiveonly = n["passiveonly"]
                                self.new_hosts[new_host].notifications_disabled = n["notifications_disabled"]
                                self.new_hosts[new_host].flapping = n["flapping"]
                                self.new_hosts[new_host].acknowledged = n["acknowledged"]
                                self.new_hosts[new_host].scheduled_downtime = n["scheduled_downtime"]
                                self.new_hosts[new_host].status_type = status_type
                            # some cleanup
                            del tds, n
                    except:
                        self.Error(sys.exc_info())

                # do some cleanup
                htobj.decompose()
                del htobj, trs, table

        except:
                # set checking flag back to False
                self.isChecking = False
                result, error = self.Error(sys.exc_info())
                return Result(result=result, error=error)

        # services
        try:
            for status_type in "hard", "soft":
                result = self.FetchURL(self.cgiurl_services[status_type])
                htobj, error = result.result, result.error
                #if error != "": return Result(result=copy.deepcopy(htobj), error=error)
                if error != "": return Result(result=htobj, error=error)

                table = htobj('table', {'class': 'status'})[0]

                # some Icinga versions have a <tbody> tag in cgi output HTML which
                # omits the <tr> tags being found
                if len(table('tbody')) == 0:
                    trs = table('tr', recursive=False)
                else:
                    tbody = table('tbody')[0]
                    trs = tbody('tr', recursive=False)

                # do some cleanup
                del result, error

                # kick out table heads
                trs.pop(0)

                for tr in trs:
                    try:
                        # ignore empty <tr> rows - there are a lot of them - a Nagios bug?
                        tds = tr('td', recursive=False)
                        if len(tds) > 1:
                            n = {}
                            # host
                            # the resulting table of Nagios status.cgi table omits the
                            # hostname of a failing service if there are more than one
                            # so if the hostname is empty the nagios status item should get
                            # its hostname from the previuos item - one reason to keep "nagitems"
                            try:
                                n["host"] = str(tds[0](text=not_empty)[0])
                            except:
                                n["host"] = str(nagitems["services"][len(nagitems["services"])-1]["host"])
                                # service
                            n["service"] = str(tds[1](text=not_empty)[0])
                            # status
                            n["status"] = str(tds[2](text=not_empty)[0])
                            # last_check
                            n["last_check"] = str(tds[3](text=not_empty)[0])
                            # duration
                            n["duration"] = str(tds[4](text=not_empty)[0])
                            # attempt
                            # to fix http://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3280961&group_id=236865 .attempt needs
                            # to be stripped
                            n["attempt"] = str(tds[5](text=not_empty)[0]).strip()
                            # status_information
                            if len(tds[6](text=not_empty)) == 0:
                                n["status_information"] = ""
                            else:
                                n["status_information"] = str(tds[6](text=not_empty)[0]).encode("utf-8")
                                # status flags
                            n["passiveonly"] = False
                            n["notifications_disabled"] = False
                            n["flapping"] = False
                            n["acknowledged"] = False
                            n["scheduled_downtime"] = False

                            # map status icons to status flags
                            icons = tds[1].findAll('img')
                            for i in icons:
                                icon = i["src"].split("/")[-1]
                                if icon in self.STATUS_MAPPING:
                                    n[self.STATUS_MAPPING[icon]] = True
                            # cleaning
                            del icons

                            # add dictionary full of information about this service item to nagitems - only if service
                            nagitems["services"].append(n)
                            # after collection data in nagitems create objects of its informations
                            # host objects contain service objects
                            if not self.new_hosts.has_key(n["host"]):
                                self.new_hosts[n["host"]] = GenericHost()
                                self.new_hosts[n["host"]].name = n["host"]
                                self.new_hosts[n["host"]].status = "UP"
                                # trying to fix https://sourceforge.net/tracker/index.php?func=detail&aid=3299790&group_id=236865&atid=1101370
                                # if host is not down but in downtime or any other flag this should be evaluated too
                                # map status icons to status flags
                                icons = tds[0].findAll('img')
                                for i in icons:
                                    icon = i["src"].split("/")[-1]
                                    if icon in self.STATUS_MAPPING:
                                        self.new_hosts[n["host"]].__dict__[self.STATUS_MAPPING[icon]] = True
                                # cleaning
                                del icons
                                # if a service does not exist create its object
                            if not self.new_hosts[n["host"]].services.has_key(n["service"]):
                                new_service = n["service"]
                                self.new_hosts[n["host"]].services[new_service] = GenericService()
                                self.new_hosts[n["host"]].services[new_service].host = n["host"]
                                self.new_hosts[n["host"]].services[new_service].server = self.name
                                self.new_hosts[n["host"]].services[new_service].name = n["service"]
                                self.new_hosts[n["host"]].services[new_service].status = n["status"]
                                self.new_hosts[n["host"]].services[new_service].last_check = n["last_check"]
                                self.new_hosts[n["host"]].services[new_service].duration = n["duration"]
                                self.new_hosts[n["host"]].services[new_service].attempt = n["attempt"]
                                self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"].encode("utf-8").replace("\n", " ").strip()
                                self.new_hosts[n["host"]].services[new_service].passiveonly = n["passiveonly"]
                                self.new_hosts[n["host"]].services[new_service].notifications_disabled = n["notifications_disabled"]
                                self.new_hosts[n["host"]].services[new_service].flapping = n["flapping"]
                                self.new_hosts[n["host"]].services[new_service].acknowledged = n["acknowledged"]
                                self.new_hosts[n["host"]].services[new_service].scheduled_downtime = n["scheduled_downtime"]
                            # some cleanup
                            del tds, n
                    except:
                        self.Error(sys.exc_info())

                # do some cleanup
                htobj.decompose()
                del htobj, trs, table

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

            # some cleanup
        del nagitems

        #dummy return in case all is OK
        return Result()


    def _set_recheck(self, host, service):
        """
        to solve https://sourceforge.net/p/nagstamon/feature-requests/74/ there is a comment parameter added
        to cgi request
        """
        if service != "":
            if self.hosts[host].services[service].is_passive_only():
                # Do not check passive only checks
                return
        # get start time from Nagios as HTML to use same timezone setting like the locally installed Nagios
        result = self.FetchURL(self.monitor_cgi_url + "/cmd.cgi?" + urllib.urlencode({"cmd_typ":"96", "host":host}))
        self.start_time = dict(result.result.find(attrs={"name":"start_time"}).attrs)["value"]

        # decision about host or service - they have different URLs
        if service == "":
            # host
            cmd_typ = "96"
        else:
            # service @ host
            cmd_typ = "7"
        # ignore empty service in case of rechecking a host
        cgi_data = urllib.urlencode([("cmd_typ", cmd_typ),\
                                     ("cmd_mod", "2"),\
                                     ("host", host),\
                                     ("service", service),\
                                     ("start_time", self.start_time),\
                                     ("force_check", "on"),\
                                     ("com_data", "Recheck by %s" % self.username),\
                                     ("btnSubmit", "Commit")])
        # execute POST request
        self.FetchURL(self.monitor_cgi_url + "/cmd.cgi", giveback="raw", cgi_data=cgi_data)
