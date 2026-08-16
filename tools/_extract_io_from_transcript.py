#!/usr/bin/env python3
import json
from pathlib import Path

p = Path(
  r"C:\Users\Anantian\.cursor\projects\c-Users-Anantian-source-repos-Py2Cpp"
  r"\agent-transcripts\afb7df37-3f7b-4d19-a834-1768d2e3e465"
  r"\afb7df37-3f7b-4d19-a834-1768d2e3e465.jsonl"
)
out = Path("tools/_extracted_io_patches.txt")
chunks: list[str] = []
for i, line in enumerate(p.open(encoding="utf-8")):
  if "wrap_std" not in line and "wrap_fp" not in line and "isatty" not in line:
    continue
  try:
    obj = json.loads(line)
  except Exception:
    continue
  for part in obj.get("message", {}).get("content", []):
    if part.get("type") != "tool_use":
      continue
    name = part.get("name")
    if name not in ("Write", "StrReplace"):
      continue
    inp = part.get("input", {})
    path = (inp.get("path") or "").replace("\\", "/")
    if "/io/" not in path and not path.endswith("/+io.inl") and "+io.inl" not in path:
      continue
    chunks.append(f"=== line {i} {name} {path} ===\n")
    if name == "Write":
      c = inp.get("contents") or ""
      chunks.append(c[:12000] + ("\n...TRUNC...\n" if len(c) > 12000 else ""))
    else:
      chunks.append("OLD:\n" + (inp.get("old_string") or "")[:2000] + "\n")
      chunks.append("NEW:\n" + (inp.get("new_string") or "")[:4000] + "\n")
out.write_text("\n".join(chunks), encoding="utf-8")
print(f"wrote {out} ({len(chunks)} chunks)")
