# -*- mode: python -*-

block_cipher = None


a = Analysis(['FloowerFlasher.py'],
             pathex=['c:\\Users\\Georgus\\Documents\\Projects\\tulip2\\floower-flasher'],
             binaries=[],
             datas=[('logo.ico', '.')],
             hiddenimports=[],
             hookspath=[],
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
          name='Floower Flasher',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False , icon='logo.ico')
app = BUNDLE(exe,
             name='FloowerFlasher.app',
             icon='logo.png.icns',
             bundle_identifier='com.jiripraus.floowerFlasher',
             info_plist={
            'NSHighResolutionCapable': 'True'
            },)
