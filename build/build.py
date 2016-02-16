#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2016 Henri Wahl <h.wahl@ifw-dresden.de> et al.
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

import platform
import os, os.path
import sys
import shutil
import subprocess
import zipfile

CURRENT_DIR = os.getcwd()
sys.path.append('{0}{1}..{1}'.format(CURRENT_DIR, os.sep))

from Nagstamon.Config import AppInfo

VERSION = AppInfo.VERSION
# InnoSetup does not like VersionInfoVersion with letters, only 0.0.0.0 schemed numbers
if 'alpha' in VERSION.lower() or 'beta' in VERSION.lower():
    VERSION_IS = VERSION.replace('alpha', '').replace('beta', '').replace('-', '.').replace('..', '.')
    VERSION_IS = VERSION_IS.split('.')
    version_segments = list()
    for part in VERSION_IS:
        if len(part) < 4:
            version_segments.append(part)
        else:
            version_segments.append(part[0:4])
            version_segments.append(part[4:])
    VERSION_IS = '.'.join(version_segments)
else:
    VERSION_IS = VERSION
ARCH = platform.architecture()[0][0:2]
ARCH_OPTS = {'32': ('win32', 'win32', '', 'x86 x64'),
             '64': ('win-amd64', 'amd64', '(X86)', 'x64')}
PYTHON_VERSION = '{0}.{1}'.format(sys.version_info[0],
                                  sys.version_info[1])

ISCC = r'{0}{1}Inno Setup 5{1}iscc.exe'.format(os.environ['PROGRAMFILES{0}'.format(ARCH_OPTS[ARCH][2])], os.sep)


def winmain():
    DIR_BUILD_EXE = '{0}{1}exe.{2}-{3}'.format(CURRENT_DIR, os.sep, ARCH_OPTS[ARCH][0], PYTHON_VERSION)
    DIR_BUILD_NAGSTAMON = '{0}{1}Nagstamon-{2}-win{3}'.format(CURRENT_DIR, os.sep, VERSION, ARCH)
    FILE_ZIP = '{0}.zip'.format(DIR_BUILD_NAGSTAMON)

    # clean older binaries
    for file in (DIR_BUILD_EXE, DIR_BUILD_NAGSTAMON, FILE_ZIP):
        if os.path.exists(file):
            try:
                shutil.rmtree(file)
            except:
                os.remove(file)

    # go one directory up and run setup.py
    os.chdir('{0}{1}..'.format(CURRENT_DIR, os.sep))
    subprocess.call(['setup.py', 'build_exe'], shell=True)
    os.rename(DIR_BUILD_EXE, DIR_BUILD_NAGSTAMON)
    os.chdir(CURRENT_DIR)

    # create .zip file
    if os.path.exists(DIR_BUILD_NAGSTAMON):
        zip_archive = zipfile.ZipFile(FILE_ZIP, mode='w', compression=zipfile.ZIP_DEFLATED)
        zip_archive.write(os.path.basename(DIR_BUILD_NAGSTAMON))
        for root, dirs, files in os.walk(os.path.basename(DIR_BUILD_NAGSTAMON)):
            for file in files:
                zip_archive.write('{0}{1}{2}'.format(root, os.sep, file ))

    # execute InnoSetup with many variables set by ISCC.EXE outside .iss file
    subprocess.call([ISCC,
                     r'/Dsource={0}'.format(DIR_BUILD_NAGSTAMON),
                     r'/Dversion_is={0}'.format(VERSION_IS),
                     r'/Dversion={0}'.format(VERSION),
                     r'/Darch={0}'.format(ARCH),
                     r'/Darchs_allowed={0}'.format(ARCH_OPTS[ARCH][3]),
                     r'/Dresources={0}{1}resources'.format(DIR_BUILD_NAGSTAMON, os.sep),
                     r'/O{0}'.format(CURRENT_DIR),
                     r'{0}{1}windows{1}nagstamon.iss'.format(CURRENT_DIR, os.sep)], shell=True)


def debmain():
    parser = OptionParser()
    parser.add_option('-t', '--target', dest='target', help='Target application directory', default=DEFAULT_LOCATION)
    parser.add_option('-d', '--debian', dest='debian', help='"debian" directory location', default='')
    options, args = parser.parse_args()
    if not options.debian:
        options.debian = '%s/%sdebian' % (options.target, INSTALLER_DIR)
    else:
        options.debian = '%s/debian' % options.debian
    options.debian = os.path.abspath(options.debian)

    if not os.path.isfile('%s/rules' % (options.debian)):
        print('Missing required "rules" file in "%s" directory' % options.debian)
        return
    execute_script_lines(['cd %(target)s; ln -s %(debian)s; chmod 755 %(debian)s/rules; fakeroot debian/rules build; \
fakeroot debian/rules binary; fakeroot debian/rules clean; rm debian'],
                         get_opt_dict(options))

    print("\nFind .deb output in ../.\n")


# from https://github.com/mizunokazumi/Nagstamon - Thanks!
def rpmmain():
    parser = OptionParser()
    parser.add_option('-t', '--target', dest='target', help='Target application directory', default=DEFAULT_LOCATION)
    parser.add_option('-r', '--redhat', dest='redhat', help='"redhat" directory location', default='')
    options, args = parser.parse_args()
    if not options.redhat:
        options.redhat = '%s/%sredhat' % (options.target, INSTALLER_DIR)
    else:
        options.redhat = '%s/redhat' % options.redhat
    options.redhat = os.path.abspath(options.redhat)

    if not os.path.isfile('%s/nagstamon.spec' % (options.redhat)):
        print('Missing required "nagstamon.spec" file in "%s" directory' % options.redhat)
        return
    execute_script_lines(['cd %(target)s; ln -s %(redhat)s; tar -czf redhat/Nagstamon-%(version)s.tar.gz .; fakeroot rpmbuild --define "_sourcedir %(redhat)s" -ba redhat/nagstamon.spec; rm -rf redhat'],
                         get_opt_dict(options))

    print("\nFind .rpm output in $HOME/rpmbuild/RPMS/noarch/.\n")


DISTS = {
    'debian': debmain,
    'Ubuntu': debmain,
    'fedora': rpmmain
}

if __name__ == '__main__':
    if platform.system() == 'Windows':
        winmain()
    else:
        dist = platform.dist()[0]
        if dist in DISTS:
            DISTS[dist]()
        else:
            print('Your system is not supported for automated build yet')
