"""S47 v2 存量改名：Protocol→Type、boxing *Unsafe、KindEnum 简化、CPython 异常回退、ThreadLocal→thread_local。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 长名优先，避免前缀误伤
RENAMES: list[tuple[str, str]] = [
  # CPython 异常回退
  ("BaseExceptionGroupError", "BaseExceptionGroup"),
  ("ExceptionGroupError", "ExceptionGroup"),
  ("StopIterationError", "StopIteration"),
  # KindEnum → Enum
  ("FlowPinKindEnum", "FlowPinEnum"),
  ("FlowNodeKindEnum", "FlowNodeEnum"),
  ("DrawCmdKindEnum", "DrawCmdEnum"),
  # boxing
  ("FrozenSetEntry", "FrozenSetEntryUnsafe"),
  ("DictEntry", "DictEntryUnsafe"),
  ("DequeNode", "DequeNodeUnsafe"),
  ("_ChunkNode", "_ChunkNodeUnsafe"),
  # ThreadLocal 标记（类名 / 装饰器名）
  ("ThreadLocal", "thread_local"),
]

# @protocol 类：*Protocol → *Type（由扫描补全）
PROTOCOL_NAMES = [
  "NavigatableProtocol",
  "GeneratorProtocol",
  "CoroutineProtocol",
  "AsyncGeneratorProtocol",
  "AwaitableProtocol",
  "AsyncIterableProtocol",
  "AsyncIteratorProtocol",
  "ContextManagerProtocol",
  "AsyncContextManagerProtocol",
  "StringFormatProtocol",
  "TextWriterProtocol",
  "TextReaderProtocol",
  "TextIOProtocol",
  "NumberProtocol",
  "ComplexProtocol",
  "RealProtocol",
  "RationalProtocol",
  "IntegralProtocol",
  "ArithmeticProtocol",
  "EncoderProtocol",
  "DecoderProtocol",
  "DocumentProtocol",
  "CursorProtocol",
  "DialectProtocol",
  "ConnectionProtocol",
  "SizedProtocol",
  "ContainerProtocol",
  "CollectionProtocol",
  "IteratorElementProtocol",
  "IterableIteratorProtocol",
  "IterableProtocol",
  "IteratorProtocol",
  "ReversibleProtocol",
  "EquatableProtocol",
  "ComparableProtocol",
  "HashableProtocol",
  "DictKeyProtocol",
  "AppendableProtocol",
  "MutableMappingProtocol",
  # 测试/文档用
  "IParsableProtocol",
]


def _protocol_to_type(name: str) -> str:
  if name.endswith("Protocol"):
    return name[: -len("Protocol")] + "Type"
  return name


for p in PROTOCOL_NAMES:
  RENAMES.append((p, _protocol_to_type(p)))

# 去重并按旧名长度降序
_seen: set[str] = set()
_ordered: list[tuple[str, str]] = []
for old, new in sorted(RENAMES, key=lambda x: -len(x[0])):
  if old in _seen or old == new:
    continue
  _seen.add(old)
  _ordered.append((old, new))
RENAMES = _ordered

SKIP_DIRS = {
  ".git",
  ".cache",
  "generated",
  "__pycache__",
  ".venv",
  "node_modules",
  "third_party",
}

EXT = {".py", ".md", ".inl", ".h", ".cpp", ".pyi", ".txt", ".bat"}


def replace_ident(text: str, old: str, new: str) -> str:
  return re.sub(rf"\b{re.escape(old)}\b", new, text)


def should_skip(path: Path) -> bool:
  parts = set(path.parts)
  if parts & SKIP_DIRS:
    return True
  if path.name.startswith("_rename_") and path.parent.name == "tools":
    return path.resolve() == Path(__file__).resolve()
  return False


def main() -> None:
  files: list[Path] = []
  for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in EXT:
      continue
    if should_skip(p):
      continue
    files.append(p)

  changed = 0
  for path in files:
    try:
      raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
      continue
    text = raw
    for old, new in RENAMES:
      text = replace_ident(text, old, new)
    if text != raw:
      path.write_text(text, encoding="utf-8", newline="\n")
      changed += 1
      print(path.relative_to(ROOT))
  print(f"updated {changed} files, {len(RENAMES)} renames")


if __name__ == "__main__":
  main()
