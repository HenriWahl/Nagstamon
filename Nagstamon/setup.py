# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2013 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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


from setuptools import setup
import sys

CLASSIFIERS = [
    'Intended Audience :: System Administrators',
    'Development Status :: 5 - Production/Stable',
    'Environment :: Win32 (MS Windows)',
    'Environment :: X11 Applications',
    'License :: OSI Approved :: GNU General Public License (GPL)',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: POSIX :: Linux',
    'Operating System :: POSIX',
    'Natural Language :: English',
    'Programming Language :: Python',
    'Topic :: System :: Monitoring',
    'Topic :: System :: Networking :: Monitoring'
]

setup(name = 'nagstamon',
    version = '1.1.0',
    license = 'GNU GPL v2',
    description = 'Nagios status monitor for desktop',
    long_description = 'Nagstamon is a Nagios status monitor which takes place in systray or on desktop (GNOME, KDE, Windows) as floating statusbar to inform you in realtime about the status of your Nagios and derivatives monitored network. It allows to connect to multiple Nagios, Icinga, Opsview, Op5Monitor, Check_MK/Multisite, Centreon and Thruk servers.',
    classifiers = CLASSIFIERS,
    author = 'Henri Wahl',
    author_email = 'h.wahl@ifw-dresden.de',
    url = 'https://nagstamon.ifw-dresden.de',
    download_url = 'https://nagstamon.ifw-dresden.de/files-nagstamon/stable/',
    dependency_links = ['setuptools'],
    scripts = ['nagstamon.py'],
    packages = ['Nagstamon', 'Nagstamon.Server', 'Nagstamon.thirdparty'],
    package_dir = {'Nagstamon':'Nagstamon'},
    package_data = {'Nagstamon':['resources/*']},
    entry_points = '''
        [nagstamon.servers]
        Nagios = Nagstamon.Server.Nagios:NagiosServer
        Centreon = Nagstamon.Server.Centreon:CentreonServer
        Multisite = Nagstamon.Server.Multisite:MultisiteServer
        Icinga = Nagstamon.Server.Icinga:IcingaServer
        op5Monitor = Nagstamon.Server.op5Monitor:Op5MonitorServer
        Opsview = Nagstamon.Server.Opsview:OpsviewServer
        Thruk = Nagstamon.Server.Thruk:ThrukServer
        Zabbix = Nagstamon.Server.Zabbix:ZabbixServer
        Ninja = Nagstamon.Server.Ninja:NinjaServer
    ''',
    data_files = [('%s/share/man/man1' % sys.prefix, ['Nagstamon/resources/nagstamon.1'])]
)
