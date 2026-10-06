# Build on Windows for a Windows executable. No credentials are bundled.
a = Analysis(['app.py'], pathex=[], binaries=[], datas=[('templates', 'templates'), ('site_data.json', '.')], hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='TextGenerator', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
