"""Keep external Codex/system programs independent of frozen library paths."""
import os
import subprocess
import sys


def external_options():
    options = {}
    if sys.platform == 'win32':
        options['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if getattr(sys, 'frozen', False):
        env = os.environ.copy()
        for name in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'):
            original = env.get(name + '_ORIG')
            if original is not None:
                env[name] = original
            else:
                env.pop(name, None)
        options['env'] = env
    return options
