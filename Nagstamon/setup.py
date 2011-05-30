# encoding: utf-8

# Nagstamon - Displays a Nagios monitored network status on desktop
# Copyright (C) 2009 Henri Wahl <h.wahl@ifw-dresden.de>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


from distutils.core import setup
import os.path
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
    version = '0.9.7.1',
    license = 'GNU GPL v2',
    description = 'Nagios status monitor for desktop',
    long_description = 'Nagstamon is a Nagios status monitor which takes place in systray or on desktop (GNOME, KDE, Windows) as floating statusbar to inform you in realtime about the status of your Nagios and derivatives monitored network. It allows to connect to multiple Nagios, Icinga, Opsview, Op5, Check_MK/Multisite and Centreon servers.',
    classifiers = CLASSIFIERS,
    author = 'Henri Wahl',
    author_email = 'h.wahl@ifw-dresden.de',
    url = 'http://nagstamon.ifw-dresden.de',
    download_url = 'http://sourceforge.net/projects/nagstamon/',
    scripts = ['nagstamon.py'],
    packages = ['Nagstamon', 'Nagstamon.Server'],
    package_dir = {'Nagstamon':'Nagstamon'},
    package_data = {'Nagstamon':['resources/*']},
    data_files = [('%s/share/man/man1' % sys.prefix, ['Nagstamon/resources/nagstamon.1'])]
)

