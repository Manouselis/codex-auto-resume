"""Read native schedule health without writing Codex's automation files."""
import json
import os
import re
from pathlib import Path


def schedule_status(automation_id, thread_id):
    if not isinstance(automation_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", automation_id):
        return "INVALID", "Native recovery schedule identity is invalid"
    path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "automations" / automation_id / "automation.toml"
    try:
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            return "INVALID", "Native recovery schedule metadata cannot be verified"
        content = path.read_text()
    except FileNotFoundError:
        return "MISSING", "Native recovery schedule is missing; restore it in Codex before rearming"
    except (OSError, UnicodeError):
        return "UNAVAILABLE", "Native recovery schedule cannot be read; no continuation is armed"
    values = {}
    for line in content.splitlines():
        match = re.fullmatch(r'\s*(id|kind|status|target_thread_id)\s*=\s*(".*")\s*', line)
        if match:
            try:
                if match[1] in values:
                    raise ValueError("duplicate metadata")
                values[match[1]] = json.loads(match[2])
            except ValueError:
                return "INVALID", "Native recovery schedule metadata is invalid"
    if (values.get("id"), values.get("kind"), values.get("target_thread_id")) != (automation_id, "heartbeat", thread_id):
        return "INVALID", "Native recovery schedule does not match this conversation"
    if values.get("status") == "ACTIVE":
        return "ACTIVE", "Native recovery schedule is active"
    if values.get("status") == "PAUSED":
        return "PAUSED", "Native recovery schedule is paused; waiting for activation in Codex"
    return "INVALID", "Native recovery schedule has an unsupported status"
