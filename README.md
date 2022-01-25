This is only a development fork if Nagstamon to add support for the Solarwinds Orion platform. Please visit the main project for up-to-date information!

Solarwinds Orion
================

The Orion module uses the Solarwinds Orion Python SDK to connect to the Orion API (port 17778) and request a list of existing alerts. It requires the username and password to be specified in the configuration option (Windows SSO does not work).

How does it work
================

The module connects via https to the Orion API and queries for all active alerts with a status "WARNING OR CRITICAL". Others are ignored.
In Orion a node status (aka host status) cannot be acknowledged. The node status is a fact. To be able to acknowledge a "node is down". Create an alert that contains #DOWN# in the alert message. The client will convert the alert to a node down status.

What is that number in front of the service?
============================================

A alert is not always associated with a node. As there is currently no option add user-defined data to an alert line in nagstamon I added the Active-Alert-ID to the service name to open and acknowledge the alert.

Example:
The volume usage critical alert is triggered by a volume object. Not a node. The node is the parent object of the alert. If the node has multiple volumes with an active alert the information "node name" + "alert name" can match multiple volumes. Which one should be acknowledge. Hence the Alert-ID in the service description the exactly identifies the alert to be acknowledged or opened.

Configuration
=============
* Set Monitor type to Orion
* Monitor name: MyOrion
* Set the Monitor URL to the MPE (Main polling engine) or AWS (additional web server) URL: https://orion.my-company.com . Do not add a path or the port 17778.
* For domain users (SSO) use the format DOMAIN\USER as username

Other options are not supported yet

Nagstamon
=========

Nagstamon is a status monitor for the desktop. It connects to multiple Nagios, Icinga, Opsview, Centreon, Op5 Monitor/Ninja, Checkmk Multisite, Thruk and monitos monitoring servers. Experimental support is provided for Zabbix, Zenoss and Livestatus monitors. It resides in systray, as a floating statusbar or fullscreen at the desktop showing a brief summary of critical, warning, unknown, unreachable and down hosts and services. It pops up a detailed status overview when being touched by the mouse pointer. Connections to displayed hosts and services are easily established by context menu via SSH, RDP, VNC or any self defined actions. Users can be notified by sound. Hosts and services can be filtered by category and regular expressions.

It is inspired by Nagios Checker for Firefox – just without an open Firefox window all the time to monitor the network.

Nagstamon is released under the GPLv2 and free to use and modify.

Nagstamon is written in Python 3 and uses the Qt 5 GUI toolkit which makes it very portable. It has been tested successfully on latest Ubuntu, Debian, Windows, NetBSD, OpenBSD, FreeBSD and MacOS X.
It works with GNOME, KDE, Windows and macOS desktops.

Successfully tested monitors include:

 - Nagios 1.x, 2.x, 3.x and 4.x
 - Icinga 1.2+ and 2.3+
 - Opsview 5+
 - Centreon 2.3+
 - Op5 Monitor 7+
 - Checkmk/Multisite 1.1.10+
 - Thruk 1.5.0+
 - monitos 4.4+
 - Livestatus – experimental
 - Zabbix 2.2+ – experimental
 - Zenoss – experimental
 - monitos 3 - experimental
 - SNAG-View3 - experimental
 - Prometheus - experimental
 - Alertmanager - experimental

See https://nagstamon.de for further information.
