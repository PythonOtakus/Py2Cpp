#!/usr/bin/env python3
"""Maintain the pinned official Windows x64 Node.js runtime; never run by packaging.

    python scripts/vendor-node.py                 # Explicit download/update
    python scripts/vendor-node.py --verify-only   # Offline integrity check

Updating the runtime requires reviewing and changing VERSION and the three
SHA-256 pins below together. The complete official Node.js LICENSE is retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request


VERSION = "v24.19.0"
DIST_URL = f"https://nodejs.org/dist/{VERSION}"
ROOT = Path(__file__).resolve().parent.parent / "vendor" / "node"
ARTIFACTS = (
    {
        "path": "SHASUMS256.txt",
        "url": f"{DIST_URL}/SHASUMS256.txt",
        "sha256": "be0629ee2bcd8e40bb856abdd3407f0762101b76bd60a36b8867f637733631c0",
    },
    {
        "path": "win32-x64/node.exe",
        "url": f"{DIST_URL}/win-x64/node.exe",
        "sha256": "3602f2bb1a10f2cbab4c36886218a33c1ab3db87290e73b033c46c77147d0237",
    },
    {
        "path": "LICENSE",
        "url": f"https://raw.githubusercontent.com/nodejs/node/{VERSION}/LICENSE",
        "sha256": "148eacf7863ef4329224a29398623077200a27194aa075569faf4a0a85566ca5",
    },
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(root: Path) -> None:
    for artifact in ARTIFACTS:
        path = root / artifact["path"]
        actual = file_sha256(path)
        if actual != artifact["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {path}: {actual}")

    manifest = {}
    for line in (root / "SHASUMS256.txt").read_text(encoding="utf-8").splitlines():
        checksum, name = line.split(maxsplit=1)
        manifest[name.lstrip("*")] = checksum
    node = next(item for item in ARTIFACTS if item["path"] == "win32-x64/node.exe")
    if manifest.get("win-x64/node.exe") != node["sha256"]:
        raise ValueError("The official checksum manifest does not match the pinned node.exe")


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Py2Cpp-Lexer-vendor-node/1"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        if not response.geturl().startswith("https://"):
            raise ValueError("Refusing a download redirected away from HTTPS")
        while chunk := response.read(1024 * 1024):
            output.write(chunk)


def write_provenance() -> None:
    provenance = {
        "name": "Node.js",
        "version": VERSION,
        "platform": "win32",
        "arch": "x64",
        "upstream": "https://nodejs.org/",
        "artifacts": list(ARTIFACTS),
        "verification": (
            "The executable SHA-256 matches the pinned official SHASUMS256.txt entry. "
            "Sources are downloaded over HTTPS; this helper does not verify release PGP signatures."
        ),
        "maintenance": "python scripts/vendor-node.py; offline: python scripts/vendor-node.py --verify-only",
    }
    (ROOT / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Verify existing files without network access or writes")
    args = parser.parse_args()
    try:
        if args.verify_only:
            verify(ROOT)
            print(f"Verified official Node.js {VERSION} Windows x64 runtime and LICENSE.")
            return 0

        ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".download-node-", dir=ROOT) as temporary:
            staging = Path(temporary)
            for artifact in ARTIFACTS:
                print(f"Downloading {artifact['url']}", flush=True)
                download(artifact["url"], staging / artifact["path"])
            verify(staging)
            for artifact in ARTIFACTS:
                destination = ROOT / artifact["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / artifact["path"], destination)
        write_provenance()
        print(f"Vendored and verified official Node.js {VERSION} Windows x64 runtime.")
        return 0
    except (OSError, ValueError) as error:
        print(f"Node.js vendoring failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
