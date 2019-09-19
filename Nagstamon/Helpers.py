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

import datetime
# import subprocess  # not used
import re
import sys
import traceback
import os
import psutil
import getpass
import webbrowser

# import md5 for centreon url autologin encoding
from hashlib import md5

from Nagstamon.Config import conf

# queue.Queue() needs threading module which might be not such a good idea to be used
# because QThread is already in use
# get debug queue from nagstamon.py
# ##debug_queue = sys.modules['__main__'].debug_queue

# states needed for gravity comparison for notification and Generic.py
STATES = ['UP',
          'UNKNOWN',
          'INFORMATION',
          'WARNING',
          'AVERAGE',
          'HIGH',
          'CRITICAL',
          'DISASTER',
          'UNREACHABLE',
          'DOWN']

# sound at the moment is only available for these states
STATES_SOUND = ['WARNING',
                'CRITICAL',
                'DOWN']


def not_empty(x):
    '''
        tiny helper function for BeautifulSoup in server Generic.py to filter text elements
    '''
    return bool(x.replace('&nbsp;', '').strip())


def is_found_by_re(string, pattern, reverse):
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


def host_is_filtered_out_by_re(host, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_host_enabled is True:
            return is_found_by_re(host, conf.re_host_pattern, conf.re_host_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except Exception:
        traceback.print_exc(file=sys.stdout)


def ServiceIsFilteredOutByRE(service, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_service_enabled is True:
            return is_found_by_re(service, conf.re_service_pattern, conf.re_service_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except Exception:
        traceback.print_exc(file=sys.stdout)


def StatusInformationIsFilteredOutByRE(status_information, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_status_information_enabled is True:
            return is_found_by_re(status_information, conf.re_status_information_pattern, conf.re_status_information_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except Exception:
        traceback.print_exc(file=sys.stdout)

def DurationIsFilteredOutByRE(duration, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_duration_enabled is True:
            return is_found_by_re(duration, conf.re_duration_pattern, conf.re_duration_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except Exception:
        traceback.print_exc(file=sys.stdout)

def AttemptIsFilteredOutByRE(attempt, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_attempt_enabled is True:
            return is_found_by_re(attempt, conf.re_attempt_pattern, conf.re_attempt_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except Exception:
        traceback.print_exc(file=sys.stdout)

def GroupsIsFilteredOutByRE(groups, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_groups_enabled is True:
            return is_found_by_re(groups, conf.re_groups_pattern, conf.re_groups_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except Exception:
        traceback.print_exc(file=sys.stdout)

def CriticalityIsFilteredOutByRE(criticality, conf=None):
    """
        helper for applying RE filters in Generic.GetStatus()
    """
    try:
        if conf.re_criticality_enabled is True:
            return is_found_by_re(criticality, conf.re_criticality_pattern, conf.re_criticality_reverse)
        # if RE are disabled return True because host is not filtered
        return False
    except Exception:
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
                return "%02sh" % (hms[0])
            elif len(hms) == 2:
                return "%02sm %02ss" % (hms[1], hms[2])
            else:
                return "%sh %02sm %02ss" % (hms[0], hms[1], hms[2])
        else:
            # waste is waste - does anyone need it?
            days, waste, hms = str(timedelta).split(" ")
            hms = hms.split(":")
            return "%sd %sh %02sm %02ss" % (days, hms[0], hms[1], hms[2])
    except Exception:
        traceback.print_exc(file=sys.stdout)
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
        if td.days > 0:
            return "%sd %sh %02dm %02ds" % (td.days, h, m, s)
        elif h > 0:
            return "%sh %02dm %02ds" % (h, m, s)
        elif m > 0:
            return "%02dm %02ds" % (m, s)
        else:
            return "%02ds" % (s)
    except Exception:
        traceback.print_exc(file=sys.stdout)


# unified machine readable date might go back to module Actions
def MachineSortableDate(raw):
    """
    Try to compute machine readable date for all types of monitor servers
    """
    # dictionary for duration date string components
    d = {'M': 0, 'w': 0, 'd': 0, 'h': 0, 'm': 0, 's': 0}

    # if for some reason the value is empty/none make it compatible: 0s
    if raw is None:
        raw = '0s'

    # Check_MK style - added new variants in 1.4.x, based on abbreviations with spaces :-(
    if ('-' in raw and ':' in raw) or\
            ('sec' in raw or 'min' in raw or 'hrs' in raw or 'days' in raw or\
             ' s' in raw or ' m' in raw or ' h' in raw or ' d' in raw):
        # check_mk has different formats - if duration takes too long it changes its scheme
        if '-' in raw and ':' in raw:
            datepart, timepart = raw.split(' ')
            # need to convert years into months for later comparison
            Y, M, D = datepart.split('-')
            d['M'] = int(Y) * 12 + int(M)
            d['d'] = int(D)
            # time does not need to be changed
            h, m, s = timepart.split(':')
            d['h'], d['m'], d['s'] = int(h), int(m), int(s)
            del datepart, timepart, Y, M, D, h, m, s
        else:
            # recalculate a timedelta of the given value
            if 'sec' in raw or ' s' in raw:
                d['s'] = raw.split(' ')[0].split('.')[0]
                delta = datetime.datetime.now() - datetime.timedelta(seconds=int(d['s']))
            elif 'min' in raw or ' m' in raw:
                d['m'] = raw.split(' ')[0].split('.')[0]
                delta = datetime.datetime.now() - datetime.timedelta(minutes=int(d['m']))
            elif 'hrs' in raw or ' h' in raw:
                d['h'] = raw.split(' ')[0]
                delta = datetime.datetime.now() - datetime.timedelta(hours=int(d['h']))
            elif 'days' in raw or ' d' in raw:
                d['d'] = raw.split(' ')[0]
                delta = datetime.datetime.now() - datetime.timedelta(days=int(d['d']))
            else:
                delta = datetime.datetime.now()

            Y, M, d['d'], d['h'], d['m'], d['s'] = delta.strftime('%Y %m %d %H %M %S').split(' ')
            # need to convert years into months for later comparison
            d['M'] = int(Y) * 12 + int(M)

        # int-ify d
        for i in d:
            # workaround to make values negative to fix Check_MK's different order
            d[i] = -int(d[i])
    else:
        # strip and replace necessary for Nagios duration values,
        # split components of duration into dictionary
        for c in raw.strip().replace('  ', ' ').split(' '):
            number, period = c[0:-1], c[-1]
            # attempt to be more robust in case of https://github.com/HenriWahl/Nagstamon/issues/405
            try:
                d[period] = int(number)
            except:
                d[period] = 0
            del number, period

    # convert collected duration data components into seconds for being comparable
    return(16934400 * d['M'] + 604800 * d['w'] + 86400 * d['d'] + 3600 * d['h'] + 60 * d['m'] + d['s'])


def MD5ify(string):
    """
        makes something md5y of a given username or password for Centreon web interface access
    """
    return md5(string).hexdigest()


def lock_config_folder(folder):
    '''
        Locks the config folder by writing a PID file into it.
        The lock is relative to user name and system's boot time.
        Returns True on success, False when lock failed

        Return True too if there is any locking error - if no locking ins possible it might run as well
        This is also the case if some setup uses the nagstamon.config directory which most probably
        will be read-only
    '''
    pidFilePath = os.path.join(folder, 'nagstamon.pid')

    try:
        # Open the file for rw or create a new one if missing
        if os.path.exists(pidFilePath):
            mode = 'r+t'
        else:
            mode = 'wt'

        with open(pidFilePath, mode, newline=None) as pidFile:
            curPid = os.getpid()
            curBootTime = int(psutil.boot_time())
            curUserName = getpass.getuser().replace('@', '_').strip()

            pid = None
            bootTime = None
            userName = None
            if mode.startswith('r'):
                try:
                    procInfo = pidFile.readline().strip().split('@')
                    pid = int(procInfo[0])
                    bootTime = int(procInfo[1])
                    userName = procInfo[2].strip()
                except(ValueError, IndexError):
                    pass

            if pid is not None and bootTime is not None and userName is not None:
                # Found a pid stored in the pid file, check if its still running
                if bootTime == curBootTime and userName == curUserName and psutil.pid_exists(pid):
                    return False

            pidFile.seek(0)
            pidFile.truncate()
            pidFile.write('{}@{}@{}'.format(curPid, curBootTime, curUserName))
    except Exception as err:
        print(err)

    return True


# the following functions are used for sorted() in sort_data_array()
def compare_host(item):
    return(item.lower())


def compare_service(item):
    return(item.lower())


def compare_status(item):
    return(STATES.index(item))


def compare_last_check(item):
    return(MachineSortableDate(item))


def compare_duration(item):
    return(MachineSortableDate(item))


def compare_attempt(item):
    return(item)


def compare_status_information(item):
    return(item.lower())


def webbrowser_open(url):
    """
        decide if default or custom browser is used for various tasks
        used by almost all
    """
    if conf.use_default_browser:
        webbrowser.open(url)
    else:
        webbrowser.get('{0} %s &'.format(conf.custom_browser)).open(url)


# depending on column different functions have to be used
# 0 + 1 are column "Hosts", 1 + 2 are column "Service" due to extra font flag pictograms
SORT_COLUMNS_FUNCTIONS = {0: compare_host,
        1: compare_host,
        2: compare_service,
        3: compare_service,
        4: compare_status,
        5: compare_last_check,
        6: compare_duration,
        7: compare_attempt,
        8: compare_status_information,
        9: compare_status_information}
