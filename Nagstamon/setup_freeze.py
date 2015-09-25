from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
build_exeOptions = dict(packages = ['PyQt5.QtNetwork',
                                    'keyring.backends.file',
                                    'keyring.backends.Gnome',
                                    'keyring.backends.Google',
                                    'keyring.backends.kwallet',
                                    'keyring.backends.multi',
                                    'keyring.backends.OS_X',
                                    'keyring.backends.pyfs',
                                    'keyring.backends.SecretService',
                                    'keyring.backends.Windows'],
                        excludes = [])

# put in platform specific options via shell script call like
# :\tools\python\python.exe setup.py build_exe --include-files=Nagstamon/resources/qt.conf,Nagstamon/resources


bdist_macOptions = dict(iconfile = 'Nagstamon/resources/nagstamon.icns')

import sys
base = 'Win32GUI' if sys.platform=='win32' else None

executables = [
    Executable('nagstamon-qt.py',
               base=base,
               icon='Nagstamon/resources/nagstamon.ico')
]

setup(name='Nagstamon',
      version = '2.0-alpha',
      description = 'Nagstamon',
      options = dict(build_exe = build_exeOptions,
                     bdist_mac = bdist_macOptions),
      executables = executables
    )



