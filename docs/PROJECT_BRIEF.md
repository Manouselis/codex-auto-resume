# PROJECT: Codex Auto-Resume — Intelligent Usage-Limit Continuation Plugin

This is the original project brief, preserved as a requirements record. It includes requested behavior and platform goals that are not all implemented or verified. For the current 0.2.1 behavior, start with the [documentation index](README.md), [delivery summary](DELIVERY.md), and [verification report](TESTING.md).

## YOUR ROLE

Act as an autonomous senior software engineering team consisting of:

- Principal Software Architect
- Senior Linux Desktop Engineer
- Senior Windows Integration Engineer
- Codex SDK / App Server Integration Specialist
- Backend and State-Machine Engineer
- Security and Reliability Engineer
- Senior UI/UX Designer
- QA Automation and Test Engineer

Your mission is to **design, implement, test, debug, refine, and deliver a production-quality Codex desktop integration called "Codex Auto-Resume."**

Do not stop after creating a prototype, writing documentation, or generating a proposed implementation.

Deliver real, functional, maintainable software with evidence that it works.

Work autonomously through multiple implementation and quality-improvement cycles. Make sensible engineering decisions independently rather than requesting approval for ordinary technical choices.

Never claim that an integration or test works unless it has actually been verified.

---

# 1. PROJECT OBJECTIVE

Create a one-click ON/OFF feature called:

**"Continue automatically when the 5h limit resets"**

The feature must allow Codex to resume an unfinished coding task automatically when the user's included five-hour usage allowance becomes available again.

The user's environment:

- Primary OS: Ubuntu 22.04 LTS
- Secondary OS: Windows
- Subscription: ChatGPT Plus
- Product: Codex desktop application
- Usage constraints: five-hour allowance and weekly allowance, when both apply
- Priority: Native-feeling integration, reliability, safety, simplicity

### Example workflow

1. The user enables "Continue automatically when the 5h limit resets."
2. The user starts a large coding task in Codex.
3. Codex works normally for approximately 3.5 hours.
4. The five-hour usage allowance becomes exhausted before the task is completed.
5. Codex cannot proceed due to its usage limit.
6. Auto-Resume detects the five-hour usage-limit interruption.
7. Auto-Resume remembers the exact unfinished conversation and task.
8. It obtains the official reset information and waits without consuming unnecessary model usage.
9. After the allowance becomes available again, Auto-Resume verifies that the weekly allowance still has included usage remaining.
10. It also verifies that continuing will not activate paid credits, API billing, or another chargeable fallback.
11. If every safety condition passes, Codex resumes the original unfinished task.
12. It continues in the original context instead of restarting the entire prompt.
13. If the weekly allowance is exhausted, Auto-Resume stops and informs the user.

The user must not have to return to their computer merely to press Continue.

**This is a continuation mechanism, not a mechanism to bypass usage limits.**

---

# 2. NON-NEGOTIABLE SAFETY REQUIREMENTS

These requirements take priority over convenience, speed, and appearance.

### A. Never automatically spend additional money

The automatic continuation feature must never intentionally:

- Purchase or consume paid usage credits.
- Trigger pay-as-you-go API billing.
- Activate a chargeable model fallback.
- Redeem banked usage resets.
- Upgrade a subscription.
- Switch accounts to evade usage limits.
- Circumvent server-side usage restrictions.
- Continue after included weekly usage is exhausted.

Use official authenticated Codex usage information where available.

Investigate the `account/rateLimits/read` App Server method and its current response schema, including:

- `ordinaryUsageAllowed`
- `rateLimitsByLimitId`
- `primary` and `secondary` usage windows
- `windowDurationMins`
- `usedPercent`
- `resetsAt`
- Credit and spend-control information
- Account identity
- Model-specific usage buckets

Verify their actual names, semantics, and availability against the installed version.

Do not hardcode assumptions about which quota window is called primary or secondary. Identify windows by their reported duration and applicable limit identity.

Treat `ordinaryUsageAllowed` as an important authorization signal. Do not infer permission to resume solely because a reset timestamp has passed or a percentage appears to have decreased.

If backend permission is unavailable, false, stale, or ambiguous, fail closed.

**The core safety invariant is: NO AUTOMATIC MODEL EXECUTION WHEN THE SYSTEM CANNOT VERIFY THAT INCLUDED, NON-CHARGEABLE USAGE IS AVAILABLE.**

### B. Weekly usage is a hard stop

When weekly usage reaches its limit:

- Immediately prohibit automatic continuation.
- Mark the affected task as paused.
- Clearly display "Weekly limit reached."
- Preserve the task and its context.
- Do not automatically resume after the weekly reset.
- Require fresh user action to rearm a task paused because of weekly exhaustion.

A five-hour reset must never override an exhausted weekly allowance.

### C. Never restart completed tasks

Auto-Resume must never:

- Replay an already completed original prompt.
- Restart a finished task.
- Create duplicate execution turns.
- Repeat destructive operations unintentionally.
- Send continuation commands into the wrong conversation.
- Resume a task that the user manually cancelled.
- Take over a thread where the user has started unrelated work.

### D. Default to OFF

The feature must be disabled initially and require explicit user opt-in.

Disabling it must cancel scheduled automatic continuation immediately.

Disabling the feature should not forcibly interrupt ordinary work already running in Codex.

### E. No security or permission bypasses

Respect Codex sandboxing, approval prompts, authentication, operating-system security, and service terms.

Never automatically approve sensitive actions requiring user permission.

---

# 3. PHASE ONE — RESEARCH THE REAL INTEGRATION SURFACE

Before implementing the solution, inspect the user's actual development environment.

Determine:

1. Which Codex desktop distribution is installed.
2. Whether it is an official build or a community-maintained Linux distribution.
3. The exact Codex version.
4. The installed Codex CLI and App Server versions.
5. Whether the app runs under X11 or Wayland.
6. Available plugin extension points.
7. Available lifecycle hooks.
8. Whether plugins can expose a persistent native UI control.
9. Whether current Codex protocols allow safe thread inspection and continuation.
10. How rate-limit state is exposed.
11. How the application persists threads.
12. Which integration surfaces survive application updates.

Consult current official documentation and, when useful, the upstream open-source Codex repository.

Starting references:

- https://github.com/openai/codex
- https://developers.openai.com/plugins/concepts/plugins
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/blog/codex-as-a-platform
- https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server

Use documentation appropriate to the installed application version.

Do not invent APIs, hooks, UI injection points, or extension capabilities.

## Required architecture decision

Evaluate these approaches in order:

**Option A — Native Codex plugin integration**

Use officially supported plugin capabilities, hooks, settings, MCP tools, or UI extension surfaces if they can genuinely implement the required functionality.

**Option B — Plugin plus local companion service**

Use a legitimate Codex plugin where useful, combined with a minimal background service and a one-click desktop control.

**Option C — Independent desktop companion integration**

If the host application does not expose the necessary hooks or UI integration, use a lightweight external controller that communicates with supported Codex interfaces.

Preference order:

Native integration > supported plugin with companion service > standalone companion controller.

Avoid fragile modifications of proprietary application bundles, monkey-patching internals, or screen-coordinate automation.

Do not claim that a system-tray toggle is a native in-app toggle.

If true native integration is unsupported, document the limitation and provide the closest reliable, maintainable alternative.

Record the architecture decision and its technical justification in `docs/ARCHITECTURE.md`.

---

# 4. PHASE TWO — IMPLEMENT THE AUTO-RESUME ENGINE

Implement a robust event-driven continuation engine.

## Core state machine

Use clearly defined states such as:

- DISABLED
- ARMED
- RUNNING
- FIVE_HOUR_LIMIT_REACHED
- WAITING_FOR_RESET
- VERIFYING_ALLOWANCE
- RESUMING
- COMPLETED
- WEEKLY_LIMIT_REACHED
- PAUSED_FOR_USER
- ERROR

Define legal transitions explicitly.

Prevent invalid state transitions.

The engine must be deterministic, testable, and resistant to concurrent events.

## Usage-limit detection

Prefer structured events, supported status interfaces, and documented APIs.

Do not rely exclusively on matching text displayed in the interface.

Detect whether the interruption was actually caused by five-hour exhaustion rather than:

- Weekly exhaustion
- Network failure
- User cancellation
- Authentication failure
- Application shutdown
- Approval requirement
- Completed work
- Other service errors

Do not schedule automatic continuation for unrelated failures.

## Reset scheduling

When a genuine five-hour limit interruption occurs:

1. Read the reported reset timestamp.
2. Persist the waiting state and thread identity.
3. Schedule a lightweight local wake-up.
4. Avoid repeated expensive polling.
5. Recheck usage shortly after the reported reset.
6. Resume only when backend data confirms eligibility.
7. Use bounded retry delays for transient errors.
8. Avoid retry storms or indefinite model-execution loops.

Use system timestamps rather than assumptions about fixed reset intervals.

Handle time zones, daylight-saving changes, clock adjustments, suspend/resume, and system restarts.

## Safe eligibility check

Before each automatic continuation, verify ALL relevant conditions:

- The feature remains enabled.
- The task remains explicitly eligible for automatic continuation.
- The original task is incomplete.
- The interruption was caused by the relevant five-hour limit.
- The five-hour included allowance is available again.
- The weekly included allowance is available.
- The authenticated account matches the original account.
- The selected model's applicable usage bucket is eligible.
- Ordinary included usage is permitted by the backend.
- The request will not intentionally consume paid credits.
- No paid fallback or automatic reset redemption is required.
- The thread has not been manually cancelled or superseded.
- No incompatible turn is currently active.
- No user approval is outstanding.
- No duplicate continuation has been submitted.

If any condition cannot be established reliably, pause and explain why.

Do not silently guess.

---

# 5. PHASE THREE — CONTINUE THE CORRECT TASK

This is one of the most important technical challenges.

The objective is to resume the interrupted work, not to start a second copy of the work.

Investigate the current Codex SDK and App Server mechanisms for:

- Thread identification
- Thread persistence
- Thread resumption
- Turn status inspection
- Turn completion events
- Failed or interrupted turns
- User cancellation
- Safe continuation

Prefer supported thread and turn protocols over UI input automation.

Persist the minimum information necessary to locate and recover the original task.

When the limit resets:

1. Reconnect to the original thread.
2. Inspect the thread's latest state.
3. Determine whether work genuinely remains unfinished.
4. Check whether Codex already resumed automatically.
5. Determine whether an existing interrupted turn can safely recover.
6. Only if necessary, submit one contextual continuation turn.
7. Never blindly resend the original task.
8. Respect the original sandbox and approval configuration.

If a continuation message is required, use an instruction equivalent to:

"Continue the previously interrupted task from its current state. First inspect existing progress, files, and test results. Do not redo completed work. Resume only the outstanding objectives, preserve the original requirements, and stop when the task is genuinely complete."

Use that message only if supported by the actual continuation protocol.

Do not attempt to reconstruct missing context through speculative summaries.

If the original context cannot be recovered safely, pause and notify the user.

Implement durable continuation IDs, deduplication, and concurrency locks to achieve effectively once-only submission behavior.

Support unexpected process crashes between scheduling, submission, and acknowledgement.

---

# 6. PHASE FOUR — DESIGN THE USER INTERFACE

The interface must feel like a polished Codex feature rather than a developer debugging utility.

## Primary control

Display a simple toggle:

**Continue automatically when the 5h limit resets**

OFF / ON

The user must be able to change this with a single click.

Use the best truly supported desktop integration surface.

If supported, integrate into the app's existing settings or task controls.

Otherwise, implement a small companion control using a system tray or equivalent desktop menu.

## Status presentation

Show understandable states such as:

- Auto-Resume disabled
- Auto-Resume enabled
- Codex working
- 5h limit reached — waiting for reset
- Checking available usage
- Resuming previous task
- Weekly limit reached — paused
- Task completed
- Unable to verify usage — paused

When waiting, show the expected reset time in local time.

Avoid displaying fabricated or unnecessarily precise countdowns.

## Visual quality

Aim for:

- Clean, modern styling
- Compact interface
- Minimal visual noise
- Native-feeling typography
- Dark and light theme support
- Accessible contrast
- Keyboard accessibility
- Helpful tooltips
- Clear status icons
- Smooth, restrained transitions
- Layouts appropriate for Ubuntu and Windows

Follow the established Codex visual language where allowed.

Do not misuse OpenAI trademarks or imply the integration is an official OpenAI product.

## Optional advanced settings

Provide an expandable settings area containing:

- Enable or disable startup with the desktop session
- Desktop notifications
- Reset verification delay
- Maximum continuation attempts
- Auto-Resume activity history
- Minimum weekly reserve threshold
- Per-thread enable/disable controls

Keep normal operation one-click simple.

Do not expose excessive technical settings in the primary interface.

---

# 7. PHASE FIVE — MULTIPLE THREADS AND CONCURRENCY

Design the system to cope with multiple Codex conversations.

The global ON/OFF toggle controls whether Auto-Resume is active.

However, automatic continuation must apply only to tasks that have been explicitly registered as eligible.

Never indiscriminately resume every unfinished conversation in the user's account.

Prefer per-thread authorization or a clearly defined active-task policy.

Requirements:

- Distinguish multiple conversations accurately.
- Do not send a continuation to the wrong project.
- Do not resume cancelled or completed conversations.
- Prevent duplicate scheduling.
- Do not create competing automated turns.
- Serialize automatic resumptions by default.
- Check the latest weekly quota before each resumed task.
- Respect user-initiated work over automatic continuation.
- Allow users to disarm individual tasks.

Protect state updates using atomic operations and proper concurrency control.

---

# 8. PHASE SIX — BACKGROUND SERVICE AND PERSISTENCE

The waiting mechanism must remain reliable during long idle periods.

On Ubuntu, evaluate a systemd user service or an equivalent appropriate mechanism.

On Windows, evaluate a supported per-user background or tray application.

Requirements:

- No unnecessary elevated privileges.
- No hidden system-wide installation.
- Minimal idle CPU usage.
- Minimal memory consumption.
- Minimal network traffic.
- No expensive continuous polling.
- Clean shutdown.
- Reliable reconnection.
- Robust local state persistence.
- Clear and reversible startup behavior.

Persist feature preferences and waiting tasks safely.

Handle the application being closed, restarted, or disconnected.

If true continuation while the desktop app is closed is unsupported, explicitly document that limitation.

Do not simulate support by opening a different session unexpectedly.

On machine startup or wake:

1. Restore local configuration.
2. Restore outstanding waiting tasks.
3. Revalidate account and task state.
4. Fetch fresh allowance information.
5. Resume only when all safety checks pass.

Do not automatically resume after a user explicitly stopped the application or task.

Avoid storing access tokens unless indispensable. Use established authentication interfaces and secure storage.

Never log credentials or sensitive conversation contents unnecessarily.

---

# 9. PHASE SEVEN — CROSS-PLATFORM ARCHITECTURE

Ubuntu 22.04 is the primary platform.

Implement and validate the Ubuntu experience first.

Use clean interfaces so the same continuation engine can later support Windows.

Separate:

- Quota inspection
- Task observation
- Scheduling
- Persistence
- Continuation execution
- OS-specific lifecycle integration
- User interface
- Notifications

Do not tightly couple the core engine to GNOME, systemd, X11, or Win32.

Prefer native Codex APIs rather than operating-system keyboard automation so Wayland and Windows compatibility are easier to maintain.

If a platform capability is unavailable, disable it gracefully and explain the limitation.

Windows support should be implemented and tested where possible, not merely claimed because the code appears portable.

---

# 10. PHASE EIGHT — TESTING AND VALIDATION

Build a comprehensive automated test suite.

Do not require actual exhaustion of the user's live Codex quota for normal tests.

Implement a fake clock, mock App Server responses, simulated thread states, and controllable reset events.

## Mandatory test scenarios

### Normal operation

1. Feature defaults to OFF.
2. User enables it.
3. Five-hour usage limit is reached.
4. Weekly usage remains available.
5. Reset time arrives.
6. Backend confirms included usage is allowed.
7. Original unfinished thread resumes exactly once.
8. Task eventually completes.
9. No further automatic continuations are triggered.

### Weekly-limit protection

10. Five-hour limit exhausted and weekly limit exhausted.
11. Weekly limit becomes exhausted while waiting.
12. Weekly usage is nearly exhausted.
13. Weekly allowance information is missing.
14. Weekly allowance information is stale.
15. Five-hour window resets but weekly allowance remains exhausted.
16. Weekly window later resets after the task was disarmed.

Expected behavior: no unauthorized automatic continuation.

### Financial safety

17. Paid credit balance exists but included usage is exhausted.
18. Credit balance is unavailable.
19. Automatic paid fallback is enabled elsewhere.
20. API-key authentication is active instead of included ChatGPT authentication.
21. Banked reset is available.
22. Backend reports `ordinaryUsageAllowed = false`.
23. Backend reports `ordinaryUsageAllowed = null`.
24. Account or model quota identity changes.

Expected behavior: never intentionally transition into chargeable continuation.

### Task safety

25. User disables Auto-Resume while waiting.
26. User manually cancels the task.
27. Task completes during the wait.
28. Another turn starts before the reset.
29. Two reset events arrive simultaneously.
30. Scheduler is restarted during continuation.
31. Connection drops after a request is sent.
32. Thread history is unavailable.
33. The original project no longer exists.
34. An approval request is pending.
35. Multiple tasks are waiting simultaneously.

Expected behavior: no duplicate or unsafe continuation.

### System robustness

36. Network unavailable at reset.
37. Authentication expired.
38. App Server temporarily unavailable.
39. Computer suspended through the reset.
40. System clock changes.
41. Daylight-saving transition.
42. OS restarts.
43. Unsupported App Server version.
44. Quota API response format changes.
45. Only the weekly usage bucket is exposed.
46. Primary and secondary quota windows are reversed.
47. A model-specific quota behaves differently from the general quota.
48. Repeated temporary errors occur.

Expected behavior: safe recovery, bounded retries, clear diagnostics, or fail-closed behavior.

## Test methodology

Use:

- Unit tests for quota interpretation and policy decisions.
- State-machine transition tests.
- Property-based tests for invariants where useful.
- Integration tests using a mocked Codex protocol.
- Crash-recovery tests.
- Concurrency and race-condition tests.
- UI interaction tests.
- Platform-specific packaging smoke tests.
- Security and dependency checks.

Verify the actual application integration using a real non-destructive Codex session if feasible and permitted.

Avoid unnecessary live model calls.

Provide a test-results report with explicit PASS, FAIL, and NOT TESTED classifications.

Never fabricate successful tests.

---

# 11. PHASE NINE — ITERATIVE REFINEMENT

After the first working implementation, perform structured improvement cycles.

Each cycle should:

1. Review the current implementation.
2. Run relevant tests.
3. Identify defects, risks, and usability issues.
4. Prioritize the most important remaining problems.
5. Improve the implementation.
6. Rerun affected tests.
7. Check that previous functionality has not regressed.
8. Record the changes and results.

Prioritize improvements in this order:

1. Financial safety
2. Weekly-limit protection
3. Correct thread continuation
4. No duplicate execution
5. Reliability and crash recovery
6. Integration correctness
7. UI usability
8. Performance
9. Maintainability
10. Visual polish

Perform at least three meaningful engineering review cycles where tools and available resources permit.

Do not create meaningless iterations solely to satisfy a numerical target.

Do not endlessly continue generating speculative improvements after acceptance criteria are satisfied.

If resources become limited, prioritize a stable and safe deliverable over extra features.

---

# 12. PHASE TEN — PACKAGING AND INSTALLATION

Create an installable, documented distribution.

For Ubuntu, prefer a standard package or an appropriate self-contained user installation.

Deliver:

- Functional application source
- Plugin package if officially supported
- Necessary local companion service
- Configuration files
- Install and uninstall scripts
- User documentation
- Developer documentation
- Automated tests
- Build instructions
- Release artifacts where the build environment permits

Installing must not overwrite unrelated Codex settings.

Existing user configuration must be preserved.

Support clean uninstallation without damaging Codex.

Ideally, normal installation should require minimal manual steps.

Document any required plugin-hook trust approvals.

Provide troubleshooting for:

- Missing Codex CLI
- Incompatible application version
- X11 versus Wayland
- Invalid authentication
- Inaccessible quota information
- Background service failures
- Unsupported native UI integration

---

# 13. CODE QUALITY REQUIREMENTS

Write production-quality software.

Use:

- Clear modular architecture
- Strict input validation
- Explicit types where appropriate
- Structured error handling
- Bounded retry behavior
- Secure credential handling
- Atomic state persistence
- Idempotent operations
- Minimal dependencies
- Useful diagnostics
- Comprehensive tests
- Consistent formatting and linting

Choose the implementation language and UI framework based on compatibility, reliability, and maintenance cost.

Prefer straightforward, auditable engineering over clever but fragile solutions.

Do not introduce unnecessary cloud services or user accounts.

The application should operate locally whenever possible.

Do not modify proprietary Codex application binaries by default.

Do not quietly change authentication, billing, sandbox, or model settings.

---

# 14. REQUIRED PROJECT DELIVERABLES

Create an organized repository containing at least:

- `README.md` — What the feature does and how to use it.
- `docs/ARCHITECTURE.md` — Technical architecture and integration decisions.
- `docs/SAFETY.md` — Quota and financial safety guarantees, assumptions, and limitations.
- `docs/INSTALL.md` — Ubuntu installation and Windows instructions.
- `docs/TESTING.md` — Testing strategy and results.
- `docs/LIMITATIONS.md` — Unsupported or unverified capabilities.
- `docs/DECISIONS.md` — Important engineering decisions and trade-offs.
- Production source code.
- Automated test suites.
- Reproducible build scripts.
- Appropriate local plugin manifest and configuration if applicable.

Also provide a final implementation summary covering:

1. What was built.
2. Which integration method was selected.
3. Why it was selected.
4. How the one-click toggle works.
5. How quota safety is enforced.
6. How the original task resumes.
7. What happens when the weekly limit is exhausted.
8. What was actually tested on Ubuntu.
9. What was actually tested on Windows.
10. Known limitations.
11. Exact installation commands.
12. Exact usage instructions.
13. Any remaining work.

---

# 15. DEFINITION OF DONE

The project is ready only when the following requirements are satisfied or clearly documented as blocked by a verified platform limitation.

### Functional acceptance

- [ ] The user can enable or disable Auto-Resume with one click.
- [ ] The application detects eligible five-hour-limit interruptions.
- [ ] It preserves the correct conversation and unfinished task.
- [ ] It can wait through the usage-limit reset.
- [ ] It checks current allowance before resuming.
- [ ] It refuses continuation if the weekly allowance is exhausted.
- [ ] It refuses continuation if paid usage cannot be excluded.
- [ ] It resumes the original unfinished task exactly once.
- [ ] It never restarts already completed work.
- [ ] Manual cancellation is respected.
- [ ] Outstanding approval requests are respected.
- [ ] It handles crashes and reconnects safely.
- [ ] It has understandable status indicators.
- [ ] Ubuntu installation works.
- [ ] The implementation is modular enough for Windows.
- [ ] Automated tests cover safety-critical behavior.
- [ ] Documentation describes actual rather than assumed functionality.

**The single most important acceptance test:**

Given an unfinished Codex task paused by an exhausted five-hour quota, when the five-hour quota becomes available again but the weekly allowance remains exhausted, the application must make zero automatic continuation requests.

**The second most important acceptance test:**

Given an unfinished Codex task paused by an exhausted five-hour quota, when fresh authoritative backend data confirms ordinary included usage is available in both required windows and no paid path is needed, the application must resume the correct task no more than once.

---

# 16. EXECUTION INSTRUCTIONS

Begin immediately.

Use the current workspace as the project repository if it is suitable. Otherwise create a dedicated `codex-auto-resume` project directory without overwriting existing user files.

Follow this execution sequence:

**STEP 1:** Inspect the installed Codex environment, available tools, and relevant official documentation.

**STEP 2:** Investigate the supported desktop integration methods and document an evidence-based architecture decision.

**STEP 3:** Implement the safest viable minimum working product, beginning with the quota policy engine and continuation state machine.

**STEP 4:** Implement the task persistence and continuation controller.

**STEP 5:** Implement the one-click user interface through the best supported integration.

**STEP 6:** Write and execute automated tests, focusing on quota safety and once-only continuation.

**STEP 7:** Fix discovered problems and harden the implementation.

**STEP 8:** Complete at least three meaningful review-and-improvement cycles where feasible.

**STEP 9:** Package the working application, document installation, and perform available integration checks.

**STEP 10:** Deliver the finished implementation with a truthful final verification report.

Do not stop after writing a plan.

Do not replace executable software with pseudocode.

Do not repeatedly ask the user to select between reasonable technical options.

Make decisions using the priorities and constraints in this specification.

For irreversible actions, modifications to unrelated software, spending, or security-sensitive operations, require explicit approval.

Use mocks and local fixtures instead of unnecessarily consuming the user's live quota.

Preserve all existing Codex functionality.

## FINAL DIRECTIVE

Build Codex Auto-Resume into a reliable, polished, low-maintenance feature that feels as close to a native desktop capability as the supported platform allows.

Make it simple enough that a nontechnical user can turn it on, forget about it, and trust that it will automatically continue only eligible unfinished tasks without bypassing limits or intentionally incurring additional charges.

**Research. Architect. Implement. Test. Debug. Improve. Verify. Package. Deliver.**
