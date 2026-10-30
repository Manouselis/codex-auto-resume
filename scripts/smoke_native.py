#!/usr/bin/env python3
"""Launch a real frozen GUI, optionally installing/removing its native package.

Smoke mode uses isolated invented data; it never connects to Codex or infers.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args, **kwargs):
    return subprocess.run([os.fspath(a) for a in args], check=True, timeout=120, **kwargs)


def nsis(binary, option, path):
    # NSIS deliberately requires an unquoted final directory, including spaces.
    # Pass a Windows command line directly to CreateProcess, never to a shell.
    command = subprocess.list2cmdline([os.fspath(binary), '/S']) + ' ' + option + os.fspath(path)
    return subprocess.run(command, check=True, timeout=120, shell=False)


def smoke(binary, report):
    start = time.monotonic()
    try:
        run(binary, '--package-smoke', report)
    except subprocess.CalledProcessError as exc:
        details = report.read_text(encoding='utf-8') if report.exists() else 'No smoke report written'
        raise RuntimeError(details) from exc
    result = json.loads(report.read_text(encoding='utf-8'))
    assert result['gui'] and result['bundled_icon'] and result['default_enabled'], result
    assert result['button'] == '+ Add conversation', result
    assert result['demo']['automatic_continuations'] == 1, result
    result['startup_and_smoke_seconds'] = round(time.monotonic() - start, 3)
    result['host'] = platform.platform()
    result['test_scope'] = 'Real packaged Tk GUI + isolated simulation; no live Codex continuation'
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package', type=Path)
    p.add_argument('--report', type=Path, default=ROOT / 'dist/package-smoke.json')
    p.add_argument('--install', action='store_true', help='Install, test and uninstall on disposable CI hosts only')
    args = p.parse_args()
    package = args.package.resolve()
    with tempfile.TemporaryDirectory(prefix='auto-resume-install-') as temporary:
        folder = Path(temporary)
        report = folder / 'gui.json'
        if package.suffix == '.deb':
            if args.install:
                run('sudo', 'dpkg', '-i', package)
                try:
                    result = smoke(Path('/opt/codex-auto-resume/codex-auto-resume'), report)
                finally:
                    run('sudo', 'dpkg', '-r', 'codex-auto-resume')
            else:
                run('dpkg-deb', '-x', package, folder)
                result = smoke(folder / 'opt/codex-auto-resume/codex-auto-resume', report)
        elif package.suffix == '.exe' and args.install:
            target = folder / 'Installed App'
            nsis(package, '/D=', target)
            try:
                assert (target / 'Uninstall.exe').is_file()
                result = smoke(target / 'codex-auto-resume.exe', report)
                # Verify the uninstaller preserves files it does not own.
                (target / 'unrelated.txt').write_text('preserve me')
            finally:
                if (target / 'Uninstall.exe').exists():
                    nsis(target / 'Uninstall.exe', '_?=', target)
            assert not (target / 'codex-auto-resume.exe').exists()
            assert (target / 'unrelated.txt').read_text() == 'preserve me'
        elif package.suffix == '.dmg':
            mount = folder / 'mount'
            run('hdiutil', 'attach', '-nobrowse', '-mountpoint', mount, package)
            try:
                app = folder / 'Codex Auto-Resume.app'
                run('ditto', mount / app.name, app)
            finally:
                run('hdiutil', 'detach', mount)
            result = smoke(app / 'Contents/MacOS/Codex Auto-Resume', report)
            shutil.rmtree(app)
        else:
            result = smoke(package, report)
        result['artifact'] = package.name
        result['installed_and_removed'] = args.install or package.suffix == '.dmg'
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
