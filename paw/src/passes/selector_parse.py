"""路径字符串 DSL → ``SelectorPlan`` IR（``select("…")`` 译期专用）。"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


class SelectorParseError(ValueError):
  """path 子串语法错误。"""


FILTER_ELEM_PLACEHOLDER = "_sel"
FILTER_BIND_PREFIX = "_bind_"
_FILTER_GLOBAL_NAMES = frozenset({"True", "False", "None", FILTER_ELEM_PLACEHOLDER})


@dataclass(frozen=True)
class FieldStep:
  name: str
  optional: bool = False


@dataclass(frozen=True)
class IndexStep:
  index: int
  optional: bool = False


@dataclass(frozen=True)
class StrIndexStep:
  """``['key']``：``dict`` 字符串键下标。"""
  key: str
  optional: bool = False


@dataclass(frozen=True)
class SliceStep:
  lo: int | None
  hi: int | None
  step: int | None = None


@dataclass(frozen=True)
class MultiBracketStep:
  """``[1, 2:4]`` / ``['u', 'v']``：同一容器上多下标选择。"""
  items: tuple[IndexStep | SliceStep | StrIndexStep, ...]


@dataclass(frozen=True)
class BindStep:
  """``: $ident``：快照当前上下文，不改变线性 ctx。"""
  name: str


@dataclass(frozen=True)
class RefStep:
  """``$ident``：从绑定表取上下文继续导航。"""
  name: str


@dataclass(frozen=True)
class FilterStep:
  expr_src: str
  expr: ast.expr
  bind_refs: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ProjectionStep:
  """``.(a.b, c)``：相对当前对象的并行子路径（arm 可为完整相对 plan）。"""
  arms: tuple[SelectorPlan, ...]


@dataclass(frozen=True)
class DescendantStep:
  """``..name``：递归收集当前上下文下所有 ``name`` 字段（经 list 自动枚举）。"""
  field: str


SelectorStep = (
  FieldStep
  | IndexStep
  | SliceStep
  | MultiBracketStep
  | FilterStep
  | ProjectionStep
  | DescendantStep
  | BindStep
  | RefStep
)


@dataclass(frozen=True)
class SortKey:
  expr_src: str
  expr: ast.expr
  bind_refs: frozenset[str]
  descending: bool = False


@dataclass(frozen=True)
class SortStep:
  keys: tuple[SortKey, ...]


@dataclass(frozen=True)
class GroupStep:
  expr_src: str
  expr: ast.expr
  bind_refs: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CountStep:
  """``key is None`` → 元素总数；否则按 key 表达式频数。"""
  expr_src: str | None = None
  expr: ast.expr | None = None
  bind_refs: frozenset[str] = field(default_factory=frozenset)


PostStep = SortStep | GroupStep | CountStep


@dataclass(frozen=True)
class SelectorPlan:
  steps: tuple[SelectorStep, ...]
  post_steps: tuple[PostStep, ...] = ()


@dataclass(frozen=True)
class SelectorChainPlan:
  """同链 ``;`` 分段 + ``:$`` / ``$`` 引用（``bind_prefix`` 只绑定不 append）。"""
  bind_prefix: tuple[SelectorStep, ...]
  steps: tuple[SelectorStep, ...]
  post_steps: tuple[PostStep, ...] = ()


def _read_int(path: str, i: int) -> tuple[int, int]:
  sign = 1
  if i < len(path) and path[i] == "-":
    sign = -1
    i += 1
  start = i
  if i >= len(path) or not path[i].isdigit():
    raise SelectorParseError(f"期望整数，位于: {path[i:]!r}")
  while i < len(path) and path[i].isdigit():
    i += 1
  return sign * int(path[start:i]), i


def _read_ident(path: str, i: int) -> tuple[str, int]:
  start = i
  if i >= len(path) or not (path[i].isalpha() or path[i] == "_"):
    raise SelectorParseError(f"期望标识符，位于: {path[i:]!r}")
  i += 1
  while i < len(path) and (path[i].isalnum() or path[i] == "_"):
    i += 1
  return path[start:i], i


def _skip_ws(path: str, i: int) -> int:
  while i < len(path) and path[i].isspace():
    i += 1
  return i


def _consume_optional(path: str, i: int) -> tuple[bool, int]:
  if i < len(path) and path[i] == "?":
    return True, i + 1
  return False, i


def _apply_optional_step(step: SelectorStep, optional: bool) -> SelectorStep:
  if not optional:
    return step
  if isinstance(step, IndexStep):
    return IndexStep(step.index, optional=True)
  if isinstance(step, StrIndexStep):
    return StrIndexStep(step.key, optional=True)
  if isinstance(step, MultiBracketStep):
    items: list[IndexStep | SliceStep | StrIndexStep] = []
    for item in step.items:
      if isinstance(item, IndexStep):
        items.append(IndexStep(item.index, optional=True))
      elif isinstance(item, StrIndexStep):
        items.append(StrIndexStep(item.key, optional=True))
      else:
        items.append(item)
    return MultiBracketStep(tuple(items))
  raise SelectorParseError("'?' 不可用于该下标/切片形式")


def _desugar_filter_bind_src(src: str) -> tuple[str, frozenset[str]]:
  """``$ident`` / ``$ident.field`` → ``_bind_ident`` / ``_bind_ident.field``。"""
  out: list[str] = []
  refs: set[str] = set()
  i = 0
  n = len(src)
  in_str: str | None = None
  escape = False
  while i < n:
    ch = src[i]
    if in_str is not None:
      out.append(ch)
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      i += 1
      continue
    if ch in ("'", '"'):
      in_str = ch
      out.append(ch)
      i += 1
      continue
    if ch == "$":
      i += 1
      name, i = _read_ident(src, i)
      refs.add(name)
      out.append(f"{FILTER_BIND_PREFIX}{name}")
      if i < n and src[i] == "." and i + 1 < n and (
        src[i + 1].isalpha() or src[i + 1] == "_"
      ):
        j = i + 1
        while j < n and (src[j].isalnum() or src[j] == "_"):
          j += 1
        out.append(src[i:j])
        i = j
      continue
    out.append(ch)
    i += 1
  return "".join(out), frozenset(refs)


def _desugar_filter_member_src(src: str) -> str:
  """``.field`` → ``_sel.field``；裸标识符保持为普通 Name。"""
  out: list[str] = []
  i = 0
  n = len(src)
  in_str: str | None = None
  escape = False
  while i < n:
    ch = src[i]
    if in_str is not None:
      out.append(ch)
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      i += 1
      continue
    if ch in ("'", '"'):
      in_str = ch
      out.append(ch)
      i += 1
      continue
    if ch == "." and i + 1 < n and (src[i + 1].isalpha() or src[i + 1] == "_"):
      joined = "".join(out)
      if re.search(rf"{re.escape(FILTER_BIND_PREFIX)}\w+$", joined):
        j = i + 1
        while j < n and (src[j].isalnum() or src[j] == "_"):
          j += 1
        out.append(src[i:j])
        i = j
        continue
      j = i + 1
      while j < n and (src[j].isalnum() or src[j] == "_"):
        j += 1
      out.append(f"{FILTER_ELEM_PLACEHOLDER}.{src[i + 1:j]}")
      i = j
      continue
    out.append(ch)
    i += 1
  return "".join(out)


def _parse_filter_expr(src: str) -> tuple[ast.expr, frozenset[str]]:
  desugared_bind, bind_refs = _desugar_filter_bind_src(src)
  desugared = _desugar_filter_member_src(desugared_bind)
  try:
    tree = ast.parse(desugared, mode="eval")
  except SyntaxError as e:
    raise SelectorParseError(f"过滤表达式语法错误: {e}") from e
  return tree.body, bind_refs


def _parse_slice_tail(path: str, i: int) -> tuple[int | None, int | None, int]:
  """解析 ``:hi`` 与可选 ``:step``，``i`` 指向第一个 ``:`` 之后。"""
  hi: int | None = None
  step: int | None = None
  if i < len(path) and (path[i].isdigit() or path[i] == "-"):
    hi, i = _read_int(path, i)
  if i < len(path) and path[i] == ":":
    i += 1
    if i < len(path) and (path[i].isdigit() or path[i] == "-"):
      step, i = _read_int(path, i)
    elif i < len(path) and path[i] not in {",", "]"}:
      raise SelectorParseError(f"切片步长须为整数，位于: {path[i:]!r}")
  return hi, step, i


def _read_string_literal(path: str, i: int) -> tuple[str, int]:
  if i >= len(path) or path[i] not in ("'", '"'):
    raise SelectorParseError(f"期望字符串字面量，位于: {path[i:]!r}")
  quote = path[i]
  i += 1
  chars: list[str] = []
  while i < len(path):
    ch = path[i]
    if ch == "\\":
      i += 1
      if i >= len(path):
        raise SelectorParseError("字符串转义不完整")
      esc = path[i]
      if esc == "n":
        chars.append("\n")
      elif esc == "t":
        chars.append("\t")
      elif esc == "r":
        chars.append("\r")
      elif esc in ("'", '"', "\\"):
        chars.append(esc)
      else:
        raise SelectorParseError(f"不支持的字符串转义 \\{esc!r}")
      i += 1
      continue
    if ch == quote:
      return "".join(chars), i + 1
    chars.append(ch)
    i += 1
  raise SelectorParseError("字符串字面量缺少结束引号")


def _parse_bracket_item(
  path: str,
  i: int,
) -> tuple[IndexStep | SliceStep | StrIndexStep, int]:
  i = _skip_ws(path, i)
  if i < len(path) and path[i] in ("'", '"'):
    key, i = _read_string_literal(path, i)
    return StrIndexStep(key), i
  if i < len(path) and path[i] == ":":
    lo: int | None = None
    hi, step, i = _parse_slice_tail(path, i + 1)
    return SliceStep(lo, hi, step), i
  lo, i = _read_int(path, i)
  if i < len(path) and path[i] == ":":
    hi, step, i = _parse_slice_tail(path, i + 1)
    return SliceStep(lo, hi, step), i
  return IndexStep(lo), i


def _check_multi_bracket_homogeneous(
  items: tuple[IndexStep | SliceStep | StrIndexStep, ...],
) -> None:
  has_str = any(isinstance(it, StrIndexStep) for it in items)
  has_seq = any(isinstance(it, (IndexStep, SliceStep)) for it in items)
  if has_str and has_seq:
    raise SelectorParseError("多下标不可混用字符串键与整型/切片")


def _parse_bracket(path: str, i: int, *, optional: bool = False) -> tuple[SelectorStep, int]:
  assert path[i] == "["
  i += 1
  item, i = _parse_bracket_item(path, i)
  i = _skip_ws(path, i)
  if i < len(path) and path[i] == ",":
    items: list[IndexStep | SliceStep | StrIndexStep] = [item]
    while True:
      i += 1
      i = _skip_ws(path, i)
      nxt, i = _parse_bracket_item(path, i)
      items.append(nxt)
      i = _skip_ws(path, i)
      if i >= len(path):
        raise SelectorParseError("缺少 ']'")
      if path[i] == "]":
        tpl = tuple(items)
        _check_multi_bracket_homogeneous(tpl)
        return _apply_optional_step(MultiBracketStep(tpl), optional), i + 1
      if path[i] != ",":
        raise SelectorParseError(f"多下标须以 ',' 分隔，位于: {path[i:]!r}")
  if i >= len(path) or path[i] != "]":
    raise SelectorParseError("缺少 ']'")
  return _apply_optional_step(item, optional), i + 1


def _parse_relative_steps(
  path: str,
  i: int,
  stop_at: frozenset[str],
) -> tuple[tuple[SelectorStep, ...], int]:
  i = _skip_ws(path, i)
  if i >= len(path) or path[i] in stop_at:
    raise SelectorParseError("投影 arm 不能为空")
  steps: list[SelectorStep] = []
  if path[i] not in "[{.":
    name, i = _read_ident(path, i)
    steps.append(FieldStep(name))
  while i < len(path):
    i = _skip_ws(path, i)
    if i >= len(path) or path[i] in stop_at:
      break
    if path[i] == "$":
      raise SelectorParseError("投影 arm 不可用 $ 引用")
    step, ni = _parse_suffix(path, i)
    if step is not None:
      steps.append(step)
      i = ni
      continue
    optional, i = _consume_optional(path, i)
    if i >= len(path):
      raise SelectorParseError("'?' 后缺少字段名")
    if path[i] != ".":
      raise SelectorParseError(f"无法解析投影 arm 剩余: {path[i:]!r}")
    if i + 1 < len(path) and path[i + 1] == "(":
      if optional:
        raise SelectorParseError("'?' 不可用于投影")
      step, i = _parse_projection(path, i)
      steps.append(step)
      continue
    i += 1
    if i >= len(path):
      raise SelectorParseError("'.' 后缺少字段名")
    name, i = _read_ident(path, i)
    steps.append(FieldStep(name, optional=optional))
  if not steps:
    raise SelectorParseError("投影 arm 不能为空")
  return tuple(steps), i


def _parse_projection(path: str, i: int) -> tuple[ProjectionStep, int]:
  assert path[i] == "." and i + 1 < len(path) and path[i + 1] == "("
  i += 2
  arms: list[SelectorPlan] = []
  while True:
    i = _skip_ws(path, i)
    if i >= len(path):
      raise SelectorParseError("投影缺少 ')'")
    if path[i] == ")":
      if not arms:
        raise SelectorParseError("投影至少需要一个 arm")
      return ProjectionStep(tuple(arms)), i + 1
    arm_steps, i = _parse_relative_steps(path, i, frozenset({",", ")"}))
    arms.append(SelectorPlan(arm_steps))
    i = _skip_ws(path, i)
    if i >= len(path):
      raise SelectorParseError("投影缺少 ')'")
    if path[i] == ")":
      return ProjectionStep(tuple(arms)), i + 1
    if path[i] != ",":
      raise SelectorParseError(f"投影 arm 须以 ',' 分隔，位于: {path[i:]!r}")
    i += 1


def _parse_filter(path: str, i: int) -> tuple[FilterStep, int]:
  assert path[i] == "{"
  depth = 0
  start = i + 1
  j = i
  in_str: str | None = None
  escape = False
  while j < len(path):
    ch = path[j]
    if in_str is not None:
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      j += 1
      continue
    if ch in ("'", '"'):
      in_str = ch
      j += 1
      continue
    if ch == "{":
      depth += 1
    elif ch == "}":
      depth -= 1
      if depth == 0:
        expr_src = path[start:j]
        expr, bind_refs = _parse_filter_expr(expr_src)
        return FilterStep(expr_src, expr, bind_refs), j + 1
    j += 1
  raise SelectorParseError("过滤表达式缺少 '}'")


def _parse_root_first_step(path: str, i: int) -> tuple[SelectorStep, int]:
  """根路径首步：取 receiver 字段须 ``.ident`` / ``?.ident``；``[…]`` / ``{…}`` 仍可直接起头。"""
  n = len(path)
  optional, i = _consume_optional(path, i)
  if i >= n:
    if optional:
      raise SelectorParseError("'?' 后缺少 '.' 或 '['")
    raise SelectorParseError("路径不能为空")
  ch = path[i]
  if ch == "[":
    step, i = _parse_bracket(path, i, optional=optional)
    return step, i
  if ch == "{":
    if optional:
      raise SelectorParseError("'?' 不可用于过滤步")
    step, i = _parse_filter(path, i)
    return step, i
  if ch == ".":
    if i + 1 < n and path[i + 1] == "(":
      step, i = _parse_projection(path, i)
      return step, i
    i += 1
    if i >= n:
      raise SelectorParseError("'.' 后缺少字段名")
    if path[i] == ".":
      if optional:
        raise SelectorParseError("'?' 不可用于递归下降 '..'")
      i += 1
      if i >= n:
        raise SelectorParseError("'..' 后缺少字段名")
      name, i = _read_ident(path, i)
      return DescendantStep(name), i
    name, i = _read_ident(path, i)
    return FieldStep(name, optional=optional), i
  if optional:
    raise SelectorParseError("'?' 须紧接 '.' 或 '['")
  if ch.isalpha() or ch == "_":
    raise SelectorParseError("根路径取字段须以 '.' 开头")
  raise SelectorParseError(f"无法解析路径: {path[i:]!r}")


def _parse_suffix(path: str, i: int) -> tuple[SelectorStep | None, int]:
  if i >= len(path):
    return None, i
  # ``?.field`` 由主循环 / 投影 arm 处理；此处只解析 ``?[…]``
  if path[i] == "?" and i + 1 < len(path) and path[i + 1] == ".":
    return None, i
  optional, i = _consume_optional(path, i)
  if i >= len(path):
    if optional:
      raise SelectorParseError("'?' 后缺少 '['")
    return None, i
  if path[i] == "[":
    step, i = _parse_bracket(path, i, optional=optional)
    return step, i
  if optional:
    raise SelectorParseError("'?' 须紧接 '.' 或 '['")
  if path[i] == "{":
    step, i = _parse_filter(path, i)
    return step, i
  if path[i] == "." and i + 1 < len(path) and path[i + 1] == "(":
    step, i = _parse_projection(path, i)
    return step, i
  return None, i


def _find_post_start(path: str) -> int:
  """导航与子串末尾 ``@sort`` / ``@group`` / ``@count`` 分界（括号/字符串外）。"""
  depth_paren = depth_brack = depth_brace = 0
  in_str: str | None = None
  escape = False
  i = 0
  n = len(path)
  while i < n:
    ch = path[i]
    if in_str is not None:
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      i += 1
      continue
    if ch in ("'", '"'):
      in_str = ch
      i += 1
      continue
    if ch == "(":
      depth_paren += 1
    elif ch == ")":
      depth_paren -= 1
    elif ch == "[":
      depth_brack += 1
    elif ch == "]":
      depth_brack -= 1
    elif ch == "{":
      depth_brace += 1
    elif ch == "}":
      depth_brace -= 1
    elif depth_paren == depth_brack == depth_brace == 0 and ch == "@":
      if path.startswith("@sort(", i):
        return i
      if path.startswith("@group(", i):
        return i
      if path.startswith("@count", i):
        tail = i + 6
        if tail >= n or path[tail] in "( @":
          return i
    i += 1
  return n


def _split_nav_post(path: str) -> tuple[str, str]:
  i = _find_post_start(path)
  nav = path[:i].strip()
  post = path[i:].strip()
  if not nav and post:
    raise SelectorParseError("后处理前须有导航路径")
  return nav, post


def _split_top_level_commas(src: str) -> list[str]:
  parts: list[str] = []
  start = 0
  depth_paren = depth_brack = depth_brace = 0
  in_str: str | None = None
  escape = False
  for j, ch in enumerate(src):
    if in_str is not None:
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      continue
    if ch in ("'", '"'):
      in_str = ch
      continue
    if ch == "(":
      depth_paren += 1
    elif ch == ")":
      depth_paren -= 1
    elif ch == "[":
      depth_brack += 1
    elif ch == "]":
      depth_brack -= 1
    elif ch == "{":
      depth_brace += 1
    elif ch == "}":
      depth_brace -= 1
    elif ch == "," and depth_paren == depth_brack == depth_brace == 0:
      part = src[start:j].strip()
      if part:
        parts.append(part)
      start = j + 1
  tail = src[start:].strip()
  if tail:
    parts.append(tail)
  return parts


def _parse_paren_body(path: str, i: int) -> tuple[str, int]:
  """``i`` 指向 ``(``；返回括号内子串与 ``)`` 后下标。"""
  if i >= len(path) or path[i] != "(":
    raise SelectorParseError(f"期望 '('，位于: {path[i:]!r}")
  depth = 0
  start = i + 1
  j = i
  in_str: str | None = None
  escape = False
  while j < len(path):
    ch = path[j]
    if in_str is not None:
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      j += 1
      continue
    if ch in ("'", '"'):
      in_str = ch
      j += 1
      continue
    if ch == "(":
      depth += 1
    elif ch == ")":
      depth -= 1
      if depth == 0:
        return path[start:j], j + 1
    j += 1
  raise SelectorParseError("缺少 ')'")


def _parse_sort_keys(body: str) -> tuple[SortKey, ...]:
  if not body.strip():
    raise SelectorParseError("@sort 至少需要一个排序键")
  keys: list[SortKey] = []
  for part in _split_top_level_commas(body):
    src = part.strip()
    descending = False
    if src.startswith("-"):
      descending = True
      src = src[1:].strip()
    if not src:
      raise SelectorParseError("@sort 排序键不可为空")
    expr, bind_refs = _parse_filter_expr(src)
    keys.append(SortKey(src, expr, bind_refs, descending))
  return tuple(keys)


def _parse_post_steps(post: str) -> tuple[PostStep, ...]:
  if not post:
    return ()
  steps: list[PostStep] = []
  i = 0
  n = len(post)
  while i < n:
    i = _skip_ws(post, i)
    if i >= n:
      break
    if post.startswith("@sort(", i):
      body, i = _parse_paren_body(post, i + 5)
      steps.append(SortStep(_parse_sort_keys(body)))
      continue
    if post.startswith("@group(", i):
      body, i = _parse_paren_body(post, i + 6)
      body = body.strip()
      if not body:
        raise SelectorParseError("@group 须指定分组键表达式")
      expr, bind_refs = _parse_filter_expr(body)
      steps.append(GroupStep(body, expr, bind_refs))
      continue
    if post.startswith("@count", i):
      i += 6
      if i < n and post[i] == "(":
        body, i = _parse_paren_body(post, i)
        body = body.strip()
        if not body:
          raise SelectorParseError("@count(…) 键表达式不可为空")
        expr, bind_refs = _parse_filter_expr(body)
        steps.append(CountStep(body, expr, bind_refs))
      else:
        steps.append(CountStep())
      continue
    raise SelectorParseError(f"未知后处理: {post[i:]!r}")
  _validate_post_steps(tuple(steps))
  return tuple(steps)


def _validate_post_steps(steps: tuple[PostStep, ...]) -> None:
  if not steps:
    return
  seen_group = False
  count_idx: int | None = None
  for idx, step in enumerate(steps):
    if isinstance(step, SortStep):
      if seen_group:
        raise SelectorParseError("@group 后不支持 @sort")
    elif isinstance(step, GroupStep):
      if seen_group:
        raise SelectorParseError("@group 不可重复")
      if count_idx is not None:
        raise SelectorParseError("@count 后不支持 @group")
      seen_group = True
    elif isinstance(step, CountStep):
      if seen_group:
        raise SelectorParseError(
          "@group 后不支持 @count；按字段频数请用 @count(.field)",
        )
      if count_idx is not None:
        raise SelectorParseError("@count 不可重复")
      count_idx = idx
  if count_idx is not None and count_idx != len(steps) - 1:
    raise SelectorParseError("@count 须为末步后处理")


def parse_selector_path(path: str) -> SelectorPlan:
  """解析相对 receiver 根的路径字符串。"""
  nav, post_s = _split_nav_post(path)
  post_steps = _parse_post_steps(post_s)
  path = nav
  if not path:
    raise SelectorParseError("路径不能为空")
  steps: list[SelectorStep] = []
  step, i = _parse_root_first_step(path, 0)
  steps.append(step)
  n = len(path)
  while i < n:
    while True:
      step, ni = _parse_suffix(path, i)
      if step is None:
        break
      steps.append(step)
      i = ni
    if i >= n:
      break
    optional, i = _consume_optional(path, i)
    if i >= n:
      raise SelectorParseError("'?' 后缺少字段名")
    if path[i] != ".":
      raise SelectorParseError(f"无法解析路径剩余: {path[i:]!r}")
    i += 1
    if i >= n:
      raise SelectorParseError("'.' 后缺少字段名")
    if path[i] == "(":
      raise SelectorParseError("投影须写为 '.(a, b)'")
    if path[i] == ".":
      if optional:
        raise SelectorParseError("'?' 不可用于递归下降 '..'")
      i += 1
      if i >= n:
        raise SelectorParseError("'..' 后缺少字段名")
      name, i = _read_ident(path, i)
      steps.append(DescendantStep(name))
      continue
    name, i = _read_ident(path, i)
    steps.append(FieldStep(name, optional=optional))
  return SelectorPlan(tuple(steps), post_steps)


def _read_bind_name(path: str, i: int) -> tuple[str, int]:
  if i >= len(path) or path[i] != "$":
    raise SelectorParseError(f"期望 '$' 绑定引用，位于: {path[i:]!r}")
  return _read_ident(path, i + 1)


def _parse_steps(
  path: str,
  start: int = 0,
  end: int | None = None,
  *,
  allow_bind: bool = True,
  allow_ref_start: bool = False,
) -> tuple[tuple[SelectorStep, ...], int]:
  end = len(path) if end is None else end
  i = _skip_ws(path, start)
  if i >= end:
    raise SelectorParseError("路径不能为空")
  steps: list[SelectorStep] = []
  if path[i] == "$":
    if not allow_ref_start:
      raise SelectorParseError("$ 引用须出现在 ';' 右侧或链内续步")
    name, i = _read_bind_name(path, i)
    steps.append(RefStep(name))
  else:
    step, i = _parse_root_first_step(path, i)
    steps.append(step)
  while i < end:
    i = _skip_ws(path, i)
    if i >= end:
      break
    if allow_bind and path[i] == ":":
      j = _skip_ws(path, i + 1)
      if j < end and path[j] == "$":
        name, i = _read_bind_name(path, j)
        steps.append(BindStep(name))
        continue
    step, ni = _parse_suffix(path, i)
    if step is not None:
      steps.append(step)
      i = ni
      continue
    if path[i] == "$":
      name, i = _read_bind_name(path, i)
      steps.append(RefStep(name))
      continue
    optional, i = _consume_optional(path, i)
    if i >= end:
      raise SelectorParseError("'?' 后缺少字段名")
    if path[i] != ".":
      raise SelectorParseError(f"无法解析路径剩余: {path[i:]!r}")
    i += 1
    if i >= end:
      raise SelectorParseError("'.' 后缺少字段名")
    if path[i] == "(":
      raise SelectorParseError("投影须写为 '.(a, b)'")
    if path[i] == ".":
      if optional:
        raise SelectorParseError("'?' 不可用于递归下降 '..'")
      i += 1
      if i >= end:
        raise SelectorParseError("'..' 后缺少字段名")
      name, i = _read_ident(path, i)
      steps.append(DescendantStep(name))
      continue
    name, i = _read_ident(path, i)
    steps.append(FieldStep(name, optional=optional))
  return tuple(steps), i


_TOP_LEVEL_COMMA_MSG = (
  "顶层 ',' 多路径已废除；请用 .field[i,j].suffix 或 .(rel1, rel2).suffix"
  "（如 .teams[0,1].name、.(teams[0], teams[1]).name）"
)


def _split_top_level_semicolon(path: str) -> list[str]:
  depth_paren = depth_brack = depth_brace = 0
  in_str: str | None = None
  escape = False
  for j, ch in enumerate(path):
    if in_str is not None:
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      continue
    if ch in ("'", '"'):
      in_str = ch
      continue
    if ch == "(":
      depth_paren += 1
    elif ch == ")":
      depth_paren -= 1
    elif ch == "[":
      depth_brack += 1
    elif ch == "]":
      depth_brack -= 1
    elif ch == "{":
      depth_brace += 1
    elif ch == "}":
      depth_brace -= 1
    elif ch == ";" and depth_paren == depth_brack == depth_brace == 0:
      left = path[:j].strip()
      right = path[j + 1:].strip()
      parts: list[str] = []
      if left:
        parts.append(left)
      if right:
        parts.append(right)
      return parts
  return [path.strip()] if path.strip() else []


def _require_ancestor_bind(name: str, bound: frozenset[str], *, in_filter: bool) -> None:
  if name in bound:
    return
  if in_filter:
    raise SelectorParseError(
      f"filter 内 ${name!r} 须来自同链祖先节点的 : ${name!r} 绑定（非路径根引用）",
    )
  raise SelectorParseError(
    f"${name!r} 须来自同链祖先节点的 : ${name!r} 绑定",
  )


def _validate_chain_bind_scope(plan: SelectorChainPlan) -> None:
  """``$ident`` 只能引用同链、严格更早步上的 ``: $ident`` 绑定。"""
  bound: set[str] = set()

  def walk(
    steps: tuple[SelectorStep, ...],
    *,
    forbid_prefix_refs: frozenset[str] | None = None,
  ) -> None:
    nonlocal bound
    for step in steps:
      if isinstance(step, BindStep):
        if step.name in bound:
          raise SelectorParseError(f"select 绑定 ${step.name!r} 重复")
        bound.add(step.name)
      elif isinstance(step, RefStep):
        if forbid_prefix_refs and step.name in forbid_prefix_refs:
          raise SelectorParseError(
            f"';' 右侧从 receiver 根导航时不可引用左段 ${step.name!r} 绑定",
          )
        _require_ancestor_bind(step.name, frozenset(bound), in_filter=False)
      elif isinstance(step, FilterStep):
        for ref in step.bind_refs:
          if forbid_prefix_refs and ref in forbid_prefix_refs:
            raise SelectorParseError(
              f"';' 右侧从 receiver 根导航时不可在 filter 内引用左段 ${ref!r} 绑定",
            )
          _require_ancestor_bind(ref, frozenset(bound), in_filter=True)

  walk(plan.bind_prefix)
  prefix_bound = frozenset(bound)
  forbid: frozenset[str] | None = None
  if plan.bind_prefix and plan.steps and not isinstance(plan.steps[0], RefStep):
    forbid = prefix_bound
  walk(plan.steps, forbid_prefix_refs=forbid)
  _validate_post_bind_refs(
    plan.post_steps, frozenset(bound), forbid_prefix_refs=forbid,
  )


def _validate_post_bind_refs(
  post_steps: tuple[PostStep, ...],
  bound: frozenset[str],
  *,
  forbid_prefix_refs: frozenset[str] | None = None,
) -> None:
  """后处理键内 ``$ident`` 与导航/filter 同规则。"""
  for step in post_steps:
    refs: tuple[frozenset[str], ...] = ()
    if isinstance(step, SortStep):
      refs = tuple(key.bind_refs for key in step.keys)
    elif isinstance(step, GroupStep):
      refs = (step.bind_refs,)
    elif isinstance(step, CountStep) and step.expr is not None:
      refs = (step.bind_refs,)
    for bind_refs in refs:
      for ref in bind_refs:
        if forbid_prefix_refs and ref in forbid_prefix_refs:
          raise SelectorParseError(
            f"';' 右侧从 receiver 根导航时不可在后处理内引用左段 ${ref!r} 绑定",
          )
        _require_ancestor_bind(ref, bound, in_filter=True)


def parse_selector_chain(path: str) -> SelectorChainPlan:
  """解析含 ``:$`` / ``$`` / ``;`` 的同链选择器。"""
  nav, post_s = _split_nav_post(path)
  post_steps = _parse_post_steps(post_s)
  path = nav
  if not path:
    raise SelectorParseError("路径不能为空")
  parts = _split_top_level_semicolon(path)
  if len(parts) > 2:
    raise SelectorParseError("同链仅允许一个 ';' 分段")
  if len(parts) == 2:
    bind_s, result_s = parts
    if len(_split_top_level_commas(result_s)) > 1:
      raise SelectorParseError("';' 右侧不可含顶层 ','")
    bind_prefix, _ = _parse_steps(
      bind_s, allow_bind=True, allow_ref_start=False,
    )
    steps, _ = _parse_steps(
      result_s, allow_bind=True, allow_ref_start=True,
    )
    plan = SelectorChainPlan(bind_prefix, steps, post_steps)
    _validate_chain_bind_scope(plan)
    return plan
  steps, _ = _parse_steps(path, allow_bind=True, allow_ref_start=False)
  plan = SelectorChainPlan((), steps, post_steps)
  _validate_chain_bind_scope(plan)
  return plan


def _split_top_level_commas(path: str) -> list[str]:
  parts: list[str] = []
  start = 0
  depth_paren = depth_brack = depth_brace = 0
  in_str: str | None = None
  escape = False
  for j, ch in enumerate(path):
    if in_str is not None:
      if escape:
        escape = False
      elif ch == "\\":
        escape = True
      elif ch == in_str:
        in_str = None
      continue
    if ch in ("'", '"'):
      in_str = ch
      continue
    if ch == "(":
      depth_paren += 1
    elif ch == ")":
      depth_paren -= 1
    elif ch == "[":
      depth_brack += 1
    elif ch == "]":
      depth_brack -= 1
    elif ch == "{":
      depth_brace += 1
    elif ch == "}":
      depth_brace -= 1
    elif (
      ch == ","
      and depth_paren == depth_brack == depth_brace == 0
    ):
      part = path[start:j].strip()
      if part:
        parts.append(part)
      start = j + 1
  tail = path[start:].strip()
  if tail:
    parts.append(tail)
  return parts


SelectorRoot = SelectorPlan | SelectorChainPlan


def parse_selector_literal(value: object) -> SelectorRoot:
  if not isinstance(value, str):
    raise SelectorParseError("select 路径须为字符串字面量")
  arms = _split_top_level_commas(value)
  if not arms:
    raise SelectorParseError("路径不能为空")
  if len(arms) > 1:
    raise SelectorParseError(_TOP_LEVEL_COMMA_MSG)
  arm = arms[0]
  if "$" in arm or ";" in arm:
    return parse_selector_chain(arm)
  return parse_selector_path(arm)
