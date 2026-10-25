"""Make an UNSIGNED, NATIVE-WINDOWS-UNTESTED preview using the exact audited runtime.

Python 3.10 only. No app/Windows executable is run. The original ZIP is read-only.
Usage: python package_preview.py path/to/audited-v0.9.10-beta.zip
A conventional Windows PyInstaller build is still available in build.py.
"""
import argparse
import hashlib
import json
import marshal
from pathlib import Path
import struct
import sys
import zipfile
import zlib

EXPECTED = "148c1eb6616c315772763228f4e28bdfa9ce3c6fc0dc261b04f36a6c58269620"
ROOT = Path(__file__).resolve().parent
MAGIC = b"MEI\014\013\012\013\016"
APP_SOURCES = {
    "share_card": "share_card.py", "diagnostics": "diagnostics.py",
    "maple_exp": "maple_exp.py", "ocr": "ocr.py", "report": "report.py",
    "ui_palette": "ui_palette.py", "ui_gfx": "ui_gfx.py", "ui_kit": "ui_kit.py", "ui_main": "ui_main.py",
    "platforms": "platforms/__init__.py", "platforms.base": "platforms/base.py",
    "platforms.windows": "platforms/windows.py", "platforms.macos": "platforms/macos.py",
    "potion_recognition": "potion_recognition.py", "potion_tracking": "potion_tracking.py", "potion_ui": "potion_ui.py",
    "privacy_guard": "privacy_guard.py", "setup_check": "setup_check.py",
}

def parse_archive(exe, expected_python=310):
    pos = exe.rfind(MAGIC)
    if pos < 0 or pos + 88 != len(exe):
        raise ValueError("Unexpected executable archive layout")
    _, size, off, length, version, library = struct.unpack("!8sIIII64s", exe[pos:pos+88])
    if version != expected_python: raise ValueError("Unexpected Python runtime version")
    base = pos + 88 - size
    current, end = base + off, base + off + length
    entries = []
    while current < end:
        size, off, packed, unpacked, flag, kind = struct.unpack("!iIIIBc", exe[current:current+18])
        if size < 19: raise ValueError("Invalid archive entry")
        name = exe[current+18:current+size].split(b"\0")[0].decode()
        raw = exe[base+off:base+off+packed]
        data = zlib.decompress(raw) if flag else raw
        if len(data) != unpacked: raise ValueError("Archive length mismatch")
        entries.append((name, kind, flag, data))
        current += size
    return exe[:base], entries, library

def replace_pyz(old, replacements):
    offset = struct.unpack("!I", old[8:12])[0]
    toc = dict(marshal.loads(old[offset:]))
    header_length = min(off for _, off, size in toc.values() if size)
    result = bytearray(old[:header_length])
    new_toc = []
    for name, (kind, offset, size) in toc.items():
        if name in replacements:
            packed = zlib.compress(replacements[name], 9)
        else:
            packed = old[offset:offset+size]
        new_toc.append((name, (kind, len(result) if packed else 0, len(packed))))
        result.extend(packed)
    for name, code in replacements.items():
        if name not in toc:
            packed = zlib.compress(code, 9)
            new_toc.append((name, (0, len(result), len(packed))))
            result.extend(packed)
    struct.pack_into("!I", result, 8, len(result))
    result.extend(marshal.dumps(new_toc))
    return bytes(result)

def pe_checksum(exe):
    result = bytearray(exe)
    pe = struct.unpack_from("<I", result, 60)[0]
    checksum_offset = pe + 24 + 64
    struct.pack_into("<I", result, checksum_offset, 0)
    total = 0
    padded = bytes(result) + (b"\0" if len(result) % 2 else b"")
    for (word,) in struct.iter_unpack("<H", padded):
        total += word
        total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    struct.pack_into("<I", result, checksum_offset, total + len(result))
    return bytes(result)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audited_zip", type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 10):
        raise SystemExit("Run this build tool with Python 3.10, not the app's EXE")
    original = args.audited_zip.read_bytes()
    if hashlib.sha256(original).hexdigest() != EXPECTED:
        raise SystemExit("STOP: original ZIP does not match the audited release")
    with zipfile.ZipFile(args.audited_zip) as archive:
        old = archive.read("Maple Classic Exp Overlay/Maple Classic Exp Overlay.exe")
    prefix, entries, library = parse_archive(old)
    codes = {name: marshal.dumps(compile((ROOT/path).read_bytes(), path, "exec", dont_inherit=True, optimize=0))
             for name, path in APP_SOURCES.items()}
    body, records = bytearray(), []
    for name, kind, flag, data in entries:
        if name == "maple_exp": data = codes["maple_exp"]
        elif name == "PYZ.pyz": data = replace_pyz(data, {k:v for k,v in codes.items() if k != "maple_exp"})
        raw = zlib.compress(data, 9) if flag else data
        records.append((len(body), len(raw), len(data), flag, kind, name))
        body.extend(raw)
    toc_offset = len(body)
    for offset, packed, unpacked, flag, kind, name in records:
        encoded = name.encode() + b"\0"
        length = (18 + len(encoded) + 15) // 16 * 16
        body.extend(struct.pack("!iIIIBc", length, offset, packed, unpacked, flag, kind))
        body.extend(encoded.ljust(length-18, b"\0"))
    toc_size = len(body) - toc_offset
    body.extend(struct.pack("!8sIIII64s", MAGIC, len(body)+88, toc_offset, toc_size, 310, library))
    output = pe_checksum(prefix + body)
    # Confirm generated archives can be parsed before publishing a candidate.
    _, rebuilt, _ = parse_archive(output)
    packed_main = next(data for name, _, _, data in rebuilt if name == "maple_exp")
    if packed_main != codes["maple_exp"]: raise RuntimeError("Verification failed")
    dest = ROOT / "release"
    dest.mkdir(exist_ok=True)
    exe = dest / "Maple Private Overlay.exe"
    exe.write_bytes(output)
    metadata = {"status": "NATIVE-WINDOWS-UNTESTED PREVIEW", "original_zip_sha256": EXPECTED,
                "preview_exe_sha256": hashlib.sha256(output).hexdigest(),
                "python_compiler": sys.version, "source_sha256": {
                    path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in APP_SOURCES.values()},
                "reference_assets_sha256": {f.relative_to(ROOT).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/"assets/consumables").rglob("*")) if f.is_file()},
                "method": "Original audited Windows launcher/runtime with source-compiled Python modules; no EXE execution"}
    (dest / "BUILD-INFO.json").write_text(json.dumps(metadata, indent=2))
    print("Built UNSIGNED, NATIVE-WINDOWS-UNTESTED preview:", exe.name)
    print("SHA-256:", metadata["preview_exe_sha256"])

if __name__ == "__main__": main()
