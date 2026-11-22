# -*- coding: utf-8 -*-
import re
import collections
from pathlib import Path

root = Path("out/tests")
skips = collections.Counter()
samples = collections.defaultdict(list)
for p in root.rglob("*.cpp"):
    t = p.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"/\* skip: (.*?) \*/", t):
        s = m.group(1).strip()
        if "yield" in s:
            cat = "yield"
        elif "await " in s or s.startswith("async "):
            cat = "async/await"
        elif s.startswith("match ") or s.startswith("case "):
            cat = "match"
        elif "Self." in s:
            cat = "Self."
        elif "lambda " in s:
            cat = "lambda"
        elif s.startswith("with "):
            cat = "with"
        elif s.startswith("raise ") or " raise " in s:
            cat = "raise"
        elif s.startswith('f"') or s.startswith("f'") or ' = f"' in s or " = f'" in s:
            cat = "fstring"
        elif "assert" in s:
            cat = "assert"
        elif "[" in s and "]" in s:
            cat = "index/slice"
        elif "new " in s:
            cat = "new"
        elif s.startswith("for ") or s.startswith("while "):
            cat = "loop"
        elif s.startswith("if ") or s.startswith("elif ") or s.startswith("else"):
            cat = "if"
        elif "=" in s:
            cat = "assign"
        else:
            cat = "other"
        skips[cat] += 1
        if len(samples[cat]) < 4:
            samples[cat].append(s[:120])

print("TOTAL_SKIPS", sum(skips.values()))
for k, v in skips.most_common():
    print(f"{v:4d} {k}")
    for s in samples[k]:
        print("    ", s)
