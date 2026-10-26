# MS Overlay — 0.1.19 RC2

A local, screen-reading tracker for **MapleStory Classic World**. It shows your farming progress without reading game memory or automating game inputs.

## Download

[Download the Windows portable ZIP](https://github.com/gincreations/MS-overlay/releases/download/v0.1.19-rc2/Maple-Private-Overlay-0.1.19-rc2-portable.zip). Extract the entire ZIP into a new folder, run **Check setup.cmd**, then **Maple Private Overlay.exe**.

## Release status

**0.1.19 RC2 — Windows prerelease.** [Release notes](https://github.com/gincreations/MS-overlay/releases/tag/v0.1.19-rc2) · [Security details](docs/SECURITY.md)

## New in 0.1.19 RC2

- **Rebind-friendly hotbar:** recognizes slot borders instead of key labels, so potions can use different keys in any of the eight slots. Standard 4×2 layout only; expanded/custom layouts are not supported.
- Prevents empty-slot borders from being mistaken for a White Potion.

- **Hotbar-first potion tracking:** reads total stock from the classic 4×2 quickslot panel. Falls back to the visible inventory Use tab when needed—never adds both together. Select your potions as usual; no extra mode to enable.
- Uses the same digit recognition and usage calculations as inventory tracking. Switching sources resets the reading baseline, not your accumulated usage or cost.

## Other features

- **PQ mode** in the more menu: tracking continues across maps; auto-idle waits 10 minutes. Off at every launch. Normal farming still uses the original policy.
- **Share** generates a local session-stat card and copies that image only when clicked. You choose where to paste it. It does not capture a screenshot or upload anything.
- **Local crash diagnostics** and **Settings > Save logs**. Text-only export excludes farming history, notes, settings and screenshots; known user-home paths are redacted. Review any ZIP before sharing. Normal closure clears the previous-run marker.
- Share and diagnostic UI fits large scaling/small screens using scrolling.

This integration targets the existing Windows download. Upstream's separately packaged Mac distribution is not part of this candidate; our existing Mac capture guard fails closed until a foreground-only Mac capture implementation is validated. Platform clipboard helpers are present but are not a claim of a working Mac release.

## What it does

- **EXP:** session EXP/hour, recent five-minute rate, EXP gained, progress percentages and estimated time to the next level.
- **Mesos:** reads your visible inventory balance, tracks balance changes and estimates mesos/hour and mesos per five minutes.
- **Optional potions:** select up to two of 21 supported potion/food types. Uses readable hotbar totals first, otherwise combines readable visible inventory stacks; shows stock, estimated usage and usage/minute. Both selections **Off** disables potion sampling and hides the readout.
- **Potion costs:** estimated spending and spending/hour from bundled NPC reference prices or your own unit prices. This is separate from the main mesos/hour number.
- **Local history:** farming sessions, map/level/party information and notes stored on your computer.
- **Readable UI:** full/compact layouts, light/dark themes, adjustable size and transparency, hotkeys, and custom colors—including separate colored potion cards. Set Transparency to **0%** for maximum readability.
- **Inventory movement:** automatically searches again when the inventory moves; no manual position selection is needed. Detection still requires visible, readable pixels.

**No potion restock countdown. No new EXP 60-second warm-up.**

## Important behavior

Original EXP/mesos calculations and the normal-mode active-session clock are retained. PQ mode deliberately changes only map/idle session handling. Idle/paused time is excluded, so hourly rates are not a stopwatch average. Main EXP/hour and level ETA may use different averaging windows. Mesos measures inventory balance changes—not pure drops or net profit. See [tracking details and limitations](docs/TRACKING.md).

Moving the inventory may briefly interrupt readings. Keep it inside the game window and away from other windows. Hidden stacks, clipped digits, unsupported UI scales, heavy transparency and ambiguous fields cannot be reliably read. Restoring the game to the foreground resumes permitted capture.

## Privacy

- No app telemetry, uploads, automatic updates or runtime item/price downloads.
- No game-memory access or automated game input.
- Capture is restricted to the foreground MapleStory client; manual Pause stops capture.
- Captured pixels and OCR inputs stay in memory; diagnostic screenshot export is removed.
- Your own settings, learned digits and history are local application data, not included in the download.

[Privacy and distribution notes](docs/PRIVACY.md) · [Verification](docs/SECURITY.md) · [Attribution](UPSTREAM.md) · [NPC price references](docs/NPC-PRICES.md)

## Source and development

Source, test fixtures and required licenses are included in the repository and the portable ZIP. Install requirements.txt in an isolated Python environment to run from source; requirements-build.txt and build.py support Windows packaging. The native build uses tools/prepare_windows_review.py with Python3.13.17 and requirements-build.txt. package_preview.py is retained only as a historical Python3.10 archive inspection/repackaging utility, not the current build path. User data, local verification output, build artifacts and credentials must never be committed.

The Windows review workflow is provided as an inactive template in `docs/windows-review.yml.example`. It is not installed as GitHub Actions automation in this sharing repository.
