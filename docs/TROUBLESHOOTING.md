# Troubleshooting

[Documentation index](README.md) · [Installation and operation](INSTALL.md)

## Check the controller and task separately

An active service does not by itself mean a task is armed. Check both:

```sh
~/.local/bin/codex-auto-resume --version
~/.local/bin/codex-auto-resume status
systemctl --user status codex-auto-resume.service
```

The service command applies when you selected background operation. For a window-owned controller, keep the window open. Use **Activity history** in the control window or `journalctl --user -u codex-auto-resume.service -n 30 --no-pager` for service diagnostics. Inspect logs locally before sharing them.

## Task states

| State | Meaning and next action |
| --- | --- |
| `ARMED` | Explicitly registered. The controller is watching the original turn; a result may still be unresolved. |
| `RUNNING` | Codex is working on the tracked turn, including an acknowledged automatic continuation. |
| `FIVE_HOUR_LIMIT_REACHED` | A five-hour interruption was confirmed. This brief transition advances to the scheduled reset wait. |
| `WAITING_FOR_RESET` | A structured usage-limit failure and exhausted five-hour window were confirmed. Wait for the scheduled fresh check. |
| `VERIFYING_ALLOWANCE` | The controller is checking current included allowance and context before dispatch. |
| `RESUMING` | A durable local reservation exists and dispatch is in progress. Do not force another submission. |
| `COMPLETED` | The tracked work completed. It will not restart automatically. |
| `WEEKLY_LIMIT_REACHED` | Weekly exhaustion disarmed the task. Inspect usage and rearm manually after recovery. |
| `PAUSED_FOR_USER` or `ERROR` | Read the recorded reason, inspect the original conversation, and resolve the cause before rearming. |
| `DISABLED` | Automation was switched OFF. Enable and explicitly rearm the task when desired. |

## A running task says it was cancelled when I arm it

Update to 0.2.1 or later and restart the companion controller. Earlier versions could mistake an unfinished external-history marker for a confirmed user interruption.

The desktop can be executing a turn while a separate reader reports `notLoaded` and reconstructs that same turn as `interrupted`, with no error or completion time. Version 0.2.1 marks this case unresolved and allows monitoring. It can show **Armed — waiting for a confirmed turn result** until a confirmed result appears.

A real completed cancellation, or an interruption reported by a loaded runtime, still blocks continuation. An unresolved turn can never pass dispatch preflight. See the [recorded read-only reproduction](evidence/external-arm.json) and [engineering decision](DECISIONS.md#021-monitoring-work-owned-by-another-runtime).

## The service is running but the conversation is not armed

Closing the control window, switching OFF, or normally stopping a controller disarms tasks. Switching ON again does not restore their eligibility. Resolve the task's recorded reason, then use `enable` and `arm THREAD_ID` or the control window to opt in again.

## The reset time passed but nothing continued

The reset timestamp schedules a check; it does not authorize execution. The companion still needs a current structured usage-limit failure for the same turn, fresh included permission, valid quota windows, enough weekly allowance, known zero credits and unchanged context.

Read-only recovery failures receive bounded retries, then pause for inspection. The default verification buffer is five seconds, with a scheduler wake every 30 seconds. Check the task's state and reason. If the task completed, was cancelled, or another turn started, it is intentionally no longer eligible.

## Connection, usage or approval problems

| Symptom | Action |
| --- | --- |
| CLI or Tk unavailable | Install the official Codex runtime and Tk, or use the companion CLI/service without a GUI. |
| Daemon/socket unavailable | Check Codex login, then run companion `enable` to start/connect to the official daemon. Use `doctor --connect` for a read-only compatibility check. |
| Unknown usage, missing permission, unknown credits or changed account/model/project | Inspect the original account and conversation. Rearm only after the underlying condition is resolved. |
| Pending approval or input | Handle it in the original Codex work. The companion never answers approvals; cross-client approval routing remains unverified. |
| A different turn started | Inspect whether the task was superseded. Rearm the desired current work explicitly. |
| Another controller owns the state file | Use the existing service/controller. Do not launch a second scheduler against the same state. |
| Continuation outcome is uncertain | Inspect the original conversation. Do not clear reservations or force a retry; the first request may already have executed. |

## Suspend, logout and reboot

Keep the computer awake, connected and logged in for an overnight wait. The companion cannot execute while the machine is suspended. A transient user service does not install boot startup. An installed user service still disarms work on a normal stop, and real reboot/logout recovery remains unverified.
