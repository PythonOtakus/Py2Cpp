"""``@protocol`` AST 扫描入口（模块路径 + 排除类名）。"""

PROTOCOL_SCAN_REL_PATHS: tuple[str, ...] = (
  "core/protocols",
  "alg/protocols",
  "io/protocols",
  "serde/protocols",
  "sql/protocols",
  "util/allocator",
)

PROTOCOL_PARAM_ERASE_EXCLUDE: frozenset[str] = frozenset({"Equatable"})
