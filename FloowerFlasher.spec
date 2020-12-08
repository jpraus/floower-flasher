# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['FloowerFlasher.py'],
        pathex=['/Users/jiripraus/Code/floower-flasher'],
        binaries=[],
        datas=[('logo.ico', '.'), ('floower.jpg', '.')],
        hiddenimports=[],
        hookspath=[],
        runtime_hooks=[],
        excludes=[],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
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
        console=True,
        icon='logo.ico')
app = BUNDLE(exe,
        name='Floower Flasher.app',
        icon='logo.icns',
        bundle_identifier='io.floower.flasher',
        info_plist={
            'NSHighResolutionCapable': 'True'
        },)
