#!/usr/bin/env python3
"""将 Py2Cpp PyML 扩展打包为 .vsix（纯 Python，无需 npm/vsce）。"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import xml.sax.saxutils as xml_escape
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

# OPC / VSIX 固定部件
_CONTENT_TYPES = b"""<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="vsixmanifest" ContentType="text/xml"/>
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="js" ContentType="application/javascript"/>
  <Default Extension="py" ContentType="text/x-python"/>
  <Default Extension="md" ContentType="text/markdown"/>
  <Override PartName="/extension.vsixmanifest" ContentType="text/xml"/>
</Types>
"""

_RELS = b"""<?xml version="1.0" encoding="utf-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship
    Type="http://schemas.microsoft.com/editions/ExtensionPackaging/2006/relationships/files"
    Target="/extension.vsixmanifest"
    Id="package-files"/>
</Relationships>
"""


def _load_vscodeignore(root: Path) -> list[str]:
  ignore_file = root / ".vscodeignore"
  if not ignore_file.is_file():
    return []
  patterns: list[str] = []
  for line in ignore_file.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
      continue
    patterns.append(line.replace("\\", "/"))
  return patterns


def _is_ignored(rel_posix: str, patterns: list[str]) -> bool:
  rel = rel_posix.replace("\\", "/")
  if rel.startswith("./"):
    rel = rel[2:]
  if not rel:
    return False
  base = rel.split("/")[-1]
  for raw in patterns:
    pat = raw.strip()
    if not pat:
      continue
    if pat.endswith("/**") and not pat.startswith("**/"):
      prefix = pat[:-3].rstrip("/")
      if rel == prefix or rel.startswith(prefix + "/"):
        return True
      continue
    if pat.endswith("/"):
      prefix = pat.rstrip("/")
      if rel == prefix or rel.startswith(prefix + "/"):
        return True
      continue
    if "**" in pat:
      rx = "^" + re.escape(pat).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
      if re.match(rx, rel):
        return True
      continue
    if "/" in pat:
      if fnmatch.fnmatch(rel, pat):
        return True
    else:
      if fnmatch.fnmatch(base, pat) or fnmatch.fnmatch(rel, pat):
        return True
  return False


def _collect_extension_files(root: Path) -> list[tuple[str, Path]]:
  patterns = _load_vscodeignore(root)
  out: list[tuple[str, Path]] = []
  for path in sorted(root.rglob("*")):
    if not path.is_file():
      continue
    rel = path.relative_to(root).as_posix()
    if rel.endswith(".vsix"):
      continue
    if _is_ignored(rel, patterns):
      continue
    out.append((f"extension/{rel}", path))
  if not any(name.endswith("package.json") for name, _ in out):
    raise FileNotFoundError(f"缺少 package.json: {root}")
  if not any(name == "extension/out/extension.js" for name, _ in out):
    raise FileNotFoundError(
      "缺少 out/extension.js；请确认 out/ 下扩展 JS 源码完整",
    )
  return out


def _manifest_xml(pkg: dict) -> bytes:
  identity_id = str(pkg["name"])
  version = str(pkg["version"])
  publisher = str(pkg.get("publisher", "unknown"))
  display = xml_escape.escape(str(pkg.get("displayName", identity_id)))
  description = xml_escape.escape(str(pkg.get("description", "")))
  license_text = str(pkg.get("license", "")).strip()
  license_attr = (
    f'\n    <License>{xml_escape.escape(license_text)}</License>'
    if license_text
    else ""
  )
  xml = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0"
  xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"
  xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{xml_escape.escape(identity_id)}" Version="{xml_escape.escape(version)}" Publisher="{xml_escape.escape(publisher)}" />
    <DisplayName>{display}</DisplayName>
    <Description xml:space="preserve">{description}</Description>{license_attr}
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
  </Assets>
</PackageManifest>
"""
  return xml.encode("utf-8")


def build_vsix(*, root: Path, out_dir: Path | None = None) -> Path:
  root = root.resolve()
  pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
  name = pkg["name"]
  version = pkg["version"]
  dest_dir = out_dir or root
  dest_dir.mkdir(parents=True, exist_ok=True)
  vsix_path = dest_dir / f"{name}-{version}.vsix"
  if vsix_path.is_file():
    vsix_path.unlink()

  files = _collect_extension_files(root)
  manifest = _manifest_xml(pkg)

  with ZipFile(vsix_path, "w", compression=ZIP_DEFLATED) as zf:
    zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
    zf.writestr("_rels/.rels", _RELS)
    zf.writestr("extension.vsixmanifest", manifest)
    for arcname, src in files:
      zf.write(src, arcname)

  return vsix_path


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
    description="打包 Py2Cpp PyML VS Code 扩展为 .vsix（无需 npm）",
  )
  parser.add_argument(
    "--root",
    type=Path,
    default=Path(__file__).resolve().parent,
    help="扩展根目录（含 package.json）",
  )
  parser.add_argument(
    "--out-dir",
    type=Path,
    default=None,
    help="输出目录（默认写入扩展根）",
  )
  args = parser.parse_args(argv)

  try:
    vsix = build_vsix(root=args.root, out_dir=args.out_dir)
  except Exception as exc:  # noqa: BLE001 — CLI 边界
    print(f"[错误] {exc}", file=sys.stderr)
    return 1

  stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
  print(f"已生成: {vsix}")
  print(f"安装: VS Code / CursorType → Extensions → … → Install from VSIX…")
  print(f"打包时间: {stamp}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
