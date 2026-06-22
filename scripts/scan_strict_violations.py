"""Bootstrap runtime 并收集 strict 违规（开发用）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.translation_error import TranslationError
from src.translator import Translator


def main() -> int:
  entry = ROOT / "py2cpp" / "__init__.py"
  out = ROOT / "generated"
  try:
    Translator.translate_file(
      str(entry),
      output_dir=str(out),
      include_stdlib=True,
      emit_main=False,
      strict=True,
    )
  except TranslationError as exc:
    print(exc)
    return 1
  print("strict: OK (no violations)")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
