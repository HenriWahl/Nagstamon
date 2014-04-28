# -*- mode: python -*-
a = Analysis(['..\\Nagstamon\\nagstamon.py'],
             pathex=['..\\Nagstamon\\build'],
             hiddenimports=['Nagstamon.keyring_3_7.credentials',\
                            'Nagstamon.keyring_3_7.backends.file',\
                            'Nagstamon.keyring_3_7.backends.Gnome',\
                            'Nagstamon.keyring_3_7.backends.Google',\
                            'Nagstamon.keyring_3_7.backends.keyczar',\
                            'Nagstamon.keyring_3_7.backends.kwallet',\
                            'Nagstamon.keyring_3_7.backends.multi',\
                            'Nagstamon.keyring_3_7.backends.OS_X',\
                            'Nagstamon.keyring_3_7.backends.pyfs',\
                            'Nagstamon.keyring_3_7.backends.SecretService',\
                            'Nagstamon.keyring_3_7.backends.Windows',\
                            'Nagstamon.keyring_3_7.backends._win_crypto',\
                            'Nagstamon.keyring_3_7.util.escape',\
                            'Nagstamon.keyring_3_7.util.XDG',\
                            'ctypes',\
                            '_ctypes',\
                            'ctypes._endian',\
                            'ctypes.wintypes',\
                            'pywintypes',\
                            'win32cred'],
             hookspath=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=1,
          name=os.path.join('build\\pyi.win32\\nagstamon', 'nagstamon.exe'),
          debug=False,
          strip=None,
          upx=False,
          console=False , icon='..\\Nagstamon\\Nagstamon\\resources\\nagstamon.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=False,
               name=os.path.join('dist', 'nagstamon'))
app = BUNDLE(coll,
             name=os.path.join('dist', 'Nagstamon.app'))
