# Native desktop builds

Release installers bundle CPython, Tcl/Tk, the application and its icon with PyInstaller. End users do not need Python. Build on each target OS: PyInstaller is not a cross-compiler ([upstream guide](https://pyinstaller.org/en/stable/usage.html)).

```sh
python -m pip install -r packaging/requirements-build.txt
python scripts/build_native.py
```

Linux also needs `dpkg-deb`, Tcl/Tk build libraries and an X11 session/Xvfb for GUI tests. Windows needs [NSIS](https://nsis.sourceforge.io/); its standard installation is discovered automatically. macOS uses Xcode command-line tools and `hdiutil` supplied with the OS. Dependencies are build-only, pinned in `packaging/requirements-build.txt`.

Artifacts are written to `dist/release`. Linux binaries are built on Ubuntu 22.04 (glibc 2.35 baseline), then the **same DEB** is installed/tested on newer Ubuntu runners. Windows builds produce a per-user NSIS wizard. macOS builds produce separate Intel/Apple silicon app bundles in drag-to-Applications DMGs. Symlinks are preserved when packaging POSIX runtimes.

## Verification and publishing

[Desktop installers workflow](../.github/workflows/desktop.yml) runs the core and real Tk GUI tests, builds native bundles, installs/copies the final packages, launches the packaged GUI, checks default settings/icon/SQLite/recovery simulation, and uninstalls/removes the app. The Windows x64 installer is additionally installed and run on the `windows-11-arm` runner under x64 emulation. Each job uploads a JSON report with its OS and measured smoke-test duration.

```sh
python scripts/verify.py --gui
python scripts/smoke_native.py dist/release/PLATFORM_PACKAGE --report dist/smoke-local.json
```

`--install` is intended for disposable CI hosts: it installs and removes the Linux/Windows application. Without that flag, Linux smoke tests extract to a temporary directory. macOS mounts a DMG and copies its app to a temporary directory. Tests use invented data in temporary state files and do not connect to a user's Codex account.

Push a `vVERSION` tag matching the source version after review. The workflow publishes a GitHub **prerelease only after all native build and compatibility jobs pass**, including Ubuntu and Windows 11. It includes installers, source, the legacy zipapp, SHA-256 checksums and platform smoke reports. Failure leaves no downloadable release advertised as passing. The release job alone receives `contents: write`; build/test jobs are read-only.

## Startup and resource choices

- Onedir bundles avoid unpacking a one-file executable on every launch; installers compress the runtime once.
- Only stdlib runtime modules and application assets are included; Pillow/PyInstaller stay in the build environment.
- One scheduler/OS lock per private state file; separate GUI instances do not duplicate continuation writers.
- Allowance refresh is once per minute; a background controller uses one idle thread and the existing guarded polling cadence.
- External programs receive restored library paths; Windows loads bundled native extensions before restoring standard DLL lookup. See [PyInstaller's subprocess guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application).
- The Windows official proxy carries raw WebSocket bytes, never a JSONL interpretation or a second App Server writer.

## Signing

No signing secrets are committed. Windows Authenticode and Apple Developer ID/notarization are not configured; v0.8.0 is an explicitly unsigned community beta. macOS bundles receive PyInstaller's ad-hoc signature. A future stable release should configure protected signing credentials and verify downloaded/quarantined installer launches on clean user machines. CI installs do not exercise SmartScreen/Gatekeeper reputation prompts.

The application is MIT licensed. Bundled Python, Tcl/Tk and PyInstaller components retain their upstream licenses; see [third-party notices](../packaging/THIRD_PARTY.md).
