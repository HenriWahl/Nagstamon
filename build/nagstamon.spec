# -*- mode: python -*-
a = Analysis(['..\\Nagstamon\\nagstamon.py'],
             pathex=['..\\Nagstamon\\build'],
             hiddenimports=['Nagstamon.thirdparty.keyring.credentials',\
                            'Nagstamon.thirdparty.keyring.backends.file',\
                            'Nagstamon.thirdparty.keyring.backends.Gnome',\
                            'Nagstamon.thirdparty.keyring.backends.Google',\
                            'Nagstamon.thirdparty.keyring.backends.keyczar',\
                            'Nagstamon.thirdparty.keyring.backends.kwallet',\
                            'Nagstamon.thirdparty.keyring.backends.multi',\
                            'Nagstamon.thirdparty.keyring.backends.OS_X',\
                            'Nagstamon.thirdparty.keyring.backends.pyfs',\
                            'Nagstamon.thirdparty.keyring.backends.SecretService',\
                            'Nagstamon.thirdparty.keyring.backends.Windows',\
                            'Nagstamon.thirdparty.keyring.backends._win_crypto',\
                            'Nagstamon.thirdparty.keyring.util.escape',\
                            'Nagstamon.thirdparty.keyring.util.XDG',\
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
