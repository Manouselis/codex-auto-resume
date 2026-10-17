# Implementation summary

1. **Built:** an executable Python companion, state/policy engine, read-only Codex adapter, simulator, native control window, tests, installer/uninstaller and reproducible release builder.
2. **Integration:** Option C, independent local companion; no proprietary bundle changes and no cosmetic plugin manifest.
3. **Reason:** inspected plugin/hook surfaces do not establish a persistent native control or a safe conditional, included-only continuation operation.
4. **Toggle:** one click in the companion window; initially OFF. The Applications-menu action can toggle observation. Closing the window disables and disarms.
5. **Quota safety:** fresh authoritative ordinary permission, account/bucket identity, both duration-identified windows, weekly reserve, explicit no-credit/spend-control checks, plus an execution-capability gate. The live gate stays closed.
6. **Original task:** the simulator pins thread/turn/revision and original configuration, then sends one contextual continuation with a durable ID. The production adapter cannot submit this request to real Codex.
7. **Weekly exhaustion:** sticky `WEEKLY_LIMIT_REACHED`, zero submissions, preserved context, fresh manual arming required.
8. **Ubuntu verification:** local automated suite, real read-only quota probe, native Tk GUI, visual inspection, isolated user-prefix install/update/uninstall, zipapp demo, static checks and reproducible builds.
9. **Windows verification:** NOT TESTED on a Windows host. Portable code, `.cmd` installer and future CI matrix supplied.
10. **Limitations:** no unattended real-task continuation, native in-app control, tray, lifecycle subscription, verified Windows/Wayland support or normal reboot auto-rearming. See `LIMITATIONS.md`.
11. **Install:** from the project directory, `python3 scripts/install.py`, then `~/.local/bin/codex-auto-resume ui`. No startup service is enabled automatically.
12. **Use:** `python3 -m auto_resume doctor --connect` for real metadata; `python3 -m auto_resume --simulation ui` or `python3 -m auto_resume demo` for the complete safe simulated workflow.
13. **Remaining work:** a documented backend included-only conditional/idempotent continuation contract, original-runtime binding, lifecycle/model-quota integration, real non-destructive end-to-end validation and Windows/Wayland host tests.

The repository is prepared for eventual personal GitHub publication with an MIT license, contribution/security notes and a CI workflow. No remote repository or public release is created by this work.
