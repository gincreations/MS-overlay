# Windows and Mac verification notes

## Mac 0.1.21 — hotbar raster correction

The hotbar frame matcher permits a small additional luminance difference only when the fixed slot structure matches with high confidence. The existing acceptance path is retained; labels and counts remain excluded from frame matching. A HUD-only regression crop contains no player names, chat, desktop or account information. It reproduces the old rejection and reads 26 Orange Potions and 146 Blue Potions with the adjustment. Covered and duplicate panels remain rejected.

Inventory recognition, digit recognition, potion usage/source selection, EXP calculations and capture/privacy behavior are unchanged. This does not claim to fix the reported brief EXP-number interruptions. The Mac app is newly built as 0.1.21. The Windows download remains byte-identical to 0.1.20, with its original internal 0.1.19 RC2 version and matching source retained. Current package checks are attached in VERIFICATION.json; actual in-game hotbar confirmation is still needed.

## Previous combined download release

The consolidated **0.1.20** release preserves the exact tested Mac 0.1.20 RC4 and Windows 0.1.19 RC2 archives under clean download names. The rename does not change either app binary. Earlier 0.1.20 prerelease entries have been replaced by this single public release; future public versions increase sequentially. Windows has not been rebuilt just to match the shared download version.

### Mac 0.1.20 RC4 — focused-game window layer correction

The affected client reports window layer **26** while focused and layer **0** while inactive. RC3 incorrectly rejected layer 26 during game discovery and required layer 0 for foreground capture. RC4 accepts this observed game layer and selects the front game window consistently. Exact process identity, Screen Recording permission, foreground ownership, minimum size, visibility, bounded crops, and the before/after focus checks remain required. No launcher, generic Wine loader, browser, VM desktop, or arbitrary title is newly allowed.

Regression cases reproduce the previous failure and cover repeated 0/26 transitions, same-process window ordering, focus loss during capture, denied permission, hidden windows, unrecognized owners, and unsupported layers. The status pill now retains blocked/error state until a real reading arrives. The user report is not included in the public source; only sanitized shapes are used in tests. The exact package checks and their limits are attached as `VERIFICATION.json`. Both app archives are unchanged for the consolidated release. The user confirmed game detection, EXP tracking, inventory potion counts and inventory mesos; hotbar recognition and intermittent EXP-reading interruptions remain under investigation.

### Previous Mac 0.1.20 RC3 — confirmed native client name

The reported process is **Maplestory Classic World**, with window title **MapleStory**. RC2 rejected this identity in a reproduced regression case. RC3 adds this exact native process name; the new regression and all 34 Mac-specific tests pass. Existing foreground-only capture checks and Mission Control behavior remain intact. Windows bytes are unchanged. Full release verification is attached as `VERIFICATION.json`; actual gameplay on the affected Mac still needs user confirmation.

### Previous Mac 0.1.20 RC2 — client detection and desktop handling

- Native Classic/Worlds name variants and executable-name fallback; foreground game preference and replacement-window reacquisition. A window title alone cannot enable capture of arbitrary apps.
- Managed Mission Control window behavior, including topmost toggles and hide/show remapping. The overlay belongs to the user-selected Space, not all desktops.
- All 26 native regression suites passed, including 33 Mac-specific tests. Three real synthetic OCR samples and six packaged setup checks passed.
- All 18 embedded application modules matched the tested source; all 401 runtime files were hash-verified. 110 native files passed arm64, dependency-path and minimum-OS checks. Ad-hoc signing and ZIP extraction/roundtrip checks passed.
- CPython 3.13.17 from the SHA256-verified official python-build-standalone 20261021 archive, with the existing hash-pinned Python dependencies. The static OCR executable was reused from the prior hash-verified, signature-verified public Mac package; its signed hash and original build provenance are retained.
- ClamAV 1.5.4 / daily 28165 scanned the updated Mac ZIP and source archive with zero detections/errors. Python dependency and pinned native OCR advisory queries returned no matches. Other native dependencies are not exhaustively vulnerability-audited.
- The Windows ZIP is byte-identical to its previous release. No new Windows Defender or Windows regression result is claimed.

These checks include actual Tk/AppKit collection flags, but not a live game session or an automated Mission Control drag/fullscreen transition. The reported Mac setup still needs user testing. This is ad-hoc signed, not Apple-notarized. Existing foreground-only capture/privacy rules remain in place.

### Previous Mac 0.1.20 RC1 evidence

- Apple Silicon arm64, macOS 14+. Fresh native app build from the current source with pinned Python dependencies and patched, source-built static OCR.
- 26 native regression suites passed, including 21 Mac guard/lock tests; three real OCR samples and six packaged setup checks passed.
- All 18 embedded application modules matched the tested source. All 463 runtime files and the exact ZIP were hash-verified; 160 native files were inspected for architecture, dependency paths and minimum OS version.
- Ad-hoc signature verified before and after ZIP extraction and on an independently downloaded copy. This is **not Developer ID signing or Apple notarization**.
- ClamAV 1.5.4 with daily 28165 scanned the Mac ZIP/source/extracted app: 470 files, zero detections/errors. Declared Python and pinned native OCR advisory queries returned no matches; other native dependencies are not exhaustively vulnerability-audited.
- Public promotion preserves the exact tested Mac ZIP and app bytes. No Windows Defender result is claimed for this Mac package.

Live gameplay, real screen-capture behavior and user-granted Screen Recording permission still need Mac tester validation. Generic VM desktops and streaming windows are blocked; global Mac hotkeys are unavailable. Automated privacy tests use synthetic screens and mocked foreground states, not a full Mac behavioral trace. No review or scan guarantees absence of all issues.

### Windows 0.1.19 RC2 evidence (unchanged)

## What is being shared

This is a documentation/source-metadata redistribution of the tested Windows 0.1.19 RC2 hotbar runtime. All 1,128 runtime-manifest files (including the executable, libraries, OCR model and launchers) and all 18 application source modules are unchanged from the validated candidate. Documentation and the accompanying source archive use this public repository. Required upstream credits and licenses are retained.

EXE SHA256: `1194c1ec82c633526a7e4f9733c16658d8cf4b2c00ec6e3d181d28d8109b826c`.

## Prior candidate checks (2026-10-26)

- 25 Windows regression suites / 788 checks passed, including 38 hotbar tests and 20 original potion-behavior contracts.
- Microsoft Defender engine 1.1.26090.9, definitions 1.461.206.0: runtime and then-original ZIP scans passed with real-time protection enabled.
- ClamAV 1.5.4, daily database 28164: original release archives and metadata passed with zero detections/errors.
- Packaged setup and three synthetic OCR cases passed. 18 embedded application modules matched the tested source.
- Pinned Python/native advisory queries returned no matches at review time; coverage is not exhaustive.
- A bounded Windows trace captured 36,872 candidate-process events across setup, 20-second startup, synthetic OCR and helper/search-path probes. No observed TCP/UDP, dummy wallet/browser-credential accesses, selected persistence writes or planted-working-directory DLL loads. The helper canary did not execute.

These are maintainer-reported checks of the unchanged runtime, not new GitHub Actions runs in this sharing repository. See release assets for this redistribution's checksums, identity verification and new ClamAV result. The original ZIP's Defender result is not a Defender scan of this repacked public ZIP.

## Limits

The trace is not a full gameplay session or exhaustive sandbox analysis; Procmon does not monitor clipboard APIs. No scan, code review or bounded observation guarantees absence of every issue or malicious behavior.

The historical 0.1.17 Bearfoos detection remains unresolved, with no Microsoft false-positive adjudication. This EXE is unsigned and may trigger SmartScreen or antivirus warnings. Keep protection enabled; do not add exclusions or restore quarantined files merely to run it.

This release retains the previous Explorer launch-path fix and minimal source-built OCR runtime. Hotbar tracking uses the standard classic 4×2 layout and falls back to visible inventory counts. Normal EXP/mesos/ETA calculations are unchanged. No updater, telemetry or upload feature is added.
