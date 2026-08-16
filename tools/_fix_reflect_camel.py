"""Accept camelCase Self.iterMethods / getMethodAnnotation etc. in reflect expanders."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_file(rel: str, repls: list[tuple[str, str]]) -> None:
  path = ROOT / rel
  text = path.read_text(encoding="utf-8")
  for old, new in repls:
    if old not in text:
      raise SystemExit(f"missing in {rel}: {old!r}")
    text = text.replace(old, new)
  path.write_text(text, encoding="utf-8", newline="\n")
  print("patched", rel)


def main() -> None:
  patch_file(
    "src/passes/method_meta.py",
    [
      (
        'and node.func.attr == "iter_method_params"',
        'and node.func.attr in ("iter_method_params", "iterMethodParams")',
      ),
      (
        'and func.attr == "get_method_param_type"',
        'and func.attr in ("get_method_param_type", "getMethodParamType")',
      ),
      (
        'and func.attr == "get_method_return_type"',
        'and func.attr in ("get_method_return_type", "getMethodReturnType")',
      ),
      (
        'and node.func.attr == "iter_methods"',
        'and node.func.attr in ("iter_methods", "iterMethods")',
      ),
      (
        'value=ast.Attribute(value=ast.Name(id="Self"), attr="iter_methods"),',
        'value=ast.Attribute(value=ast.Name(id="Self"), attr="iterMethods"),',
      ),
      (
        'and func.value.attr == "get_method_annotation"',
        'and func.value.attr in ("get_method_annotation", "getMethodAnnotation")',
      ),
      (
        'allowed=frozenset({"public_only", "mro", "glob"}),',
        'allowed=frozenset({"public_only", "publicOnly", "mro", "glob"}),',
      ),
    ],
  )

  # subscript annotation match still hardcodes attr="iter_methods" in one place —
  # after first replace of Call check, the match case needs both. Use a helper approach:
  # rewrite _iter_methods_subscript_annotation to check attr in set.
  path = ROOT / "src/passes/method_meta.py"
  text = path.read_text(encoding="utf-8")
  old = '''def _iter_methods_subscript_annotation(iter_node: ast.expr) -> str | None:
  match iter_node:
    case ast.Call(
      func=ast.Subscript(
        value=ast.Attribute(value=ast.Name(id="Self"), attr="iterMethods"),
        slice=sl,
      ),
    ):
      if isinstance(sl, ast.Name):
        return sl.id
      if isinstance(sl, ast.Call) and isinstance(sl.func, ast.Name):
        return sl.func.id
  return None'''
  new = '''def _iter_methods_subscript_annotation(iter_node: ast.expr) -> str | None:
  if not isinstance(iter_node, ast.Call):
    return None
  func = iter_node.func
  if not isinstance(func, ast.Subscript):
    return None
  value = func.value
  if not (
    isinstance(value, ast.Attribute)
    and isinstance(value.value, ast.Name)
    and value.value.id == "Self"
    and value.attr in ("iter_methods", "iterMethods")
  ):
    return None
  sl = func.slice
  if isinstance(sl, ast.Name):
    return sl.id
  if isinstance(sl, ast.Call) and isinstance(sl.func, ast.Name):
    return sl.func.id
  return None'''
  if old not in text:
    raise SystemExit("subscript annotation block mismatch")
  path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
  print("patched method_meta subscript helper")

  patch_file(
    "src/passes/annotation_options.py",
    [
      (
        'if kw.arg == "public_only":\n      public_only = kw.value.value',
        'if kw.arg in ("public_only", "publicOnly"):\n      public_only = kw.value.value',
      ),
    ],
  )

  patch_file(
    "src/passes/match_case.py",
    [
      (
        "node.func.attr in ('iter_fields', 'enum_fields')",
        "node.func.attr in ('iter_fields', 'iterFields', 'enum_fields', 'enumFields')",
      ),
      (
        "info[1] == 'iter_fields'",
        "info[1] in ('iter_fields', 'iterFields')",
      ),
      (
        "allowed=frozenset({'public_only', 'mro', 'glob'})",
        "allowed=frozenset({'public_only', 'publicOnly', 'mro', 'glob'})",
      ),
      (
        "val.func.attr == 'get_field_annotation'",
        "val.func.attr in ('get_field_annotation', 'getFieldAnnotation')",
      ),
      (
        "func.value.attr == 'get_field_annotation'",
        "func.value.attr in ('get_field_annotation', 'getFieldAnnotation')",
      ),
    ],
  )

  patch_file(
    "src/passes/mixins.py",
    [
      (
        '''        if node.func.attr in (
          "iter_fields",
          "enum_fields",
          "get_field_annotation",
          "get_field_annotations",
          "iter_methods",
          "get_method_annotation",
          "iter_method_params",
          "get_method_param_type",
          "get_method_return_type",
        ):''',
        '''        if node.func.attr in (
          "iter_fields",
          "iterFields",
          "enum_fields",
          "enumFields",
          "get_field_annotation",
          "getFieldAnnotation",
          "get_field_annotations",
          "getFieldAnnotations",
          "iter_methods",
          "iterMethods",
          "get_method_annotation",
          "getMethodAnnotation",
          "iter_method_params",
          "iterMethodParams",
          "get_method_param_type",
          "getMethodParamType",
          "get_method_return_type",
          "getMethodReturnType",
        ):''',
      ),
      (
        '''      if isinstance(node.func, ast.Attribute) and node.func.attr in (
        "iter_fields",
        "enum_fields",
      ):''',
        '''      if isinstance(node.func, ast.Attribute) and node.func.attr in (
        "iter_fields",
        "iterFields",
        "enum_fields",
        "enumFields",
      ):''',
      ),
      (
        'value=ast.Attribute(value=ast.Name(id="Self"), attr="iter_fields"),',
        'value=ast.Attribute(value=ast.Name(id="Self"), attr="iterFields"),',
      ),
    ],
  )

  # Fix mixins iter_fields subscript similarly if still match-based
  mp = ROOT / "src/passes/mixins.py"
  mt = mp.read_text(encoding="utf-8")
  old_m = '''def _iter_fields_subscript_annotation(iter_node: ast.expr) -> str | None:
  match iter_node:
    case ast.Call(
      func=ast.Subscript(
        value=ast.Attribute(value=ast.Name(id="Self"), attr="iterFields"),
        slice=sl,
      ),
    ):
      if isinstance(sl, ast.Name):
        return sl.id
      if isinstance(sl, ast.Call) and isinstance(sl.func, ast.Name):
        return sl.func.id
  return None'''
  new_m = '''def _iter_fields_subscript_annotation(iter_node: ast.expr) -> str | None:
  if not isinstance(iter_node, ast.Call):
    return None
  func = iter_node.func
  if not isinstance(func, ast.Subscript):
    return None
  value = func.value
  if not (
    isinstance(value, ast.Attribute)
    and isinstance(value.value, ast.Name)
    and value.value.id == "Self"
    and value.attr in ("iter_fields", "iterFields")
  ):
    return None
  sl = func.slice
  if isinstance(sl, ast.Name):
    return sl.id
  if isinstance(sl, ast.Call) and isinstance(sl.func, ast.Name):
    return sl.func.id
  return None'''
  if old_m not in mt:
    # try original snake
    old_m2 = old_m.replace('attr="iterFields"', 'attr="iter_fields"')
    if old_m2 in mt:
      mt = mt.replace(old_m2, new_m)
      mp.write_text(mt, encoding="utf-8", newline="\n")
      print("patched mixins subscript helper (from snake)")
    else:
      raise SystemExit("mixins subscript block mismatch")
  else:
    mp.write_text(mt.replace(old_m, new_m), encoding="utf-8", newline="\n")
    print("patched mixins subscript helper")


if __name__ == "__main__":
  main()
