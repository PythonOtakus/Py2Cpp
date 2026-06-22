"""为 clangd / IDE 生成 compile_commands.json 与根目录 compile_flags.txt。

``#include "py2cpp/..."`` 的 include 根与 ``src/compile.py`` 的 ``discover_include_dirs`` 一致。
bootstrap 或翻译后若 IDE 仍报头文件找不到，可运行::

    python scripts/gen_compile_commands.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.codegen.template_scope import (  # noqa: E402
  format_macro_header,
  iter_templates_needing_macro_header,
  macro_header_path,
  macro_header_rel_for_template,
  template_uses_begin_scope,
)
from src.compile import discover_include_dirs  # noqa: E402
from src.constant.template_module_bindings import module_rel_from_template_rel  # noqa: E402

GENERATED_RUNTIME = ROOT / "generated" / "runtime"
TEMPLATES_ROOT = ROOT / "templates"
MACRO_ROOT = TEMPLATES_ROOT / "~macro"


def _discover_include_dirs(source: Path) -> list[Path]:
    """``discover_include_dirs`` + 仓库根 ``generated/runtime``（``templates/`` 路径扫不到）。"""
    dirs = list(discover_include_dirs(source))
    if GENERATED_RUNTIME.is_dir():
        gr = GENERATED_RUNTIME.resolve()
        if all(d.resolve() != gr for d in dirs):
            dirs.append(gr)
    return dirs


def _posix(path: Path) -> str:
    return path.resolve().as_posix()


def write_macro_headers() -> list[Path]:
    """为含 ``PY2CPP_*`` 的模板生成 ``templates/~macro/<rel>.h``（桩宏 + 可选 scope）。"""
    MACRO_ROOT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    expected_rels: set[str] = set()
    for template_rel in iter_templates_needing_macro_header(templates_root=TEMPLATES_ROOT):
        path = TEMPLATES_ROOT / template_rel
        text = path.read_text(encoding="utf-8")
        has_begin_scope = template_uses_begin_scope(text)
        module_rel = module_rel_from_template_rel(template_rel)
        if has_begin_scope and not module_rel:
            print(
                f"跳过宏头（BEGIN_SCOPE 但无法推断模块）: templates/{template_rel}",
                file=sys.stderr,
            )
            continue
        macro_rel = macro_header_rel_for_template(template_rel)
        expected_rels.add(macro_rel)
        out = macro_header_path(template_rel, templates_root=TEMPLATES_ROOT)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            format_macro_header(
                template_rel,
                module_rel,
                has_begin_scope=has_begin_scope,
            ),
            encoding="utf-8",
        )
        written.append(out)
    if MACRO_ROOT.is_dir():
        for path in sorted(MACRO_ROOT.rglob("*.h")):
            rel = path.relative_to(TEMPLATES_ROOT).as_posix()
            if rel not in expected_rels:
                path.unlink()
                parent = path.parent
                while parent != MACRO_ROOT and parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
    return written


def _compile_command(source: Path) -> str:
    parts = ["clang++", "-std=c++14", "-D_WIN32", "-Wno-everything"]
    if source.is_relative_to(TEMPLATES_ROOT):
        parts.extend(["-I", _posix(TEMPLATES_ROOT)])
        if source.suffix in (".inl", ".h"):
            template_rel = source.relative_to(TEMPLATES_ROOT).as_posix()
            macro = macro_header_path(template_rel, templates_root=TEMPLATES_ROOT)
            if macro.is_file():
                parts.extend(["-include", _posix(macro)])
    for inc in _discover_include_dirs(source):
        parts.extend(["-I", _posix(inc)])
    rel = source.relative_to(ROOT).as_posix()
    if source.suffix == ".h":
        parts.extend(["-x", "c++-header", "-fsyntax-only", rel])
    elif source.suffix == ".inl":
        parts.extend(["-x", "c++", "-fsyntax-only", rel])
    else:
        parts.extend(["-c", rel])
    return " ".join(parts)


def _collect_sources() -> list[Path]:
    sources: list[Path] = []
    runtime = ROOT / "generated" / "runtime"
    if runtime.is_dir():
        sources.extend(sorted(runtime.rglob("*.h")))
        sources.extend(sorted(runtime.rglob("*.inl")))
    if TEMPLATES_ROOT.is_dir():
        sources.extend(sorted(TEMPLATES_ROOT.rglob("*.inl")))
        for path in sorted(TEMPLATES_ROOT.rglob("*.h")):
            if path.relative_to(TEMPLATES_ROOT).as_posix().startswith("~macro/"):
                continue
            sources.append(path)
    test_root = ROOT / "generated" / "test"
    if test_root.is_dir():
        sources.extend(sorted(test_root.rglob("*.cpp")))
    examples = ROOT / "generated" / "examples"
    if examples.is_dir():
        sources.extend(sorted(examples.rglob("*.cpp")))
    return sources


def write_compile_flags() -> None:
    # 相对路径便于提交；clangd 自仓库根解析
    flags = [
        "-std=c++14",
        "-I",
        "generated/runtime",
        "-I",
        "templates",
        "-D_WIN32",
    ]
    (ROOT / "compile_flags.txt").write_text("\n".join(flags) + "\n", encoding="utf-8")


def main() -> int:
    runtime_dir = ROOT / "generated" / "runtime"
    if not runtime_dir.is_dir():
        print("generated/runtime 不存在，请先 bootstrap：", file=sys.stderr)
        print("  python main.py py2cpp\\__init__.py -o generated --no-main", file=sys.stderr)
        return 1

    macro_written = write_macro_headers()
    sources = _collect_sources()
    directory = _posix(ROOT)
    entries = [
        {
            "directory": directory,
            "file": _posix(path),
            "command": _compile_command(path),
        }
        for path in sources
    ]
    out = ROOT / "compile_commands.json"
    out.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    write_compile_flags()
    print(f"wrote {len(macro_written)} macro header(s) under templates/~macro/")
    print(f"wrote {out} ({len(entries)} entries)")
    print(f"wrote {ROOT / 'compile_flags.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
