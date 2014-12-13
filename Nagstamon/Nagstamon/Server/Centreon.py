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

import urllib, urllib2
import webbrowser
import socket
import sys
import re
import copy

from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer

class CentreonServer(GenericServer):
    TYPE = 'Centreon'
    # centreon generic web interface uses a sid which is needed to ask for news
    SID = None
    # count for SID regeneration
    SIDcount = 0

    # URLs for browser shortlinks/buttons on popup window
    BROWSER_URLS= { "monitor": "$MONITOR$/main.php?p=1",\
                    "hosts": "$MONITOR$/main.php?p=20103&o=hpb",\
                    "services": "$MONITOR$/main.php?p=20202&o=svcpb",\
                    "history": "$MONITOR$/main.php?p=203"}

    # A Monitor CGI URL is not necessary so hide it in settings
    DISABLED_CONTROLS = ["label_monitor_cgi_url",
                         "input_entry_monitor_cgi_url",
                         "input_checkbutton_use_display_name_host",
                         "input_checkbutton_use_display_name_service"]

    # newer Centreon versions (2.3+?) have different URL paths with a "/ndo" fragment
    # will be checked by _get_ndo_url() but default is /xml/ndo/
    # new in Centreon 2.4 seems to be a /xml/broker/ URL so this will be tried first
    XML_NDO = "xml/broker"

    # HARD/SOFT state mapping
    HARD_SOFT = {"(H)": "hard", "(S)": "soft"}

    # apparently necessesary because of non-english states as in https://github.com/HenriWahl/Nagstamon/issues/91
    TRANSLATIONS = {"INDISPONIBLE": "DOWN",
                    "INJOIGNABLE": "UNREACHABLE",
                    "CRITIQUE": "CRITICAL",
                    "INCONNU": "UNKNOWN",
                    "ALERTE": "WARNING"}


    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]

        GenericServer.__init__(self, **kwds)

        # Entries for monitor default actions in context menu
        self.MENU_ACTIONS = ["Monitor", "Recheck", "Acknowledge", "Downtime"]


    def init_HTTP(self):
        """
        initialize HTTP connection
        """
        if self.HTTPheaders == {}:
            GenericServer.init_HTTP(self)
            # Centreon xml giveback method just should exist
            self.HTTPheaders["xml"] = {}


    def reset_HTTP(self):
        """
        Centreon needs deletion of SID
        """
        self.HTTPheaders = {}
        self.SID = None
        self.SIDcount = 0
        self._get_sid()


    def init_config(self):
        """
        dummy init_config, called at thread start, not really needed here, just omit extra properties
        """
        pass


    def open_tree_view(self, host, service=""):
        if str(self.use_autologin) == "True":
            auth = "&autologin=1&useralias=" + self.username + "&token=" + self.autologin_key
            if host == '_Module_Meta':
                webbrowser.open(self.monitor_cgi_url + "/index.php?" + urllib.urlencode({"p":20206,"o":"meta"}) + auth )
            elif service == "":
                webbrowser.open(self.monitor_cgi_url + "/index.php?" + urllib.urlencode({"p":201,"o":"hd", "host_name":host}) + auth )
            else:
                webbrowser.open(self.monitor_cgi_url + "/index.php?" + urllib.urlencode({"p":202, "o":"svcd",  "host_name":host, "service_description":service}) + auth )
        else:
            if host == '_Module_Meta':
                webbrowser.open(self.monitor_cgi_url + "/main.php?" + urllib.urlencode({"p":20206,"o":"meta"}))
            # must be a host if service is empty...
            elif service == "":
                webbrowser.open(self.monitor_cgi_url + "/main.php?" + urllib.urlencode({"p":201,"o":"hd", "host_name":host}))
            else:
                webbrowser.open(self.monitor_cgi_url + "/main.php?" + urllib.urlencode({"p":202, "o":"svcd",  "host_name":host, "service_description":service}))


    def get_start_end(self, host):
        """
        get start and end time for downtime from Centreon server
        """
        try:
            cgi_data = urllib.urlencode({"p":"20106",\
                                         "o":"ah",\
                                         "host_name":host})
            result = self.FetchURL(self.monitor_cgi_url + "/main.php?" + cgi_data, giveback="obj")
            html, error = result.result, result.error
            if error == "":
                html = result.result
                start_time = html.find(attrs={"name":"start"}).attrMap["value"]
                end_time = html.find(attrs={"name":"end"}).attrMap["value"]

                # give values back as tuple
                return start_time, end_time
        except:
            self.Error(sys.exc_info())
            return "n/a", "n/a"


    def GetHost(self, host):
        """
        Centreonified way to get host ip - attribute "a" in down hosts xml is of no use for up
        hosts so we need to get ip anyway from web page
        """
        # the fastest method is taking hostname as used in monitor
        if str(self.conf.connect_by_host) == "True" or host == "":
            return Result(result=host)

        # do a web interface search limited to only one result - the hostname
        cgi_data = urllib.urlencode({"sid":self.SID,\
                                    "search":host,\
                                    "num":0,\
                                    "limit":1,\
                                    "sort_type":"hostname",\
                                    "order":"ASC",\
                                    "date_time_format_status":"d/m/Y H:i:s",\
                                    "o":"h",\
                                    "p":20102,\
                                    "time":0})

        result = self.FetchURL(self.monitor_cgi_url + "/include/monitoring/status/Hosts/" + self.XML_NDO + "/hostXML.php?"\
                              + cgi_data, giveback="xml")
        xmlobj = result.result

        if len(xmlobj) != 0:
            # when connection by DNS is not configured do it by IP
            try:
                if str(self.conf.connect_by_dns) == "True":
                   # try to get DNS name for ip, if not available use ip
                    try:
                        address = socket.gethostbyaddr(xmlobj.l.a.text)[0]
                        del xmlobj
                    except:
                        self.Error(sys.exc_info())
                        address = str(xmlobj.l.a.text)
                        del xmlobj
                else:
                    address = str(xmlobj.l.a.text)
                    del xmlobj
            except:
                result, error = self.Error(sys.exc_info())
                return Result(error=error)

        else:
            result, error = self.Error(sys.exc_info())
            return Result(error=error)

        # print IP in debug mode
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(), host=host, debug ="IP of %s:" % (host) + " " + address)
        # give back host or ip
        return Result(result=address)


    def _get_sid(self):
        """
        gets a shiny new SID for XML HTTP requests to Centreon cutting it out via .partition() from raw HTML
        additionally get php session cookie
        """
        # BROWSER_URLS using autologin
        if str(self.use_autologin) == "True":
            auth = "&autologin=1&useralias=" + self.username + "&token=" + self.autologin_key
            self.BROWSER_URLS= { "monitor": "$MONITOR$/index.php?p=1" + auth,\
                            "hosts": "$MONITOR$/index.php?p=20103&o=hpb" + auth,\
                            "services": "$MONITOR$/index.php?p=20202&o=svcpb" + auth,\
                            "history": "$MONITOR$/index.php?p=203" + auth}
        try:
            if str(self.use_autologin) == "True":
              raw = self.FetchURL(self.monitor_cgi_url + "/index.php?p=101&autologin=1&useralias=" + self.username + "&token=" + self.autologin_key, giveback="raw")
              #p=101&autologin=1&useralias=foscarini&token=8sEvwyEcMt
            else:
              login_data = urllib.urlencode({"useralias" : self.username, "password" : self.password, "submit" : "Login"})
              raw = self.FetchURL(self.monitor_cgi_url + "/index.php",cgi_data=login_data, giveback="raw")

            del raw
            sid = str(self.Cookie._cookies.values()[0].values()[0]["PHPSESSID"].value)
            return Result(result=sid)
        except:
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)


    def _get_ndo_url(self):
        """
        Find out where this instance of Centreon is publishing the status XMLs
	    Centreon + ndo            - /include/monitoring/status/Hosts/xml/hostXML.php
	    Centreon + broker 2.3/2.4 - /include/monitoring/status/Hosts/xml/{ndo,broker}/hostXML.php according to configuration
	    regexping HTML for Javascript
        """
        cgi_data = urllib.urlencode({"p":201})
        result = self.FetchURL(self.monitor_cgi_url + "/main.php?" + cgi_data, cgi_data=urllib.urlencode({"sid":self.SID}), giveback="raw")
        raw, error = result.result, result.error

        if error == "":
            if   re.search("var _addrXML.*xml\/host", raw):
              self.XML_NDO = "xml"
            elif re.search("var _addrXML.*xml\/ndo\/host", raw):
              self.XML_NDO = "xml/ndo"
            elif re.search("var _addrXML.*xml\/broker\/host", raw):
              self.XML_NDO = "xml/broker"
            else:
              self.XML_NDO = "xml/broker"
            del raw
        else:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug = "Could not detect host/service status version. Using Centreon_Broker")
        # some cleanup
        del result, error
	

    def _get_host_id(self, host):
        """
        get host_id via parsing raw html
        """
        cgi_data = urllib.urlencode({"p":201,\
                                    "o":"hd", "host_name":host})
        result = self.FetchURL(self.monitor_cgi_url + "/main.php?" + cgi_data, cgi_data=urllib.urlencode({"sid":self.SID}), giveback="raw")
        raw, error = result.result, result.error

        if error == "":
            host_id = raw.partition("var host_id = '")[2].partition("'")[0]
            del raw
        else:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug = "Host ID could not be retrieved.")

        # some cleanup
        del result, error

        # only if host_id is an usable integer return it
        try:
            if int(host_id):
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), host=host, debug = "Host ID is " + host_id)
                return host_id
            else:
                return ""
        except:
            return ""


    def _get_host_and_service_id(self, host, service):
        """
        parse a ton of html to get a host and a service id...
        """
        cgi_data = urllib.urlencode({"p":"20218",\
                                     "host_name":host,\
                                     "service_description":service,\
                                     "o":"as"})
        # might look strange to have cgi_data 2 times, the first it is the "real" in URL and the second is the cgi_data parameter
        # from urllib to get the session id POSTed
        result = self.FetchURL(self.monitor_cgi_url + "/main.php?"+ cgi_data, cgi_data=urllib.urlencode({"sid":self.SID}), giveback="raw")
        raw, error = result.result, result.error

        # ids to give back, should contain two items, a host and a service id
        ids = []

        if error == "":
            # search ids
            for l in raw.splitlines():
                if l.find('selected="selected"') <> -1:
                    ids.append(l.split('value="')[1].split('"')[0])
            else:
                return ids
        else:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), host=host, service=service, debug = "IDs could not be retrieved.")

            return "", ""


    def _get_status(self):
        """
        Get status from Centreon Server
        """
        # get sid in case this has not yet been done
        if self.SID == None or self.SID == "":
            self.SID = self._get_sid().result
            # those ndo urls would not be changing too often so this check migth be done here
            self._get_ndo_url()

        # services (unknown, warning or critical?)
        nagcgiurl_services = self.monitor_cgi_url + "/include/monitoring/status/Services/" + self.XML_NDO + "/serviceXML.php?" + urllib.urlencode({"num":0, "limit":999, "o":"svcpb", "sort_type":"status", "sid":self.SID})

        # hosts (up or down or unreachable)
        nagcgiurl_hosts = self.monitor_cgi_url + "/include/monitoring/status/Hosts/" + self.XML_NDO + "/hostXML.php?" + urllib.urlencode({"num":0, "limit":999, "o":"hpb", "sort_type":"status", "sid":self.SID})

        # hosts - mostly the down ones
        # unfortunately the hosts status page has a different structure so
        # hosts must be analyzed separately
        try:
            result = self.FetchURL(nagcgiurl_hosts, giveback="xml")
            xmlobj, error = result.result, result.error

            if error != "": return Result(result=copy.deepcopy(xmlobj), error=copy.deepcopy(error))

            # in case there are no children session id is invalid
            if xmlobj == "<response>bad session id</response>" or str(xmlobj) == "Bad Session ID":
                del xmlobj
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), debug="Bad session ID, retrieving new one...")

                # try again...
                self.SID = self._get_sid().result
                result = self.FetchURL(nagcgiurl_hosts, giveback="xml")
                xmlobj, error = result.result, result.error
                if error != "": return Result(result=copy.deepcopy(xmlobj), error=copy.deepcopy(error))

                # a second time a bad session id should raise an error
                if xmlobj == "<response>bad session id</response>" or str(xmlobj) == "Bad Session ID":
                    return Result(result="ERROR", error=str(xmlobj))

            for l in xmlobj.findAll("l"):
                try:
                    # host objects contain service objects
                    if not self.new_hosts.has_key(str(l.hn.text)):
                        self.new_hosts[str(l.hn.text)] = GenericHost()
                        self.new_hosts[str(l.hn.text)].name =  str(l.hn.text)
                        self.new_hosts[str(l.hn.text)].server = self.name
                        self.new_hosts[str(l.hn.text)].status = str(l.cs.text)
                        # disgusting workaround for https://github.com/HenriWahl/Nagstamon/issues/91
                        if self.new_hosts[str(l.hn.text)].status in self.TRANSLATIONS:
                            self.new_hosts[str(l.hn.text)].status = self.TRANSLATIONS[self.new_hosts[str(l.hn.text)].status]
                        self.new_hosts[str(l.hn.text)].attempt, self.new_hosts[str(l.hn.text)].status_type  = str(l.tr.text).split(" ")
                        self.new_hosts[str(l.hn.text)].status_type = self.HARD_SOFT[self.new_hosts[str(l.hn.text)].status_type]
                        self.new_hosts[str(l.hn.text)].last_check = str(l.lc.text)
                        self.new_hosts[str(l.hn.text)].duration = str(l.lsc.text)
                        self.new_hosts[str(l.hn.text)].status_information= str(l.ou.text)
                        if l.find("cih") != None:
                            self.new_hosts[str(l.hn.text)].criticality = str(l.cih.text)
                        else:
                            self.new_hosts[str(l.hn.text)].criticality = ""
                        self.new_hosts[str(l.hn.text)].acknowledged = bool(int(str(l.ha.text)))
                        self.new_hosts[str(l.hn.text)].scheduled_downtime = bool(int(str(l.hdtm.text)))
                        if l.find("is") != None:
                            self.new_hosts[str(l.hn.text)].flapping = bool(int(str(l.find("is").text)))
                        else:
                            self.new_hosts[str(l.hn.text)].flapping = False
                        self.new_hosts[str(l.hn.text)].notifications_disabled = not bool(int(str(l.ne.text)))
                        self.new_hosts[str(l.hn.text)].passiveonly = not bool(int(str(l.ace.text)))
                except:
                    # set checking flag back to False
                    self.isChecking = False
                    result, error = self.Error(sys.exc_info())
                    return Result(result=result, error=error)

            del xmlobj

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # services
        try:
            result = self.FetchURL(nagcgiurl_services, giveback="xml")
            xmlobj, error = result.result, result.error

            if error != "": return Result(result=xmlobj, error=copy.deepcopy(error))

            # in case there are no children session id is invalid
            if xmlobj == "<response>bad session id</response>" or xmlobj == "Bad Session ID":
                # debug
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), debug="Bad session ID, retrieving new one...")
                # try again...
                self.SID = self._get_sid().result
                result = self.FetchURL(nagcgiurl_services, giveback="xml")
                xmlobj, error = result.result, result.error
                if error != "": return Result(result="ERROR", error=copy.deepcopy(error))

            # //----- META SERVICES -----
            # define meta-services xml URL
            nagcgiurl_meta_services = self.monitor_cgi_url + "/include/monitoring/status/Services/" + self.XML_NDO + "/serviceXML.php?" + urllib.urlencode({"num":0, "limit":999, "o":"meta", "sort_type":"status", "sid":self.SID})
            # retrive meta-services xml STATUS
            result_meta = self.FetchURL(nagcgiurl_meta_services, giveback="xml")
            xmlobj_meta, error_meta = result_meta.result, result_meta.error
            if error_meta != "": return Result(result=xmlobj_meta, error=copy.deepcopy(error_meta))
            # INSERT META-services xml at the end of the services xml
            try:
                    xmlobj.insert( -1, xmlobj_meta.reponse )
            except:
                    # set checking flag back to False
                    self.isChecking = False
                    result, error = self.Error(sys.exc_info())
                    return Result(result=result, error=error)
            # do some cleanup
            del xmlobj_meta
            # ----- META SERVICES -----//

            for l in xmlobj.findAll("l"):
                try:
                    # host objects contain service objects
                    if not self.new_hosts.has_key(str(l.hn.text)):
                        self.new_hosts[str(l.hn.text)] = GenericHost()
                        self.new_hosts[str(l.hn.text)].name = str(l.hn.text)
                        self.new_hosts[str(l.hn.text)].status = "UP"
                    # if a service does not exist create its object
                    if not self.new_hosts[str(l.hn.text)].services.has_key(str(l.sd.text)):
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)] = GenericService()
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].host = str(l.hn.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].name = str(l.sd.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].server = self.name
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status = str(l.cs.text)
                        # //----- META SERVICES -----
                        # if it is a meta-service, add the "sdl" fild in parenthesis after the service name. ( used in _set_acknowledge() and _set_recheck() ) :
                        if self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].host == '_Module_Meta':
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].name = '{} ({})'.format( 
                                                                                                                    self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].name,
                                                                                                                    l.sdl.text
                            )
                        # ----- META SERVICES -----//
                        # disgusting workaround for https://github.com/HenriWahl/Nagstamon/issues/91
                        if self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status in self.TRANSLATIONS:
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status = self.TRANSLATIONS[\
                                self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status]
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].attempt, \
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type = str(l.ca.text).split(" ")
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type =\
                            self.HARD_SOFT[self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_type]
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].last_check = str(l.lc.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].duration = str(l.d.text)
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].status_information = str(l.po.text).replace("\n", " ").strip()
                        if l.find("cih") != None:
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].criticality = str(l.cih.text)
                        else:
                            self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].criticality = ""
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].acknowledged = bool(int(str(l.pa.text)))
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].scheduled_downtime = bool(int(str(l.dtm.text)))
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].flapping = bool(int(str(l.find("is").text)))
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].notifications_disabled = not bool(int(str(l.ne.text)))
                        self.new_hosts[str(l.hn.text)].services[str(l.sd.text)].passiveonly = not bool(int(str(l.ac.text)))
                except:
                    # set checking flag back to False
                    self.isChecking = False
                    result, error = self.Error(sys.exc_info())
                    return Result(result=result, error=error)

            # do some cleanup
            del xmlobj

        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        # return True if all worked well
        return Result()


    def _set_acknowledge(self, host, service, author, comment, sticky, notify, persistent, all_services=[]):
        # decision about host or service - they have different URLs
        try:
            if service == "":
                # host
                cgi_data = urllib.urlencode({"p":"20105", "cmd":"14", "host_name":host, \
                        "author":author, "comment":comment, "submit":"Add", "notify":int(notify),\
                        "persistent":int(persistent), "sticky":int(sticky), "ackhostservice":"0", "o":"hd", "en":"1"})
                # debug
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), host=host, debug=self.monitor_cgi_url + "/main.php?"+ cgi_data)

                # running remote cgi command, also possible with GET method
                raw = self.FetchURL(self.monitor_cgi_url + "/main.php?" + cgi_data, giveback="raw")
                del raw

            # if host is acknowledged and all services should be to or if a service is acknowledged
            # (and all other on this host too)
            if service != "" or len(all_services) > 0:
                # service(s) @ host
                # if all_services is empty only one service has to be checked - the one clicked
                # otherwise if there all services should be acknowledged
                if len(all_services) == 0: all_services = [service]

                # acknowledge all services on a host
                for s in all_services:
                    # service @ host
                    # in case the Centreon guys one day fix their typos "persistent" and
                    # "persistent" will both be given (it is "persistant" in scheduling for downtime)
                    cgi_data = urllib.urlencode({"p":"20215", "cmd":"15", "host_name":host, \
                            "author":author, "comment":comment, "submit":"Add", "notify":int(notify),\
                            "service_description":s, "force_check":"1", \
                            "persistent":int(persistent), "persistant":int(persistent),\
                            "sticky":int(sticky), "o":"svcd", "en":"1"})
                    # //----- META SERVICES -----
                    # in case of a meta-service, extract the "sdl" fild from the service name :
                    if host == '_Module_Meta':
                        m =  re.search(r"^.+ \((?P<sdl>.+)\)$", s)
                        if m:
                            sdl = m.group('sdl')
                            cgi_data = urllib.urlencode({"p":"20206", "o":"meta", "cmd":"70", \
                                                                        "select["+host+";"+sdl+"]":"1", "limit":"0"})
                    # ----- META SERVICES -----//
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        self.Debug(server=self.get_name(), host=host, service=s, debug=self.monitor_cgi_url + "/main.php?" + cgi_data)

                    # running remote cgi command with GET method, for some strange reason only working if
                    # giveback is "raw"
                    raw = self.FetchURL(self.monitor_cgi_url + "/main.php?" + cgi_data, giveback="raw")
                    del raw
        except:
            self.Error(sys.exc_info())


    def _set_recheck(self, host, service):
        """
        host and service ids are needed to tell Centreon what whe want
        """
        # yes this procedure IS resource waste... suggestions welcome!
        try:
        # decision about host or service - they have different URLs
            if host == '_Module_Meta':
                m =  re.search(r"^.+ \((?P<sdl>.+)\)$", service)
                if m:
                    sdl = m.group('sdl')
                    cgi_data = urllib.urlencode({"p":"20206", "o":"meta", "cmd":"3", \
                                                                "select["+host+";"+sdl+"]":"1", "limit":"0"})
                    url = self.monitor_cgi_url + "/main.php?" + cgi_data
            elif service == "":
                # ... it can only be a host, get its id
                host_id = self._get_host_id(host)
                # fill and encode CGI data
                cgi_data = urllib.urlencode({"cmd":"host_schedule_check", "actiontype":1,\
                                             "host_id":host_id, "sid":self.SID})
                url = self.monitor_cgi_url + "/include/monitoring/objectDetails/xml/hostSendCommand.php?" + cgi_data
                del host_id
            else:
                # service @ host
                host_id, service_id = self._get_host_and_service_id(host, service)
                # fill and encode CGI data
                cgi_data = urllib.urlencode({"cmd":"service_schedule_check", "actiontype":1,\
                                             "host_id":host_id, "service_id":service_id, "sid":self.SID})
                url = self.monitor_cgi_url + "/include/monitoring/objectDetails/xml/serviceSendCommand.php?" + cgi_data
                del host_id, service_id
            # execute POST request
            raw = self.FetchURL(url, giveback="raw")
            del raw
        except:
            self.Error(sys.exc_info())


    def _set_downtime(self, host, service, author, comment, fixed, start_time, end_time, hours, minutes):
        """
        gets actual host and service ids and apply them to downtime cgi
        """
        try:
            if service == "":
                # host
                host_id = self._get_host_id(host)
                cgi_data = urllib.urlencode({"p":"20106",\
                                             "host_id":host_id,\
                                             "host_or_hg[host_or_hg]":1,\
                                             "submitA":"Save",\
                                             "persistent":int(fixed),\
                                             "persistant":int(fixed),\
                                             "start":start_time,\
                                             "end":end_time,\
                                             "comment":comment,\
                                             "o":"ah"})
                # debug
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), host=host, debug=self.monitor_cgi_url + "/main.php?" + cgi_data)

            else:
                # service
                host_id, service_id = self._get_host_and_service_id(host, service)
                cgi_data = urllib.urlencode({"p":"20218",\
                                             "host_id":host_id,\
                                             "service_id":service_id,\
                                             "submitA":"Save",\
                                             "persistant":int(fixed),\
                                             "start":start_time,\
                                             "end":end_time,\
                                             "comment":comment,\
                                             "o":"as"})
                # debug
                if str(self.conf.debug_mode) == "True":
                    self.Debug(server=self.get_name(), host=host, service=service, debug=self.monitor_cgi_url + "/main.php?" + cgi_data)

            # running remote cgi command
            raw = self.FetchURL(self.monitor_cgi_url + "/main.php", giveback="raw", cgi_data=cgi_data)
            del raw
        except:
            self.Error(sys.exc_info())


    def Hook(self):
        """
        in case count is down get a new SID, just in case
        was kicked out but as to be seen in https://sourceforge.net/p/nagstamon/bugs/86/ there are problems with older
        Centreon installations so this should come back
        """
        # renewing the SID once an hour might be enough
        # maybe this is unnecessary now that we authenticate via login/password, no md5
        if self.SIDcount >= 3600:
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="Old SID: " + self.SID + " " + str(self.Cookie))
            self.SID = self._get_sid().result
            if str(self.conf.debug_mode) == "True":
                self.Debug(server=self.get_name(), debug="New SID: " + self.SID + " " + str(self.Cookie))
            self.SIDcount = 0
        else:
            self.SIDcount += 1
