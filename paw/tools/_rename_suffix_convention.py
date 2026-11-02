"""Batch-rename class names to naming-suffix convention (S47).

Ambiguous / short names use path scopes. ``IteratorType`` suffix list in
``iterator_patterns.py`` is left alone (host-bound class suffixes ≠ protocol).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Longer keys first when applying.
RENAMES: list[tuple[str, str]] = [
    # protocols
    ("AsyncContextManagerType", "AsyncContextManagerType"),
    ("AsyncGeneratorType", "AsyncGeneratorType"),
    ("AsyncIteratorType", "AsyncIteratorType"),
    ("AsyncIterableType", "AsyncIterableType"),
    ("IterableIteratorType", "IterableIteratorType"),
    ("IteratorElementType", "IteratorElementType"),
    ("MutableMappingType", "MutableMappingType"),
    ("ContextManagerType", "ContextManagerType"),
    ("StringFormatType", "StringFormatType"),
    ("NavigatableType", "NavigatableType"),
    ("ArithmeticType", "ArithmeticType"),
    ("AppendableType", "AppendableType"),
    ("ComparableType", "ComparableType"),
    ("EquatableType", "EquatableType"),
    ("ReversibleType", "ReversibleType"),
    ("CollectionType", "CollectionType"),
    ("ContainerType", "ContainerType"),
    ("TextWriterType", "TextWriterType"),
    ("TextReaderType", "TextReaderType"),
    ("TextIOType", "TextIOType"),
    ("HashableType", "HashableType"),
    ("GeneratorType", "GeneratorType"),
    ("CoroutineType", "CoroutineType"),
    ("AwaitableType", "AwaitableType"),
    ("ConnectionType", "ConnectionType"),
    ("DialectType", "DialectType"),
    ("DocumentType", "DocumentType"),
    ("IteratorType", "IteratorType"),
    ("IterableType", "IterableType"),
    ("RationalType", "RationalType"),
    ("IntegralType", "IntegralType"),
    ("ComplexType", "ComplexType"),
    ("EncoderType", "EncoderType"),
    ("DecoderType", "DecoderType"),
    ("DictKeyType", "DictKeyType"),
    ("NumberType", "NumberType"),
    ("CursorType", "CursorType"),
    ("SizedType", "SizedType"),
    ("RealType", "RealType"),
    ("IParsableType", "IParsableType"),
    ("INamedProtocol", "INamedProtocol"),
    # enums (stdlib-wide)
    ("GridConnectivityEnum", "GridConnectivityEnum"),
    ("RoundingModeEnum", "RoundingModeEnum"),
    ("FlowPinEnum", "FlowPinEnum"),
    ("FlowNodeEnum", "FlowNodeEnum"),
    ("DrawCmdEnum", "DrawCmdEnum"),
    ("FlowMenuIdEnum", "FlowMenuIdEnum"),
    ("StatusCodeEnum", "StatusCodeEnum"),
    ("AnsiColorEnum", "AnsiColorEnum"),
    ("LogLevelEnum", "LogLevelEnum"),
    ("AggModeEnum", "AggModeEnum"),
    ("PetKindTypeEnum", "PetKindTypeEnum"),
    # unions (stdlib / shared)
    ("JsonDocStepUnion", "JsonDocStepUnion"),
    ("_PymlValueUnion", "_PymlValueUnion"),
    ("ErrorTypeUnion", "ErrorTypeUnion"),
    ("ExcTypeUnion", "ExcTypeUnion"),
    # exceptions
    ("BaseExceptionGroup", "BaseExceptionGroup"),
    ("ExceptionGroup", "ExceptionGroup"),
    ("BrokenThreadPoolError", "BrokenThreadPoolError"),
    ("InvalidOperationError", "InvalidOperationError"),
    ("StopIteration", "StopIteration"),
    ("ShutDownError", "ShutDownError"),
    # mixin
    ("ArgumentParser", "ArgumentParserMixin"),
]

# Short / test-local / ambiguous → only these relative prefixes.
SCOPED: dict[str, tuple[str, ...]] = {
    "Empty": ("py2cpp/concur/", "templates/concur/", "test/concur/", "docs/concur-thread.md"),
    "Full": ("py2cpp/concur/", "templates/concur/", "test/concur/", "docs/concur-thread.md"),
    "Event": ("test/perf/",),
    "Request": ("test/serde/",),
    "ArgumentParser": (
        "py2cpp/console/",
        "src/passes/argument_parser.py",
        "src/tests/test_argument_parser.py",
        "test/console/",
        "docs/console.md",
    ),
    "Mode": ("test/lang/test_enum.py", "docs/参考手册.md"),
    "Wide": ("test/lang/test_enum.py", "docs/参考手册.md"),
    "Ext": ("test/lang/test_enum.py", "docs/参考手册.md"),
    "Perm": ("test/lang/test_enum.py", "docs/参考手册.md"),
    "PermExt": ("test/lang/test_enum.py", "docs/参考手册.md"),
    "Message": ("test/lang/test_union.py", "docs/编码规范.md", "docs/参考手册.md"),
    "Signal": ("test/lang/test_union.py", "docs/编码规范.md", "docs/参考手册.md"),
    "Core": ("test/lang/test_union.py", "docs/编码规范.md", "docs/参考手册.md"),
    "Extended": ("test/lang/test_union.py", "docs/编码规范.md", "docs/参考手册.md"),
    "CoreT": ("test/lang/test_union.py", "docs/编码规范.md", "docs/参考手册.md"),
    "BoxT": ("test/lang/test_union.py", "docs/编码规范.md", "docs/参考手册.md"),
    "TickPacket": ("test/serde/",),
}

# (old_name, relative path) — do not replace this old name in that file.
EXCLUDE: set[tuple[str, str]] = {
    ("IteratorType", "src/constant/iterator_patterns.py"),
}

SKIP_DIRS = {
    ".git",
    "generated",
    ".cache",
    "node_modules",
    "__pycache__",
    ".venv",
    "third_party",
}

TEXT_SUFFIXES = {".py", ".md", ".inl", ".h", ".hpp", ".cpp", ".txt", ".json"}


def _should_skip(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return True
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False


def _in_scope(old: str, rel: str) -> bool:
    prefixes = SCOPED.get(old)
    if not prefixes:
        return True
    return any(rel == p or rel.startswith(p) for p in prefixes)


def _replace_ident(text: str, old: str, new: str) -> str:
    if old == "ArgumentParser":

        def repl(m: re.Match[str]) -> str:
            start = m.start()
            prefix = text[max(0, start - 9) : start]
            if prefix.endswith("argparse."):
                return m.group(0)
            return new

        return re.sub(rf"\b{re.escape(old)}\b", repl, text)
    # Avoid "Immediate Mode GUI" / "Core Schema" false positives for scoped docs:
    if old == "Mode":
        return re.sub(rf"\b{re.escape(old)}\b(?!\s+GUI)", new, text)
    if old == "Core":
        return re.sub(rf"\b{re.escape(old)}\b(?!\s+Schema)", new, text)
    return re.sub(rf"\b{re.escape(old)}\b", new, text)


def main() -> None:
    extra = [
        ("PermExt", "PermExtFlag"),
        ("Perm", "PermFlag"),
        ("Mode", "ModeEnum"),
        ("Wide", "WideEnum"),
        ("Ext", "ExtEnum"),
        ("Message", "MessageUnion"),
        ("Signal", "SignalUnion"),
        ("Extended", "ExtendedUnion"),
        ("CoreT", "CoreTUnion"),
        ("BoxT", "BoxTUnion"),
        ("Core", "CoreUnion"),
        ("Event", "EventUnion"),
        ("Request", "RequestUnion"),
        ("TickPacket", "TickPacketUnion"),
        ("Empty", "EmptyError"),
        ("Full", "FullError"),
    ]
    ordered = sorted(RENAMES + extra, key=lambda kv: len(kv[0]), reverse=True)
    # de-dup keeping first
    seen: set[str] = set()
    uniq: list[tuple[str, str]] = []
    for old, new in ordered:
        if old in seen:
            continue
        seen.add(old)
        uniq.append((old, new))

    changed_files = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or _should_skip(path):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        orig = text
        for old, new in uniq:
            if (old, rel) in EXCLUDE:
                continue
            if not _in_scope(old, rel):
                continue
            text = _replace_ident(text, old, new)
        if text != orig:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed_files += 1
            print(rel)
    print(f"updated {changed_files} files")


if __name__ == "__main__":
    main()
