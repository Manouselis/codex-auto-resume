import hashlib
import io
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from auto_resume import update


WINDOWS = "windows-x64-setup.exe"


def published(version, payload=b"verified bytes", *, target=WINDOWS, **fields):
    name = f"codex-auto-resume-{version}-{target}"
    return {"tag_name": f"v{version}", "prerelease": True, "assets": [{
        "name": name, "size": len(payload), "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "browser_download_url": f"https://github.com/{update.REPO}/releases/download/v{version}/{name}",
    }], **fields}


def atom_feed(*versions):
    links = "".join(f'<entry><link rel="alternate" href="{update.RELEASE_PAGE}/tag/v{version}"/></entry>'
                    for version in versions)
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{links}</feed>'.encode()


class UpdateTests(unittest.TestCase):
    def test_selects_latest_compatible_published_beta_by_version(self):
        wrong_url = published("5.0.0")
        wrong_url["assets"][0]["browser_download_url"] = "https://example.com/installer.exe"
        no_digest = published("4.0.0")
        no_digest["assets"][0]["digest"] = None
        releases = [published("0.10.0"), published("0.9.0"), published("6.0.0", draft=True),
                    wrong_url, no_digest, published("3.0.0", assets=[])]
        self.assertEqual(update.select_release(releases, current="0.8.1", target=WINDOWS).version, "0.10.0")
        self.assertIsNone(update.select_release(releases, current="0.10.0", target=WINDOWS))

    def test_selects_newest_release_with_a_compatible_asset(self):
        for platform, arch, target in (("win32", "ARM64", WINDOWS), ("linux", "x86_64", "linux-x64.deb"),
                                       ("darwin", "arm64", "macos-arm64.dmg"),
                                       ("darwin", "x86_64", "macos-x64.dmg")):
            other = "macos-arm64.dmg" if target != "macos-arm64.dmg" else "macos-x64.dmg"
            with (self.subTest(target=target), patch("auto_resume.update.sys.platform", platform),
                  patch("auto_resume.update.platform.machine", return_value=arch)):
                self.assertEqual(update.package_target(), target)
                releases = [published("2.0.0", target=other), published("1.3.0", target=target)]
                self.assertEqual(update.select_release(releases, target=target).version, "1.3.0")

    def test_download_saves_only_verified_installer(self):
        payload = b"verified bytes"
        release = update.select_release([published("1.2.3", payload)], target=WINDOWS)
        with tempfile.TemporaryDirectory() as folder, patch("auto_resume.update._cache_dir", return_value=Path(folder)):
            for invalid in (b"incorrect byte", b"short", payload + b"extra"):
                with patch("auto_resume.update.urlopen", return_value=io.BytesIO(invalid)):
                    with self.assertRaises(ValueError):
                        update.download_update(release)
                self.assertEqual(list(Path(folder).iterdir()), [])
            with patch("auto_resume.update.urlopen", return_value=io.BytesIO(payload)):
                result = update.download_update(release)
            self.assertEqual(result.name, release.name)
            self.assertEqual(result.read_bytes(), payload)

    def test_update_uses_atom_and_checksums_without_the_rest_api(self):
        payload = b"verified Windows build"
        digest = hashlib.sha256(payload).hexdigest()
        name = "codex-auto-resume-1.2.3-windows-x64-setup.exe"
        assets = f"{update.RELEASE_PAGE}/download/v1.2.3/"

        def read(request, timeout):
            body = {
                f"{update.RELEASE_PAGE}.atom": atom_feed("0.8.2", "1.2.3"),
                assets + "SHA256SUMS": f"{digest}  {name}\n".encode(),
                assets + name: payload,
            }[getattr(request, "full_url", request)]
            return io.BytesIO(body)

        with (tempfile.TemporaryDirectory() as folder,
              patch.object(update, "_cache_dir", return_value=Path(folder)),
              patch.object(update, "installed_target", return_value=WINDOWS),
              patch.object(update, "_open_url", side_effect=read)):
            release = update.check_for_update()
            self.assertEqual(release, update.Release("1.2.3", name, assets + name, digest, None))
            with patch.object(update, "MAX_INSTALLER_SIZE", len(payload) - 1):
                with self.assertRaisesRegex(ValueError, "Unexpected installer size"):
                    update.download_update(release)
            self.assertEqual(list(Path(folder).iterdir()), [])
            self.assertEqual(update.download_update(release).read_bytes(), payload)

    def test_atom_up_to_date_checks_no_other_endpoints(self):
        with patch.object(update, "_open_url", return_value=io.BytesIO(atom_feed("0.8.3", "0.8.4"))) as request:
            self.assertIsNone(update._select_feed_release(WINDOWS, current="0.8.4"))
        self.assertEqual(request.call_count, 1)

    def test_rest_metadata_still_works_if_atom_is_unavailable(self):
        error = HTTPError(f"{update.RELEASE_PAGE}.atom", 503, "Unavailable", {}, None)
        body = io.BytesIO(json.dumps([published("1.2.3")]).encode())
        with (tempfile.TemporaryDirectory() as folder,
              patch.object(update, "_cache_dir", return_value=Path(folder)),
              patch.object(update, "installed_target", return_value=WINDOWS),
              patch.object(update, "_open_url", side_effect=[error, body]) as request):
            self.assertEqual(update.check_for_update().version, "1.2.3")
            self.assertEqual(request.call_args.args[0].full_url, update.RELEASES)

    def test_mac_offers_updates_for_installed_app_but_not_read_only_disk_image(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Codex Auto-Resume.app"
            binary = app / "Contents/MacOS/Codex Auto-Resume"
            binary.parent.mkdir(parents=True)
            binary.touch()
            (app / "Contents/Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier": update.MAC_BUNDLE_ID,
                "CFBundleExecutable": binary.name,
                "CFBundleShortVersionString": update.__version__,
            }))
            with (patch("auto_resume.update.sys.platform", "darwin"),
                  patch("auto_resume.update.sys.executable", str(binary)),
                  patch("auto_resume.update.sys.frozen", True, create=True),
                  patch("auto_resume.update.platform.machine", return_value="arm64"),
                  patch("auto_resume.update.os.ST_RDONLY", 1, create=True),
                  patch("auto_resume.update.os.statvfs", create=True) as stat):
                stat.return_value.f_flag = 0
                self.assertEqual(update.installed_target(), "macos-arm64.dmg")
                stat.return_value.f_flag = 1
                self.assertIsNone(update.installed_target())

    def test_ubuntu_validates_deb_before_requesting_authorization(self):
        target = "linux-x64.deb"
        release = update.select_release([published("1.2.3", target=target)], target=target)
        installer = Path(release.name)
        invalid = subprocess.CompletedProcess([], 0, stdout=b"other-package\n1.2.3\namd64\n")
        valid = subprocess.CompletedProcess([], 0, stdout=b"codex-auto-resume\n1.2.3\namd64\n")
        with patch("auto_resume.update._run", return_value=invalid) as run:
            with self.assertRaises(ValueError):
                update._install_ubuntu(installer, release)
            run.assert_called_once()
        with (patch("auto_resume.update._run", return_value=valid) as run,
              patch("auto_resume.update.os.geteuid", return_value=1000, create=True)):
            update._install_ubuntu(installer, release)
            install = run.call_args_list[1].args[0]
            self.assertEqual(install[:3], ["/usr/bin/pkexec", "--disable-internal-agent", "/bin/sh"])
            self.assertEqual(install[-2:], [str(installer), release.digest])
            self.assertIn("codex-auto-resume-native.service", run.call_args_list[2].args[0])

    def test_windows_handoff_keeps_install_path_and_releases_main_process(self):
        target = WINDOWS
        release = update.select_release([published("1.2.3", target=target)], target=target)
        installer = Path(release.name)
        executable = Path("Installed App") / "codex-auto-resume.exe"
        with (patch("auto_resume.update.sys.platform", "win32"),
              patch("auto_resume.update.installed_target", return_value=target),
              patch("auto_resume.update.sys.executable", str(executable)),
              patch("auto_resume.update.subprocess.Popen") as run):
            self.assertFalse(update.install_update(installer, release))
        command = run.call_args.args[0]
        self.assertIn("/UPDATEPID=", command)
        self.assertTrue(command.endswith(" /D=Installed App"))
        self.assertEqual(run.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    @unittest.skipIf(sys.platform == "win32", "POSIX exec replaces the old process")
    def test_relaunch_preserves_original_arguments_and_resets_frozen_environment(self):
        with (patch("auto_resume.update.sys.argv", ["app", "--state", "state.sqlite3", "ui"]),
              patch("auto_resume.update.os.execve") as execute):
            update.relaunch()
        binary, args, env = execute.call_args.args
        self.assertEqual(args, [binary, "--state", "state.sqlite3", "ui"])
        self.assertEqual(env["PYINSTALLER_RESET_ENVIRONMENT"], "1")
