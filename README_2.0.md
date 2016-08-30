Nagstamon
=========

Nagstamon is a status monitor for the desktop. It connects to multiple Nagios, Icinga, Opsview, Centreon, Op5 Monitor/Ninja, Check_MK Multisite and Thruk monitoring servers. Experimental support is provided for Zabbix, Zenoss and Livestatus monitors. It resides in systray, as a floating statusbar or fullscreen at the desktop showing a brief summary of critical, warning, unknown, unreachable and down hosts and services. It pops up a detailed status overview when being touched by the mouse pointer. Connections to displayed hosts and services are easily established by context menu via SSH, RDP, VNC or any self defined actions. Users can be notified by sound. Hosts and services can be filtered by category and regular expressions.

It is inspired by Nagios Checker for Firefox – just without an open Firefox window all the time to monitor the network.

Nagstamon is released under the GPLv2 and free to use and modify.

Nagstamon is written in Python 3 and uses the Qt 5 GUI toolkit which makes it very portable. It has been tested successfully on latest Ubuntu, Debian, Windows, NetBSD, OpenBSD, FreeBSD and MacOS X.
It works with GNOME, KDE, Windows and MacOS X desktop.

Successfully tested monitors include:

 - Nagios 1.x, 2.x, 3.x and 4.x
 - Icinga 1.2+ and 2.3+
 - Opsview 5+
 - Centreon 2.3+
 - Op5 Monitor 7+
 - Check_MK/Multisite 1.1.10+
 - Thruk 1.5.0+
 - Livestatus – experimental
 - Zabbix 2.2+ – experimental
 - Zenoss – experimental

See https://nagstamon.ifw-dresden.de for further information.
