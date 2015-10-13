from cx_Freeze import setup, Executable
import platform

# workaround to get directory of Qt5 plugins to add missing 'mediaservice' folder needed for audio on OSX and Windows
import os.path
from PyQt5 import QtCore
if platform.system() == 'Windows':
    QTPLUGINS = os.path.join(os.path.dirname(QtCore.__file__), 'plugins')
elif platform.system() == 'Darwin':
    # works of course only with Fink-based Qt5-installation
    QTPLUGINS = '/sw/lib/qt5-mac/plugins'

NAME = 'Nagstamon'
VERSION = '2.0-alpha-20151009'

# condition is necessary because if qt.conf exists in folder Nagstamon will have the plain basic Qt5 look
# which does rather not fit well into desktop environment
if platform.system() in ['Windows', 'Darwin']:
    os_dependent_include_files = ['Nagstamon/resources/qt.conf',
                                  'Nagstamon/resources',
                                  '{0}/mediaservice'.format(QTPLUGINS)]
else:
    os_dependent_include_files = ['Nagstamon/resources',
                                  '{0}/mediaservice'.format(QTPLUGINS)]

# Dependencies are automatically detected, but it might need
# fine tuning.
build_exe_options = dict(packages = ['PyQt5.QtNetwork',
                                     'keyring.backends.file',
                                     'keyring.backends.Gnome',
                                     'keyring.backends.Google',
                                     'keyring.backends.kwallet',
                                     'keyring.backends.multi',
                                     'keyring.backends.OS_X',
                                     'keyring.backends.pyfs',
                                     'keyring.backends.SecretService',
                                     'keyring.backends.Windows'],
                        include_files = os_dependent_include_files,
                        include_msvcr = True,
                        excludes = [])

bdist_mac_options = dict(iconfile = 'Nagstamon/resources/nagstamon.icns')

bdist_dmg_options = dict(volume_label = '{0} {1}'.format(NAME, VERSION),
                        applications_shortcut = False)

bdist_msi_options = dict(upgrade_code = '{3681ab2-6f2d-931c-7341cb0426}')

import sys
base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable('nagstamon-qt.py',
               base=base,
               icon='Nagstamon/resources/nagstamon.ico')
]

setup(name = NAME,
      version = VERSION,
      description = 'Nagstamon',
      options = dict(build_exe = build_exe_options,
                     bdist_mac = bdist_mac_options,
                     bdist_dmg = bdist_dmg_options,
                     bdist_msi = bdist_msi_options),
      executables = executables
    )



