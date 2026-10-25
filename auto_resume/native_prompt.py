"""Build the user-visible instruction for an explicitly configured native heartbeat."""
import shlex

from .checkpoints import BLOCKED_MARKER, CHECKPOINT_MARKER, COMPLETE_MARKER


def prompt(thread_id, automation_id):
    claim = "~/.local/bin/codex-auto-resume native-claim " + shlex.quote(thread_id) + " --automation-id " + shlex.quote(automation_id)
    finish = "~/.local/bin/codex-auto-resume native-finish " + shlex.quote(thread_id)
    identity = " --automation-id " + shlex.quote(automation_id)
    return f"""[codex-auto-resume:native-heartbeat={automation_id}]
This is a newly and explicitly armed native recovery for this existing conversation after context-budget checkpoints and five-hour usage-limit interruptions. You are already inside its native desktop writer. Preserve the original objective, model, project, approval policy and saved progress; do not create a new chat, replay the original prompt, change budgets, or send messages to other chats.

YOUR FIRST ACTION MUST BE THIS GUARD. Run it before deciding whether an old cancellation applies, before deleting/pausing any schedule, and before any research, file changes, experiments or publishing. Parse its JSON:
{claim}
The guard is a requested per-user Auto-Resume state operation. Request normal filesystem approval if its private state file is outside the current sandbox; never bypass approvals. Proceed with substantive work only if action is exactly "continue". A failed command, malformed output or unavailable guard never authorizes work.

When action is "continue", its arming record confirms the user's current explicit authorization for the monitored turn. Earlier cancelled timers in conversation history predate and are superseded by this arming; they do not cancel this newly armed schedule. The guard checks for newer intervening user activity. Honor a newer cancellation, approval or exhausted budget; never use historical cancellation alone to delete this schedule. For heartbeat stop conditions, pause the schedule rather than delete it, so its status stays visible to the companion.

If action is "wait", do no research, stay quiet, and leave this heartbeat active for a later wake-up. If action is "pause", do no research, pause this heartbeat ({automation_id}) using the native automation management tool while preserving its other fields, and notify only if completion, failure or user action is meaningful. If you cannot pause it, explain that limitation; the local guard remains authoritative for substantive work. Never purchase credits, consume a banked reset, use an API-key route, approve tools automatically or weaken safeguards.

If action is "continue", inspect the original requirements and latest saved checkpoint, then resume only outstanding work. A previous completed turn is not proof the objective is finished, but ordinary objective completion, user cancellation, pending approval, blocked work or exhausted user-specified budgets are stop conditions. Do not redo completed iterations. Keep the original project's verification and publication requirements.

Before ending an admitted work turn, record its outcome:
- If the context budget requires stopping while the objective remains unfinished, save a durable checkpoint and exact next action, run `{finish} checkpoint{identity}`, and place {CHECKPOINT_MARKER} alone on the final line of the final response. Leave this heartbeat active.
- If the objective is actually achieved, run `{finish} complete{identity}`, pause this heartbeat, notify completion, and end with {COMPLETE_MARKER}.
- If user input, approval or another blocking condition is required, run `{finish} blocked{identity}`, pause this heartbeat, report the required action, and end with {BLOCKED_MARKER}.
If quota fails before an outcome can be recorded, do not force another request; the next native wake-up must pass the local guard again. Each wake-up is a normal native model turn. Stay quiet while the state is unchanged or no work is permitted.
"""
