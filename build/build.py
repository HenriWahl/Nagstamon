#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

from pathlib import Path
import platform
import os, os.path
from os import environ
import sys
import shutil
import subprocess
import zipfile
import glob

CURRENT_DIR = os.getcwd()
NAGSTAMON_DIR = os.path.normpath('{0}{1}..{1}'.format(CURRENT_DIR, os.sep))
sys.path.insert(1, NAGSTAMON_DIR)

SCRIPTS_DIR = '{0}{1}scripts-{2}.{3}'.format(CURRENT_DIR, os.sep, sys.version_info.major, sys.version_info.minor)

# has to be imported here after NAGSTAMON_DIR was wadded to sys.path
from Nagstamon.Config import AppInfo
from Nagstamon.Helpers import get_distro

VERSION = AppInfo.VERSION
ARCH = platform.architecture()[0][0:2]
ARCH_OPTS = {'32': ('win32', 'win32', '', 'x86'),
             '64': ('win-amd64', 'amd64', '(X86)', 'x64')}
PYTHON_VERSION = '{0}.{1}'.format(sys.version_info[0],
                                  sys.version_info[1])

DIST_NAME, DIST_VERSION, DIST_ID = get_distro()

# depending on debug build or not a console window will be shown or not
if len(sys.argv) > 1 and sys.argv[1] == 'debug':
    DEBUG = True
    # create console window with pyinstaller to get some output
    GUI_MODE = '--console'
    # add '_debug' to name of zip file
    FILENAME_SUFFIX = '_debug'
else:
    DEBUG = False
    # no console window via pyinstaller
    GUI_MODE = '--windowed'
    # also no need for filename suffix
    FILENAME_SUFFIX = ''

# when run by GitHub Actions with PFX and password as environment variables
# signing will be done
SIGNING = False
if 'WIN_SIGNING_CERT_BASE64' in environ \
    and 'WIN_SIGNING_PASSWORD' in environ:
    SIGNING = True


def winmain():
    """
        execute steps necessary for compilation of Windows binaries and setup.exe
    """

    # InnoSetup does not like VersionInfoVersion with letters, only 0.0.0.0 schemed numbers
    if 'alpha' in VERSION.lower() or 'beta' in VERSION.lower() or 'rc' in VERSION.lower() or '-' in VERSION.lower():
        VERSION_IS = VERSION.replace('alpha', '').replace('beta', '').replace('rc', '').replace('-', '.').replace('..',
                                                                                                                  '.')
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

    print('VERSION_IS:', VERSION_IS)

    # old-school formatstrings needed for old Debian build base distro jessie and its old python
    ISCC = r'{0}{1}Inno Setup 6{1}iscc.exe'.format(os.environ['PROGRAMFILES{0}'.format(ARCH_OPTS[ARCH][2])], os.sep)
    DIR_BUILD_EXE = '{0}{1}dist{1}Nagstamon'.format(CURRENT_DIR, os.sep, ARCH_OPTS[ARCH][0], PYTHON_VERSION)
    DIR_BUILD_NAGSTAMON = '{0}{1}dist{1}Nagstamon-{2}-win{3}{4}'.format(CURRENT_DIR, os.sep, VERSION, ARCH,
                                                                        FILENAME_SUFFIX)
    FILE_ZIP = '{0}.zip'.format(DIR_BUILD_NAGSTAMON)

    # clean older binaries
    for file in (DIR_BUILD_EXE, DIR_BUILD_NAGSTAMON, FILE_ZIP):
        if os.path.exists(file):
            try:
                shutil.rmtree(file)
            except:
                os.remove(file)

    # now with pyinstaller - dev version is able to run with Python 3.6
    subprocess.call(['{0}\\Scripts\\pyinstaller'.format(sys.base_prefix),
                     '--noconfirm',
                     '--add-data=..\\Nagstamon/resources;resources',
                     '--icon=..\\Nagstamon\\resources\\nagstamon.ico',
                     '--name=Nagstamon',
                     '--hidden-import=PyQt6.uic.plugins',
                     '--hidden-import=win32timezone',
                     GUI_MODE,
                     '..\\nagstamon.py'],
                    shell=True)

    if SIGNING:
        # environment variables will be used by powershell script for signing
        subprocess.run(['pwsh.exe', './windows/code_signing.ps1', 'build/Nagstamon/Nagstamon.exe'])

    # rename output
    os.rename(DIR_BUILD_EXE, DIR_BUILD_NAGSTAMON)

    # create simple batch file for debugging
    if DEBUG:
        # got to Nagstamon build directory with Nagstamon.exe
        os.chdir(DIR_BUILD_NAGSTAMON)
        batch_file = Path('nagstamon-debug.bat')
        # cmd /k keeps the console window open to get some debug output
        batch_file.write_text('cmd /k nagstamon.exe')

    # after cleaning start zipping and setup.exe-building - go back to original directory
    os.chdir(CURRENT_DIR)

    # create .zip file
    if os.path.exists('{0}{1}dist'.format(CURRENT_DIR, os.sep)):
        os.chdir('{0}{1}dist'.format(CURRENT_DIR, os.sep))
        zip_archive = zipfile.ZipFile(FILE_ZIP, mode='w', compression=zipfile.ZIP_DEFLATED)
        zip_archive.write(os.path.basename(DIR_BUILD_NAGSTAMON))
        for root, dirs, files in os.walk(os.path.basename(DIR_BUILD_NAGSTAMON)):
            for file in files:
                zip_archive.write('{0}{1}{2}'.format(root, os.sep, file))

    if not DEBUG:
        # execute InnoSetup with many variables set by ISCC.EXE outside .iss file
        subprocess.call([ISCC,
                         r'/Dsource={0}'.format(DIR_BUILD_NAGSTAMON),
                         r'/Dversion_is={0}'.format(VERSION_IS),
                         r'/Dversion={0}'.format(VERSION),
                         r'/Darch={0}'.format(ARCH),
                         r'/Darchs_allowed={0}'.format(ARCH_OPTS[ARCH][3]),
                         r'/Dresources={0}{1}resources'.format(DIR_BUILD_NAGSTAMON, os.sep),
                         r'/O{0}{1}dist'.format(CURRENT_DIR, os.sep),
                         r'{0}{1}windows{1}nagstamon.iss'.format(CURRENT_DIR, os.sep)], shell=True)

    if SIGNING:
        # environment variables will be used by powershell script for signing
        subprocess.run(['pwsh.exe', '../windows/code_signing.ps1', '*.exe'])

def macmain():
    """
        execute steps necessary for compilation of MacOS X binaries and .dmg file
    """
    # can't pass --version to pyinstaller in spec mode, so export as env var
    os.environ['NAGSTAMON_VERSION'] = VERSION

    # create one-file .app bundle by pyinstaller
    subprocess.call(['pyinstaller --noconfirm macos/nagstamon.spec'], shell=True)

    # create staging DMG folder for later compressing of DMG
    shutil.rmtree('Nagstamon {0} Staging DMG'.format(VERSION), ignore_errors=True)

    # copy app bundle folder
    shutil.move('dist/Nagstamon.app', 'Nagstamon {0} Staging DMG/Nagstamon.app'.format(VERSION))

    # cleanup before new images get created
    for dmg_file in glob.iglob('*.dmg'):
        os.unlink(dmg_file)

    # create DMG
    subprocess.call(['hdiutil create -srcfolder "Nagstamon {0} Staging DMG" '
                     '-volname "Nagstamon {0}" -fs HFS+ -format UDRW -size 100M '
                     '"Nagstamon {0} uncompressed.dmg"'.format(VERSION)], shell=True)

    # Compress DMG
    subprocess.call(['hdiutil convert "Nagstamon {0} uncompressed".dmg '
                     '-format UDZO -imagekey zlib-level=9 -o "Nagstamon {0}.dmg"'.format(VERSION)], shell=True)

    # Delete uncompressed DMG file as it is no longer needed
    os.unlink('Nagstamon {0} uncompressed.dmg'.format(VERSION))


def debmain():
    shutil.rmtree(SCRIPTS_DIR, ignore_errors=True)
    shutil.rmtree('{0}{1}.pybuild'.format(CURRENT_DIR, os.sep), ignore_errors=True)
    shutil.rmtree('{0}{1}debian'.format(NAGSTAMON_DIR, os.sep), ignore_errors=True)

    os.chdir(NAGSTAMON_DIR)

    # masquerade .py file as .py-less
    shutil.copyfile('nagstamon.py', 'nagstamon')

    shutil.copytree('{0}{1}debian{1}'.format(CURRENT_DIR, os.sep), '{0}{1}debian'.format(NAGSTAMON_DIR, os.sep))

    os.chmod('{0}{1}debian{1}rules'.format(CURRENT_DIR, os.sep), 0o755)

    subprocess.call(['fakeroot', 'debian/rules', 'build'])

    subprocess.call(['fakeroot', 'debian/rules', 'binary'])

    # copy .deb file to current directory
    for deb in glob.iglob('../nagstamon*.deb'):
        shutil.move(deb, CURRENT_DIR)


def rpmmain():
    """
        create .rpm file via setup.py bdist_rpm - most settings are in setup.py
    """

    os.chdir(NAGSTAMON_DIR)

    # masquerade .py file as .py-less
    shutil.copyfile('nagstamon.py', 'nagstamon')

    # workaround for manpage gzipping bug in bdist_rpm
    import gzip
    man = open('Nagstamon/resources/nagstamon.1', 'rb')
    mangz = gzip.open('Nagstamon/resources/nagstamon.1.gz', 'wb')
    mangz.writelines(man)
    mangz.close()
    man.close()

    # run setup.py for rpm creation
    subprocess.call(['python3', 'setup.py', 'bdist_rpm'], shell=False)

    current_dir = Path(CURRENT_DIR)
    for file in current_dir.iterdir():
        if VERSION.replace('-', '.') in file.name and ('noarch' in file.name or 'src' in file.name):
            for file_type in ['noarch', 'src']:
                if file_type in file.name:
                    file.replace(file.parent / Path(file.name.replace(f'{file_type}.rpm',
                                                                      f'{DIST_NAME}{DIST_VERSION}.{file_type}.rpm')))


DISTS = {
    'debian': debmain,
    'ubuntu': debmain,
    'linuxmint': debmain,
    'fedora': rpmmain,
    'rhel': rpmmain
}

if __name__ == '__main__':
    if platform.system() == 'Windows':
        winmain()
    elif platform.system() == 'Darwin':
        macmain()
    else:
        dist = get_distro()[0]
        if dist in DISTS:
            DISTS[dist]()
        else:
            print('Your system is not supported for automated build yet')
