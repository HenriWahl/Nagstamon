# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

a = Analysis(['../../nagstamon.py'],
             pathex=[],
             binaries=[],
             datas=[('../../Nagstamon/resources', 'Nagstamon/resources')],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='Nagstamon',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='../../Nagstamon/resources/nagstamon.icns')

# LSUIElement in info_plist hides the icon in dock
app = BUNDLE(exe,
             name='Nagstamon.app',
             icon='../../Nagstamon/resources/nagstamon.icns',
             bundle_identifier='de.nagstamon',
             version=os.environ['NAGSTAMON_VERSION'],
             info_plist={
                'NSRequiresAquaSystemAppearance': False,
                'LSBackgroundOnly': False,
                'LSUIElement': True
             })
