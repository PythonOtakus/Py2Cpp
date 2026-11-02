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
  out = Path("generated/mid_emit_test")
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


def test_stdlib_ast_from_mid_zero_fallback():
  """stdlib mid_ok 全部 ``ast_from_mid`` 成功（无 span 回退）。"""
  from compiler.py.mid.ast_from_mid import ast_module_from_mid

  n = 0
  for path in sorted(Path("py2cpp").rglob("*.paw")):
    src = path.read_text(encoding="utf-8")
    mid = lower_to_mid(
      bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=str(path))
    )
    if not can_emit_mid(mid):
      continue
    ast_module_from_mid(mid, filename=str(path))
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


def test_no_materialize_skips_ast(monkeypatch):
  from src.frontend.api import clear_parse_cache, parse_module

  monkeypatch.setenv("PY2CPP_NO_MATERIALIZE", "1")
  clear_parse_cache()
  path = Path("compiler/paw/frontend/diagnostic.paw")
  parsed = parse_module(path.read_text(encoding="utf-8"), path=str(path), use_cache=False)
  assert parsed.mid_emit_ok
  assert parsed.tree.body == []
  assert any("跳过 materialize_ast" in d for d in parsed.diagnostics)


def test_seed_no_materialize_default(monkeypatch):
  """未设 env 时 mid_ok 一律空树；=0 时走 ast_from_mid。"""
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from src.frontend.api import clear_parse_cache, parse_module

  clear_parse_cache()
  seed = Path("compiler/paw/frontend/diagnostic.paw")
  sp = parse_module(seed.read_text(encoding="utf-8"), path=str(seed), use_cache=False)
  assert sp.mid_emit_ok and sp.tree.body == []
  assert any("跳过 materialize_ast" in d for d in sp.diagnostics)

  opt = Path("py2cpp/core/optional.paw")
  op = parse_module(opt.read_text(encoding="utf-8"), path=str(opt), use_cache=False)
  assert op.mid_emit_ok and op.tree.body == []
  assert any("跳过 materialize_ast" in d for d in op.diagnostics)

  monkeypatch.setenv("PY2CPP_NO_MATERIALIZE", "0")
  clear_parse_cache()
  sp2 = parse_module(seed.read_text(encoding="utf-8"), path=str(seed), use_cache=False)
  assert len(sp2.tree.body) > 0
  assert any("ast_from_mid" in d for d in sp2.diagnostics)
  op2 = parse_module(opt.read_text(encoding="utf-8"), path=str(opt), use_cache=False)
  assert op2.mid_emit_ok and len(op2.tree.body) > 0
  assert any("ast_from_mid" in d for d in op2.diagnostics)


def test_mid_ok_prefers_ast_from_mid(monkeypatch):
  """典型 mid_ok 走 ``ast_from_mid``（已无 span materialize）。"""
  monkeypatch.setenv("PY2CPP_NO_MATERIALIZE", "0")
  from src.frontend.api import clear_parse_cache, parse_module

  clear_parse_cache()
  path = Path("py2cpp/core/optional.paw")
  parsed = parse_module(path.read_text(encoding="utf-8"), path=str(path), use_cache=False)
  assert parsed.mid_emit_ok and len(parsed.tree.body) > 0
  assert any(d.endswith("mid_ok → ast_from_mid") for d in parsed.diagnostics)


def test_repo_paw_mid_ok_and_from_mid():
  """``py2cpp`` / ``test`` / ``compiler/paw`` 全部 mid_ok 且 ``ast_from_mid``。"""
  from compiler.py.mid.ast_from_mid import ast_module_from_mid

  n = 0
  for root in ("py2cpp", "test", "compiler/paw"):
    for path in sorted(Path(root).rglob("*.paw")):
      src = path.read_text(encoding="utf-8")
      mid = lower_to_mid(
        bind_module(
          parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=str(path)
        )
      )
      assert can_emit_mid(mid), path
      ast_module_from_mid(mid, filename=str(path))
      n += 1
  assert n >= 153 + 6


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
  out = Path("generated/mid_emit_test_ns")
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
  """未设 env：仅 seed PRIMARY；stdlib/test 否；=0 全关；=1 全开。"""
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  from src.translator import Translator

  tr = Translator("t", "compiler/paw/frontend/diagnostic.paw")
  tr.module_mid_emit_ok = {
    "compiler/paw/frontend/diagnostic": True,
    "py2cpp/core/optional": True,
    "test/lang/test_enum": True,
  }
  assert tr._module_mid_emit_primary("compiler/paw/frontend/diagnostic")
  assert not tr._module_mid_emit_primary("test/lang/test_enum")
  assert not tr._module_mid_emit_primary("py2cpp/core/optional")
  monkeypatch.setenv("PY2CPP_MID_PRIMARY", "0")
  assert not tr._module_mid_emit_primary("compiler/paw/frontend/diagnostic")
  assert not tr._module_mid_emit_primary("test/lang/test_enum")
  monkeypatch.setenv("PY2CPP_MID_PRIMARY", "1")
  assert tr._module_mid_emit_primary("py2cpp/core/optional")
  assert tr._module_mid_emit_primary("test/lang/test_enum")


def test_seed_translate_keeps_module_path(tmp_path, monkeypatch):
  """翻译 seed 时模块路径为 ``compiler/paw/<stem>``，生产 cpp 为 MidIR emit。"""
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from src.frontend.api import clear_parse_cache
  from src.translator import Translator

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
  from src.analysis.stubs.template_prefix_stubs import load_cpp_template_type_prefixes
  from src.frontend.api import clear_parse_cache

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
  out = Path("generated/mid_emit_attr_test")
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
  out = Path("generated/mid_emit_local_call")
  _h, c = emit_mid_module(mid, out_dir=out, module_path="m")
  text = c.read_text(encoding="utf-8")
  assert "Class()" in text
  assert "PyClass{}" not in text


def test_register_module_from_mid_no_materialize(monkeypatch):
  """``register_module_from_mid`` 仍可用；生产空树改走回填。"""
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from src.frontend.api import clear_parse_cache, parse_module
  from src.translator import Translator

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
  from src.analysis.import_resolver import discover_translation_modules
  from src.frontend.api import clear_parse_cache

  clear_parse_cache()
  root = Path(".").resolve()
  mods = discover_translation_modules(
    (root / "compiler/paw/frontend/parser.paw").resolve(),
    include_stdlib=False,
    runtime_root=root / "py2cpp",
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
  from src.frontend.api import clear_parse_cache
  from src.translator import Translator

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
  from src.translator import Translator

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

  out = Path("generated/mid_emit_enum_base")
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
  from src.passes.dataclass_expand import expand_dataclass
  from src.passes.union_expand import expand_union
  from src.translator import Translator

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
  """非 stdlib mid_ok 默认 PRIMARY → 生产 cpp 为 MidIR emit。"""
  monkeypatch.delenv("PY2CPP_MID_PRIMARY", raising=False)
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from src.frontend.api import clear_parse_cache
  from src.translator import Translator

  clear_parse_cache()
  _h, cpp = Translator.translate_file(
    "test/lang/test_enum.paw",
    str(tmp_path / "out"),
    include_stdlib=False,
    emit_main=False,
    strict=False,
  )
  assert Path(cpp).read_text(encoding="utf-8").startswith("// MidIR emit")


def test_stdlib_mid_primary_writes_runtime(tmp_path, monkeypatch):
  """``MID_PRIMARY=1`` 时 stdlib 入口 Mid 落 ``runtime/py2cpp/...`` 且 ``.h/.inl/.cpp`` 齐。"""
  monkeypatch.setenv("PY2CPP_MID_PRIMARY", "1")
  monkeypatch.delenv("PY2CPP_NO_MATERIALIZE", raising=False)
  from src.frontend.api import clear_parse_cache
  from src.translator import Translator

  clear_parse_cache()
  h, cpp = Translator.translate_file(
    "py2cpp/core/optional.paw",
    str(tmp_path / "out"),
    include_stdlib=False,
    emit_main=False,
    strict=False,
  )
  cpp_p = Path(cpp)
  h_p = Path(h)
  assert cpp_p.is_file() and h_p.is_file()
  assert "runtime" in cpp_p.as_posix()
  assert "optional" in cpp_p.name
  inl = cpp_p.with_suffix(".inl")
  assert inl.is_file()
  h_text = h_p.read_text(encoding="utf-8")
  assert 'include "py2cpp/core/optional.inl"' in h_text.replace("\\", "/")
  cpp_text = cpp_p.read_text(encoding="utf-8")
  assert "PY2CPP_LIBRARY_TU" in cpp_text
  assert "optional.inl" in cpp_text
  assert inl.read_text(encoding="utf-8").startswith("// MidIR emit inl")


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
  from src.passes.protocol import expand_protocol
  from src.translator import Translator

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

