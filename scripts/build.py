#!/usr/bin/env python3
"""Reproducible stdlib zipapp and source tarball. No downloads or build dependencies."""
import gzip
import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.3.0"


def build_app(root=ROOT):
    output = io.BytesIO()
    output.write(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        files = {"__main__.py": b"from auto_resume.cli import main\nraise SystemExit(main())\n"}
        files.update({p.relative_to(root).as_posix(): p.read_bytes() for p in sorted((root / "auto_resume").glob("*.py"))})
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return output.getvalue()


def source_files(root=ROOT):
    excluded = {".git", "dist", "__pycache__", ".pytest_cache", ".venv", ".ruff_cache"}
    directories = {"auto_resume", "tests", "scripts", "docs", "packaging", ".github"}
    top_files = {"README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "pyproject.toml", ".gitignore"}
    extensions = {".py", ".md", ".json", ".png", ".service", ".toml", ".yml", ".yaml"}
    for p in sorted(root.rglob("*")):
        relative = p.relative_to(root)
        allowed = (relative.as_posix() in top_files or
                   (relative.parts[0] in directories and p.suffix in extensions))
        private = (p.name in {"auth.json", "config.toml"} or p.name.startswith((".env", "core"))
                   or ".sqlite3" in p.name)
        if p.is_file() and not p.is_symlink() and allowed and not private and not (excluded & set(relative.parts)):
            yield p


def build():
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    app = dist / f"codex-auto-resume-{VERSION}.pyz"
    app.write_bytes(build_app())
    app.chmod(0o755)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for p in source_files():
            data = p.read_bytes()
            info = tarfile.TarInfo(f"codex-auto-resume-{VERSION}/" + p.relative_to(ROOT).as_posix())
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    source = dist / f"codex-auto-resume-{VERSION}-source.tar.gz"
    source.write_bytes(gzip.compress(raw.getvalue(), compresslevel=9, mtime=0))
    sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in (app, source))
    (dist / "SHA256SUMS").write_text(sums)
    print(sums, end="")


if __name__ == "__main__":
    build()
