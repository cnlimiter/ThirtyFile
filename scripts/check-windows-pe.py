#!/usr/bin/env python3
"""Validate the delivered AMD64 PE executable and its SHA-256 manifest."""

import argparse
import hashlib
import json
from pathlib import Path
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--write-checksums", action="store_true")
    parser.add_argument("--verify-checksums", action="store_true")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    data = binary.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError("Not a Windows executable")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[offset:offset + 4] != b"PE\0\0":
        raise ValueError("PE signature is missing")
    machine = struct.unpack_from("<H", data, offset + 4)[0]
    magic = struct.unpack_from("<H", data, offset + 24)[0]
    if machine != 0x8664 or magic != 0x20B:
        raise ValueError(f"Expected AMD64 PE32+, got machine={machine:#x}, magic={magic:#x}")
    report = {"machine": "AMD64", "machine_hex": hex(machine), "format": "PE32+", "sha256": hashlib.sha256(data).hexdigest()}
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "pe-amd64.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    manifest = binary.parent / "SHA256SUMS"
    if args.write_checksums:
        files = [binary, binary.parent / "LICENSE", binary.parent / "THIRD-PARTY-NOTICES", binary.parent / "README.md"]
        manifest.write_text("".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files), encoding="utf-8")
    if args.verify_checksums:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, name = line.split("  ", 1)
            path = binary.parent / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Checksum mismatch: {name}")
            print(f"{name}: OK")
        smoke = json.loads((args.evidence / "smoke-result.json").read_text(encoding="utf-8"))
        if smoke["status"] != "passed" or smoke["binary_sha256"] != report["sha256"]:
            raise ValueError("Tested executable does not match the delivered executable")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
