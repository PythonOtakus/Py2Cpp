#!/usr/bin/env python3
"""将 Py2Cpp Lexer 扩展打包为 .vsix（纯 Python，无需 npm）。"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import xml.sax.saxutils as xml_escape
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

_CONTENT_TYPES = {
    "rels": "application/vnd.openxmlformats-package.relationships+xml",
    "vsixmanifest": "text/xml",
    "json": "application/json",
    "js": "application/javascript",
    "mjs": "application/javascript",
    "cjs": "application/javascript",
    "html": "text/html",
    "css": "text/css",
    "md": "text/markdown",
    "txt": "text/plain",
    "wgsl": "text/plain",
    "wasm": "application/wasm",
    "bin": "application/octet-stream",
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "woff": "font/woff",
    "woff2": "font/woff2",
}

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
    return [
        line.strip().replace("\\", "/")
        for line in ignore_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _is_ignored(rel_posix: str, patterns: list[str]) -> bool:
    rel = rel_posix.replace("\\", "/").removeprefix("./")
    for pattern in patterns:
        pattern = pattern.removeprefix("./")
        if pattern.endswith("/"):
            pattern += "**"
        # A leading **/ also matches a file or directory at the package root.
        if pattern.startswith("**/") and _is_ignored(rel, [pattern[3:]]):
            return True
        if pattern.endswith("/**") and "*" not in pattern[:-3]:
            prefix = pattern[:-3]
            if rel == prefix or rel.startswith(prefix + "/"):
                return True
        elif "/" not in pattern:
            if fnmatch.fnmatchcase(PurePosixPath(rel).name, pattern):
                return True
        else:
            expression = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
            if re.fullmatch(expression, rel):
                return True
    return False


def _collect_extension_files(root: Path) -> list[tuple[str, Path]]:
    patterns = _load_vscodeignore(root)
    files: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".vsix" or _is_ignored(rel, patterns):
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"文件指向扩展目录之外: {rel}")
        files.append((f"extension/{rel}", path))
    return files


def _validate_package(pkg: dict, files: list[tuple[str, Path]]) -> None:
    name = pkg.get("name", "")
    version = pkg.get("version", "")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise ValueError("package.json 的 name 必须是小写扩展名称")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9][A-Za-z0-9.+-]*", version):
        raise ValueError("package.json 的 version 无效")
    if not isinstance(pkg.get("publisher"), str) or not pkg["publisher"].strip():
        raise ValueError("package.json 缺少 publisher")
    if not pkg.get("engines", {}).get("vscode"):
        raise ValueError("package.json 缺少 engines.vscode")
    if not isinstance(pkg.get("main"), str) or not pkg["main"]:
        raise ValueError("package.json 缺少 main")

    included = {arcname for arcname, _ in files}

    def require_file(value: str, field: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"package.json 的 {field} 必须是相对文件路径")
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or ":" in value:
            raise ValueError(f"package.json 的 {field} 必须位于扩展目录内: {value}")
        if f"extension/{path.as_posix()}" not in included:
            raise FileNotFoundError(f"清单引用文件不存在或已被排除 ({field}): {value}")

    require_file("package.json", "package.json")
    for field in ("main", "browser", "icon"):
        if field in pkg:
            require_file(pkg[field], field)
    contributes = pkg.get("contributes", {})
    for language in contributes.get("languages", []):
        if "configuration" in language:
            require_file(language["configuration"], "contributes.languages.configuration")
    for collection in ("grammars", "snippets", "themes", "iconThemes", "productIconThemes"):
        for entry in contributes.get(collection, []):
            if "path" in entry:
                require_file(entry["path"], f"contributes.{collection}.path")


def _content_types_xml(files: list[tuple[str, Path]]) -> bytes:
    root = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    types = dict(_CONTENT_TYPES)
    for arcname, _ in files:
        suffix = PurePosixPath(arcname).suffix.lstrip(".")
        if suffix:
            types.setdefault(suffix, "application/octet-stream")
        else:
            ET.SubElement(root, "Override", PartName=f"/{arcname}", ContentType="text/plain")
    for extension, content_type in sorted(types.items()):
        ET.SubElement(root, "Default", Extension=extension, ContentType=content_type)
    ET.SubElement(root, "Override", PartName="/extension.vsixmanifest", ContentType="text/xml")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _manifest_xml(pkg: dict) -> bytes:
    quote = xml_escape.quoteattr
    display = xml_escape.escape(str(pkg.get("displayName", pkg["name"])))
    description = xml_escape.escape(str(pkg.get("description", "")))
    license_text = str(pkg.get("license", "")).strip()
    license_xml = f"\n    <License>{xml_escape.escape(license_text)}</License>" if license_text else ""
    engine = str(pkg["engines"]["vscode"])
    return f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0"
  xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"
  xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id={quote(pkg['name'])} Version={quote(pkg['version'])} Publisher={quote(pkg['publisher'])} />
    <DisplayName>{display}</DisplayName>
    <Description xml:space="preserve">{description}</Description>{license_xml}
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value={quote(engine)} />
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
  </Assets>
</PackageManifest>
""".encode("utf-8")


def build_vsix(*, root: Path, out_dir: Path | None = None) -> Path:
    root = root.resolve()
    pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    files = _collect_extension_files(root)
    _validate_package(pkg, files)
    manifest = _manifest_xml(pkg)
    content_types = _content_types_xml(files)
    dest_dir = out_dir.resolve() if out_dir else root
    dest_dir.mkdir(parents=True, exist_ok=True)
    vsix_path = dest_dir / f"{pkg['name']}-{pkg['version']}.vsix"
    # Validate before touching an existing package, then publish the complete ZIP atomically.
    with tempfile.NamedTemporaryFile(prefix=".packaging-", suffix=".tmp", dir=dest_dir, delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        with ZipFile(temp_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", _RELS)
            archive.writestr("extension.vsixmanifest", manifest)
            for arcname, source in files:
                archive.write(source, arcname)
        temp_path.replace(vsix_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return vsix_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="打包 Py2Cpp Lexer VSIX（无需 npm）")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent, help="扩展根目录")
    parser.add_argument("--out-dir", type=Path, default=None, help="输出目录（默认扩展根目录）")
    args = parser.parse_args(argv)
    try:
        vsix = build_vsix(root=args.root, out_dir=args.out_dir)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    print(f"已生成: {vsix}")
    print("安装: VS Code / Cursor → Extensions → … → Install from VSIX…")
    print(f"打包时间: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
