# -*- mode: python ; coding: utf-8 -*-
# 打字对战服务端打包配置文件


a = Analysis(
    ['main.py'],
    pathex=['.', '..'],
    binaries=[],
    datas=[('..\\common', 'common'), ('data', 'data'), ('protocol.md', '.'), ('..\\server.ico', '.')],
    hiddenimports=[
        'common', 
        'common.logger', 
        'common.protocol', 
        'common.models', 
        'logging', 
        'logging.handlers', 
        'websockets', 
        'websockets.legacy', 
        'websockets.server', 
        'websockets.protocol', 
        'asyncio', 
        'json', 
        'uuid', 
        'psutil'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6.QtNetwork', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuick3D',
        'PyQt6.QtTest', 'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel', 'PyQt6.QtBluetooth', 'PyQt6.QtPositioning',
        'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtSensors',
        'PyQt6.QtSerialPort', 'PyQt6.QtSql', 'PyQt6.QtSvg', 'PyQt6.QtXml',
        'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets', 'PyQt6.QtPrintSupport',
        'PyQt6.QtHelp', 'PyQt6.QtTextToSpeech', 'PyQt6.QtCharts',
        'PyQt6.QtDataVisualization', 'PyQt6.QtLocation',
        'tensorflow', 'torch', 'tkinter', 'notebook', 'jupyter',
        'matplotlib', 'scipy', 'pandas',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TypeBattleServer',
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
    icon='..\\server.ico',
)
