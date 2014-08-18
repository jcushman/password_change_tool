# -*- mode: python -*-
import os

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))

a = Analysis(['main.py'],
             pathex=[ROOT_DIR],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='main',
          debug=False,
          strip=True,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               Tree('managers','managers'),
               Tree('rules', 'rules'),
               Tree('contrib', 'contrib'),
               Tree('assets', 'assets'),

               # TODO: we should use strip=False, upx=True on windows
               strip=True,
               upx=False,

               name='main')
app = BUNDLE(coll,
             name='FreshPass.app',
             icon='assets/icon.icns',
             #info_plist='build/Info.plist', # not yet supported in pyinstaller 2.0 -- wait for 2.1
)
