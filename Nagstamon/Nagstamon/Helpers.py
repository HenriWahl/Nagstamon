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

import threading
import time
import datetime
import webbrowser
import subprocess
import re
import sys
import traceback

# import md5 for centreon url autologin encoding
from hashlib import md5

# flag which indicates if already rechecking all
###RecheckingAll = False

# experimenting with new debug queue
# queue.Queue() needs threading module which might be not such a good idea to be used
# because QThread is already in use
debug_queue = list()

# states needed for gravity comparison for notification and Generic.py
STATES = ['UP', 'UNKNOWN', 'WARNING', 'CRITICAL', 'UNREACHABLE', 'DOWN']


def RefreshAllServers(servers=None, output=None, conf=None):
    """
    one refreshing action, starts threads, one per polled server
    """
    # first delete all freshness flags
    output.UnfreshEventHistory()

    for server in servers.values():
        # check if server is already checked
        if server.isChecking == False and conf.servers[server.get_name()].enabled == True:
            #debug
            if conf.debug_mode:
                server.Debug(server=server.get_name(), debug="Checking server...")

            server.thread.Refresh()

            # set server status for status field in popwin
            server.status = "Refreshing"
            gobject.idle_add(output.popwin.UpdateStatus, server)



class RecheckAll(threading.Thread):
    """
    recheck all services/hosts
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self, name="RecheckAll")
        self.setDaemon(1)


    def run(self):
        # get RecheckingAll flag to decide if rechecking all is possible (only if not already running)
        global RecheckingAll

        if RecheckingAll == False:
            RecheckingAll = True
            # put all rechecking threads into one dictionary
            rechecks_dict = dict()
            try:
                # debug
                if str(self.conf.debug_mode) == "True":
                    # workaround, take Debug method from first server reachable
                    self.servers.values()[0].Debug(debug="Recheck all: Rechecking all services on all hosts on all servers...")
                for server in self.servers.values():
                    # only test enabled servers and only if not already
                    if str(self.conf.servers[server.get_name()].enabled) == "True":
                        # set server status for status field in popwin
                        server.status = "Rechecking all started"
                        gobject.idle_add(self.output.popwin.UpdateStatus, server)

                        # special treatment for Check_MK Multisite because there is only one URL call necessary
                        if server.type != "Check_MK Multisite":
                            for host in server.hosts.values():
                                # construct an unique key which refers to rechecking thread in dictionary
                                rechecks_dict[server.get_name() + ": " + host.get_name()] = Recheck(server=server, host=host.get_name(), service="")
                                rechecks_dict[server.get_name() + ": " + host.get_name()].start()
                                # debug
                                if str(self.conf.debug_mode) == "True":
                                    server.Debug(server=server.get_name(), host=host.get_name(), debug="Rechecking...")
                                for service in host.services.values():
                                    # dito
                                    if service.is_passive_only() == True:
                                        continue
                                    rechecks_dict[server.get_name() + ": " + host.get_name() + ": " + service.get_name()] = Recheck(server=server, host=host.get_name(), service=service.get_name())
                                    rechecks_dict[server.get_name() + ": " + host.get_name() + ": " + service.get_name()].start()
                                    # debug
                                    if str(self.conf.debug_mode) == "True":
                                        server.Debug(server=server.get_name(), host=host.get_name(), service=service.get_name(), debug="Rechecking...")
                        else:
                            # Check_MK Multisite does it its own way
                            server.recheck_all()
                # wait until all rechecks have been done
                while len(rechecks_dict) > 0:
                    # debug
                    if str(self.conf.debug_mode) == "True":
                        # once again taking .Debug() from first server
                        self.servers.values()[0].Debug(server=server.get_name(), debug="Recheck all: # of checks which still need to be done: " + str(len(rechecks_dict)))

                    for i in rechecks_dict.copy():
                        # if a thread is stopped pop it out of the dictionary
                        if rechecks_dict[i].isAlive() == False:
                            rechecks_dict.pop(i)
                    # wait a second
                    time.sleep(1)

                # debug
                if str(self.conf.debug_mode) == "True":
                    # once again taking .Debug() from first server
                    self.servers.values()[0].Debug(server=server.get_name(), debug="Recheck all: All servers, hosts and services are rechecked.")
                # reset global flag
                RecheckingAll = False

                # after all and after a short delay to let the monitor apply the recheck requests get_status all to make changes visible soon
                time.sleep(5)
                RefreshAllServers(servers=self.servers, output=self.output, conf=self.conf)
                # do some cleanup
                del rechecks_dict

            except:
                RecheckingAll = False
        else:
            # debug
            if str(self.conf.debug_mode) == "True":
                # once again taking .Debug() from first server
                self.servers.values()[0].Debug(debug="Recheck all: Already rechecking all services on all hosts on all servers.")


class SubmitCheckResult(threading.Thread):
    """
    exceute remote cgi command with parameters from submit check result dialog
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)

    def run(self):
        self.server.set_submit_check_result(self)


class Notification(threading.Thread):
    """
        Flash statusbar in a threadified way to omit hanging gui
    """
    def __init__(self, **kwds):
        # add all keywords to object, every mode searchs inside for its favorite arguments/keywords
        for k in kwds: self.__dict__[k] = kwds[k]
        threading.Thread.__init__(self)
        self.setDaemon(1)


    def run(self):
        # counter for repeated sound
        soundcount = 0
        # in case of notifying in statusbar do some flashing and honking
        while self.output.Notifying == True:
            # as long as flashing flag is set statusbar flashes until someone takes care
            if self.output.statusbar.Flashing == True:
                if self.output.statusbar.isShowingError == False:
                    # check again because in the mean time this flag could have been changed by NotificationOff()
                    gobject.idle_add(self.output.statusbar.Flash)
            # Ubuntu AppIndicator simulates flashing by brute force
            if str(self.conf.appindicator) == "True":
                if self.output.appindicator.Flashing == True:
                    gobject.idle_add(self.output.appindicator.Flash)
            # if wanted play notification sound, if it should be repeated every minute (2*interval/0.5=interval) do so.
            if str(self.conf.notification_sound) == "True":
                if soundcount == 0:
                    sound = PlaySound(sound=self.sound, Resources=self.Resources, conf=self.conf, servers=self.servers)
                    sound.start()
                    soundcount += 1
                elif str(self.conf.notification_sound_repeat) == "True" and\
                        soundcount >= 2*int(self.conf.update_interval_seconds) and\
                        len([k for k,v in self.output.events_history.items() if v == True]) != 0:
                    soundcount = 0
                else:
                    soundcount += 1
            time.sleep(0.5)
        # reset statusbar
        self.output.statusbar.Label.set_markup(self.output.statusbar.statusbar_labeltext)


def not_empty(x):
    '''
        tiny helper function for BeautifulSoup in server Generic.py to filter text elements
    '''
    return bool(x.replace('&nbsp;', '').strip())


def OpenNagstamonDownload(output=None):
    """
        Opens Nagstamon Download page after being offered by update check
    """
    # first close popwin
    output.popwin.Close()
    # start browser with URL
    webbrowser.open("https://nagstamon.ifw-dresden.de/download")


def IsFoundByRE(string, pattern, reverse):
    """
    helper for context menu actions in context menu - hosts and services might be filtered out
    also useful for services and hosts and status information
    """
    pattern = re.compile(pattern)
    if len(pattern.findall(string)) > 0:
        if str(reverse) == "True":
            return False
        else:
            return True
    else:
        if str(reverse) == "True":
            return True
        else:
            return False


def HostIsFilteredOutByRE(host, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_host_enabled == True:
            return IsFoundByRE(host, conf.re_host_pattern, conf.re_host_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except:
        import traceback
        traceback.print_exc(file=sys.stdout)


def ServiceIsFilteredOutByRE(service, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_service_enabled == True:
            return IsFoundByRE(service, conf.re_service_pattern, conf.re_service_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except:
        import traceback
        traceback.print_exc(file=sys.stdout)


def StatusInformationIsFilteredOutByRE(status_information, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_status_information_enabled == True:
            return IsFoundByRE(status_information, conf.re_status_information_pattern, conf.re_status_information_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except:
        import traceback
        traceback.print_exc(file=sys.stdout)


def CriticalityIsFilteredOutByRE(criticality, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_criticality_enabled == True:
            return IsFoundByRE(criticality, conf.re_criticality_pattern, conf.re_criticality_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except:
        import traceback
        traceback.print_exc(file=sys.stdout)


def HumanReadableDurationFromSeconds(seconds):
    """
    convert seconds given by Opsview to the form Nagios gives them
    like 70d 3h 34m 34s
    """
    timedelta = str(datetime.timedelta(seconds=int(seconds)))
    try:
        if timedelta.find("day") == -1:
            hms = timedelta.split(":")
            if len(hms) == 1:
                return "0d 0h 0m %ss" % (hms[0])
            elif len(hms) == 2:
                return "0d 0h %sm %ss" % (hms[0], hms[1])
            else:
                return "0d %sh %sm %ss" % (hms[0], hms[1], hms[2])
        else:
            # waste is waste - does anyone need it?
            days, waste, hms = str(timedelta).split(" ")
            hms = hms.split(":")
            return "%sd %sh %sm %ss" % (days, hms[0], hms[1], hms[2])
    except:
        # in case of any error return seconds we got
        return seconds


def HumanReadableDurationFromTimestamp(timestamp):
    """
    Thruk server supplies timestamp of latest state change which
    has to be subtracted from .now()
    """
    try:
        td = datetime.datetime.now() - datetime.datetime.fromtimestamp(int(timestamp))
        h = int(td.seconds / 3600)
        m = int(td.seconds % 3600 / 60)
        s = int(td.seconds % 60)
        return "%sd %sh %sm %ss" % (td.days, h, m ,s)
    except:
        import traceback
        traceback.print_exc(file=sys.stdout)


def MachineSortableDate(raw):
    """
    Monitors gratefully show duration even in weeks and months which confuse the
    sorting of popup window sorting - this functions wants to fix that
    """
    # dictionary for duration date string components
    d = {"M":0, "w":0, "d":0, "h":0, "m":0, "s":0}

    # if for some reason the value is empty/none make it compatible: 0s
    if raw == None: raw = "0s"

    # strip and replace necessary for Nagios duration values,
    # split components of duration into dictionary
    for c in raw.strip().replace("  ", " ").split(" "):
        number, period = c[0:-1],c[-1]
        d[period] = int(number)
        del number, period
    # convert collected duration data components into seconds for being comparable
    return 16934400 * d["M"] + 604800 * d["w"] + 86400 * d["d"] + 3600 * d["h"] + 60 * d["m"] + d["s"]


def MachineSortableDateMultisite(raw):
    """
    Multisite dates/times are so different to the others so it has to be handled separately
    """

    # dictionary for duration date string components
    d = {"M":0, "d":0, "h":0, "m":0, "s":0}

    # if for some reason the value is empty/none make it compatible: 0 sec
    if raw == None: raw = "0 sec"

    # check_mk has different formats - if duration takes too long it changes its scheme
    if "-" in raw and ":" in raw:
        datepart, timepart = raw.split(" ")
        # need to convert years into months for later comparison
        Y, M, D = datepart.split("-")
        d["M"] = int(Y) * 12 + int(M)
        d["d"] = int(D)
        # time does not need to be changed
        h, m, s = timepart.split(":")
        d["h"], d["m"], d["s"] = int(h), int(m), int(s)
        del datepart, timepart, Y, M, D, h, m, s
    else:
        # recalculate a timedelta of the given value
        if "sec" in raw:
            d["s"] = raw.split(" ")[0]
            delta = datetime.datetime.now() - datetime.timedelta(seconds=int(d["s"]))
        elif "min" in raw:
            d["m"] = raw.split(" ")[0]
            delta = datetime.datetime.now() - datetime.timedelta(minutes=int(d["m"]))
        elif "hrs" in raw:
            d["h"] = raw.split(" ")[0]
            delta = datetime.datetime.now() - datetime.timedelta(hours=int(d["h"]))
        elif "days" in raw:
            d["d"] = raw.split(" ")[0]
            delta = datetime.datetime.now() - datetime.timedelta(days=int(d["d"]))
        else:
            delta = datetime.datetime.now()

        Y, M, d["d"], d["h"], d["m"], d["s"] = delta.strftime("%Y %m %d %H %M %S").split(" ")
        # need to convert years into months for later comparison
        d["M"] = int(Y) * 12 + int(M)

    # int-ify d
    for i in d: d[i] = int(d[i])

    # convert collected duration data components into seconds for being comparable
    return 16934400 * d["M"] + 86400 * d["d"] + 3600 * d["h"] + 60 * d["m"] + d["s"]


# unified machine readable date might go back to module Actions
def UnifiedMachineSortableDate(raw):
    """
    Try to compute machine readable date for all types of monitor servers
    """
    # dictionary for duration date string components
    d = {"M":0, "w":0, "d":0, "h":0, "m":0, "s":0}

    # if for some reason the value is empty/none make it compatible: 0s
    if raw == None: raw = "0s"

    # Check_MK style
    if ("-" in raw and ":" in raw) or ("sec" in raw or "min" in raw or "hrs" in raw or "days" in raw):
        # check_mk has different formats - if duration takes too long it changes its scheme
        if "-" in raw and ":" in raw:
            datepart, timepart = raw.split(" ")
            # need to convert years into months for later comparison
            Y, M, D = datepart.split("-")
            d["M"] = int(Y) * 12 + int(M)
            d["d"] = int(D)
            # time does not need to be changed
            h, m, s = timepart.split(":")
            d["h"], d["m"], d["s"] = int(h), int(m), int(s)
            del datepart, timepart, Y, M, D, h, m, s
        else:
            # recalculate a timedelta of the given value
            if "sec" in raw:
                d["s"] = raw.split(" ")[0]
                delta = datetime.datetime.now() - datetime.timedelta(seconds=int(d["s"]))
            elif "min" in raw:
                d["m"] = raw.split(" ")[0]
                delta = datetime.datetime.now() - datetime.timedelta(minutes=int(d["m"]))
            elif "hrs" in raw:
                d["h"] = raw.split(" ")[0]
                delta = datetime.datetime.now() - datetime.timedelta(hours=int(d["h"]))
            elif "days" in raw:
                d["d"] = raw.split(" ")[0]
                delta = datetime.datetime.now() - datetime.timedelta(days=int(d["d"]))
            else:
                delta = datetime.datetime.now()

            Y, M, d["d"], d["h"], d["m"], d["s"] = delta.strftime("%Y %m %d %H %M %S").split(" ")
            # need to convert years into months for later comparison
            d["M"] = int(Y) * 12 + int(M)

        # int-ify d
        for i in d: d[i] = int(d[i])
    else:
        # strip and replace necessary for Nagios duration values,
        # split components of duration into dictionary
        for c in raw.strip().replace("  ", " ").split(" "):
            number, period = c[0:-1],c[-1]
            d[period] = int(number)
            del number, period

    # convert collected duration data components into seconds for being comparable
    return 16934400 * d["M"] + 604800 * d["w"] + 86400 * d["d"] + 3600 * d["h"] + 60 * d["m"] + d["s"]


def MD5ify(string):
    """
    makes something md5y of a given username or password for Centreon web interface access
    """
    return md5(string).hexdigest()


def RunNotificationAction(action):
    """
    run action for notification
    """
    subprocess.Popen(action, shell=True)
