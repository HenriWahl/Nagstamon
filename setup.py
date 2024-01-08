#!/usr/bin/env python3
# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2024 Henri Wahl <henri@nagstamon.de> et al.
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

# from distutils.core import setup
import sys
import platform
import os.path

from Nagstamon.Config import AppInfo, \
    OS
from Nagstamon.Helpers import get_distro

# dummy debug queue for compiling
debug_queue = list()

NAME = AppInfo.NAME

# make name lowercase for Linux/Unix
if OS not in ['Windows', 'Darwin']:
    if OS == 'Linux':
        DIST, DIST_VERSION, DIST_NAME = get_distro()
    # platform.dist() returns "('', '', '')" on FreeBSD
    elif OS == 'FreeBSD':
        DIST, DIST_VERSION, DIST_NAME = ('', '', '')
    # platform.dist() does not exist on NetBSD
    elif OS == 'NetBSD':
        DIST, DIST_VERSION, DIST_NAME = ('', '', '')
    else:
        DIST, DIST_VERSION, DIST_NAME = platform.dist()
    NAME = NAME.lower()
else:
    DIST = ""
#VERSION = AppInfo.VERSION.replace('-', '.') + '.' + DIST + DIST_VERSION
VERSION = AppInfo.VERSION.replace('-', '.')
NAGSTAMON_SCRIPT = 'nagstamon.py'

from setuptools import setup

os_dependent_include_files = ['Nagstamon/resources']
if os.path.exists('nagstamon'):
    NAGSTAMON_SCRIPT = 'nagstamon'

CLASSIFIERS = ['Intended Audience :: System Administrators',
               'Development Status :: 5 - Production/Stable',
               'Environment :: Win32 (MS Windows)',
               'Environment :: X11 Applications',
               'Environment :: MacOS X',
               'License :: OSI Approved :: GNU General Public License (GPL)',
               'Operating System :: Microsoft :: Windows',
               'Operating System :: POSIX :: Linux',
               'Operating System :: POSIX',
               'Natural Language :: English',
               'Programming Language :: Python',
               'Topic :: System :: Monitoring',
               'Topic :: System :: Networking :: Monitoring']

# Dependencies are automatically detected, but it might need
# fine tuning.
build_exe_options = dict(packages=['PyQt6.QtNetwork',
                                   'keyring.backends.kwallet',
                                   'keyring.backends.OS_X',
                                   'keyring.backends.SecretService',
                                   'keyring.backends.Windows'],
                         include_files=os_dependent_include_files,
                         include_msvcr=True,
                         excludes=[])

bdist_mac_options = dict(iconfile='Nagstamon/resources/nagstamon.icns',
                         custom_info_plist='Nagstamon/resources/Info.plist')

bdist_dmg_options = dict(volume_label='{0} {1}'.format(NAME, VERSION),
                         applications_shortcut=False)

# older Fedora needs Qt5
if OS not in ['Windows', 'Darwin']:
    if DIST.lower() == 'fedora' and int(DIST_VERSION) < 36 or \
       DIST.lower() == 'rhel' and int(DIST_VERSION) <= 9:
        bdist_rpm_options = dict(requires='python3 '
                                          'python3-beautifulsoup4 '
                                          'python3-cryptography '
                                          'python3-dateutil '
                                          'python3-keyring '
                                          'python3-lxml '
                                          'python3-psutil '
                                          'python3-pysocks '
                                          'python3-qt5 '
                                          'python3-requests '
                                          'python3-requests-kerberos '
                                          'python3-SecretStorage '
                                          'qt5-qtmultimedia '
                                          'qt5-qtsvg ',
                                 dist_dir='./build')
    else:
        bdist_rpm_options = dict(requires='python3 '
                                          'python3-beautifulsoup4 '
                                          'python3-cryptography '
                                          'python3-dateutil '
                                          'python3-keyring '
                                          'python3-lxml '
                                          'python3-psutil '
                                          'python3-pysocks '
                                          'python3-pyqt6 '
                                          'python3-requests '
                                          'python3-requests-kerberos '
                                          'python3-SecretStorage '
                                          'qt6-qtmultimedia '
                                          'qt6-qtsvg ',
                                 dist_dir='./build')

setup(name=NAME,
      version=VERSION,
      license='GNU GPL v2',
      description='Nagios status monitor for desktop',
      long_description='Nagstamon is a Nagios status monitor which takes place in systray or on desktop (GNOME, KDE, Windows) as floating statusbar to inform you in realtime about the status of your Nagios and derivatives monitored network. It allows to connect to multiple Nagios, Icinga, Opsview, Op5Monitor, Checkmk/Multisite, Centreon and Thruk servers.',
      classifiers=CLASSIFIERS,
      author='Henri Wahl',
      author_email='henri@nagstamon.de',
      url='https://nagstamon.de',
      download_url='https://nagstamon.de/download',
      scripts=[NAGSTAMON_SCRIPT],
      packages=['Nagstamon',
                'Nagstamon.QUI',
                'Nagstamon.Servers',
                'Nagstamon.Servers.Alertmanager',
                'Nagstamon.Servers.Centreon',
                'Nagstamon.thirdparty',
                'Nagstamon.thirdparty.Xlib',
                'Nagstamon.thirdparty.Xlib.ext',
                'Nagstamon.thirdparty.Xlib.protocol',
                'Nagstamon.thirdparty.Xlib.support',
                'Nagstamon.thirdparty.Xlib.xobject'],
      package_dir={'Nagstamon': 'Nagstamon'},
      package_data={'Nagstamon': ['resources/*.*',
                                  'resources/qui/*',
                                  'resources/LICENSE',
                                  'resources/CREDITS']},
      data_files=[('%s/share/man/man1' % sys.prefix, ['Nagstamon/resources/nagstamon.1.gz']),
                  ('%s/share/pixmaps' % sys.prefix, ['Nagstamon/resources/nagstamon.svg']),
                  ('%s/share/applications' % sys.prefix, ['Nagstamon/resources/nagstamon.desktop'])],
      options=dict(build_exe=build_exe_options,
                   bdist_mac=bdist_mac_options,
                   bdist_dmg=bdist_dmg_options,
                   bdist_rpm=bdist_rpm_options)
      )
