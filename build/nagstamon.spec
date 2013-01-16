# -*- mode: python -*-
a = Analysis(['..\\Nagstamon\\nagstamon.py'],
             pathex=['..\\Nagstamon\\build'],
             hiddenimports=[],
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
