#!/usr/bin/env python3
"""py2cpp 命令行入口：翻译 Python 源文件并可选择编译为可执行文件。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src import GENERATED_DIR, Translator
from src.compile import compile_cpp
from src.translation_error import format_translation_failure


def _build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description="将 Python 翻译为 C++11（标准库由 Python 实现并一并翻译，无手写 C++ 运行时）",
  )
  parser.add_argument("input", help="输入 .py 文件路径")
  parser.add_argument(
    "-o", "--output",
    help=(
      f"输出根目录（默认仓库 {GENERATED_DIR}/：用户脚本 → <根>/<源路径>/，"
      f"标准库 → <根>/runtime/）"
    ),
    default=None,
  )
  parser.add_argument("--no-stdlib", action="store_true", help="不嵌入 py2cpp 标准库模块")
  parser.add_argument(
    "--no-main",
    action="store_true",
    help="不生成 main；若源文件已有 def main() 则只翻译该函数",
  )
  parser.add_argument(
    "--debug",
    action="store_true",
    help="为每次函数调用生成 stderr 跟踪日志（fprintf），便于排查运行时问题；同时将 __debug__ 设为 true",
  )
  compile_group = parser.add_argument_group("编译")
  compile_group.add_argument(
    "-c", "--compile",
    action="store_true",
    help="翻译完成后编译生成的 .cpp",
  )
  compile_group.add_argument(
    "--compiler",
    choices=("auto", "g++", "clang++", "cl", "msvc"),
    default="auto",
    help="C++ 编译器（auto：优先 build.bat，再 g++/clang++/cl）",
  )
  compile_group.add_argument(
    "--exe",
    metavar="PATH",
    help="可执行文件输出路径（默认与 .cpp 主文件名相同）",
  )
  compile_group.add_argument(
    "--obj-only",
    action="store_true",
    help="仅生成目标文件 .obj / .o，不链接",
  )
  parser.add_argument(
    "--strict",
    action=argparse.BooleanOptionalAction,
    default=True,
    help="翻译期强检查编码规范（默认开启；--no-strict 关闭）",
  )
  parser.add_argument(
    "--openmp",
    action=argparse.BooleanOptionalAction,
    default=True,
    help="prange 发射 OpenMP pragma（--no-openmp 译期降级为 range）",
  )
  return parser


def main() -> int:
  parser = _build_parser()
  args = parser.parse_args()
  input_path = Path(args.input).resolve()
  if not input_path.is_file():
    print(f"错误: 找不到文件 {input_path}", file=sys.stderr)
    return 1

  try:
    header_path, source_path = Translator.translate_file(
      str(input_path),
      output_dir=args.output,
      include_stdlib=not args.no_stdlib,
      emit_main=not args.no_main,
      debug=args.debug,
      strict=args.strict,
      openmp_enabled=args.openmp,
    )
  except Exception as e:
    print(format_translation_failure(e, entry_path=input_path), file=sys.stderr)
    return 1

  print(f"已生成 {header_path}")
  print(f"已生成 {source_path}")

  if args.compile:
    result = compile_cpp(
      source_path,
      exe=Path(args.exe) if args.exe else None,
      compiler=args.compiler,
      obj_only=args.obj_only,
      openmp=False if not args.openmp else None,
    )
    if not result.ok:
      if result.stderr:
        print(result.stderr, file=sys.stderr)
      elif result.stdout:
        print(result.stdout, file=sys.stderr)
      else:
        print("编译失败", file=sys.stderr)
      return 1
    if result.artifact:
      print(f"编译成功 ({result.compiler}): {result.artifact}")
    else:
      print(f"编译成功 ({result.compiler})")

  return 0


if __name__ == "__main__":
  sys.exit(main())
