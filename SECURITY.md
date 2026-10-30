# Security

Version 0.8.0 sends real continuation requests only while globally enabled, after explicit per-task arming and current included-usage checks. Opening the GUI checks the master switch; previously disarmed chats remain disarmed. Preserve all refusal paths and the no-resend behavior for uncertain acknowledgements. Unresolved history from another runtime permits monitoring only and cannot authorize dispatch.

Never add billing purchases, API-key fallback, reset redemption, automatic approvals or implicit account changes. Changes to dispatch require tests for weekly exhaustion, missing ordinary permission, paid/unknown credits, concurrent work, cancellation and lost acknowledgements.

Report suspected vulnerabilities privately to the project owner. Use the repository's private reporting mechanism when available; keep sensitive information out of public issues. Do not publish account IDs, private prompts, tokens or raw runtime logs. Public verification evidence is redacted.

The local socket and task state are per-user resources, not a boundary against malicious code already running as that user. The financial checks are preflight checks; no claim of an atomic future billing reservation is made.

Context-checkpoint recovery requires explicit per-arming opt-in. It must not override a paused or exhausted user goal budget, treat quoted examples as checkpoints, or restart ordinary completion. Preserve the checkpoint fingerprint and fresh preflight checks.

## Download integrity

Native release assets include SHA-256 checksums and per-host installer smoke reports. The release workflow publishes only after its platform checks pass. Windows/macOS downloads are currently an unsigned community beta (macOS bundles have an ad-hoc signature); no production signing/notarization credentials are configured. Install only assets from this repository's release page. The app never downloads a Codex runtime or handles its credentials.
