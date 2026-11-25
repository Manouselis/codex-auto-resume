#!/bin/sh
set -eu

[ "${1:-}" = configure ] && [ -z "${DPKG_ROOT:-}" ] || exit 0

# APT or the app's polkit update supplies the caller. Graphical package
# managers may only expose the affected users through the local login manager.
{
    printf '%s\n' "${SUDO_UID:-}" "${PKEXEC_UID:-}"
    /usr/bin/timeout 3s /usr/bin/loginctl list-users --no-legend --no-pager 2>/dev/null |
        /usr/bin/awk '{print $1}'
} | /usr/bin/sort -u | while IFS= read -r uid; do
    case "$uid" in ''|*[!0-9]*) continue ;; esac
    [ "$uid" -ge 1000 ] && [ "$uid" -ne 65534 ] || continue
    account=$(/usr/bin/getent passwd "$uid") || continue
    name=${account%%:*}
    [ -n "$name" ] || continue

    # The helper only moves an exact source-installer entry and runs with
    # the same permissions as the user who owns it, never as root.
    /usr/bin/timeout 5s /usr/sbin/runuser --user "$name" -- \
        /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/codex-auto-resume --migrate-shortcuts || :
done

exit 0
