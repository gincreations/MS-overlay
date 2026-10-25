## 0.1.18 RC3 — Native OCR and shell-helper hardening

- Replace the legacy OCR DLL tree with source-built Tesseract 5.5.3 plus pinned upstream security fixes, Leptonica 1.87.0, libpng 1.6.59 and the patched zlib 1.3.2.1 development revision. External codecs are limited to PNG/zlib; curl/archive/TLS and ScrollView are not included.
- Pin source commits, archive hashes and the unchanged English model; package native provenance.
- Launch Explorer only by its verified Windows-directory absolute path; never search the working directory.
- Require realtime-enabled Defender and exact-bundle OCR smoke tests before packaging.
- Original normal-farming EXP/mesos/ETA calculations remain unchanged. Old 0.1.17 Defender detection remains unresolved; these fixes are not a malware-free guarantee.

# 0.1.18-rc2 — native security rebuild candidate

- 24/24 native Windows suites (732 checks), packaged setup, enabled Defender runtime/ZIP scans and independent ClamAV scans passed. Exact downloaded artifact hashes verified.

- Fresh Python3.13.17 runtime; Pillow13.0.0 and setuptools84.2.1 replace versions with reported advisories.
- PyInstaller6.22.3, hooks2026.9 and packaging26.3; hash-pinned Windows wheels, standard onedir build, no UPX.
- PNG-only share-card decoding; original farming calculations and all PQ/potion features retained.
- Release gates check current Python dependency advisories, full regressions, enabled Defender, packaged setup, embedded code and exact download hashes.
- Unsigned build: no promise of zero antivirus/reputation warnings. Historical native OCR bundle retained with its hash/provenance, not claimed exhaustively vulnerability-free.

# 0.1.18-rc1 — superseded; do not use

- Port PQ session mode, local share cards and platform clipboard support from upstream v0.9.13-beta.
- Add bounded local crash/activity diagnostics, explicit redacted text-only export and unexpected-shutdown notice.
- Preserve optional potion cards, no-restock policy, foreground-only capture, faster inventory reacquisition, and original normal-farming EXP/mesos/ETA computations.
- Keep application offline: no self-updater or automatic upload.
- Historical integration candidate; dependency findings are preserved in docs/SECURITY-RECHECK-0.1.18.md.

# 0.1.17 — withdrawn pending security review

- EXP/hour, recent farming rate, progress and level-up ETA with the original calculation policy.
- Inventory balance and mesos/hour tracking with faster reacquisition after inventory movement.
- Optional two-item potion/food tracking, visible-stack totals, usage and costs.
- Readable colored potion cards, customizable themes/colors, full/compact layouts and screen-fitting dialogs.
- Local farming history and notes; no potion restock estimates.
- Offline app behavior with foreground-only bounded capture; no memory reading, automated inputs, telemetry or updater.
- Final distribution contains clean source documentation and no personal settings, gameplay captures or development-history exports.

This historical release is withdrawn following an unresolved Defender detection. Use the current candidate evidence above; do not restore quarantined files. See README.md for setup and docs/TRACKING.md for calculation limits.
