# Attribution and provenance

Based on [guddevbaddev/Maple-Classic-Exp-Overlay](https://github.com/guddevbaddev/Maple-Classic-Exp-Overlay), v0.9.10-beta, commit `9369cfbe732fbb01ac24c8f12342b23f60c46a28`, itself derived from [beanguri/Maple-Classic-Exp-Overlay](https://github.com/beanguri/Maple-Classic-Exp-Overlay). The original MIT license is retained in LICENSE. Not affiliated with Nexon or the upstream maintainers.

This distribution adds offline-only restrictions, foreground-bounded capture, optional potion recognition/costs, themed readable controls and faster inventory relocation. Original EXP, mesos and session calculation classes are preserved; see [tracking behavior](docs/TRACKING.md).

NPC reference metadata is attributed to MapleClassic Wiki contributors under its stated CC BY-NC-SA 4.0 terms; see [price sources](docs/NPC-PRICES.md). It is not relicensed as MIT. [Item artwork and digit glyphs](docs/CONSUMABLE-ARTWORK.md) belong to Nexon/Wizet. Font licensing is retained under assets/fonts/OFL.txt.

The existing EXP/inventory/party screenshot crops and migration fixtures under tests are byte-identical to audited public upstream source, not saved settings from this distribution's users. The new hotbar-classic test crop contains only game quickslot UI from an owner-supplied feature example; see docs/CONSUMABLE-ARTWORK.md. Original image assets and attribution are preserved for regression testing.


The 0.1.18 integration candidate additionally adapts PQ session handling, share-card rendering, clipboard helpers and local diagnostic concepts from guddevbaddev/Maple-Classic-Exp-Overlay v0.9.13-beta (commit 3d9ae1a6bfd7342cc1c14fdb0a5a082adf640baf), under the upstream MIT license. Original copyright and license notices are retained. This is not an endorsement or safety certification by the upstream maintainer.

The 0.1.20 RC1 Mac test build adapts the macOS platform backend from the same upstream v0.9.13-beta source, adds foreground/permission restrictions and builds a fresh Apple Silicon app and patched OCR runtime. It does not redistribute upstream’s prebuilt Mac ZIP.
