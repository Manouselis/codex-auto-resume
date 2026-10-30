#!/usr/bin/env python3
"""Build on the target OS: standalone onedir runtime + graphical installer."""
import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from auto_resume import __version__ as VERSION


def run(*command):
    subprocess.run([os.fspath(c) for c in command], check=True)


def build():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-only', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'dist/native'
    work = ROOT / 'dist/work'
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    icon = Image.open(ROOT / 'auto_resume/assets/icon.png').convert('RGBA')
    icon.resize((1024, 1024)).save(work / 'icon.icns')
    icon.save(work / 'icon.ico', sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
    name = 'Codex Auto-Resume' if sys.platform == 'darwin' else 'codex-auto-resume'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--noupx',
               '--name', name, '--distpath', str(output), '--workpath', str(work / 'pyinstaller'),
               '--specpath', str(work), '--paths', str(ROOT), '--collect-data', 'auto_resume',
               '--add-data', str(ROOT / 'packaging/licenses') + ':licenses',
               '--add-data', str(ROOT / 'LICENSE') + ':licenses',
               '--add-data', str(ROOT / 'packaging/THIRD_PARTY.md') + ':licenses']
    if sys.platform == 'win32':
        version_info = work / 'windows-version.txt'
        file_version = tuple(int(part) for part in VERSION.split('.')) + (0,)
        version_info.write_text(f"""VSVersionInfo(
ffi=FixedFileInfo(filevers={file_version},prodvers={file_version},mask=0x3f,flags=0,OS=0x40004,fileType=0x1,subtype=0,date=(0,0)),
kids=[StringFileInfo([StringTable('040904B0',[
StringStruct('CompanyName','Manouselis'),StringStruct('FileDescription','Codex Auto-Resume'),
StringStruct('FileVersion','{VERSION}'),StringStruct('ProductName','Codex Auto-Resume'),
StringStruct('ProductVersion','{VERSION}'),StringStruct('LegalCopyright','MIT licensed')])]),
VarFileInfo([VarStruct('Translation',[1033,1200])])])
""", encoding='utf-8')
        command += ['--windowed', '--icon', str(work / 'icon.ico'), '--version-file', str(version_info)]
    elif sys.platform == 'darwin':
        command += ['--windowed', '--icon', str(work / 'icon.icns'),
                    '--osx-bundle-identifier', 'io.github.manouselis.codex-auto-resume']
    command += [str(ROOT / 'packaging/desktop_entry.py')]
    run(*command)
    if sys.platform == 'darwin':
        app = output / f'{name}.app'
        info_path = app / 'Contents/Info.plist'
        with info_path.open('rb') as handle:
            info = plistlib.load(handle)
        info.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION,
                    LSMinimumSystemVersion='14.0' if platform.machine() == 'arm64' else '15.0',
                    NSHighResolutionCapable=True)
        with info_path.open('wb') as handle:
            plistlib.dump(info, handle)
        run('codesign', '--force', '--deep', '--sign', '-', app)
        run('codesign', '--verify', '--deep', '--strict', app)
    if args.bundle_only:
        return
    release = ROOT / 'dist/release'
    release.mkdir(parents=True, exist_ok=True)
    machine = platform.machine().lower()
    arch = 'arm64' if machine in ('arm64', 'aarch64') else 'x64'
    stem = f'codex-auto-resume-{VERSION}'
    if sys.platform.startswith('linux'):
        package = work / 'deb'
        if package.exists():
            shutil.rmtree(package)
        application = package / 'opt/codex-auto-resume'
        application.parent.mkdir(parents=True)
        shutil.copytree(output / name, application, symlinks=True)
        (package / 'DEBIAN').mkdir()
        size = sum(p.stat().st_size for p in application.rglob('*') if p.is_file()) // 1024
        (package / 'DEBIAN/control').write_text(f'''Package: codex-auto-resume
Version: {VERSION}
Section: utils
Priority: optional
Architecture: {'arm64' if arch == 'arm64' else 'amd64'}
Depends: libc6 (>= 2.35), libx11-6, libxext6, libxrender1, libxft2, libfontconfig1
Maintainer: Pantelis Manouselis <noreply@github.com>
Installed-Size: {size}
Homepage: https://github.com/Manouselis/codex-auto-resume
Description: Resume armed Codex chats when included usage resets
 Standalone desktop companion. Requires the official Codex desktop app.
''')
        desktop = package / 'usr/share/applications/codex-auto-resume.desktop'
        desktop.parent.mkdir(parents=True)
        desktop.write_text('''[Desktop Entry]
Type=Application
Name=Codex Auto-Resume
Comment=Continue armed Codex chats after included usage resets
Exec=/opt/codex-auto-resume/codex-auto-resume
Icon=codex-auto-resume
Terminal=false
Categories=Utility;
StartupWMClass=CodexAutoResume
''')
        png = package / 'usr/share/icons/hicolor/256x256/apps/codex-auto-resume.png'
        png.parent.mkdir(parents=True)
        shutil.copy2(ROOT / 'auto_resume/assets/icon.png', png)
        license_path = package / 'usr/share/doc/codex-auto-resume/copyright'
        license_path.parent.mkdir(parents=True)
        shutil.copy2(ROOT / 'LICENSE', license_path)
        run('dpkg-deb', '--root-owner-group', '--build', package, release / f'{stem}-linux-{arch}.deb')
    elif sys.platform == 'win32':
        compiler = shutil.which('makensis') or r'C:\Program Files (x86)\NSIS\makensis.exe'
        run(compiler, '/WX', f'/DVERSION={VERSION}', f'/DBUNDLE={output / name}', f'/DICON={work / "icon.ico"}',
            f'/DLICENSE={ROOT / "LICENSE"}', f'/DOUTPUT={release / (stem + "-windows-" + arch + "-setup.exe")}',
            ROOT / 'packaging/windows.nsi')
    elif sys.platform == 'darwin':
        volume = work / 'dmg'
        if volume.exists():
            shutil.rmtree(volume)
        volume.mkdir()
        run('ditto', output / f'{name}.app', volume / f'{name}.app')
        (volume / 'Applications').symlink_to('/Applications')
        run('hdiutil', 'create', '-volname', name, '-srcfolder', volume, '-ov', '-format', 'UDZO',
            release / f'{stem}-macos-{arch}.dmg')
    else:
        raise SystemExit('Unsupported build platform')
    artifacts = [p for p in sorted(release.iterdir()) if p.suffix in ('.deb', '.exe', '.dmg')]
    (release / f'SHA256SUMS-{sys.platform}-{arch}.txt').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in artifacts))
    print(json.dumps({'version': VERSION, 'os': platform.platform(), 'arch': arch,
                      'artifacts': [p.name for p in artifacts]}, indent=2))


if __name__ == '__main__':
    build()
