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

# for python2 and upcomping python3 compatiblity
from __future__ import print_function, absolute_import, unicode_literals


STATES = ['WARNING', 'UNKNOWN', 'CRITICAL', 'UNREACHABLE', 'DOWN']


class GenericObject(object):

    """
    template for hosts and services
    """

    def __init__(self):
        self.name = ''
        self.status = ''
        self.status_information = ''
        # default state is soft, to be changed by status_type check
        self.status_type = ''
        self.last_check = ''
        self.duration = ''
        self.attempt = ''
        self.passiveonly = False
        self.acknowledged = False
        self.notifications_disabled = False
        self.flapping = False
        self.scheduled_downtime = False
        # compress all flags like acknowledged and flapping into one string
        self.host_flags = ''
        self.service_flags = ''
        self.visible = True
        # Check_MK also has site info
        self.site = ''
        # server to be added to hash
        self.server = ''
        # might help in Qt
        self.host = ''
        self.service = ''
        self.dummy_column = ''

    def is_passive_only(self):
        return bool(self.passiveonly)

    def is_flapping(self):
        return bool(self.flapping)

    def has_notifications_disabled(self):
        return bool(self.notifications)

    def is_acknowledged(self):
        return bool(self.acknowledged)

    def is_in_scheduled_downtime(self):
        return bool(self.scheduled_downtime)

    def is_visible(self):
        return bool(self.visible)

    def get_name(self):
        """
            return stringified name
        """
        return str(self.name)

    def get_host_name(self):
        """
            Extracts host name from status item.
            Presentation purpose.
        """
        return ''

    def get_service_name(self):
        """
            Extracts service name from status item.
            Presentation purpose.
        """
        return ''

    def get_hash(self):
        """
            returns hash of event status information - different for host and service thus empty here
        """
        return ''

    def get_columns(self, columns_wanted):
        """
            Yield host/service status information for treeview table columns
        """
        for c in columns_wanted:
            yield str(self.__dict__[c])


class GenericHost(GenericObject):

    """
        one host which is monitored by a Nagios server, gets populated with services
    """

    def __init__(self):
        GenericObject.__init__(self)
        # take all the faulty services on host
        self.services = dict()

    def get_host_name(self):
        return str(self.name)

    def is_host(self):
        """
            decides where to put acknowledged/downtime pixbufs in Liststore for Treeview in Popwin
        """
        return True

    def get_hash(self):
        """
        return hash for event history tracking
        """
        return " ".join((self.server, self.site, self.name, self.status))


class GenericService(GenericObject):

    """
        one service which runs on a host
    """

    def __init__(self):
        GenericObject.__init__(self)

    def get_host_name(self):
        return str(self.host)

    def get_service_name(self):
        return str(self.name)

    def is_host(self):
        """
            decides where to put acknowledged/downtime pixbufs in Liststore for Treeview in Popwin
        """
        return False

    def get_hash(self):
        """
            return hash for event history tracking
        """
        return " ".join((self.server, self.site, self.host, self.name, self.status))


class Result(object):

    """
    multi purpose result object, used in Servers.Generic.FetchURL()
    """
    result = ''
    error = ''
    status_code = 0

    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds:
            self.__dict__[k] = kwds[k]
