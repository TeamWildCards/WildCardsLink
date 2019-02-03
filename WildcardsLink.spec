# -*- mode: python -*-

block_cipher = None


a = Analysis(['Wildcards_Main.py'],
             pathex=['D:\\Users\\david\\Downloads\\Wildcardslink'],
             binaries=[],
             datas=[('*.ico', '.')],
             hiddenimports=['pkg_resources'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['FixTk', 'tk', 'tcl', '_tkinter', 'tkinter', 'Tkinter'],
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
          name='WildcardsLink',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False , icon='wc_site_icon_filled.ico')
