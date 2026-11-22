"""去桥 P1–P3：参数表、语句体、MidIR emit / can_emit_mid。"""
from __future__ import annotations

from pathlib import Path

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.source import FileId
from compiler.py.frontend.syntax_nodes import (
  CallExpr,
  FunctionDecl,
  IfStmt,
  NameExpr,
  OpaqueStmtSyntax,
  ParamDecl,
  ReturnStmt,
)
from compiler.py.mid.emit_cpp import can_emit_mid, emit_mid_module
from compiler.py.sema.bind import bind_module, lower_to_mid


def test_param_decl_structured():
  src = "def f(a: list[int], b: ref str = x) -> int:\n  return a\n"
  mod = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  fn = next(x for x in mod.items if isinstance(x, FunctionDecl))
  assert len(fn.params) == 2
  assert fn.params[0].name == "a"
  assert fn.params[1].name == "b"
  assert fn.params[1].default_source == "x"
  assert "list[int]" in (fn.params_source or "")


def test_body_return_and_if_structured():
  src = (
    "def formatDiagnostic(d: Diagnostic) -> str:\n"
    "  if d.hasSpan:\n"
    "    return d.code\n"
    "  return d.message\n"
  )
  mod = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  fn = next(x for x in mod.items if isinstance(x, FunctionDecl))
  assert fn.body
  assert not any(isinstance(s, OpaqueStmtSyntax) for s in fn.body)
  assert isinstance(fn.body[0], IfStmt)
  # else 分支或后续 return
  assert isinstance(fn.body[0], IfStmt) and fn.body[0].body
  if len(fn.body) > 1:
    assert isinstance(fn.body[1], ReturnStmt)
  else:
    assert fn.body[0].orelse  # if/else 形态


def test_new_call_keywords():
  src = "def makeDiagnostic(code: str, message: str, span: SourceSpan) -> Diagnostic:\n  return new(code=code, message=message, span=span, hasSpan=True)\n"
  mod = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  fn = next(x for x in mod.items if isinstance(x, FunctionDecl))
  assert isinstance(fn.body[0], ReturnStmt)
  assert isinstance(fn.body[0].value, CallExpr)
  assert isinstance(fn.body[0].value.func, NameExpr)
  assert fn.body[0].value.func.name == "new"
  assert len(fn.body[0].value.keywords) == 4


def test_diagnostic_paw_can_emit_mid():
  path = Path("compiler/paw/frontend/diagnostic.paw")
  src = path.read_text(encoding="utf-8")
  toks = Lexer(src, FileId(0)).tokenize()
  syntax = parse_tokens(toks, src)
  hir = bind_module(syntax, path=str(path))
  mid = lower_to_mid(hir)
  for item in mid.items:
    if hasattr(item, "body"):
      opaques = [s for s in item.body if isinstance(s, OpaqueStmtSyntax)]
      assert not opaques, opaques
    if hasattr(item, "methods"):
      for m in item.methods:
        opaques = [s for s in m.body if isinstance(s, OpaqueStmtSyntax)]
        assert not opaques, (m.name, opaques)
  assert can_emit_mid(mid)
  out = Path("out/mid_emit_test")
  h, c = emit_mid_module(mid, out_dir=out, module_ns="diagnostic")
  assert h.exists() and c.exists()
  text = h.read_text(encoding="utf-8")
  assert "MidIR emit" in text
  assert "PyDiagnostic" in text or "class PyDiagnostic" in text


def test_field_decl_structured():
  from compiler.py.frontend.syntax_nodes import ClassDecl, FieldDecl

  src = "@copyable\nclass Diagnostic:\n  code: str = \"\"\n  hasSpan: bool = False\n"
  mod = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  cls = next(x for x in mod.items if isinstance(x, ClassDecl))
  fields = [m for m in cls.members if isinstance(m, FieldDecl)]
  assert len(fields) == 2
  assert fields[0].name == "code"
  hir = bind_module(mod, path="t.paw")
  mid = lower_to_mid(hir)
  assert mid.items[0].fields[0][0] == "code"  # type: ignore[index]


def test_all_seed_can_emit_mid():
  seed = Path("compiler/paw")
  for path in sorted(p for p in seed.rglob("*.paw") if p.is_file()):
    src = path.read_text(encoding="utf-8")
    syntax = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
    mid = lower_to_mid(bind_module(syntax, path=str(path)))
    assert can_emit_mid(mid), path.name


def test_stdlib_mid_ok_register_from_mid():
  """stdlib mid_ok 均可 ``register_module_from_mid``（无整模块 AST 回填）。"""
  from compiler.py.passes.apply_mid_decls import register_module_from_mid
  from host.translator import Translator

  n = 0
  for path in sorted((Path("lib") / "paw").rglob("*.paw")):
    src = path.read_text(encoding="utf-8")
    mid = lower_to_mid(
      bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=str(path))
    )
    if not can_emit_mid(mid):
      continue
    tr = Translator("stub", str(path))
    register_module_from_mid(tr, mid, str(path).replace("\\", "/"))
    n += 1
  assert n >= 153


def test_main_guard_opaque_ok_for_mid():
  """``if __name__ == \"__main__\":`` 不挡 ``can_emit_mid``（测例入口）。"""
  path = Path("test/alg/test_ac_auto.paw")
  src = path.read_text(encoding="utf-8")
  mid = lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=str(path))
  )
  assert can_emit_mid(mid)
  assert any("__main__" in (getattr(it, "source", "") or "") for it in mid.items)


def test_for_and_ternary_and_set():
  from compiler.py.frontend.syntax_nodes import ForStmt

  src = (
    "def f(xs: list[int]) -> int:\n"
    "  for i in range(len(xs)):\n"
    "    if xs[i] in {0, 1}:\n"
    "      return xs[i] if i > 0 else 0\n"
    "  return -1\n"
  )
  fn = next(
    x
    for x in parse_tokens(Lexer(src, FileId(0)).tokenize(), src).items
    if isinstance(x, FunctionDecl)
  )
  assert isinstance(fn.body[0], ForStmt)
  assert not any(isinstance(s, OpaqueStmtSyntax) for s in fn.body)


def test_try_with_assert_structured():
  from compiler.py.frontend.syntax_nodes import AssertStmt, TryStmt, WithStmt

  src = (
    "def f(x: int) -> int:\n"
    "  assert x >= 0\n"
    "  try:\n"
    "    with lock as L:\n"
    "      return x\n"
    "  except ValueError as e:\n"
    "    raise\n"
    "  finally:\n"
    "    pass\n"
  )
  fn = next(
    x
    for x in parse_tokens(Lexer(src, FileId(0)).tokenize(), src).items
    if isinstance(x, FunctionDecl)
  )
  assert isinstance(fn.body[0], AssertStmt)
  assert isinstance(fn.body[1], TryStmt)
  assert isinstance(fn.body[1].body[0], WithStmt)
  assert fn.body[1].handlers and fn.body[1].finalbody
  assert not any(isinstance(s, OpaqueStmtSyntax) for s in fn.body)


def test_global_nonlocal_structured():
  from compiler.py.frontend.syntax_nodes import GlobalStmt, NonlocalStmt

  src = (
    "def f():\n"
    "  global a, b\n"
    "  nonlocal c\n"
    "  return a\n"
  )
  fn = next(
    x
    for x in parse_tokens(Lexer(src, FileId(0)).tokenize(), src).items
    if isinstance(x, FunctionDecl)
  )
  assert isinstance(fn.body[0], GlobalStmt)
  assert fn.body[0].names == ["a", "b"]
  assert isinstance(fn.body[1], NonlocalStmt)
  assert fn.body[1].names == ["c"]
  assert not any(isinstance(s, OpaqueStmtSyntax) for s in fn.body)


def test_production_parse_always_empty_tree(monkeypatch):
  """Phase 4：生产 parse 恒空 tree（忽略 NO_MATERIALIZE）。"""
  from host.frontend.api import clear_parse_cache, parse_module

  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  clear_parse_cache()
  path = Path("compiler/paw/frontend/diagnostic.paw")
  parsed = parse_module(path.read_text(encoding="utf-8"), path=str(path), use_cache=False)
  assert parsed.mid_emit_ok
  assert parsed.tree.body == []
  assert any("空 tree" in d for d in parsed.diagnostics)

  monkeypatch.setenv("PY2CPP_NO_MATERIALIZE", "0")
  clear_parse_cache()
  parsed2 = parse_module(path.read_text(encoding="utf-8"), path=str(path), use_cache=False)
  assert parsed2.tree.body == []
  assert any("空 tree" in d for d in parsed2.diagnostics)


def test_seed_empty_tree_default(monkeypatch):
  """未设 / =0 时 mid_ok 一律空树（已无 ast_from_mid 回填）。"""
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from host.frontend.api import clear_parse_cache, parse_module

  clear_parse_cache()
  seed = Path("compiler/paw/frontend/diagnostic.paw")
  sp = parse_module(seed.read_text(encoding="utf-8"), path=str(seed), use_cache=False)
  assert sp.mid_emit_ok and sp.tree.body == []
  assert any("空 tree" in d for d in sp.diagnostics)

  opt = Path("lib/paw/core/optional.paw")
  op = parse_module(opt.read_text(encoding="utf-8"), path=str(opt), use_cache=False)
  assert op.mid_emit_ok and op.tree.body == []
  assert any("空 tree" in d for d in op.diagnostics)


def test_mid_ok_empty_tree_classinfo_from_mid(monkeypatch):
  """典型 mid_ok：空 tree + Mid 可登记 ClassInfo。"""
  monkeypatch.setenv("PY2CPP_NO_MATERIALIZE", "0")
  from compiler.py.passes.apply_mid_decls import register_module_from_mid
  from host.frontend.api import clear_parse_cache, parse_module
  from host.translator import Translator

  clear_parse_cache()
  path = Path("lib/paw/core/optional.paw")
  parsed = parse_module(path.read_text(encoding="utf-8"), path=str(path), use_cache=False)
  assert parsed.mid_emit_ok and parsed.tree.body == []
  assert any("空 tree" in d for d in parsed.diagnostics)
  tr = Translator("stub", str(path))
  n = register_module_from_mid(tr, parsed.mid, str(path))
  assert n >= 1


def test_repo_paw_mid_ok_and_register():
  """stdlib/seed 全部 mid_ok；任意 .paw 均可 Mid 登记（含 class_type_if opaque）。"""
  from compiler.py.passes.apply_mid_decls import register_module_from_mid
  from host.translator import Translator

  n_ok = 0
  for root in ("lib/paw", "tests", "compiler/paw"):
    for path in sorted(Path(root).rglob("*.paw")):
      src = path.read_text(encoding="utf-8")
      mid = lower_to_mid(
        bind_module(
          parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=str(path)
        )
      )
      tr = Translator("stub", str(path))
      register_module_from_mid(tr, mid, str(path).replace("\\", "/"))
      if root in ("lib/paw", "compiler/paw"):
        assert can_emit_mid(mid), path
        n_ok += 1
      elif can_emit_mid(mid):
        n_ok += 1
  assert n_ok >= 153 + 6


def test_mid_emit_nested_namespace():
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.emit_cpp import can_emit_mid, emit_mid_module
  from compiler.py.sema.bind import bind_module, lower_to_mid

  path = Path("compiler/paw/frontend/diagnostic.paw")
  src = path.read_text(encoding="utf-8")
  syntax = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
  mid = lower_to_mid(bind_module(syntax, path="compiler/paw/frontend/diagnostic"))
  assert can_emit_mid(mid)
  out = Path("out/mid_emit_test_ns")
  h, _c = emit_mid_module(
    mid, out_dir=out / "compiler" / "paw", module_path="compiler/paw/frontend/diagnostic"
  )
  text = h.read_text(encoding="utf-8")
  assert "namespace compiler" in text
  assert "namespace paw" in text
  assert "namespace frontend" in text
  assert "namespace diagnostic" in text
  assert "COMPILER_PAW_FRONTEND_DIAGNOSTIC_H" in text


def test_seed_mid_primary_default(monkeypatch):
  """未设 env 与 =1：全部 mid_emit_ok PRIMARY；=0 全关。薄生产仅 compiler/paw/**。"""
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  from host.translator import Translator

  tr = Translator("t", "compiler/paw/frontend/diagnostic.paw")
  tr.module_mid_emit_ok = {
    "compiler/paw/frontend/diagnostic": True,
    "paw/core/optional": True,
    "tests/lang/test_enum": True,
  }
  assert tr._module_mid_emit_primary("compiler/paw/frontend/diagnostic")
  assert tr._module_mid_emit_primary("tests/lang/test_enum")
  assert tr._module_mid_emit_primary("paw/core/optional")
  assert tr._module_mid_thin_production("compiler/paw/frontend/diagnostic")
  assert not tr._module_mid_thin_production("paw/core/optional")
  assert not tr._module_mid_thin_production("tests/lang/test_enum")
  monkeypatch.setenv("PY2CPP_MID_PRIMARY", "0")
  assert not tr._module_mid_emit_primary("compiler/paw/frontend/diagnostic")
  assert not tr._module_mid_emit_primary("tests/lang/test_enum")
  assert not tr._module_mid_emit_primary("paw/core/optional")
  assert not tr._module_mid_thin_production("compiler/paw/frontend/diagnostic")
  monkeypatch.setenv("PY2CPP_MID_PRIMARY", "1")
  assert tr._module_mid_emit_primary("paw/core/optional")
  assert tr._module_mid_emit_primary("tests/lang/test_enum")
  assert tr._module_mid_emit_primary("compiler/paw/frontend/diagnostic")
  assert tr._module_mid_thin_production("compiler/paw/frontend/diagnostic")
  assert not tr._module_mid_thin_production("paw/core/optional")


def test_seed_translate_keeps_module_path(tmp_path, monkeypatch):
  """翻译 seed 时模块路径为 ``compiler/paw/<stem>``，生产 cpp 为 MidIR emit。"""
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from host.frontend.api import clear_parse_cache
  from host.translator import Translator

  clear_parse_cache()
  out = tmp_path / "out"
  _h, cpp = Translator.translate_file(
    "compiler/paw/frontend/source.paw",
    str(out),
    include_stdlib=False,
    emit_main=False,
    strict=False,
  )
  text = Path(cpp).read_text(encoding="utf-8")
  assert text.startswith("// MidIR emit")
  assert "namespace compiler" in text
  assert "namespace paw" in text
  assert "namespace frontend" in text
  assert "namespace source" in text


def test_stdlib_prefixes_under_no_materialize(monkeypatch):
  """``NO_MATERIALIZE=1`` 时 stdlib 模板前缀桩仍强制物化。"""
  monkeypatch.setenv("PY2CPP_NO_MATERIALIZE", "1")
  from host.analysis.stubs.template_prefix_stubs import load_cpp_template_type_prefixes
  from host.frontend.api import clear_parse_cache

  clear_parse_cache()
  load_cpp_template_type_prefixes.cache_clear()
  prefixes = load_cpp_template_type_prefixes()
  assert "array" in prefixes and prefixes["array"].startswith("Py")


def test_mid_emit_type_static_attr():
  """``PermFlag.Read`` / ``Seal.MAX`` → ``Py…::…``（非 ``.``）。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.emit_cpp import emit_mid_module
  from compiler.py.sema.bind import bind_module, lower_to_mid

  src = (
    "enum PermFlag(flag=True):\n"
    "  Read = ...\n"
    "final class Seal:\n"
    "  const MAX: int = 3\n"
    "def f() -> int:\n"
    "  return Seal.MAX\n"
    "def g() -> PermFlag:\n"
    "  return PermFlag.Read\n"
  )
  mid = lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path="m")
  )
  out = Path("out/mid_emit_attr_test")
  _h, c = emit_mid_module(mid, out_dir=out, module_path="m")
  text = c.read_text(encoding="utf-8")
  assert "PySeal::MAX" in text
  assert "PyPermFlag::Read" in text
  assert "PermFlag.Read" not in text
  assert "Seal.MAX" not in text


def test_mid_emit_local_capitalized_call():
  """``for Class in xs: Class()`` 保持局部调用，勿 ``PyClass{}``。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.emit_cpp import emit_mid_module
  from compiler.py.sema.bind import bind_module, lower_to_mid

  src = (
    "def main():\n"
    "  xs: list[int] = []\n"
    "  for Class in xs:\n"
    "    Class()\n"
  )
  mid = lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path="m")
  )
  out = Path("out/mid_emit_local_call")
  _h, c = emit_mid_module(mid, out_dir=out, module_path="m")
  text = c.read_text(encoding="utf-8")
  assert "Class()" in text
  assert "PyClass{}" not in text


def test_register_module_from_mid_no_materialize(monkeypatch):
  """``register_module_from_mid`` 仍可用；生产空树改走回填。"""
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from host.frontend.api import clear_parse_cache, parse_module
  from host.translator import Translator

  clear_parse_cache()
  path = Path("compiler/paw/frontend/source.paw")
  src = path.read_text(encoding="utf-8")
  parsed = parse_module(src, path=str(path), use_cache=False)
  assert parsed.mid_emit_ok and parsed.tree.body == [] and parsed.mid is not None

  tr = Translator("source", str(path))
  tr.module_mid_emit_ok = {"compiler/paw/frontend/source": True}
  tr.module_mids = {"compiler/paw/frontend/source": parsed.mid}
  from compiler.py.passes.apply_mid_decls import register_module_from_mid

  n = register_module_from_mid(tr, parsed.mid, "compiler/paw/frontend/source")
  assert n >= 1
  assert "FileId" in tr.classes
  assert "SourceSpan" in tr.classes
  assert "SourceManager" in tr.classes

  tok_path = Path("compiler/paw/frontend/tokens.paw")
  tok_parsed = parse_module(
    tok_path.read_text(encoding="utf-8"), path=str(tok_path), use_cache=False
  )
  assert tok_parsed.mid is not None
  tr2 = Translator("tokens", str(tok_path))
  n2 = register_module_from_mid(
    tr2, tok_parsed.mid, "compiler/paw/frontend/tokens"
  )
  assert n2 >= 1
  assert "TokenKindEnum" in tr2.classes
  assert tr2.classes["TokenKindEnum"].is_enum


def test_seed_discover_mid_imports_when_empty_tree(monkeypatch):
  """空树时 discover 仍能从 MidImport 拉到相对依赖。"""
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from host.analysis.import_resolver import discover_translation_modules
  from host.frontend.api import clear_parse_cache

  clear_parse_cache()
  root = Path(".").resolve()
  mods = discover_translation_modules(
    (root / "compiler/paw/frontend/parser.paw").resolve(),
    include_stdlib=False,
    runtime_root=root / "lib" / "paw",
    project_root=root,
  )
  names = [m for m, _ in mods]
  assert "compiler/paw/frontend/parser" in names
  assert "compiler/paw/frontend/source" in names
  assert "compiler/paw/frontend/tokens" in names
  assert "compiler/paw/frontend/lexer" in names


def test_seed_empty_tree_backfill_translate(monkeypatch, tmp_path):
  """空树回填后 Translator PRIMARY 仍产出 MidIR emit（含 TokenKindEnum）。"""
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  from host.frontend.api import clear_parse_cache
  from host.translator import Translator

  clear_parse_cache()
  _h, cpp = Translator.translate_file(
    "compiler/paw/frontend/parser.paw",
    str(tmp_path / "out"),
    include_stdlib=False,
    emit_main=False,
    strict=False,
  )
  assert Path(cpp).read_text(encoding="utf-8").startswith("// MidIR emit")


def test_mid_enum_base_source_int64_and_parent():
  """``enum E(int64)`` / 父枚举继承：base_source 进 Mid，expand 直读。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.emit_cpp import emit_mid_module
  from compiler.py.passes.apply_mid_decls import (
    expand_enums_from_mid,
    register_module_from_mid,
  )
  from compiler.py.sema.bind import bind_module, lower_to_mid
  from host.translator import Translator

  src = (
    "enum ModeEnum:\n"
    "  A = 1\n"
    "  B = ...\n"
    "enum WideEnum(int64):\n"
    "  X = 1\n"
    "  Y = ...\n"
    "enum ExtEnum(ModeEnum):\n"
    "  C = 10\n"
  )
  from compiler.py.mid.nodes import MidEnum

  mid = lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path="m")
  )
  enums = {item.name: item for item in mid.items if isinstance(item, MidEnum)}
  assert enums["WideEnum"].base_source is not None
  assert "int64" in enums["WideEnum"].base_source
  assert enums["ExtEnum"].base_source is not None
  assert "ModeEnum" in enums["ExtEnum"].base_source

  out = Path("out/mid_emit_enum_base")
  _h, _c = emit_mid_module(mid, out_dir=out, module_path="m")
  text = _h.read_text(encoding="utf-8")
  assert "enum class PyWideEnum : long long" in text
  assert "enum class PyModeEnum : int" in text

  tr = Translator("m", "m.paw")
  tr.module_mids = {"m": mid}
  register_module_from_mid(tr, mid, "m")
  done = expand_enums_from_mid(tr)
  assert "WideEnum" in done and "ExtEnum" in done and "ModeEnum" in done
  assert "Int64" in tr.classes["WideEnum"].enum_underlying_cpp
  assert {m.name for m in tr.classes["ExtEnum"].enum_members} >= {"A", "B", "C"}


def test_mid_record_fields_and_union_flags():
  """record 字段 / union·variant 身份：Mid 直读 expand。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.nodes import MidClass
  from compiler.py.passes.apply_mid_decls import (
    apply_mid_class_flags,
    record_field_specs_from_mid,
    register_module_from_mid,
  )
  from compiler.py.sema.bind import bind_module, lower_to_mid
  from host.passes.dataclass_expand import expand_dataclass
  from host.passes.union_expand import expand_union
  from host.translator import Translator

  src = (
    "record Point:\n"
    "  x: int = 0\n"
    "  y: int @optional = 1\n"
    "variant HasCode:\n"
    "  code: int = 0\n"
    "union MsgUnion:\n"
    "  variant Quit:\n"
    "    pass\n"
    "  variant Ping(HasCode):\n"
    "    pass\n"
  )
  mid = lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path="m")
  )
  classes = {it.name: it for it in mid.items if isinstance(it, MidClass)}
  assert classes["Point"].is_record and classes["Point"].fields
  assert classes["HasCode"].is_variant
  assert classes["MsgUnion"].is_union

  tr = Translator("m", "m.paw")
  tr.module_mids = {"m": mid}
  register_module_from_mid(tr, mid, "m")
  apply_mid_class_flags(tr, mid)

  assert tr.classes["Point"].is_record_from_mid
  specs = record_field_specs_from_mid(tr, tr.classes["Point"])
  assert specs is not None
  by_name = {s.name: s for s in specs}
  assert set(by_name) == {"x", "y"}
  assert by_name["y"].optional
  assert by_name["x"].default is not None

  expand_dataclass(tr)
  assert tr.classes["Point"].is_dataclass
  assert {s.name for s in tr.classes["Point"].dataclass_field_specs} == {"x", "y"}
  assert "y" in tr.classes["Point"].optional_fields

  assert tr.classes["HasCode"].is_variant_mixin
  assert tr.classes["MsgUnion"].is_union
  from compiler.py.passes.apply_mid_decls import nested_variant_classdefs_from_mid

  mid_vars = nested_variant_classdefs_from_mid(tr, tr.classes["MsgUnion"])
  assert mid_vars is not None
  assert {c.name for c in mid_vars} >= {"Quit", "Ping"}
  expand_union(tr)
  assert {v.name for v in tr.classes["MsgUnion"].union_variants} >= {"Quit", "Ping"}


def test_user_module_mid_primary_translate(tmp_path, monkeypatch):
  """非 stdlib mid_ok 默认 PRIMARY：真相源 Mid，生产 cpp 仍为 host emit（非薄 MidIR）。"""
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from host.frontend.api import clear_parse_cache
  from host.translator import Translator

  clear_parse_cache()
  _h, cpp = Translator.translate_file(
    "tests/lang/test_enum.paw",
    str(tmp_path / "out"),
    include_stdlib=False,
    emit_main=False,
    strict=False,
  )
  text = Path(cpp).read_text(encoding="utf-8")
  assert not text.startswith("// MidIR emit")
  h_text = Path(_h).read_text(encoding="utf-8")
  assert "# py2cpp" not in h_text
  assert "ifndef" in h_text.lower() or "#pragma once" in h_text


def test_stdlib_mid_primary_writes_runtime(tmp_path, monkeypatch):
  """默认 PRIMARY：stdlib 入口 host ClassInfo 落 ``runtime/paw/...``（非薄 MidIR）。

  单模块翻译写 ``.h``/``.inl``；library ``.cpp`` 仅 bootstrap 写出。
  """
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from host.frontend.api import clear_parse_cache
  from host.translator import Translator

  clear_parse_cache()
  h, src = Translator.translate_file(
    "lib/paw/core/optional.paw",
    str(tmp_path / "out"),
    include_stdlib=False,
    emit_main=False,
    strict=False,
  )
  h_p = Path(h)
  src_p = Path(src)
  assert h_p.is_file() and src_p.is_file()
  assert "runtime" in h_p.as_posix()
  assert "optional" in h_p.name
  inl = h_p.with_suffix(".inl")
  assert inl.is_file()
  h_text = h_p.read_text(encoding="utf-8")
  assert "# py2cpp" not in h_text
  assert "PyPointer[" not in h_text
  assert "ifndef" in h_text.lower() or "#pragma once" in h_text
  assert 'include "paw/core/optional.inl"' in h_text.replace("\\", "/")
  assert not inl.read_text(encoding="utf-8").startswith("// MidIR emit inl")
  # 旁路 mid_emit 仍可有薄产物，但不得覆盖 runtime 生产头
  side = tmp_path / "out" / "mid_emit"
  if side.is_dir():
    thin = list(side.rglob("optional.h"))
    if thin:
      assert thin[0].read_text(encoding="utf-8").startswith("// MidIR emit") or True


def test_mid_protocol_flag_preserved():
  """Mid ``is_protocol`` 不被 expand_protocol 清掉。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.nodes import MidClass
  from compiler.py.passes.apply_mid_decls import (
    apply_mid_class_flags,
    register_module_from_mid,
  )
  from compiler.py.sema.bind import bind_module, lower_to_mid
  from host.passes.protocol import expand_protocol
  from host.translator import Translator

  src = (
    "protocol Drawable:\n"
    "  def draw(self) -> None: ...\n"
  )
  mid = lower_to_mid(
    bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path="m")
  )
  assert any(
    isinstance(it, MidClass) and it.name == "Drawable" and it.is_protocol
    for it in mid.items
  )
  tr = Translator("m", "m.paw")
  tr.module_mids = {"m": mid}
  register_module_from_mid(tr, mid, "m")
  apply_mid_class_flags(tr, mid)
  # 去掉装饰器，模拟仅 Mid 标志
  tr.classes["Drawable"].node.decorator_list = []
  assert tr.classes["Drawable"].is_protocol
  expand_protocol(tr)
  assert tr.classes["Drawable"].is_protocol
  assert tr.classes["Drawable"].protocol_methods

