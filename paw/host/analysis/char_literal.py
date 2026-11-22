"""字面量引号语义（C 系规则）：单引号 = ``char``，双引号 = ``str``。

与 Python 不同（Python 里 ``'a'`` 与 ``"a"`` 都是 ``str``），本方言采用 C 系规则：

  ``'a'``   → ``char``  （``PyChar(97)``）
  ``'ab'``  → 译期错误：单引号只能单字符
  ``"a"``   → ``str``   （``PyStr("a")``）
  ``"abc"`` → ``str``

``LiteralExpr.text`` 保留源码原文（含引号与前缀），故本模块只看原文即可判定，
**不**依赖内容长度猜测。
"""
from __future__ import annotations

import re

# 前缀（r/b/f/u 任意顺序）+ 引号 + 内容
_STR_LIT_RE = re.compile(
  r"^(?P<prefix>[A-Za-z]*)"
  r"(?P<quote>'''|\"\"\"|'|\")"
  r"(?P<body>.*)"
  r"(?P=quote)$",
  re.DOTALL,
)


def _strip_prefix_and_quotes(text: str) -> tuple[str, str, str] | None:
  """``r'abc'`` → ``("r", "'", "abc")``；非字面量返回 ``None``。"""
  m = _STR_LIT_RE.match(text.strip())
  if m is None:
    return None
  return (m.group("prefix"), m.group("quote"), m.group("body"))


def literal_is_single_quoted(text: str) -> bool:
  """字面量是否以**单**引号书写（``'a'`` / ``r'x'`` / ``'''x'''`` 皆为真）。"""
  parsed = _strip_prefix_and_quotes(text)
  if parsed is None:
    return False
  return parsed[1].startswith("'")


def literal_is_triple_quoted(text: str) -> bool:
  parsed = _strip_prefix_and_quotes(text)
  if parsed is None:
    return False
  return len(parsed[1]) == 3


def literal_is_char(text: str) -> bool:
  """单引号且恰好一个字符 → ``char``。"""
  parsed = _strip_prefix_and_quotes(text)
  if parsed is None:
    return False
  prefix, quote, body = parsed
  if not quote.startswith("'"):
    return False
  if len(quote) == 3:
    # 三引号按 str 处理（见下）
    return False
  if "r" in prefix.lower() or "b" in prefix.lower():
    return False
  return _decoded_len(body) == 1


def literal_single_quote_body_len(text: str) -> int | None:
  """单引号非三引号字面量的字符数；非此类返回 ``None``（供诊断报错）。"""
  parsed = _strip_prefix_and_quotes(text)
  if parsed is None:
    return None
  prefix, quote, body = parsed
  if len(quote) != 1 or not quote.startswith("'"):
    return None
  return _decoded_len(body)


def _decoded_len(body: str) -> int:
  """转义序列按 1 个字符计（``'\\n'`` 长度为 1）。"""
  n = 0
  i = 0
  while i < len(body):
    if body[i] == "\\" and i + 1 < len(body):
      i += 2
      n += 1
      continue
    i += 1
    n += 1
  return n


def literal_char_codepoint(text: str) -> int | None:
  """单引号单字符字面量 → 码点；否则 ``None``。"""
  parsed = _strip_prefix_and_quotes(text)
  if parsed is None:
    return None
  _, quote, body = parsed
  if len(quote) != 1 or not quote.startswith("'"):
    return None
  if not body:
    return None
  if body[0] == "\\":
    esc = body[1:2]
    simple = {
      "n": 10, "t": 9, "r": 13, "\\": 92, "'": 39, '"': 34,
      "0": 0, "a": 7, "b": 8, "f": 12, "v": 11,
    }
    if esc in simple and len(body) == 2:
      return simple[esc]
    return None
  if len(body) != 1:
    return None
  return ord(body)
