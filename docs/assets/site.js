"use strict";

const preview = document.querySelector("#app-preview");
const themeButtons = [...document.querySelectorAll("[data-theme]")];
if (preview && themeButtons.length) {
  document.querySelector(".preview-controls").hidden = false;
  for (const button of themeButtons) {
    button.addEventListener("click", () => {
      const theme = button.dataset.theme;
      preview.src = `screenshots/${theme}.png?v=0.8.4`;
      preview.alt = `Auto-Resume ${theme} control panel showing included allowance, an example recovery queue, version 0.8.4, and Check for updates.`;
      for (const item of themeButtons) {
        item.setAttribute("aria-pressed", String(item === button));
      }
    });
  }
}

const project = "Manouselis/codex-auto-resume";
const releasesUrl = `https://github.com/${project}/releases`;
const downloads = [...document.querySelectorAll("[data-package]")];

async function updateDownloads() {
  const response = await fetch(`https://api.github.com/repos/${project}/releases?per_page=30`);
  if (!response.ok) return;
  const releases = await response.json();
  if (!Array.isArray(releases)) return;

  // Keep bundled links available offline or when GitHub rate-limits the feed.
  const versionLabel = document.querySelector("#release-version");
  const currentTag = versionLabel.textContent.split(" ")[0];
  const newestFirst = (a, b) => b.localeCompare(a, "en", { numeric: true });
  const published = releases
    .filter(release => !release.draft && /^v\d+\.\d+\.\d+$/.test(release.tag_name)
      && newestFirst(release.tag_name, currentTag) <= 0 && Array.isArray(release.assets))
    .sort((a, b) => newestFirst(a.tag_name, b.tag_name));

  for (const release of published) {
    const version = release.tag_name.slice(1);
    const links = downloads.map(link => {
      const name = `codex-auto-resume-${version}-${link.dataset.package}`;
      const url = `${releasesUrl}/download/${release.tag_name}/${name}`;
      return release.assets.some(asset => asset.name === name && asset.state === "uploaded"
        && asset.browser_download_url === url) ? url : null;
    });
    if (links.some(url => !url)) continue;
    downloads.forEach((link, index) => { link.href = links[index]; });
    versionLabel.textContent = release.tag_name + (release.prerelease ? " beta" : "");
    document.querySelector("#release-details").href = `${releasesUrl}/tag/${release.tag_name}`;
    break;
  }
}

if (downloads.length) updateDownloads().catch(() => {});
