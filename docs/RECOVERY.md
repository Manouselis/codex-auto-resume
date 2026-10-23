# Usage limits and context-budget recovery

[Documentation index](README.md) · [Installation and operation](INSTALL.md)

## Two different stopping conditions

The five-hour allowance controls how much included Codex usage is available in a time window. A context budget limits the conversation and working material that one execution can handle. A run can end at its context budget while included usage is still available.

The App Server can report a context-checkpoint stop as a normally completed turn. That means the execution ended; it does not prove the wider research or coding objective is finished. Older versions called this **Task completed** and stopped quota monitoring, so they did not recover this case.

| Stopping condition | Recovery behavior |
| --- | --- |
| Structured five-hour usage-limit failure | Wait for the official reset and verify fresh included allowance |
| Recognized context-budget checkpoint with recovery enabled | Verify allowance and continue the same conversation without waiting unnecessarily |
| Context checkpoint while five-hour usage is exhausted | Wait for reset, then run the same fresh checks |
| Ordinary completion, cancellation, pending approval or blocked work | Stop; do not automatically restart |
| A paused or exhausted user-specified goal budget | Stop; context recovery does not override that budget |

## Enable context recovery explicitly

In the control window, select **Also recover context-budget checkpoints for this arming**, then arm the original conversation. The option starts unchecked and applies to that registration only. Global ON does not enable it for every conversation.

The CLI equivalent is:

```sh
~/.local/bin/codex-auto-resume enable
~/.local/bin/codex-auto-resume arm THREAD_ID --recover-context
~/.local/bin/codex-auto-resume status
```

Replace `THREAD_ID` with the original conversation's ID. The status output includes `recover_context: true`. Keep a controller running using the [background service recipe](INSTALL.md#overnight-operation-without-a-window).

This option can arm a recognized checkpoint that was already marked as an ended turn by an older version. It does not make an arbitrary completed response eligible for recovery.

## What recovery checks

The same account, model, project, turn and saved context must still match. Fresh included permission, both quota windows, enough weekly allowance, known zero credits and the original provider/tier checks remain mandatory. Goal state is read before recovering a context checkpoint; a non-active goal or exhausted/unknown configured token budget blocks continuation.

Recovery sends a contextual continuation in the original thread, asking Codex to inspect the saved checkpoint and perform only outstanding work. It does not replay the original prompt or create a new conversation. The default limit remains three automatic continuation attempts per arming. Uncertain submissions are never resent automatically.

## Recognition limits

The adapter recognizes structured `contextWindowExceeded` failures and explicit model-reported context checkpoints in final responses. Future continuations receive instructions for reporting a context checkpoint, objective completion or a user-input block. A narrow compatibility rule also recognizes the previously observed final paragraph declaring a context-budget stop and a saved next action.

A mention of context budgets in an explanation, quoted example or tool output is insufficient. This is conservative checkpoint recognition, not a general proof that an objective is complete or unfinished. If no supported checkpoint is present, the controller stops that turn for inspection. Repeated hard context-window failures can still reach the attempt cap; compaction success is not guaranteed.

## Closing the control window

When a background controller already owns scheduling, closing its control panel leaves armed work enabled. Use the global OFF switch or `disable` to stop it. When the window owns the only controller, closing it still disables and disarms work. The panel identifies a connected background controller when opened.

Keep the computer awake, online and logged in. A background controller does not prevent suspend or wake the computer.

## Desktop writer ownership

The original desktop can retain its writer even while a chat is idle. A separate App Server cannot reopen it. Queue start requires the thread to be resumed on that same server, so it cannot bypass this refusal. The adapter records the definite pre-dispatch refusal as `not_sent` and pauses. It does not silently claim successful recovery.

## Native desktop recovery (experimental)

Native heartbeat recovery is a separate opt-in setup for a desktop-owned chat. The GUI context checkbox only enables checkpoint recognition; it does not create a native heartbeat. The native integration has automated guard tests but no verified real scheduled wake-up yet.

1. Explicitly choose native scheduled recovery, understanding that each wake-up is a normal model turn. Use Codex’s native automation management tool to create a **paused heartbeat** attached to the original conversation, for example with a five-minute interval. Do not create a separate task or cron job.
2. Obtain its automation ID and generate the guarded prompt with the command below. Update the paused heartbeat through the native tool with that exact prompt while preserving its other fields.
3. Enable the companion and arm the original conversation with both `--recover-context` and `--native-heartbeat`. Outstanding or uncertain submissions must first be inspected; never clear them merely to enable a retry.
4. Activate the prepared heartbeat using Codex’s native tool. Confirm an actual wake-up and admitted work in the original chat before describing it as working.

```sh
~/.local/bin/codex-auto-resume native-prompt THREAD_ID --automation-id AUTOMATION_ID
~/.local/bin/codex-auto-resume enable
~/.local/bin/codex-auto-resume arm THREAD_ID --recover-context --native-heartbeat AUTOMATION_ID
~/.local/bin/codex-auto-resume status
```

The prompt calls `native-claim` before research and `native-finish` before ending admitted work. It saves an exact next action at a context stop, pauses on actual completion or a block, and preserves the original project and budgets. The guard rejects manual intervening turns, cancellation, pending approvals, changed identity, exhausted/unknown goal budgets, paid credits and unavailable included usage. It admits at most ten native work turns per arming; `--native-max-attempts` can lower that limit.

The external controller skips native-bound chats. The native scheduler owns initial model admission, so this mode cannot promise zero inference while waiting or prevent billing changes before a wake-up. The guard authorizes substantive work only after its fresh checks. OFF or disarm blocks that work immediately; also pause the native heartbeat to stop future wake-up model turns. The heartbeat prompt tries to pause itself when it observes a stop condition. Keep the app and computer available; suspend/reboot recovery remains unverified.
