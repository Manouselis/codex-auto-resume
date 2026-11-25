# Release checklist

Use this checklist whenever a fix, feature, or documentation update is delivered. It keeps the source, documentation, website, and public downloads in sync.

## Prepare the change

1. Check the branch, configured remote, and newest **published** GitHub release. A Git tag can exist before its installers are available.
2. Update the README and affected guides. Record user-visible changes in the changelog and release notes. Refresh screenshots when the interface changes. Document the scope of the checks you actually ran.
3. Update the website under `docs/` to reflect the change. Check the Windows, Ubuntu, and both macOS downloads, the release-notes link, screenshots, and setup instructions. Check the site's static HTML as well as its JavaScript download selector.
4. Keep the static fallback links on the newest complete release you have verified. The website can show a newer release automatically when GitHub lists all four uploaded installers and the checksum file. README download links route through the platform cards so they remain usable while CI builds.
5. Run checks appropriate to the work. For an app release, run the local suite and use the tagged installer workflow to verify the packaged GUI and native installers across the supported platforms. For documentation-only changes, check the changed links and the deployed site.

## Commit, tag, and push

1. Commit related changes together. Add an annotated tag for each delivered fix, feature, performance improvement, or documentation change. Point each tag at the commit that contains that work.
2. Push the branch and the descriptive tags. If installer contents change, bump `auto_resume/__init__.py`, prepare `docs/RELEASE_NOTES.md`, and tag the exact release commit `vX.Y.Z`. Push the version tag separately to trigger the installer workflow. [GitHub skips tag push events when more than three tags are pushed together](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push).
3. Confirm the branch and tags are on GitHub and the relevant workflow started. A documentation-only update needs no new version tag.

## Verify after pushing

1. Check GitHub Pages deployment and open the live website. Verify that the changes are visible and that the download cards still work if the release feed is unavailable.
2. For an app release, check the [desktop workflow](../.github/workflows/desktop.yml) at the tag. Confirm the public release contains the Ubuntu DEB, Windows installer, Apple silicon DMG, Intel DMG, and `SHA256SUMS`. Check the installer URLs and hashes. Read the smoke reports before claiming platform coverage.
3. Once the new release is available, update any pinned fallback links and version labels that still point to the previous release. Verify the README, install guide, and website agree. Push and tag that documentation follow-up without bumping the app version.
4. Report the pushed commit and tags, the verified downloads and platforms, and any pending checks. Report a release as published only once its assets are available.
