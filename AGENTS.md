# Codex Auto-Resume repository instructions

Follow the [release checklist](docs/RELEASING.md) for every delivery in this repository.

- Update the README, relevant documentation in `docs/`, and the GitHub Pages site in `docs/index.html` as part of the change. Keep instructions, screenshots, release notes, and download links consistent with what users can actually install.
- Run checks appropriate to the change. Push completed commits and an annotated tag for each fix or feature to the configured GitHub repository. Use `fix/<name>`, `feature/<name>`, `perf/<name>`, or `docs/<name>`.
- If the installed app changes, bump the app version and push a separate `vX.Y.Z` release tag that points to the tested release commit. Documentation-only changes still get a descriptive tag and keep the existing installer version.
- Keep public download links working while a new release builds. Verify the live website, the release, and the installer links before reporting them as published. If CI is still running, say what has passed and what is pending.
- Preserve explicit chat arming, the included-usage checks, and the protections against duplicate or uncertain sends. Distinguish tests with fixtures from live Codex continuation. Keep private state and credentials out of Git and release files.

For figures, use the diagram-design skill and inspect the rendered result at its intended display size.
