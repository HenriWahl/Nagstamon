from cx_Freeze import setup, Executable

NAME = 'Nagstamon'
VERSION = '2.0-alpha-20150930'

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
                        include_files = ['Nagstamon/resources/qt.conf', 'Nagstamon/resources'],
                        include_msvcr = True,
                        excludes = [])

# put in platform specific options via shell script call like
# :\tools\python\python.exe setup.py build_exe --include-files=Nagstamon/resources/qt.conf,Nagstamon/resources


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



