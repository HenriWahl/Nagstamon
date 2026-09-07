# -*- mode: python ; coding: utf-8 -*-

import os

try:
    from PyInstaller.utils.hooks import collect_submodules
    # same as the --collect-submodules gssapi.raw of the Linux build - Nagstamon imports
    # gssapi.raw.cython_converters on macOS to get Kerberos support compiled in
    hidden_imports = collect_submodules('gssapi.raw')
except Exception:
    hidden_imports = []

# oldest macOS release Nagstamon is built for - has to match the minimum deployment target
# of the shipped Qt binaries, which the CI verifies after the build
minimum_system_version = os.environ.get('MACOSX_DEPLOYMENT_TARGET', '13.0')

# macOS 26 draws applications in the new Liquid Glass design which Qt does not fully
# support yet - UIDesignRequiresCompatibility keeps the look and metrics of the earlier
# releases. Opt-in via environment variable to be able to build and compare both.
ui_compatibility = os.environ.get('NAGSTAMON_MACOS_UI_COMPAT', '').lower() in ('1', 'true', 'yes')

a = Analysis(['../../nagstamon.py'],
             pathex=[],
             binaries=[],
             datas=[('../../Nagstamon/resources', 'Nagstamon/resources')],
             hiddenimports=hidden_imports,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='Nagstamon',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          # UPX is not supported on macOS arm64 and breaks the ad-hoc signature every
          # arm64 binary needs to be startable at all
          upx=False,
          console=False,
          codesign_identity=None,
          entitlements_file=None,
          icon='../../Nagstamon/resources/nagstamon.icns')

# a one-dir bundle instead of a one-file bundle - macOS empties the /var/folders temp
# directory a one-file bundle unpacks itself into while it is still running
coll = COLLECT(exe,
               a.binaries,
               a.datas,
               strip=False,
               upx=False,
               name='Nagstamon')

info_plist = {
    'CFBundleName': 'Nagstamon',
    'CFBundleDisplayName': 'Nagstamon',
    # without CFBundleVersion crash reports show the version as '???'
    'CFBundleVersion': os.environ['NAGSTAMON_VERSION'],
    'LSMinimumSystemVersion': minimum_system_version,
    'NSHighResolutionCapable': True,
    'NSRequiresAquaSystemAppearance': False,
    'LSBackgroundOnly': False,
    # LSUIElement hides the icon in dock
    'LSUIElement': True
}

if ui_compatibility:
    info_plist['UIDesignRequiresCompatibility'] = True

app = BUNDLE(coll,
             name='Nagstamon.app',
             icon='../../Nagstamon/resources/nagstamon.icns',
             bundle_identifier='de.nagstamon',
             version=os.environ['NAGSTAMON_VERSION'],
             info_plist=info_plist)
