#!/usr/bin/env python3
"""Launch a real frozen GUI, optionally installing/removing its native package.

Smoke mode uses isolated invented data; it never connects to Codex or infers.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from auto_resume import __version__, update
from auto_resume.linux_shortcuts import DESKTOP_NAME, source_entry
from auto_resume.store import Store


def run(*args, **kwargs):
    return subprocess.run([os.fspath(a) for a in args], check=True, timeout=120, **kwargs)


def nsis(binary, option='', path=None):
    # NSIS deliberately requires an unquoted final directory, including spaces.
    # Pass a Windows command line directly to CreateProcess, never to a shell.
    command = subprocess.list2cmdline([os.fspath(binary), '/S'])
    if path is not None:
        command += ' ' + option + os.fspath(path)
    return subprocess.run(command, check=True, timeout=120, shell=False)


def smoke(binary, report, *, relaunch=False):
    start = time.monotonic()
    command = [binary, '--package-smoke', report]
    if relaunch:
        restart = 'import sys; from auto_resume.update import relaunch; sys.executable = sys.argv.pop(1); relaunch()'
        command = [sys.executable, '-c', restart, *command]
    try:
        # The first argument after -c becomes the executable to restart.
        run(*command, cwd=ROOT)
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


def apt_install(package):
    run('sudo', 'apt-get', '-y', '--no-install-recommends', '-o', 'DPkg::Lock::Timeout=30', 'install', package)


def package_release(package):
    return update.Release(__version__, package.name, "", hashlib.sha256(package.read_bytes()).hexdigest(),
                          package.stat().st_size)


def install_deb_update(package):
    execute = update._run

    def headless(command, **options):
        # CI has sudo access and no desktop polkit authentication agent.
        if command[0] == "/usr/bin/pkexec":
            command = ["sudo", "-n", *command[2:]]
        return execute(command, **options)

    with patch.object(update, "_run", side_effect=headless):
        update._install_ubuntu(package, package_release(package))


@contextmanager
def legacy_shortcut():
    """Seed the historical default desktop entry for the disposable CI user."""
    import pwd

    prefix = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve() / ".local"
    directory = prefix / "share/applications"
    directory.mkdir(parents=True, exist_ok=True)
    entry = directory / DESKTOP_NAME
    original = source_entry(sys.executable, prefix.resolve()).encode()
    existing_backups = set(directory.glob(".codex-auto-resume-*.source-backup"))
    # Refuse to overwrite any real launcher, even when run outside CI.
    with entry.open("xb") as stream:
        stream.write(original)

    def backups():
        return set(directory.glob(".codex-auto-resume-*.source-backup")) - existing_backups

    def verify():
        assert not entry.exists(), "Legacy source launcher still shadows the system installer"
        archived = backups()
        assert len(archived) == 1, archived
        backup = archived.pop()
        assert backup.read_bytes() == original and backup.stat().st_uid == os.getuid()
        assert "Exec=/usr/bin/codex-auto-resume\n" in (Path("/usr/share/applications") / DESKTOP_NAME).read_text()

    try:
        yield verify
    finally:
        if not entry.is_symlink() and entry.is_file() and entry.read_bytes() == original:
            entry.unlink()
        for backup in backups():
            if not backup.is_symlink() and backup.read_bytes() == original:
                backup.unlink()


def upgrade_deb(previous, package, folder, report):
    old_binary = Path('/opt/codex-auto-resume/codex-auto-resume')
    new_binary = Path('/usr/bin/codex-auto-resume')
    apt_install(previous)
    try:
        old_version = run(old_binary, '--version', capture_output=True, text=True).stdout.strip()
        state = folder / 'existing-state.sqlite3'
        command = [str(old_binary), '--simulation', '--state', str(state)]
        run(*command, 'arm', 'demo-task', capture_output=True, text=True)
        with subprocess.Popen([*command, 'run'], stdout=subprocess.DEVNULL) as controller:
            try:
                deadline = time.monotonic() + 10
                with closing(sqlite3.connect(state)) as database:
                    while database.execute("SELECT value FROM meta WHERE key='controller_heartbeat'").fetchone()[0] == '0':
                        if controller.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError('Previous controller did not start')
                        time.sleep(0.1)
                start = time.monotonic()
                with legacy_shortcut() as verify_shortcut:
                    install_deb_update(package)
                    verify_shortcut()
                upgrade_seconds = round(time.monotonic() - start, 3)
                assert controller.poll() is None, 'Upgrade interrupted the previous controller'
                installed = run('dpkg-query', '-W', '-f=${Version}', 'codex-auto-resume',
                                capture_output=True, text=True).stdout.strip()
                result = smoke(new_binary, report, relaunch=True)
                assert installed == result['version'] and installed != old_version, result
                status = run(new_binary, '--simulation', '--state', state, 'status', capture_output=True, text=True)
                assert [task['thread_id'] for task in json.loads(status.stdout)['tasks']] == ['demo-task']
                with closing(sqlite3.connect(state)) as database:
                    assert database.execute('SELECT thread_id, eligible FROM tasks').fetchall() == [('demo-task', 1)]
            finally:
                if controller.poll() is None:
                    controller.terminate()
                    controller.wait(timeout=10)
        result.update(upgraded_from=old_version, apt_upgrade_seconds=upgrade_seconds, existing_state_preserved=True,
                      legacy_shortcut_migrated=True)
        return result
    finally:
        run('sudo', 'dpkg', '-r', 'codex-auto-resume')


def launch_windows_dashboard(binary, folder):
    """Start the installed app normally and close its actual Tk dashboard."""
    import ctypes
    from ctypes import wintypes

    profile_state = folder / 'Local données # user'
    state = profile_state / 'codex-auto-resume/state.sqlite3'
    with closing(Store(state)) as store:
        store.db.execute("INSERT INTO recovery_messages VALUES (?, ?)", ('fixture-chat', 'Keep this message'))
    run(sys.executable, ROOT / 'tests/fixtures/interrupt_database.py', state)
    journal = state.with_name(state.name + '-journal')
    with journal.open('rb') as stream:
        assert stream.read(8) == bytes.fromhex('d9d505f920a163d7'), 'Fixture must require rollback'

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    with subprocess.Popen([str(binary)], cwd=folder, env={**os.environ, 'LOCALAPPDATA': str(profile_state)}) as app:
        windows = {}

        @callback
        def inspect(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == app.pid and user32.IsWindowVisible(hwnd):
                name = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, name, len(name))
                if name.value == 'Codex Auto-Resume':
                    user32.GetClassNameW(hwnd, name, len(name))
                    windows[name.value] = hwnd
            return True

        deadline = time.monotonic() + 45
        try:
            while True:
                windows.clear()
                user32.EnumWindows(inspect, 0)
                if '#32770' in windows:
                    raise RuntimeError('Normal Windows launch displayed a startup error dialog')
                if 'TkTopLevel' in windows:
                    assert not journal.exists(), 'The normal launch did not roll back the interrupted write'
                    with closing(sqlite3.connect(state)) as database:
                        assert database.execute(
                            "SELECT message FROM recovery_messages WHERE thread_id='fixture-chat'"
                        ).fetchone() == ('Keep this message',), 'The saved recovery message was lost'
                    assert user32.PostMessageW(windows['TkTopLevel'], 0x0010, 0, 0), 'Could not close the dashboard'
                    assert app.wait(timeout=15) == 0, 'Windows dashboard did not exit cleanly'
                    break
                if app.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(f'No dashboard on normal Windows launch (exit {app.poll()})')
                time.sleep(0.2)
        finally:
            if app.poll() is None:
                app.terminate()
                app.wait(timeout=10)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package', type=Path)
    p.add_argument('--report', type=Path, default=ROOT / 'dist/package-smoke.json')
    p.add_argument('--install', action='store_true', help='Install, test and uninstall on disposable CI hosts only')
    p.add_argument('--upgrade-from', type=Path, help='Install this older DEB, EXE or DMG before updating in place')
    args = p.parse_args()
    package = args.package.resolve()
    if args.upgrade_from and (package.suffix not in ('.deb', '.dmg', '.exe')
                              or (package.suffix != '.dmg' and not args.install)):
        p.error('--upgrade-from requires a DMG, or a DEB or EXE with --install')
    with tempfile.TemporaryDirectory(prefix='auto-resume-install-') as temporary:
        folder = Path(temporary)
        report = folder / 'gui.json'
        if package.suffix == '.deb':
            if args.upgrade_from:
                result = upgrade_deb(args.upgrade_from.resolve(), package, folder, report)
            elif args.install:
                with legacy_shortcut() as verify_shortcut:
                    apt_install(package)
                    try:
                        verify_shortcut()
                        result = smoke(Path('/usr/bin/codex-auto-resume'), report)
                        result['legacy_shortcut_migrated'] = True
                    finally:
                        run('sudo', 'dpkg', '-r', 'codex-auto-resume')
            else:
                run('dpkg-deb', '-x', package, folder)
                result = smoke(folder / 'opt/codex-auto-resume/codex-auto-resume', report)
        elif package.suffix == '.exe' and args.install:
            target = folder / 'Installed App'
            binary = target / 'codex-auto-resume.exe'
            prior = args.upgrade_from.resolve() if args.upgrade_from else package
            nsis(prior, '/D=', target)
            try:
                assert (target / 'Uninstall.exe').is_file()
                previous = None
                if args.upgrade_from:
                    previous = smoke(binary, report)['version']
                    assert previous != __version__, 'Expected to start with an older installer'
                    nsis(package)
                result = smoke(binary, report)
                assert result['version'] == __version__, 'The installer did not replace the existing app'
                launch_windows_dashboard(binary, folder)
                result.update(normal_dashboard_launch=True, interrupted_state_preserved=True)
                if previous:
                    result.update(upgraded_from=previous, custom_windows_install_upgraded_in_place=True)
                # Verify the uninstaller preserves files it does not own.
                (target / 'unrelated.txt').write_text('preserve me')
            finally:
                if (target / 'Uninstall.exe').exists():
                    nsis(target / 'Uninstall.exe', '_?=', target)
                    # _?= runs the uninstaller in place, so it cannot delete itself.
                    # Windows can briefly retain a handle even after the process exits.
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            (target / 'Uninstall.exe').unlink(missing_ok=True)
                            break
                        except PermissionError:
                            if time.monotonic() >= deadline:
                                raise
                            time.sleep(0.25)
            assert not (target / 'codex-auto-resume.exe').exists()
            assert not (target / '_internal').exists(), 'The bundled Windows runtime was not removed'
            assert (target / 'unrelated.txt').read_text() == 'preserve me'
        elif package.suffix == '.dmg':
            mount = folder / 'mount'
            run('hdiutil', 'attach', '-nobrowse', '-mountpoint', mount, args.upgrade_from or package)
            try:
                app = folder / 'Codex Auto-Resume.app'
                run('ditto', mount / app.name, app)
            finally:
                run('hdiutil', 'detach', mount)
            if args.upgrade_from:
                previous = update._mac_bundle(app)
                assert previous != __version__
                with patch.object(update, "__version__", previous):
                    update._install_macos(package, package_release(package), app)
                result = smoke(app / 'Contents/MacOS/Codex Auto-Resume', report, relaunch=True)
                assert result['version'] == __version__
                result['upgraded_from'] = previous
            else:
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
