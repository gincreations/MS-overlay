# MS Overlay — Mac

Apple Silicon (M1 or newer), macOS 14 or newer. Intel Macs are not supported by this build.

1. Extract the entire ZIP and open **Maple Private Overlay.app**.
2. Allow Screen Recording for the overlay in **System Settings → Privacy & Security** when prompted, then restart the overlay.
3. Open MapleStory, start tracking with the overlay's button, and click back into the game.

Tracking pauses when another app is in front. Global keyboard shortcuts are not available on Mac; use the overlay buttons. EXP, mesos, hotbar-first potion counts and inventory fallback use the same recognition and calculation logic as Windows.

The Mac build recognizes the **MapleStory Classic World** process as well as MapleStory Classic/MapleStory Worlds window-name variants and narrowly named Wine game windows. It prefers the foreground game and reacquires its window when the client changes windows. Generic virtual-machine desktops, browsers and streaming clients are deliberately not captured. Game detection, EXP tracking, inventory potion counts and inventory mesos have been confirmed on the reported Classic World Mac setup. Hotbar potion detection and brief EXP-reading interruptions remain under investigation; broader CrossOver/Wine compatibility still needs testing. Only the standard 4×2 potion hotbar layout is currently supported.

This release fixes Classic World becoming undetectable when focused: the client raises its game window to a higher macOS window layer. Both discovery and the foreground check now support that observed layer while retaining process identity, permission, and game-bounds checks. The status badge also shows when capture is blocked instead of incorrectly claiming it is reading EXP.

The overlay participates in Mission Control even with **Always on top** enabled. Drag it to the desktop/Space you want to use; it stays assigned to that Space rather than appearing on every desktop. Tracking still pauses whenever the game is not in front. These native window settings are regression-tested; confirm the actual drag/fullscreen behavior on your Mac.

**Check setup.command** runs an optional local assets/OCR/interface check and writes `setup-check.txt` beside the app. It does not capture your screen or use existing player history.

This is an ad-hoc signed test build, not Apple-notarized. macOS may show a developer/reputation warning. Keep system protections enabled. Download only from the intended release and verify its checksum if macOS blocks it; do not disable Gatekeeper globally.

The overlay does not send input to the game, read its memory, or upload screenshots. Screen pixels are processed in RAM. Capture is restricted to the recognized foreground game bounds, but visible panels/notifications overlapping those bounds can appear in a crop. Python network requests are blocked; this is not an OS sandbox or a guarantee about every native dependency.

Build instructions and evidence are in `tools/build_ocr_macos.py`, `tools/build_macos.py`, and the Mac review workflow. Real-game accuracy, performance and screen-permission behavior remain tester checks. Existing Windows releases are unchanged.
