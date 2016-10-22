#!/usr/bin/env python3
# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2016 Henri Wahl <h.wahl@ifw-dresden.de> et al. Maik Lüdeke <m.luedeke@ifw-dresden.de>
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

import sys
import socket
# import datetime  # never used
import re

# fix/patch for https://bugs.launchpad.net/ubuntu/+source/nagstamon/+bug/732544
socket.setdefaulttimeout(30)
# checks if there is a current value for the variable, if not the default value will be returned


def checkDefaultValue(value, default):
    if value is None:
        return default
    else:
        return value


# extracts the time from the start_time and adds hours and minutes
def createEndTime(info_dict):

    # extracts the time from arg 'start_time'
    # then adds the hours/minutes to the start_date and reassambles the string
    regex = re.compile('(.*)\s(\d{1,2})([\:\.])(\d{1,2})(.*)')

    time_string = re.search(regex, info_dict['start_time'])

    start_hour = int(time_string.group(2))
    separator = (time_string.group(3))
    start_minute = int(time_string.group(4))
    # if the time has a format like "12:12:53.122" the seconds and milliseconds were
    # extracted and then attached as string again
    if (len(time_string.group()) == 6):
        attached_timestring = int(time_string.group(5))
    else:
        attached_timestring = ""
    #  calculate the hour/minutes for downtime. convert 120 minutes to 2 h or 90 minutes to 1 h 30 min
    hour, minute = divmod(info_dict['minutes'] + int(start_minute) +
                          (60 * (start_hour + info_dict['hours'])), 60)

    if hour > 23:
        print("it is (at the moment) not possible to end the timer after 0:00 o`clock")
        sys.exit(0)

    info_dict['end_time'] = (time_string.group(1) + " " +
                             str(hour) + separator + '{0:02d}'.format(minute) + attached_timestring)

    return info_dict


def executeCli():
    # from Nagstamon.Config import (conf,
            # debug_queue)
    from Nagstamon.Config import conf

    from Nagstamon.Servers import (create_server)

    # Initialize global configuration

    from Nagstamon.Objects import (GenericHost)

    # creates new server object from given servername
    server = create_server(conf.servers[conf.cli_args.servername])

    # gets the current default start/endtime from the server (default current time + 2h)
    start_end_time = server.get_start_end(conf.cli_args.hostname)
    default_start_time = start_end_time[0]
    default_end_time = start_end_time[1]
    # gets the default downtime duration from the nagstamon config
    # default_downtime = conf.defaults_downtime_duration_minutes  # never used

    server.GetStatus()

    server.hosts[conf.cli_args.hostname] = GenericHost()
    server.hosts[conf.cli_args.hostname].name = conf.cli_args.hostname
    server.hosts[conf.cli_args.hostname].server = server.name
    server.hosts[conf.cli_args.hostname].site = "monitor"

    fixedType = {"y": True, "n": False}

    info_dict = dict()
    info_dict['host'] = conf.cli_args.hostname
    info_dict['service'] = conf.cli_args.service
    info_dict['author'] = server.username
    info_dict['comment'] = conf.cli_args.comment
    info_dict['fixed'] = fixedType[conf.cli_args.fixed]

    info_dict['start_time'] = checkDefaultValue(conf.cli_args.start_time, default_start_time)
    info_dict['end_time'] = default_end_time

    info_dict['hours'] = checkDefaultValue(conf.cli_args.hours, 0)
    info_dict['minutes'] = checkDefaultValue(conf.cli_args.minutes, conf.defaults_downtime_duration_minutes)
    info_dict['view_name'] = "host"

    info_dict = createEndTime(info_dict)
    # creates output,v which parameter were processed
    if conf.cli_args.output == 'y':
        print('trying to downtime host "' + info_dict['host'] + '", with the following parameters:')
        if info_dict['service'] != "":
            print('service: ', info_dict['service'])
        if info_dict['comment'] is not None:
            print('comment: ', info_dict['comment'])
        print('fixed: ', info_dict['fixed'])
        print('start time: ', info_dict['start_time'])
        print('end time: ', info_dict['end_time'])

    server.set_downtime(info_dict)

try:
    if __name__ == '__main__':
        # ##debug_queue = list()
        executeCli()


except Exception as err:
    import traceback
    traceback.print_exc(file=sys.stdout)
