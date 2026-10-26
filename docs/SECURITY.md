# 0.1.19 RC1 security and redistribution notes

## What is being shared

This is a documentation/source-metadata redistribution of the tested Windows 0.1.19 RC1 hotbar runtime. All 1,127 runtime-manifest files (including the executable, libraries, OCR model and launchers) and all 18 application source modules are unchanged from the validated candidate. Documentation and the accompanying source archive use this public repository. Required upstream credits and licenses are retained.

EXE SHA256: `1a9eada8519e582ce14fdf1f9530934392e243a02eccc97db56def746e6356f3`.

## Prior candidate checks (2026-10-25)

- 25 Windows regression suites / 779 checks passed, including 29 hotbar tests and 20 original potion-behavior contracts.
- Microsoft Defender engine 1.1.26090.9, definitions 1.461.206.0: runtime and then-original ZIP scans passed with real-time protection enabled.
- ClamAV 1.5.4, daily database 28164: original release archives and metadata passed with zero detections/errors.
- Packaged setup and three synthetic OCR cases passed. 18 embedded application modules matched the tested source.
- Pinned Python/native advisory queries returned no matches at review time; coverage is not exhaustive.
- A bounded Windows trace captured 36,854 candidate-process events across setup, 20-second startup, synthetic OCR and helper/search-path probes. No observed TCP/UDP, dummy wallet/browser-credential accesses, selected persistence writes or planted-working-directory DLL loads. The helper canary did not execute.

These are maintainer-reported checks of the unchanged runtime, not new GitHub Actions runs in this sharing repository. See release assets for this redistribution's checksums, identity verification and new ClamAV result. The original ZIP's Defender result is not a Defender scan of this repacked public ZIP.

## Limits

The trace is not a full gameplay session or exhaustive sandbox analysis; Procmon does not monitor clipboard APIs. No scan, code review or bounded observation guarantees absence of every issue or malicious behavior.

The historical 0.1.17 Bearfoos detection remains unresolved, with no Microsoft false-positive adjudication. This EXE is unsigned and may trigger SmartScreen or antivirus warnings. Keep protection enabled; do not add exclusions or restore quarantined files merely to run it.

This release retains the previous Explorer launch-path fix and minimal source-built OCR runtime. Hotbar tracking uses the standard classic 4×2 layout and falls back to visible inventory counts. Normal EXP/mesos/ETA calculations are unchanged. No updater, telemetry or upload feature is added.
