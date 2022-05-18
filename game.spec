# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['game.py'],
    pathex=[],
    binaries=[],
    datas=[('maps/*', 'maps'), ('maps/tiles/images/*', 'maps/tiles/images'), ('maps/tiles/*', 'maps/tiles'), ('Graphics/Knight/*', 'Graphics/Knight'), ('Graphics/small_dragon/*', 'Graphics/small_dragon'), ('Graphics/demon_axe_red/*', 'Graphics/demon_axe_red'), ('Graphics/projectiles/*', 'Graphics/projectiles'), ('Graphics/weapons/*', 'Graphics/weapons'), ('Graphics/items/*', 'Graphics/items'), ('Graphics/*', 'Graphics')],
    hiddenimports=['pygame'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='game',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
