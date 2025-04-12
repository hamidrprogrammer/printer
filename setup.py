"""
Setup script for creating a macOS application bundle (.app) using py2app
"""

from setuptools import setup

APP = ['main_mac.py']
DATA_FILES = ['serviceAccountKey.json']
OPTIONS = {
    'argv_emulation': True,
    'packages': ['firebase_admin', 'cups', 'customtkinter'],
    'iconfile': 'icons/app_icon.icns',
    'plist': {
        'CFBundleName': 'PrinterSync Pro',
        'CFBundleDisplayName': 'PrinterSync Pro',
        'CFBundleIdentifier': 'com.printersync.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '© 2025 PrinterSync',
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'LSMinimumSystemVersion': '10.14',
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'NSRequiresAquaSystemAppearance': False,
    },
}

setup(
    name='PrinterSync Pro',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
