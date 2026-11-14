import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_resume.update import REPO, download_update, select_release


def published(version, payload=b"verified bytes", **fields):
    name = f"codex-auto-resume-{version}-windows-x64-setup.exe"
    return {"tag_name": f"v{version}", "prerelease": True, "assets": [{
        "name": name, "size": len(payload), "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "browser_download_url": f"https://github.com/{REPO}/releases/download/v{version}/{name}",
    }], **fields}


class UpdateTests(unittest.TestCase):
    def test_selects_latest_compatible_published_beta_by_version(self):
        wrong_url = published("5.0.0")
        wrong_url["assets"][0]["browser_download_url"] = "https://example.com/installer.exe"
        no_digest = published("4.0.0")
        no_digest["assets"][0]["digest"] = None
        releases = [published("0.10.0"), published("0.9.0"), published("6.0.0", draft=True),
                    wrong_url, no_digest, published("3.0.0", assets=[])]
        self.assertEqual(select_release(releases, current="0.8.1").version, "0.10.0")
        self.assertIsNone(select_release(releases, current="0.10.0"))

    def test_download_saves_only_verified_installer(self):
        payload = b"verified bytes"
        release = select_release([published("1.2.3", payload)])
        with tempfile.TemporaryDirectory() as folder, patch("auto_resume.update._cache_dir", return_value=Path(folder)):
            for invalid in (b"incorrect byte", b"short", payload + b"extra"):
                with patch("auto_resume.update.urlopen", return_value=io.BytesIO(invalid)):
                    with self.assertRaises(ValueError):
                        download_update(release)
                self.assertEqual(list(Path(folder).iterdir()), [])
            with patch("auto_resume.update.urlopen", return_value=io.BytesIO(payload)):
                result = download_update(release)
            self.assertEqual(result.name, release.name)
            self.assertEqual(result.read_bytes(), payload)
