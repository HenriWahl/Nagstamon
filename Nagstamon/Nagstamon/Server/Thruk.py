# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2013 Henri Wahl <h.wahl@ifw-dresden.de> et al.
# Thruk additions copyright by dcec@Github
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
import sys

# to let Linux distributions use their own BeautifulSoup if existent try importing local BeautifulSoup first
# see https://sourceforge.net/tracker/?func=detail&atid=1101370&aid=3302612&group_id=236865
try:
    from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
except:
    from Nagstamon.BeautifulSoup import BeautifulSoup, BeautifulStoneSoup

from Nagstamon.Actions import HostIsFilteredOutByRE, ServiceIsFilteredOutByRE, StatusInformationIsFilteredOutByRE, not_empty
from Nagstamon.Objects import *


class ThrukServer(GenericServer):
    """
        Thruk is derived from generic (Nagios) server
    """
    TYPE = 'Thruk'

<<<<<<< HEAD
=======
    # GUI sortable columns stuff
    DEFAULT_SORT_COLUMN_ID = 2
    # lost any memory what this COLOR_COLUMN_ID is used for...
    #COLOR_COLUMN_ID = 2
    HOST_COLUMN_ID = 0
    SERVICE_COLUMN_ID = 1
    # used for $STATUS$ variable for custom actions
    STATUS_INFO_COLUMN_ID = 6

    COLUMNS = [
        HostColumn,
        ServiceColumn,
        StatusColumn,
        LastCheckColumn,
        DurationColumn,
        AttemptColumn,
        StatusInformationColumn
    ]

    # autologin is used only by Centreon
    DISABLED_CONTROLS = ["input_checkbutton_use_autologin", "label_autologin_key", "input_entry_autologin_key"]

    # dictionary to translate status bitmaps on webinterface into status flags
    # this are defaults from Nagios
    # "disabled.gif" is in Nagios for hosts the same as "passiveonly.gif" for services
    STATUS_MAPPING = { "ack.gif" : "acknowledged",\
                       "passiveonly.gif" : "passiveonly",\
                       "disabled.gif" : "passiveonly",\
                       "ndisabled.gif" : "notifications_disabled",\
                       "downtime.gif" : "scheduled_downtime",\
                       "flapping.gif" : "flapping"}

    # Entries for monitor default actions in context menu
    MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Submit check result", "Downtime"]

    # Arguments available for submitting check results
    SUBMIT_CHECK_RESULT_ARGS = ["check_output", "performance_data"]

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS = { "monitor": "$MONITOR$",\
                    "hosts": "$MONITOR-CGI$/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12",\
                    "services": "$MONITOR-CGI$/status.cgi??dfl_s0_value_sel=5&dfl_s0_servicestatustypes=29&dfl_s0_op=%3D&style=detail&dfl_s0_type=host&dfl_s0_serviceprops=0&dfl_s0_servicestatustype=4&dfl_s0_servicestatustype=8&dfl_s0_servicestatustype=16&dfl_s0_servicestatustype=1&hidetop=&dfl_s0_hoststatustypes=15&dfl_s0_val_pre=&hidesearch=2&dfl_s0_value=all&dfl_s0_hostprops=0&nav=&page=1&entries=all",\
                    "history": "$MONITOR-CGI$/history.cgi?host=all&page=1&entries=all"}


    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        self.type = ""
        self.monitor_url = ""
        self.monitor_cgi_url = ""
        self.username = ""
        self.password = ""
        self.use_proxy = False
        self.use_proxy_from_os = False
        self.proxy_address = ""
        self.proxy_username = ""
        self.proxy_password = ""
        self.hosts = dict()
        self.new_hosts = dict()
        self.thread = None
        self.isChecking = False
        self.CheckingForNewVersion = False
        self.WorstStatus = "UP"
        self.States = ["UP", "UNKNOWN", "WARNING", "CRITICAL", "UNREACHABLE", "DOWN"]
        self.nagitems_filtered_list = list()
        self.nagitems_filtered = {"services":{"CRITICAL":[], "WARNING":[], "UNKNOWN":[]}, "hosts":{"DOWN":[], "UNREACHABLE":[]}}
        self.downs = 0
        self.unreachables = 0
        self.unknowns = 0
        self.criticals = 0
        self.warnings = 0
        self.status = ""
        self.status_description = ""
        # needed for looping server thread
        self.count = 0
        # needed for RecheckAll - save start_time once for not having to get it for every recheck
        self.start_time = None
        self.Cookie = cookielib.CookieJar()
        # use server-owned attributes instead of redefining them with every request
        self.passman = None
        self.basic_handler = None
        self.digest_handler = None
        self.proxy_handler = None
        self.proxy_auth_handler = None
        self.urlopener = None
        # headers for HTTP requests, might be needed for authorization on Nagios/Icinga Hosts
        self.HTTPheaders = dict()
        # attempt to use only one bound list of TreeViewColumns instead of ever increasing one
        self.TreeView = None
        self.TreeViewColumns = list()
        self.ListStore = None
        self.ListStoreColumns = list()
        # flag which decides if authentication has to be renewed
        self.refresh_authentication = False
        # to handle Icinga versions this information is necessary, might be of future use for others too
        self.version = ""


    def init_HTTP(self):
        """
        partly not constantly working Basic Authorization requires extra Autorization headers,
        different between various server types
        """
        if self.HTTPheaders == {}:
            for giveback in ["raw", "obj"]:
                self.HTTPheaders[giveback] = {"Authorization": "Basic " + base64.b64encode(self.get_username() + ":" + self.get_password())}

>>>>>>> 2034ac0a3f656c54a0f600d9ee5ae612fb134c7a

    def init_config(self):
        """
        set URLs for CGI - they are static and there is no need to set them with every cycle
        """
        # create filters like described in
        # http://www.nagios-wiki.de/nagios/tips/host-_und_serviceproperties_fuer_status.cgi?s=servicestatustypes
        #
        # the following variables are not necessary anymore as with "new" filtering
        #
        # hoststatus
        #hoststatustypes = 12
        # servicestatus
        #servicestatustypes = 253
        # serviceprops & hostprops both have the same values for the same states so I
        # group them together
        #hostserviceprops = 0

        # services (unknown, warning or critical?) as dictionary, sorted by hard and soft state type
        self.cgiurl_services = {"hard": self.monitor_cgi_url + "/status.cgi?dfl_s0_servicestatustypes=29&style=detail&dfl_s0_serviceprops=262144&dfl_s0_hoststatustypes=15&dfl_s0_hostprops=0&nav=&page=1&entries=all",\
                                 "soft": self.monitor_cgi_url + "/status.cgi?dfl_s0_servicestatustypes=29&style=detail&dfl_s0_serviceprops=524288&dfl_s0_hoststatustypes=15&dfl_s0_hostprops=0&nav=&page=1&entries=all"}
        # hosts (up or down or unreachable)
        self.cgiurl_hosts = { "hard": self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=262144",\
                              "soft": self.monitor_cgi_url + "/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12&hostprops=524288"}



    def _get_status(self):
        """
        Get status from Thruk Server
        """
        # create Nagios items dictionary with to lists for services and hosts
        # every list will contain a dictionary for every failed service/host
        # this dictionary is only temporarily
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

                if error != "": return Result(result=copy.deepcopy(htobj), error=error)

                # put a copy of a part of htobj into table to be able to delete htobj
                table = htobj('table', {'class': 'status'})[0]

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
                            n = dict()
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
                                    n["status_information"] = str(tds[4](text=not_empty)[1]).encode("utf-8")
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
                                self.new_hosts[new_host].status = n["status"]
                                self.new_hosts[new_host].last_check = n["last_check"]
                                self.new_hosts[new_host].duration = n["duration"]
                                self.new_hosts[new_host].attempt = n["attempt"]
                                self.new_hosts[new_host].status_information= n["status_information"].encode("utf-8")
                                self.new_hosts[new_host].passiveonly = n["passiveonly"]
                                self.new_hosts[new_host].notifications_disabled = n["notifications_disabled"]
                                self.new_hosts[new_host].flapping = n["flapping"]
                                self.new_hosts[new_host].acknowledged = n["acknowledged"]
                                self.new_hosts[new_host].scheduled_downtime = n["scheduled_downtime"]
                                self.new_hosts[new_host].status_type = status_type
                        del n
                    except:
                        self.Error(sys.exc_info())

                # do some cleanup
                htobj.decompose()
                del trs, table, htobj, result, error

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
                if error != "": return Result(result=copy.deepcopy(htobj), error=error)

                table = htobj('table', {'class': 'status servicestatus'})[0]

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
                        # ignore empty <tr> rows - there are a lot of them - a Nagios bug?
                        tds = tr('td', recursive=False)

                        if len(tds) > 1:
                            n = dict()
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
                                try:
                                    n["status_information"] = str(tds[6](text=not_empty)[1])
                                except:
                                    n["status_information"] = ""
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

                            # if a service does not exist create its object
                            if not self.new_hosts[n["host"]].services.has_key(n["service"]):
                                new_service = n["service"]
                                self.new_hosts[n["host"]].services[new_service] = GenericService()
                                self.new_hosts[n["host"]].services[new_service].host = n["host"]
                                self.new_hosts[n["host"]].services[new_service].name = n["service"]
                                self.new_hosts[n["host"]].services[new_service].status = n["status"]
                                self.new_hosts[n["host"]].services[new_service].last_check = n["last_check"]
                                self.new_hosts[n["host"]].services[new_service].duration = n["duration"]
                                self.new_hosts[n["host"]].services[new_service].attempt = n["attempt"]
                                self.new_hosts[n["host"]].services[new_service].status_information = n["status_information"].encode("utf-8")
                                self.new_hosts[n["host"]].services[new_service].passiveonly = n["passiveonly"]
                                self.new_hosts[n["host"]].services[new_service].notifications_disabled = n["notifications_disabled"]
                                self.new_hosts[n["host"]].services[new_service].flapping = n["flapping"]
                                self.new_hosts[n["host"]].services[new_service].acknowledged = n["acknowledged"]
                                self.new_hosts[n["host"]].services[new_service].scheduled_downtime = n["scheduled_downtime"]
                                self.new_hosts[n["host"]].services[new_service].status_type = status_type
                            del n
                    except:
                        self.Error(sys.exc_info())

                # do some cleanup
                htobj.decompose()
                del trs, table, htobj, result, error
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # some cleanup
        del nagitems

        #dummy return in case all is OK
        return Result()

