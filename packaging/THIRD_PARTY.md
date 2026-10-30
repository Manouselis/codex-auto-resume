# Bundled runtime notices

Codex Auto-Resume is MIT licensed (see LICENSE). Its standalone installers include:

- CPython: Python Software Foundation License Version 2, with incorporated historical notices. [License text](https://docs.python.org/3/license.html).
- Tcl/Tk: permissive Tcl/Tk license and incorporated notices. [Tcl license](https://www.tcl-lang.org/software/tcltk/license.html).
- PyInstaller bootloader: GPL with an exception permitting distribution of bundled applications under their own license. [License and exception](https://pyinstaller.org/en/stable/license.html).

The build copies available Python/Tcl/Tk license files into the runtime's `licenses` directory. PyInstaller, Pillow and other build dependencies are not imported by the application at runtime. The official Codex runtime is a separate installed product; no Codex executables, account tokens or user chat data are bundled in these downloads.
