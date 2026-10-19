# Delivery summary — 0.2.0

1. Built a real local Codex continuation adapter, reset scheduler, state store, native control window, tests and installer.
2. Integration is a standalone companion connected to the official persistent App Server over its local WebSocket socket.
3. Supported thread resume/start and quota reads provide real continuation without modifying proprietary bundles.
4. One-click global ON/OFF controls the feature; the original task is explicitly chosen and armed. ON alone never sweeps conversations.
5. Fresh ordinary permission, Plus auth, account/model identity, both quota windows, zero/known credits, spend controls and standard provider/tier are required.
6. The same thread is resumed without configuration overrides and receives one contextual continuation, not its original prompt.
7. Weekly exhaustion pauses and disarms, with fresh manual rearming required after recovery.
8. Ubuntu verification includes controlled tests, native GUI, official daemon metadata and a genuine two-turn same-thread/context check.
9. Windows real integration remains NOT TESTED.
10. Remaining limitations include a small cross-client dispatch race, no future quota reservation, unverified cross-client approval routing and conservative crash/reboot pauses.
11. Install: `python3 scripts/install.py` from this directory.
12. Use: `~/.local/bin/codex-auto-resume ui`; enable, choose the original task, arm it and leave the controller running. Optional user-service instructions are in INSTALL.md.
13. Remaining validation: a naturally encountered live quota reset, real user approval routing, Windows/Wayland and OS reboot tests. No live quota was deliberately exhausted.

Real evidence is in `docs/evidence/live-continuation.json`. GitHub publication is deferred until the owner requests it.
