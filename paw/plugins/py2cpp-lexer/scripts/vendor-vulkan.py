#!/usr/bin/env python3
"""Vendor the pinned LunarG Vulkan loader; --download is explicitly opt-in."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import urllib.request
import zipfile


VERSION = "1.4.357.0"
ARCHIVE_NAME = f"VulkanRT-X64-{VERSION}-Components.zip"
ARCHIVE_BYTES = 18_134_567
ARCHIVE_SHA256 = "a14672efed15aafc7f5a16572d35cd3a3416eadf670aeee3cdf50ee32d5fbf83"
ARCHIVE_URL = f"https://sdk.lunarg.com/sdk/download/{VERSION}/windows/{ARCHIVE_NAME}"
METADATA_URL = "https://vulkan.lunarg.com/sdk/files.json"
ARCHIVE_PREFIX = f"VulkanRT-X64-{VERSION}-Components/"
DLL_MEMBER = ARCHIVE_PREFIX + "x64/vulkan-1.dll"
DLL_SHA256 = "cd862090370454630b31b174e3d4eb474fda38ea034998d1fe1767b0c99a8696"
DLL_DESTINATION = "vendor/webgpu/dist/win32-x64/vulkan-1.dll"
APACHE_URL = "https://www.apache.org/licenses/LICENSE-2.0.txt"
APACHE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
APACHE_DESTINATION = "vendor/vulkan/licenses/Apache-2.0.txt"
PLUGIN_DIR = Path(__file__).resolve().parents[1]
VENDOR_DIR = PLUGIN_DIR / "vendor" / "vulkan"
CACHE_DIR = PLUGIN_DIR.parents[1] / ".cache" / "py2cpp-lexer"
DEFAULT_ARCHIVE = CACHE_DIR / ARCHIVE_NAME

NOTICE = f"""# Vulkan loader for Windows x64

The unmodified Vulkan loader in `../webgpu/dist/win32-x64/vulkan-1.dll` comes
from LunarG's official Windows runtime components ZIP, version `{VERSION}`.
It is placed next to Dawn's native module so its explicit library search can
find the loader. It uses the user's installed GPU driver for Vulkan compute.

- Upstream: https://github.com/KhronosGroup/Vulkan-Loader
- Publisher/download page: https://vulkan.lunarg.com/sdk/home
- Official file metadata (including archive SHA-256): {METADATA_URL}
- Archive: {ARCHIVE_URL}
- Archive bytes: {ARCHIVE_BYTES}
- Archive SHA-256: `{ARCHIVE_SHA256}`
- Original member: `{DLL_MEMBER}`
- Loader SHA-256: `{DLL_SHA256}`
- Binary format: PE32+ / AMD64 (`0x8664`).

`licenses/VulkanRT-License.txt` is the entire license file supplied in the
runtime ZIP, copied byte-for-byte. It includes the upstream copyright notices,
MIT license texts, and an Apache 2.0 reference. `licenses/Apache-2.0.txt` contains
the complete Apache 2.0 license, copied unchanged from {APACHE_URL}.
These files cover the loader's upstream MIT and Apache-2.0 components.

Only the x64 loader and licenses are shipped: x86 DLLs, debug symbols, diagnostic
executables, and installers are omitted. No system DLLs or editor-private files
supply this published dependency. The loader is not an installer and is never
copied into Windows system directories. Other platforms use their native
system backends. GPU hardware and a compatible installed driver are required.

`provenance.json` records archive members, source URLs, byte lengths, and SHA-256
digests. Its file paths are relative to the extension root. This notice and the
provenance manifest are generated locally; upstream DLL and license bytes are
unchanged.

Maintenance:
- `python scripts/vendor-vulkan.py --archive PATH --apache-license PATH`
  reproduces the vendored files from verified local inputs.
- `python scripts/vendor-vulkan.py --download` explicitly downloads the pinned
  runtime ZIP and the Apache license before verification.
- `python scripts/vendor-vulkan.py --verify` checks the installed file hashes
  and PE machine offline without writing.

Normal extension packaging and runtime inference perform no downloads.
"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_archive(path: Path) -> None:
    data = path.read_bytes()
    if len(data) != ARCHIVE_BYTES or digest(data) != ARCHIVE_SHA256:
        raise ValueError(f"Archive does not match the pinned LunarG release: {path}")


def download(url: str, destination: Path, sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".download")
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://vulkan.lunarg.com/sdk/home",
    })
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if digest(data) != sha256:
        raise ValueError(f"Downloaded file has an unexpected SHA-256: {url}")
    temporary.write_bytes(data)
    temporary.replace(destination)


def relative_path(value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in value or ":" in value:
        raise ValueError(f"Unsafe relative path: {value}")
    return Path(*relative.parts)


def check_x64_dll(data: bytes) -> None:
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("Vulkan loader is not a PE binary")
    offset = struct.unpack_from("<I", data, 60)[0]
    if offset + 26 > len(data) or data[offset:offset + 4] != b"PE\0\0":
        raise ValueError("Vulkan loader has an invalid PE signature")
    if struct.unpack_from("<H", data, offset + 4)[0] != 0x8664:
        raise ValueError("Vulkan loader is not AMD64")
    if struct.unpack_from("<H", data, offset + 24)[0] != 0x20B:
        raise ValueError("Vulkan loader is not PE32+")
    if digest(data) != DLL_SHA256:
        raise ValueError("Vulkan loader does not match the pinned DLL SHA-256")


def vendor(archive: Path, apache_license: Path) -> None:
    check_archive(archive)
    apache = apache_license.read_bytes()
    if digest(apache) != APACHE_SHA256:
        raise ValueError("Apache license does not match its pinned SHA-256")
    # destination => (unmodified bytes, archive member or None, source URL)
    files: dict[str, tuple[bytes, str | None, str | None]] = {}
    with zipfile.ZipFile(archive) as source:
        dll = source.read(DLL_MEMBER)
        check_x64_dll(dll)
        files[DLL_DESTINATION] = dll, DLL_MEMBER, ARCHIVE_URL
        for member in sorted(source.namelist()):
            name = PurePosixPath(member).name.casefold()
            if not member.endswith("/") and ("license" in name or "licence" in name):
                if not member.startswith(ARCHIVE_PREFIX):
                    raise ValueError(f"Unexpected license path: {member}")
                suffix = member[len(ARCHIVE_PREFIX):]
                relative_path(suffix)
                files[f"vendor/vulkan/licenses/{suffix}"] = source.read(member), member, ARCHIVE_URL
    if not any(member for _, member, _ in files.values() if member != DLL_MEMBER):
        raise ValueError("Runtime archive has no license files")
    files[APACHE_DESTINATION] = apache, None, APACHE_URL
    files["vendor/vulkan/NOTICE.md"] = NOTICE.encode("utf-8"), None, None

    records = []
    for name, (data, member, url) in sorted(files.items()):
        destination = PLUGIN_DIR / relative_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        records.append({
            "path": name, "archiveMember": member, "source": url,
            "bytes": len(data), "sha256": digest(data),
        })
    provenance = {
        "package": "LunarG Vulkan Runtime Components",
        "version": VERSION,
        "repository": "https://github.com/KhronosGroup/Vulkan-Loader",
        "source": ARCHIVE_URL,
        "metadataSource": METADATA_URL,
        "archiveBytes": ARCHIVE_BYTES,
        "archiveSha256": ARCHIVE_SHA256,
        "pathBase": "extension root",
        "files": records,
        "notes": (
            "Only the official x64 Vulkan loader is bundled beside Dawn. "
            "All archive licenses are preserved unchanged, with the complete "
            "Apache 2.0 text added from apache.org. NOTICE.md is generated locally. "
            "No installer, SDK, system DLL, or editor-private DLL is used."
        ),
    }
    (VENDOR_DIR / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    verify()


def verify() -> None:
    provenance = json.loads((VENDOR_DIR / "provenance.json").read_text(encoding="utf-8"))
    if provenance.get("archiveSha256") != ARCHIVE_SHA256 or provenance.get("version") != VERSION:
        raise ValueError("Provenance does not match the pinned LunarG release")
    expected = {DLL_DESTINATION, APACHE_DESTINATION,
                "vendor/vulkan/licenses/VulkanRT-License.txt", "vendor/vulkan/NOTICE.md"}
    seen = set()
    for record in provenance["files"]:
        name = record["path"]
        if name in seen:
            raise ValueError(f"Duplicate provenance entry: {name}")
        seen.add(name)
        data = (PLUGIN_DIR / relative_path(name)).read_bytes()
        if len(data) != record["bytes"] or digest(data) != record["sha256"]:
            raise ValueError(f"Vendored file failed verification: {name}")
        if name == DLL_DESTINATION:
            check_x64_dll(data)
        if name == APACHE_DESTINATION and digest(data) != APACHE_SHA256:
            raise ValueError("Apache license SHA-256 mismatch")
    if not expected <= seen:
        raise ValueError(f"Required files are absent: {sorted(expected - seen)}")
    print(f"Verified {len(seen)} Vulkan loader/license/notice files ({VERSION}, x64).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE,
                        help="local pinned LunarG runtime components ZIP")
    parser.add_argument("--apache-license", type=Path, default=CACHE_DIR / "Apache-2.0.txt",
                        help="local complete Apache 2.0 license")
    parser.add_argument("--download", action="store_true",
                        help="explicitly download the pinned runtime ZIP and Apache license")
    parser.add_argument("--verify", action="store_true",
                        help="verify existing vendored files offline without writing")
    args = parser.parse_args()
    if args.verify:
        if args.download:
            parser.error("--verify cannot be combined with --download")
        verify()
        return
    archive = args.archive.resolve()
    apache_license = args.apache_license.resolve()
    if args.download:
        download(ARCHIVE_URL, archive, ARCHIVE_SHA256)
        download(APACHE_URL, apache_license, APACHE_SHA256)
    for path in (archive, apache_license):
        if not path.is_file():
            parser.error(f"Local input not found: {path}; provide local paths or explicitly use --download.")
    vendor(archive, apache_license)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, struct.error) as error:
        print(f"Vulkan vendoring failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
