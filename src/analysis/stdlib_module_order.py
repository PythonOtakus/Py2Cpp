"""bootstrap 后按 ``ModuleAnalysis`` include 图重排 ``stdlib_modules_for_umbrella``。"""
from __future__ import annotations

from collections.abc import Sequence

from ..constant.stdlib_discovery import STDLIB_REL_PATH_SET, _stdlib_tier_index
from ..constant.stdlib_modules import UMBRELLA_PREFIX_TIERS
from ..constant.stdlib_layout import CORE_PKG, RUNTIME_PKG, stdlib_module_path
from .ir import ModuleAnalysis

_PROTOCOL_TRAITS_H = f"{CORE_PKG}/protocol_traits.h"


def header_path_to_stdlib_rel(header: str) -> str | None:
  """``py2cpp/util/list.h`` → ``util/list``；非标准库头返回 ``None``。"""
  h = header.strip().strip('"')
  if not h or h.startswith("<"):
    return None
  if h == _PROTOCOL_TRAITS_H:
    return "core/protocols"
  prefix = f"{RUNTIME_PKG}/"
  if not h.startswith(prefix) or not h.endswith(".h"):
    return None
  rel = h[len(prefix) : -2]
  if rel in STDLIB_REL_PATH_SET:
    return rel
  return None


def _module_header_deps(
  rel_mod: str,
  module_analysis: dict[str, ModuleAnalysis],
  module_set: frozenset[str],
) -> frozenset[str]:
  mp = stdlib_module_path(rel_mod)
  ma = module_analysis.get(mp)
  deps: set[str] = set()
  if ma is not None:
    for h in (*ma.includes, *ma.post_class_includes):
      dep = header_path_to_stdlib_rel(h)
      if dep is not None and dep != rel_mod and dep in module_set:
        deps.add(dep)
  # ``console`` 包根 ``using`` 再导出子模块异常/类型，子头须先于包根。
  # 勿对所有 ``pkg``/``pkg/child`` 一律子先父后（``math/complex`` 依赖 ``math`` 中 ``math_sin`` 等）。
  if rel_mod == "console":
    for other in module_set:
      if other.startswith("console/"):
        deps.add(other)
  # ``task`` 依赖 ``popen``（``CompletedProcess`` / ``Popen``）；类型 include 图常漏边。
  if rel_mod == "console/task" and "console/popen" in module_set:
    deps.add("console/popen")
  return frozenset(deps)


def _topo_sort_tier(
  tier_mods: list[str],
  must_before: dict[str, frozenset[str]],
  base_rank: dict[str, int],
) -> list[str]:
  """``must_before[m]``：须在 ``m`` 之前出现的模块（同 tier 子集）。"""
  tier_set = frozenset(tier_mods)
  in_degree = {m: 0 for m in tier_mods}
  adj: dict[str, list[str]] = {m: [] for m in tier_mods}
  for m in tier_mods:
    for dep in must_before[m]:
      if dep not in tier_set:
        continue
      adj[dep].append(m)
      in_degree[m] += 1
  ready = sorted((m for m in tier_mods if in_degree[m] == 0), key=lambda x: base_rank[x])
  out: list[str] = []
  while ready:
    m = ready.pop(0)
    out.append(m)
    for nxt in sorted(adj[m], key=lambda x: base_rank[x]):
      in_degree[nxt] -= 1
      if in_degree[nxt] == 0:
        ready.append(nxt)
        ready.sort(key=lambda x: base_rank[x])
  if len(out) < len(tier_mods):
    seen = frozenset(out)
    for m in sorted(tier_mods, key=lambda x: base_rank[x]):
      if m not in seen:
        out.append(m)
  return out


def order_stdlib_modules_by_header_deps(
  modules: Sequence[str],
  module_analysis: dict[str, ModuleAnalysis],
) -> tuple[str, ...]:
  """在 ``UMBRELLA_PREFIX_TIERS`` 约束下，按 include 依赖对每个 tier 拓扑排序。"""
  mods = [m for m in modules if m in STDLIB_REL_PATH_SET]
  module_set = frozenset(mods)
  base_rank = {m: i for i, m in enumerate(mods)}
  must_before = {m: _module_header_deps(m, module_analysis, module_set) for m in mods}
  tier_count = len(UMBRELLA_PREFIX_TIERS) + 1
  buckets: list[list[str]] = [[] for _ in range(tier_count)]
  for m in mods:
    buckets[_stdlib_tier_index(m)].append(m)
  ordered: list[str] = []
  for tier_mods in buckets:
    if not tier_mods:
      continue
    ordered.extend(_topo_sort_tier(tier_mods, must_before, base_rank))
  # 环回退时 base_rank 可能仍把 task 排在 popen 前；编译期 using 需要 popen 先完整可见。
  if "console/popen" in ordered and "console/task" in ordered:
    popen_at = ordered.index("console/popen")
    task_at = ordered.index("console/task")
    if popen_at > task_at:
      ordered.insert(task_at, ordered.pop(popen_at))
  return tuple(ordered)


def reorder_stdlib_modules_for_umbrella(translator) -> None:
  """``analyze`` 之后、写 ``minimal.h`` 之前更新 ``stdlib_modules_for_umbrella``。"""
  if not translator.stdlib_modules_for_umbrella:
    return
  if not translator._is_runtime_bootstrap():
    return
  ordered = order_stdlib_modules_by_header_deps(
    translator.stdlib_modules_for_umbrella,
    translator.module_analysis,
  )
  translator.stdlib_modules_for_umbrella = ordered
