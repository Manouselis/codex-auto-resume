# Contributing

Use Python 3.10+. Run `python3 -m unittest discover -s tests -v` and `python3 scripts/build.py`. If installed, `python3 -m pyflakes auto_resume scripts tests` checks imports and undefined names. Runtime code has no third-party dependencies.

Keep fixtures invented and deterministic. Do not add real account IDs, token files, conversation text, project paths, private logs, or quota response captures to the repository. Report environment/version metadata using `doctor`.

Changes to quota interpretation or dispatch need regression tests for weekly exhaustion, missing ordinary permission, nonzero/unknown credits, account/model changes, user cancellation, concurrent input and lost acknowledgements. Never bypass the quota preflight, approve sensitive actions automatically or retry an uncertain submission. Review the real protocol's limitations in `docs/LIMITATIONS.md` and preserve the distinction between model-backed checks and controlled reset tests.

When creating diagrams or figures, use the diagram-design skill, simplify before drawing, prefer editable Figma when available, otherwise SVG/D2, and render and visually inspect the result. Keep text minimal, typography clean, whitespace generous and colors restrained.

For documentation changes, verify relative links, heading anchors and shell examples. Match CLI instructions to the implemented commands. Keep test counts and verification dates tied to evidence; distinguish headless Windows CI from live Windows Codex integration, and controlled reset tests from a natural reset observed live.

Source is published at [Manouselis/codex-auto-resume](https://github.com/Manouselis/codex-auto-resume). Release notes should describe the final behavior and its tested scope. Private runtime state and credentials must stay outside the repository and source packages.
