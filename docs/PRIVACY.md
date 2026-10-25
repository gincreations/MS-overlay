# Privacy and distribution

## Application

The app removes telemetry, uploads, automatic updating, browser-launch features and runtime catalog/price requests. It does not read game memory or generate game input. A Python audit guard rejects network/browser events as defense in depth, not as an OS firewall for native libraries.

Capture starts only after Start, stops on manual Pause, and is bounded to the foreground MapleStory client. A window/focus change detected during capture discards the frame. Screenshots can still contain another always-on-top window drawn over the game; foreground checks are not perfect compositor isolation. OCR crops pass through memory rather than temporary image files. The operating system may still page process memory to disk.

Settings, learned digit templates and farming history remain on the user's computer. History is plain text, not encrypted. Clear history removes app-owned records and backups but is ordinary deletion, not forensic secure erasure.

## Published files

The final source tree, source ZIP and portable package are checked for personal identifiers, credential patterns, build-machine paths and accidental user-data files. Personal settings, local farming records, local backups, private screenshots and development logs are excluded. Required third-party credits and licenses remain. Public-upstream test fixtures are not user data.

This distribution starts with a new Git history under the publishing account; prior development history is not included. A repository is still associated with its hosting account, and release/push activity may identify that account; these measures do not make GitHub hosting anonymous. Replacing refs or deleting releases cannot retract prior downloads, third-party clones, provider-retained records or caches.

Static review, automated tests, local antivirus scanning and a packaged Wine setup check are limited evidence—not a guarantee of zero risk or anti-cheat approval. No private binaries are automatically submitted to public scanning services by the packaging workflow.


## 0.1.18 candidate additions

A Share action writes a generated statistics card, not a game screenshot, to local storage and the clipboard. It can contain map, class, level, party size and farming rates. Only the user decides to paste or share it. Nothing is uploaded automatically.

Local diagnostic logs record technical status and exception types. Crash traces contain stack locations, not a memory dump or Python locals. Save logs exports only a fixed allowlist of diagnostic text plus bounded technical counters. It never includes config, farming history/notes, images or arbitrary files; known home paths are redacted. Review exports before sending. This is not a guarantee that all potentially identifying free text can always be recognized.

No updater, download executor, browser launcher or new application network path is introduced. Original capture bounds and manual-pause behavior remain. PQ mode does not grant extra capture permissions.

Earlier submitted 0.1.17 samples were uploaded to VirusTotal only after owner authorization. General packaging does not automatically submit artifacts. The Defender detection remains unresolved; clean source checks or other scanners do not override it.
