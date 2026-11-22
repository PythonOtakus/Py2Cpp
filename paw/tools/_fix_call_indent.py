# -*- coding: utf-8 -*-
from pathlib import Path

p = Path("compiler/paw/mid/emit_cpp.paw")
lines = p.read_text(encoding="utf-8").splitlines(True)
start = None
end = None
for i, l in enumerate(lines):
  if l.startswith("    if (not isCallShape) or rp0 < 0:"):
    start = i
  if start is not None and end is None and i > start and l.startswith("  # ``names[i]``"):
    end = i
    break
if start is None or end is None:
  raise SystemExit(f"markers not found start={start} end={end}")

chunk = lines[start + 3 : end]  # from callee0 through last return ""
out_chunk = []
for j, l in enumerate(chunk):
  if j < 2:
    out_chunk.append(l)
  elif l.strip() == "":
    out_chunk.append(l)
  else:
    out_chunk.append("  " + l)

new_block = ["    if isCallShape:\n"] + out_chunk
lines = lines[:start] + new_block + lines[end:]
p.write_text("".join(lines), encoding="utf-8")
print("ok", start, end, "new_len", len(new_block))
