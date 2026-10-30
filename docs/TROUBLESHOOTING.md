# Troubleshooting

## “Waiting for reset” keeps moving even though usage is available

Version 0.4.1 could retain a completed native turn's global reservation and poll it every 30 seconds under the wrong reset label. Update to 0.5.0. Chats now have independent reservations, and a read-only audit retires a stale acknowledged reservation only after verifying that exact turn ended. Select a row or read its **Details** column for the actual reason. Connection failures show **Retrying connection**. Genuine quota waits still require fresh included-usage permission; a percentage or timer alone never authorizes continuation.

## Codex is open but Auto-Resume cannot find its daemon

The desktop window and the local daemon transport are separate. Version 0.5.0 starts the official daemon automatically when its local socket is unavailable, then connects again. This bootstrap sends no model work and does not replay failed submissions. If it fails, check the installed runtime and sign-in with `doctor --connect`.

## Working with Ubuntu locked

Open the installed application once, arm the desired chats, and confirm **Background controller active** in the footer. While work is armed, the footer should also report **sleep prevented**. You may lock with Super+L and let the screen blank. Keep Codex open and stay logged in. If sleep protection is unavailable, keep the laptop awake until the reported host issue is resolved. OFF or disarming every chat releases sleep protection; forced suspend and reboot are not supported recovery guarantees.

## A saved native checkpoint is rejected and the next guard says disarmed

Update to 0.4.1. A 0.4.0 parser bug rejected a valid checkpoint when Codex wrapped its final message in heartbeat XML. The first wake-up disarmed recovery; later attempts then reported the misleading combined OFF/disarmed message even though the global switch remained ON. Version 0.4.1 recognizes the final marker inside a valid heartbeat message and reports the precise saved disarm reason. Explicitly rearm after the repair; a legitimate OFF choice or user cancellation is never automatically undone.

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
| `WAITING_FOR_SCHEDULE` | The native heartbeat exists but is paused. Activate it through Codex; the controller then returns to ARMED. |
| `ARMED` | Explicitly registered. The controller is watching the original turn; a result may still be unresolved. |
| `RUNNING` | Codex is working on the tracked turn, including an acknowledged automatic continuation. |
| `FIVE_HOUR_LIMIT_REACHED` | A five-hour interruption was confirmed. This brief transition advances to the scheduled reset wait. |
| `WAITING_FOR_RESET` | A structured usage-limit failure and exhausted five-hour window were confirmed. Wait for the scheduled fresh check. |
| `VERIFYING_ALLOWANCE` | The controller is checking current included allowance and context before dispatch. |
| `RESUMING` | A durable local reservation exists and dispatch is in progress. Do not force another submission. |
| `COMPLETED` | The tracked Codex turn ended. This does not establish that the wider objective is finished. Usage-limit monitoring stops and does not restart the turn automatically. |
| `WEEKLY_LIMIT_REACHED` | Weekly exhaustion disarmed the task. Inspect usage and rearm manually after recovery. |
| `PAUSED_FOR_USER` or `ERROR` | Read the recorded reason, inspect the original conversation, and resolve the cause before rearming. |
| `DISABLED` | Automation was switched OFF. Enable and explicitly rearm the task when desired. |

## A running task says it was cancelled when I arm it

Update to 0.2.1 or later and restart the companion controller. Earlier versions could mistake an unfinished external-history marker for a confirmed user interruption.

The desktop can be executing a turn while a separate reader reports `notLoaded` and reconstructs that same turn as `interrupted`, with no error or completion time. Version 0.2.1 marks this case unresolved and allows monitoring. It can show **Armed — waiting for a confirmed turn result** until a confirmed result appears.

A real completed cancellation, or an interruption reported by a loaded runtime, still blocks continuation. An unresolved turn can never pass dispatch preflight. See the [recorded read-only reproduction](evidence/external-arm.json) and [engineering decision](DECISIONS.md#021-monitoring-work-owned-by-another-runtime).

## The service is running but the conversation is not armed

Closing a window-owned controller, switching OFF, or normally stopping a controller disarms tasks. In 0.3.0, closing a service-owned panel keeps monitoring active. Switching ON again does not restore their eligibility. Resolve the task's recorded reason, then use `enable` and `arm THREAD_ID` or the control window to opt in again.

## The reset time passed but nothing continued

The reset timestamp schedules a check; it does not authorize execution. The companion still needs a current structured usage-limit failure for the same turn, fresh included permission, valid quota windows, enough weekly allowance, known zero credits and unchanged context.

Read-only recovery failures receive bounded retries, then pause for inspection. The default verification buffer is five seconds, with a scheduler wake every 30 seconds. Check the task's state and reason. If the task completed, was cancelled, or another turn started, it is intentionally no longer eligible.

## The research is unfinished but the turn ended

A turn can end normally after saving a checkpoint, reaching a context budget, or choosing to hand control back. The App Server can report that turn as `completed` even when the wider research objective remains unfinished. This is different from a structured `usageLimitExceeded` failure. The default quota-only mode stops monitoring that turn and cannot treat available quota as permission to restart it. Version 0.3.0 provides a separate explicit [context recovery option](RECOVERY.md) for recognized checkpoints.

The original 0.2.1 reason text, **Task completed**, overstated what the controller could verify. Turn completion establishes that the current execution ended, not that the user's objective was achieved. Inspect the final response and checkpoint before choosing whether to continue the work.

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

## Desktop writer is already active

The desktop can retain its exclusive writer while the chat is idle. The external controller cannot restore this chat, and queue APIs cannot bypass the restore requirement. This is a definite pre-dispatch refusal, recorded as `not_sent`; it is not a successful continuation. Do not restart Codex or send duplicate requests to work around it. The experimental [native heartbeat setup](RECOVERY.md#native-desktop-recovery-experimental) uses the existing writer. Its first real native wake-up resumed saved research on Ubuntu; repeated checkpoint and natural quota-reset cycles remain unverified.

A native-bound task is skipped by the external scheduler. Check `status` for `native_heartbeat` and attempts, and inspect the native heartbeat’s own active/paused state in Codex. OFF prevents substantive work but does not itself pause the native scheduler; pause the heartbeat to stop model wake-ups.

## Arming says execution is outstanding or uncertain

Update to 0.3.1 and rearm the original conversation. The controller checks the exact acknowledged turn using read-only history. If that turn has a confirmed end time and terminal status, it finishes the stale reservation and arms the current eligible turn atomically. It does not resend the old request. An unknown delivery without an acknowledged turn, unavailable history, or an open marker still blocks rearming for inspection.

Clicking a saved row now fills its ID and context-recovery setting; choosing it in the picker does the same. Rearming preserves the saved native heartbeat binding. Clicking Arm again while a known native turn is running preserves that run and its attempt count. Native scheduling remains a separate Codex automation: if it was cancelled or deleted, restore it through Codex's native automation management tool before expecting wake-ups.

## The panel says armed but its native schedule is gone

Update to 0.4.0. The controller checks native metadata every scheduler tick and refuses new native arming when the schedule is missing or bound to another chat. Missing schedules become **Needs attention**, with the reason recorded in the activity log. Restore a schedule through Codex's native automation tool, then explicitly rearm. Paused schedules appear as **Schedule paused**.

An earlier heartbeat incorrectly acted on an old cancellation before running the guard and deleted itself. The updated prompt requires its guard first and reports the newer arming authorization. Prefer a new schedule identity when restoring after cancellation. The prompt pauses on stop conditions rather than silently deleting the schedule.

After diagnostic replies have become the latest turn, explicit Arm can reuse the exact earlier acknowledged native checkpoint only after reading and verifying it again. That arming records the current turn as its authorization boundary. It does not reopen completed objectives, accept an unverified checkpoint, or ignore manual activity arriving after arming. No extra “continue” message is needed before the next native wake-up.
