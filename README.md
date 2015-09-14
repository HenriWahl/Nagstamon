Nagstamon
=========

**Major development at the moment only happens in the '2.0' branch.**


v2.0 Roadmap (by Marcin Nowak)
------------------------------
 
 - [ ] pluggable Servers using setuptool`s entry points
 - [ ] code cleanup 
 - [ ] define new&clean Server`s public interface and create real abstract BaseServer class
 - [ ] compatibility layer for old GenericServer


Further notes
-------------

To make this work on Yosemite:
* brew install gtk-mac-integration

Nagstamon is a Nagios status monitor for the desktop. It connects to multiple Nagios, Icinga, Opsview, Centreon, Op5 Monitor/Ninja, Check_MK Multisite and Thruk monitoring servers and resides in systray or as a floating statusbar at the desktop showing a brief summary of critical, warning, unknown, unreachable and down hosts and services and pops up a detailed status overview when moving the mouse pointer over it. Connecting to displayed hosts and services is easily established by context menu via SSH, RDP and VNC or any self defined actions. Users can be notified by sound. Hosts and services can be filtered by category and regular expressions.

It is inspired by Nagios Checker for Firefox - just without an open Firefox window all the time to monitor the network.

Nagstamon is released under the GPLv2 and free to use and modify.

Nagstamon is written in Python so it is highly portable. It has been tested successfully on Ubuntu 8.04 - 14.04, Debian 6.0 - 7.0, Fedora 8 - 20, OpenSUSE 11.x, Windows 2000 + XP + XP 64bit + Vista + Windows 7 + 8 + 2008 + 2012, OpenSolaris 2009.06, NetBSD, OpenBSD, FreeBSD and MacOS X.
It works with GNOME, KDE, Windows and MacOS X desktop.

Successfully tested monitor versions include:

Nagios 1.x, 2.x and 3.x, Icinga 1.2+, Opsview 3.5+, Centreon 2.1.x, Op5 Monitor 6.3+, Check_MK/Multisite 1.1.10+ and Thruk 1.5.0+.

Experimental Zabbix 2.2+ support is included since Nagstamon 1.0.


See https://nagstamon.ifw-dresden.de for further information.
