"""把「多字符」单引号字面量改写为双引号形式（C 系引号规则迁移）。

  ``'abc'``        → ``"abc"``
  ``'a"b'``        → ``"a\\"b"``      （内部双引号转义）
  ``'a\\'b'``      → ``"a'b"``        （单引号无需转义）
  ``'a\\\\b'``      → ``"a\\\\b"``  （反斜杠转义保持不变）

单字符单引号（``'a'``）**保留**（char 语义）。三引号改为双三引号。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _decoded_len(body: str) -> int:
  n = 0
  i = 0
  while i < len(body):
    if body[i] == '\\' and i + 1 < len(body):
      i += 2
      n += 1
      continue
    i += 1
    n += 1
  return n


def _convert_single_to_double(body: str) -> str:
  """把单引号字面量的**内容**转换为可放进双引号的等价内容。"""
  out: list[str] = []
  i = 0
  while i < len(body):
    ch = body[i]
    if ch == '\\' and i + 1 < len(body):
      nxt = body[i + 1]
      if nxt == "'":
        # ``\'`` 在双引号里无需转义
        out.append("'")
      elif nxt == '"':
        # ``\"`` 在双引号里必须转义
        out.append('\\"')
      else:
        out.append(ch)
        out.append(nxt)
      i += 2
      continue
    if ch == '"':
      out.append('\\"')
      i += 1
      continue
    out.append(ch)
    i += 1
  return ''.join(out)


def _rewrite(text: str) -> tuple[str, int]:
  """扫描源码，改写多字符单引号字面量；返回 (新文本, 改动数)。"""
  res: list[str] = []
  i = 0
  n = len(text)
  count = 0
  while i < n:
    ch = text[i]
    # 注释：整行到行尾原样保留
    if ch == '#':
      j = text.find('\n', i)
      if j < 0:
        res.append(text[i:])
        break
      res.append(text[i:j])
      i = j
      continue
    # 字符串前缀（r/b/f/u 组合）
    if ch.isalpha() and ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
      res.append(ch)
      i += 1
      continue
    if ch.isalpha():
      j = i
      while j < n and text[j].isalpha():
        j += 1
      if j < n and text[j] in '"\'':
        prefix = text[i:j]
        # 进入字面量处理
        quote = text[j]
        body_start = j + 1
        triple = text[j:j + 3] == quote * 3
        if triple:
          end = text.find(quote * 3, body_start + 2)
          if end < 0:
            res.append(text[i:])
            break
          body = text[body_start + 2:end]
          res.append(prefix + quote * 3 + body + quote * 3)
          i = end + 3
          continue
        k = body_start
        while k < n:
          if text[k] == '\\':
            k += 2
            continue
          if text[k] == quote:
            break
          k += 1
        if k >= n:
          res.append(text[i:])
          break
        body = text[body_start:k]
        if quote == "'" and _decoded_len(body) != 1:
          res.append(prefix + '"' + _convert_single_to_double(body) + '"')
          count += 1
        else:
          res.append(text[i:k + 1])
        i = k + 1
        continue
      res.append(text[i:j])
      i = j
      continue
    if ch in '"\'':
      quote = ch
      body_start = i + 1
      triple = text[i:i + 3] == quote * 3
      if triple:
        end = text.find(quote * 3, body_start + 2)
        if end < 0:
          res.append(text[i:])
          break
        body = text[body_start + 2:end]
        if quote == "'":
          res.append('"""' + body + '"""')
          count += 1
        else:
          res.append(text[i:end + 3])
        i = end + 3
        continue
      k = body_start
      while k < n:
        if text[k] == '\\':
          k += 2
          continue
        if text[k] == quote:
          break
        if text[k] == '\n':
          break
        k += 1
      if k >= n or text[k] != quote:
        res.append(text[i:])
        break
      body = text[body_start:k]
      if quote == "'" and _decoded_len(body) != 1:
        res.append('"' + _convert_single_to_double(body) + '"')
        count += 1
      else:
        res.append(text[i:k + 1])
      i = k + 1
      continue
    res.append(ch)
    i += 1
  return ''.join(res), count


def main() -> int:
  dry = '--dry' in sys.argv
  targets = [a for a in sys.argv[1:] if not a.startswith('--')] or ['lib', 'compiler', 'tests']
  total = 0
  files = 0
  for t in targets:
    base = ROOT / t
    if not base.is_dir():
      continue
    for f in sorted(base.rglob('*.paw')):
      text = f.read_text(encoding='utf-8')
      new, cnt = _rewrite(text)
      if cnt:
        if not dry:
          f.write_text(new, encoding='utf-8', newline='\n')
        files += 1
        total += cnt
        print(f'  {f.relative_to(ROOT)}: {cnt}')
  print(f'OK {"DRY-RUN " if dry else ""}改写 {total} 处 / {files} 个文件')
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
