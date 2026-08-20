"""FBX ASCII 子集读写（Vertices → ``Mesh``）。二进制 FBX 本阶段不解析。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.io.path import Path
from py2cpp.spatial.color import Color

from ..render.mesh import Mesh

_FBX_SUFFIX: str = ".fbx"


@copyable
@dataclass
class _FbxScan:
  pos: int = 0
  value: float64 = 0.0


def _ensure_fbx(path: str) -> str:
  p: Path = new(path)
  if p.suffix == _FBX_SUFFIX:
    return path
  if not p.suffix:
    out: str = path
    out += _FBX_SUFFIX
    return out
  return path


def _skip_spaces(s: str, i: int) -> int:
  n: int = len(s)
  for k in range(i, n):
    c: str = s[k : k + 1]
    if c not in " \t\n\r":
      return k
  return n


def _parse_float_at(s: str, scan: _FbxScan @ref) -> None:
  i: int = _skip_spaces(s, scan.pos)
  n: int = len(s)
  start: int = i
  if i < n:
    c0: str = s[i : i + 1]
    if c0 in "-+":
      i += 1
  for j in range(i, n):
    c1: str = s[j : j + 1]
    if not (c1 >= "0" and c1 <= "9"):
      i = j
      break
    i = j + 1
  else:
    i = n
  if i < n and s[i : i + 1] == ".":
    i += 1
    for j2 in range(i, n):
      c2: str = s[j2 : j2 + 1]
      if not (c2 >= "0" and c2 <= "9"):
        i = j2
        break
      i = j2 + 1
    else:
      i = n
  if i <= start:
    scan.pos = i
    scan.value = 0.0
    return
  scan.value = float(s[start:i])
  scan.pos = i


def _find_vertices_body(text: str) -> str:
  pos: int = text.find("Vertices")
  if pos < 0:
    return ""
  apos: int = text.find("a:", pos)
  if apos < 0:
    return ""
  depth: int = 0
  start: int = -1
  n: int = len(text)
  for i in range(apos + 2, n):
    ch: str = text[i : i + 1]
    if ch == "{":
      if depth == 0:
        start = i + 1
      depth += 1
    elif ch == "}":
      depth -= 1
      if depth == 0 and start >= 0:
        return text[start:i]
  end: int = text.find("\n", apos)
  if end < 0:
    end = n
  return text[apos + 2 : end]


def _parse_number_list(body: str) -> list[float64]:
  out: list[float64] = []
  scan: _FbxScan = new()
  scan.pos = 0
  n: int = len(body)
  while scan.pos < n:
    scan.pos = _skip_spaces(body, scan.pos)
    if scan.pos >= n:
      break
    c: str = body[scan.pos : scan.pos + 1]
    if c in ",;":
      scan.pos += 1
      continue
    if (c >= "0" and c <= "9") or c in "-+.":
      _parse_float_at(body, scan)
      out.append(scan.value)
      continue
    scan.pos += 1
  return out


def mesh_from_fbx_ascii(text: str, color: Color) -> Mesh:
  body: str = _find_vertices_body(text)
  nums: list[float64] = _parse_number_list(body)
  if len(nums) < 9:
    return new.colored_cube(1.0, color)
  pos_count: int = len(nums) // 3
  verts: list[float64] = []
  r: float64 = color.r
  g: float64 = color.g
  b: float64 = color.b
  t: int = 0
  while t + 2 < pos_count:
    for k in range(3):
      base: int = (t + k) * 3
      verts.append(nums[base])
      verts.append(nums[base + 1])
      verts.append(nums[base + 2])
      verts.append(r)
      verts.append(g)
      verts.append(b)
    t += 3
  if not verts:
    return new.colored_cube(1.0, color)
  m: Mesh = new()
  m.vertices = verts
  m.vertex_count = len(verts) // 6
  return m


def mesh_to_fbx_ascii(mesh: Mesh) -> str:
  n: int = mesh.vertex_count
  out: str = "; FBX 7.4.0 project file\n; Zeus ASCII subset\n"
  out += "FBXHeaderExtension:  {\n  FBXHeaderVersion: 1003\n}\n"
  out += "Geometry: 0, \"Geometry::mesh\", \"Mesh\" {\n"
  out += "  Vertices: *" + str(n * 3) + " {\n    a: "
  first: bool = True
  for i in range(n):
    base: int = i * 6
    if not first:
      out += ","
    first = False
    out += str(mesh.vertices[base]) + "," + str(mesh.vertices[base + 1]) + "," + str(
      mesh.vertices[base + 2]
    )
  out += "\n  }\n}\n"
  return out


def read_fbx(path: str, color: Color) -> Mesh:
  p: str = _ensure_fbx(path)
  doc: Path = new(p)
  if doc.suffix != _FBX_SUFFIX:
    return new.colored_cube(1.0, color)
  if not doc.exists():
    return new.colored_cube(1.0, color)
  return mesh_from_fbx_ascii(doc.readText(), color)


def write_fbx(mesh: Mesh, path: str) -> str:
  p: str = _ensure_fbx(path)
  doc: Path = new(p)
  doc.writeText(mesh_to_fbx_ascii(mesh))
  return p
