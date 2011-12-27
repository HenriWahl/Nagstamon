# encoding: utf-8

# Pingdom plugin for Nagstamon
# Copyright (C) 2011 Julien Rottenberg <julien@rottenberg.info>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
"""
Pingdom specific class

"""




# https://github.com/drcraig/python-restful-pingdom
import PingdomAPI

import datetime
from Nagstamon.Objects import *
from Nagstamon.Server.Generic import GenericServer


class PingdomServer(GenericServer):
    """
special treatment for pingdom RESTful based API
"""

    TYPE = 'Pingdom'

    # http://www.pingdom.com/services/api-documentation-rest/#ResourceChecks
    # Change it if you know what you are doing
    # ie : you shouldn't have to
    pingdom_apikey = "tn3ee3eueg1ug6o480n8mr23bv0r8k66"
    pingdom_url = "https://pp.pingdom.com/index.php/member"

    # Put the apikey in the server url (until we have a better field name)
    def init_HTTP(self):
        self.Debug("username: ", self.get_username())
        self.Debug("password: ", self.get_password())

    def open_nagios(self):
        webbrowser.open(self.pingdom_url + "/default")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(),
            debug="Open monitor web page " + self.pingdom_url + "/default")

    def open_services(self):
        webbrowser.open(self.pingdom_url + "/reports/detailed")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(),
            debug="Open services web page " +
            self.pingdom_url +
            "/reports/detailed")

    def open_hosts(self):
        webbrowser.open(self.pingdom_url + "/reports/detailed")
        # debug
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(),
            debug="Open hosts web page " +
            self.pingdom_url +
            "/reports/detailed")

    def GetHost(self, host):
        """
go to the 'host' defined as hostname in the pingdom checks
"""
        return Result(result=host)

    def open_tree_view(self, host, service=""):
        """
open monitor from treeview context menu
"""
        if str(self.conf.debug_mode) == "True":
            self.Debug(server=self.get_name(),
            host=host, service=service,
            debug="Open monitor page " +
            self.pingdom_url +
            '/reports/detailed/show/' +
            host)
        webbrowser.open(self.pingdom_url + '/reports/detailed/show/' + host)

    def _get_status(self):
        """
Get status from Pingdom
"""
        self.i = 0

        # set checking flag to be sure only one thread cares about Pingdom
        self.isChecking = True
        try:
            result = pingdomapi.Pingdom(username=self.get_username(),
                        password=self.get_password(),
                        appkey=self.pingdom_apikey).method("checks")

            self.Debug("Total checks: ", str(len(result['checks'])))

            for c in result['checks']:
                self.Debug("Check " + str(self.i) + ' : ' + str(c))

                if c["status"] != 'up':
                    # pp.id --> n.host # we have one hostname/id
                    # pp.name --> n.servicename # that can have many checks

                    last = datetime.datetime.fromtimestamp(c["lasttesttime"])

                    # states come in lower case from pingdom
                    # Pingdom --> Nagios
                    # Pingdom API http://goo.gl/xDXdW
                    if c["status"] == 'down':
                        status = 'CRITICAL'
                    elif c["status"] == 'unconfirmed_down':
                        status = 'WARNING'
                    else:
                        status = 'UNKNOWN'

                    self.new_hosts[c["id"]] = GenericHost()
                    self.new_hosts[c["id"]].name = c["id"]
                    # pingdom manages only services, hosts are always up
                    # Todo : check is a ping --> it is a host ?
                    self.new_hosts[c["id"]].status = "UP"

                    self.new_hosts[c["id"]].services[c["name"]] = GenericService()
                    self.new_hosts[c["id"]].services[c["name"]].host = c["id"]
                    self.new_hosts[c["id"]].services[c["name"]].name = c["name"]
                    self.new_hosts[c["id"]].services[c["name"]].last_check = last
                    self.new_hosts[c["id"]].services[c["name"]].attempt = "N/A"
                    self.new_hosts[c["id"]].services[c["name"]].duration = "N/A"
                    self.new_hosts[c["id"]].services[c["name"]].status_information = "%s : %s" % (c["type"], c["hostname"])
                    self.new_hosts[c["id"]].services[c["name"]].status = status

                    self.Debug("Parsed Check " + str(self.i) + ' : ' + ' ' + str(c["id"]) + ' ' + c['name'] + ' ' + c['hostname'] + ' ' + status + ' ' + str(last))

                self.i += 1
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()
