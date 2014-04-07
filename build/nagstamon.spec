# -*- mode: python -*-
a = Analysis(['..\\Nagstamon\\nagstamon.py'],
             pathex=['..\\Nagstamon\\build'],
             hiddenimports=['Nagstamon.keyring.credentials',\
                            'Nagstamon.keyring.backends.file',\
                            'Nagstamon.keyring.backends.Gnome',\
                            'Nagstamon.keyring.backends.Google',\
                            'Nagstamon.keyring.backends.keyczar',\
                            'Nagstamon.keyring.backends.kwallet',\
                            'Nagstamon.keyring.backends.multi',\
                            'Nagstamon.keyring.backends.OS_X',\
                            'Nagstamon.keyring.backends.pyfs',\
                            'Nagstamon.keyring.backends.SecretService',\
                            'Nagstamon.keyring.backends.Windows',\
                            'Nagstamon.keyring.backends._win_crypto',\
                            'Nagstamon.keyring.util.escape',\
                            'Nagstamon.keyring.util.XDG',\
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
