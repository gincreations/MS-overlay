# RC3 security and redistribution notes

## What is being shared

This is a documentation/source-metadata redistribution of the tested Windows 0.1.18 RC3 runtime. Application code, executables, libraries, model data, launchers and all 1,126 runtime-manifest files are byte-identical to the previously validated candidate. Only documentation and the accompanying source archive change. The source starts with fresh public history; build helpers now refer to this repository. Required upstream credits and licenses are retained.

EXE SHA256: `3792cca83ba0d98874f7e37f9589e577645011fa746b5f55ad103ab045e71676`.

## Prior runtime checks (2026-10-25)

- 24 Windows regression suites / 732 checks passed.
- Microsoft Defender engine 1.1.26090.9, definitions 1.461.201.0: runtime and then-original ZIP scans passed with real-time protection enabled.
- ClamAV 1.5.4, daily database 28164: original ZIP and extracted package, 1,147 files, zero detections/errors.
- Packaged setup and three synthetic OCR cases passed. 18 embedded application modules matched the tested source.
- OSV queries returned zero matches for 11 pinned Python packages and four pinned native source commits at review time. This is not exhaustive vulnerability coverage.
- A bounded Windows trace captured 36,894 process-tree events across setup, 20-second startup, synthetic OCR and Explorer/search-path probes. No observed TCP/UDP, dummy wallet/browser-credential accesses, persistence writes or planted-working-directory DLL loads. The Explorer canary did not execute.

These are maintainer-reported prior checks of the unchanged runtime, not newly executed GitHub Actions in this repository. Private CI URLs and development identity metadata are intentionally omitted. Native source provenance and dependency pins remain available. See release assets for the new archive checksum, file-identity checks and current redistribution scan result. The old ZIP's Defender result must not be described as a scan of the new ZIP.

## Limits

No wallet/password-stealing implementation was identified within reviewed application code and the stated observations. This is not a guarantee against every behavior, vulnerability, or anti-cheat decision. The trace is not a full gameplay session or exhaustive sandbox analysis; Procmon does not monitor clipboard APIs.

The historical 0.1.17 Bearfoos detection remains unresolved, with no Microsoft false-positive adjudication. This EXE is unsigned and may still trigger SmartScreen or antivirus warnings. Keep protection enabled; do not add exclusions or restore quarantined files merely to run it.

RC3 fixes the Windows Explorer launch-path weakness and replaces legacy OCR dependencies with a minimal source-built runtime. Normal EXP/mesos/ETA calculations and optional potion tracking remain unchanged. No runtime updater, telemetry or upload feature is added.
