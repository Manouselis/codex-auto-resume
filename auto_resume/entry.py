"""Frozen desktop entry point; no arguments always opens the application."""
import json
import os
import sys
from pathlib import Path


def package_smoke(report):
    """Exercise bundled Tk, assets, SQLite and recovery core without Codex access."""
    import tempfile
    import tkinter as tk
    from . import __version__
    from .adapters import SimulationAdapter
    from .cli import demo
    from .engine import Engine
    from .store import Store
    from .ui import ControlWindow
    with tempfile.TemporaryDirectory(prefix="auto-resume-package-") as directory:
        path = Path(directory)
        store = Store(path / "ui.sqlite3")
        adapter = SimulationAdapter()
        root = tk.Tk()
        window = ControlWindow(root, Engine(store, adapter), simulation=True)
        root.update()
        result = {"version": __version__, "platform": sys.platform,
                  "machine": __import__('platform').machine(),
                  "gui": bool(root.winfo_exists()), "bundled_icon": window.icon is not None,
                  "default_enabled": window.enabled.get(), "button": window.add_button.cget("text"),
                  "demo": demo(path)}
        window.close()
        store.close()
        Path(report).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 0 if result["bundled_icon"] and result["default_enabled"] else 1


def main():
    # Windowed Windows executables have no inherited console streams.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        # Load the bundled native extensions before restoring DLL search paths
        # for external Codex processes (PyInstaller's documented requirement).
        __import__("tkinter")
        __import__("sqlite3")
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    if sys.argv[1:2] == ["--inhibit-wait"]:
        print("ready", flush=True)
        sys.stdin.buffer.read()
        return 0
    if sys.argv[1:2] == ["--package-smoke"] and len(sys.argv) == 3:
        try:
            return package_smoke(sys.argv[2])
        except Exception as exc:
            Path(sys.argv[2]).write_text(json.dumps({"package_smoke": "FAIL", "error_type": type(exc).__name__}) + "\n", encoding="utf-8")
            return 1
    from .cli import main as cli_main
    try:
        return cli_main(sys.argv[1:] or ["ui"])
    except Exception:
        # Display a useful failure even when there is no terminal. Do not expose
        # raw protocol payloads, account identifiers or conversation contents.
        if not sys.argv[1:]:
            from tkinter import messagebox
            messagebox.showerror("Codex Auto-Resume", "Auto-Resume could not start. Close another copy, check your installation and reopen the app. See the Troubleshooting page in the README.")
            return 2
        raise
