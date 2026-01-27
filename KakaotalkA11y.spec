# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/kakaotalk_a11y_client/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/kakaotalk_a11y_client/emojis', 'kakaotalk_a11y_client/emojis'),
        ('docs', 'docs'),
    ],
    hiddenimports=[
        # accessible_output2 - 모든 outputs (조건부 import라 PyInstaller가 감지 못함)
        'accessible_output2',
        'accessible_output2.outputs',
        'accessible_output2.outputs.auto',
        'accessible_output2.outputs.base',
        'accessible_output2.outputs.nvda',
        'accessible_output2.outputs.sapi5',
        'accessible_output2.outputs.jaws',
        'accessible_output2.outputs.window_eyes',
        'accessible_output2.outputs.system_access',
        'accessible_output2.outputs.dolphin',
        'accessible_output2.outputs.pc_talker',
        'accessible_output2.outputs.zdsr',
        # libloader (COM 로딩)
        'libloader',
        'libloader.com',
        'uiautomation',
        'win32api',
        'win32con',
        'win32gui',
        'kakaotalk_a11y_client',
        'kakaotalk_a11y_client.navigation',
        'kakaotalk_a11y_client.navigation.chat_room',
        'kakaotalk_a11y_client.navigation.message_monitor',
        'kakaotalk_a11y_client.utils',
        # wxPython GUI
        'wx',
        'wx.adv',
        'kakaotalk_a11y_client.gui',
        'kakaotalk_a11y_client.gui.app',
        'kakaotalk_a11y_client.gui.main_frame',
        'kakaotalk_a11y_client.gui.tray_icon',
        'kakaotalk_a11y_client.gui.settings_dialog',
        'kakaotalk_a11y_client.gui.hotkey_panel',
        'kakaotalk_a11y_client.gui.status_panel',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # tkinter (미사용, wx 사용)
        'tkinter', '_tkinter', 'tcl', 'tk',
        # 테스트/문서 모듈
        'unittest', 'test', 'pydoc', 'doctest',
        # 네트워크 - email은 pywin32 의존성으로 필요, http는 updater에서 사용
        'html', 'xmlrpc', 'ftplib',
        # 데이터베이스 (미사용)
        'sqlite3',
        # 기타 미사용
        'lib2to3', 'multiprocessing',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KakaotalkA11y',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='KakaotalkA11y',
)
