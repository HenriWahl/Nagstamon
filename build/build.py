#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2025 Henri Wahl <henri@nagstamon.de> et al.
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

import glob
import gzip
import os, os.path
from os import environ
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile


CURRENT_DIR = os.getcwd()
NAGSTAMON_DIR = os.path.normpath('{0}{1}..{1}'.format(CURRENT_DIR, os.sep))
sys.path.insert(1, NAGSTAMON_DIR)

SCRIPTS_DIR = '{0}{1}scripts-{2}.{3}'.format(CURRENT_DIR, os.sep, sys.version_info.major, sys.version_info.minor)

# has to be imported here after NAGSTAMON_DIR was wadded to sys.path
from Nagstamon.Config import AppInfo
from Nagstamon.Helpers import get_distro

VERSION = AppInfo.VERSION

ARCH_WINDOWS = platform.architecture()[0][0:2]
ARCH_WINDOWS_OPTS = {'32': ('win32', 'win32', '', 'x86'),
                     '64': ('win-amd64', 'amd64', '(X86)', 'x64compatible')}

ARCH_MACOS = platform.machine()
ARCH_MACOS_NAMES = {'x86_64': 'Intel',
                    'arm64': 'ARM'}

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


def zip_manpage():
    # workaround for manpage gzipping bug in bdist_rpm
    os.chdir(NAGSTAMON_DIR)
    man = open('Nagstamon/resources/nagstamon.1', 'rb')
    mangz = gzip.open('Nagstamon/resources/nagstamon.1.gz', 'wb')
    mangz.writelines(man)
    mangz.close()
    man.close()


def package_windows():
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

    # old-school formatstrings needed for old Debian build base distro jessie and its old python
    ISCC = r'{0}{1}Inno Setup 6{1}iscc.exe'.format(os.environ['PROGRAMFILES{0}'.format(ARCH_WINDOWS_OPTS[ARCH_WINDOWS][2])], os.sep)
    DIR_BUILD_EXE = '{0}{1}dist{1}Nagstamon'.format(CURRENT_DIR, os.sep, ARCH_WINDOWS_OPTS[ARCH_WINDOWS][0], PYTHON_VERSION)
    DIR_BUILD_NAGSTAMON = '{0}{1}dist{1}Nagstamon-{2}-win{3}{4}'.format(CURRENT_DIR, os.sep, VERSION, ARCH_WINDOWS,
                                                                        FILENAME_SUFFIX)
    FILE_ZIP = '{0}.zip'.format(DIR_BUILD_NAGSTAMON)

    # clean older binaries
    for file in (DIR_BUILD_EXE, DIR_BUILD_NAGSTAMON, FILE_ZIP):
        if os.path.exists(file):
            try:
                shutil.rmtree(file)
            except:
                os.remove(file)

    # pyinstaller seems also to be installed not in \Scripts folder - if so, try without path
    pyinstaller_path = f'{sys.base_prefix}\\Scripts\\pyinstaller'
    if not Path(pyinstaller_path).exists():
        pyinstaller_path = 'pyinstaller'
    subprocess.call([pyinstaller_path,
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
        subprocess.run(['pwsh.exe', './windows/code_signing.ps1', 'build/Nagstamon/*.exe'])

    # rename output
    os.rename(DIR_BUILD_EXE, DIR_BUILD_NAGSTAMON)

    # create simple batch file for debugging
    if DEBUG:
        # got to Nagstamon build directory with Nagstamon.exe
        os.chdir(DIR_BUILD_NAGSTAMON)
        batch_file = Path('nagstamon-debug.bat')
        # cmd /k keeps the console window open to get some debug output
        batch_file.write_text('set \n'
                              'cmd /k nagstamon.exe')

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
        zip_archive.close()

    if not DEBUG:
        # for some reason out of nowhere the old path SetupIconFile={#resources}\nagstamon.ico
        # does not work anymore, so the icon gets copied into the path referenced to
        # as SourceDir in the ISS file
        shutil.copyfile(f'{NAGSTAMON_DIR}{os.sep}Nagstamon{os.sep}resources{os.sep}nagstamon.ico',
                        f'{DIR_BUILD_NAGSTAMON}{os.sep}nagstamon.ico')

        # execute InnoSetup with many variables set by ISCC.EXE outside .iss file
        result = subprocess.call([ISCC,
                         r'/Dsource={0}'.format(DIR_BUILD_NAGSTAMON),
                         r'/Dversion_is={0}'.format(VERSION_IS),
                         r'/Dversion={0}'.format(VERSION),
                         r'/Darch={0}'.format(ARCH_WINDOWS),
                         r'/Darchs_allowed={0}'.format(ARCH_WINDOWS_OPTS[ARCH_WINDOWS][3]),
                         r'/O{0}{1}dist'.format(CURRENT_DIR, os.sep),
                         r'{0}{1}windows{1}nagstamon.iss'.format(CURRENT_DIR, os.sep)],
                         shell=True)
        if result > 0:
            sys.exit(result)

    if SIGNING:
        # environment variables will be used by powershell script for signing
        subprocess.run(['pwsh.exe', '../windows/code_signing.ps1', '*.exe'])

def package_macos():
    """
        execute steps necessary for compilation of MacOS X binaries and .dmg file
    """
    # can't pass --version to pyinstaller in spec mode, so export as env var
    os.environ['NAGSTAMON_VERSION'] = VERSION

    # create one-file .app bundle by pyinstaller
    subprocess.call(['pyinstaller --noconfirm macos/nagstamon.spec'], shell=True)

    # create staging DMG folder for later compressing of DMG
    shutil.rmtree(f'Nagstamon_{VERSION}_Staging_DMG/', ignore_errors=True)

    # move app bundle folder
    shutil.move('dist/Nagstamon.app', f'Nagstamon_{VERSION}_Staging_DMG/Nagstamon.app')

    # copy icon to staging folder
    shutil.copy('../Nagstamon/resources/nagstamon.ico', 'nagstamon.ico'.format(VERSION))

    # cleanup before new images get created
    for dmg_file in glob.iglob('*.dmg'):
        os.unlink(dmg_file)

    # create dmg file with create-dmg insttaled via brew
    subprocess.call([f'create-dmg '
                     f'--volname "Nagstamon {VERSION}" '
                     f'--volicon "nagstamon.ico" '
                     f'--window-pos 400 300 '
                     f'--window-size 600 320 '
                     f'--icon-size 100 '
                     f'--icon "Nagstamon.app" 175 110 '
                     f'--hide-extension "Nagstamon.app" '
                     f'--app-drop-link 425 110 '
                     f'"dist/Nagstamon-{VERSION}-{ARCH_MACOS_NAMES[ARCH_MACOS]}.dmg" '
                     f'Nagstamon_{VERSION}_Staging_DMG/'
                     ], shell=True)

def package_linux_deb():
    shutil.rmtree(SCRIPTS_DIR, ignore_errors=True)
    shutil.rmtree('{0}{1}.pybuild'.format(CURRENT_DIR, os.sep), ignore_errors=True)
    shutil.rmtree('{0}{1}debian'.format(NAGSTAMON_DIR, os.sep), ignore_errors=True)

    os.chdir(NAGSTAMON_DIR)

    # masquerade .py file as .py-less
    shutil.copyfile('nagstamon.py', 'nagstamon')

    shutil.copytree('{0}{1}debian{1}'.format(CURRENT_DIR, os.sep), '{0}{1}debian'.format(NAGSTAMON_DIR, os.sep))

    # just in case some Windows commit converted linebreaks
    # for debian_file in glob.iglob('debian/*'):
    #     subprocess.call(['dos2unix', f'{debian_file}'])

    os.chmod(f'{CURRENT_DIR}/debian/rules', 0o755)

    subprocess.call(['fakeroot', 'debian/rules', 'build'])

    subprocess.call(['fakeroot', 'debian/rules', 'binary'])

    # copy .deb file to current directory
    for debian_package in glob.iglob('../nagstamon*.deb'):
        shutil.move(debian_package, CURRENT_DIR)


def package_linux_rpm():
    """
        create .rpm file via setup.py bdist_rpm - most settings are in setup.py
    """

    os.chdir(NAGSTAMON_DIR)

    # masquerade .py file as .py-less
    shutil.copyfile('nagstamon.py', 'nagstamon')

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
    'debian': package_linux_deb,
    'ubuntu': package_linux_deb,
    'linuxmint': package_linux_deb,
    'fedora': package_linux_rpm,
    'rhel': package_linux_rpm
}

if __name__ == '__main__':
    if platform.system() == 'Windows':
        package_windows()
    elif platform.system() == 'Darwin':
        package_macos()
    else:
        dist = get_distro()[0]
        if dist in DISTS:
            zip_manpage()
            DISTS[dist]()
        else:
            print('Your system is not supported for automated build yet')
