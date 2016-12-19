a = Analysis(['../bin/svtplay-dl'],
             binaries=None,
             datas=None,
             hiddenimports=["Crypto"],
             hookspath=None,
             runtime_hooks=None,
             excludes=None)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='svtplay-dl',
          debug=False,
          strip=None,
          upx=False,
          console=True)