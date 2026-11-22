from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

logdir = Path("out/.native_build_logs")
pat = re.compile(r"error C\d+: (.+)")
idents: Counter[str] = Counter()
msgs: Counter[str] = Counter()
n = 0
for p in logdir.glob("*.log"):
  t = p.read_text(encoding="utf-8", errors="replace")
  if "error C" not in t and "run exit" not in t:
    continue
  n += 1
  for m in pat.finditer(t):
    msg = m.group(1).strip()
    msg2 = re.sub(r"“[^”]+”", '"X"', msg)
    msg2 = re.sub(r'"[^"]+"', '"X"', msg2)
    msgs[msg2] += 1
    for idm in re.finditer(r"[“\"]([^”\"]+)[”\"]", msg):
      idents[idm.group(1)] += 1
print("fail_logs", n)
print("TOP_MSGS")
for m, c in msgs.most_common(25):
  print(f"{c:4d} {m[:140]}")
print("TOP_IDENTS")
for m, c in idents.most_common(40):
  print(f"{c:4d} {m}")
