"""编译期 ``static_assert`` 文案（与 ``translation_error`` 的 ``翻译失败:`` 对称）。

MSVC 编译须带 ``/utf-8``（见 ``compile._cmd_msvc_cl``），否则 UTF-8 字面量可能报 C2001。
"""
from __future__ import annotations

# 与 ``format_translation_failure`` 的 ``翻译失败:`` 前缀对应
COMPILE_DIAG_PREFIX = "编译期"


def compile_diag_location_prefix(display: str, lineno: int, *, col_offset: int | None = None) -> str:
  """与 ``SourceLocation.prefix()`` 一致的位置前缀（含尾部 ``: ``）。"""
  if lineno <= 0:
    return ""
  base = f"{display}:{lineno}"
  if col_offset is not None:
    base += f":{col_offset + 1}"
  return f"{base}: "


def compile_diag_type_param_decorator(
  param: str,
  decorator: str,
  *,
  loc_prefix: str = "",
) -> str:
  """类/函数模板形参装饰器约束（``T: refcount`` 等）。"""
  return (
    f"{loc_prefix}{COMPILE_DIAG_PREFIX}: 类型参数 {param} 须为 @{decorator} 类"
  )


def compile_diag_type_param_protocol(
  param: str,
  protocol: str,
  *,
  loc_prefix: str = "",
) -> str:
  """类/别名模板形参约束（写入 ``static_assert`` 字符串字面量）。"""
  return (
    f"{loc_prefix}{COMPILE_DIAG_PREFIX}: 类型参数 {param} 须满足 @protocol {protocol}"
  )


def compile_diag_protocol_unsatisfied(protocol: str) -> str:
  """``Protocol_verify<T>`` 显式校验。"""
  return f"{COMPILE_DIAG_PREFIX}: 类型 T 不满足 @protocol {protocol}"


def compile_diag_descriptor_protocol(
  cpp_type: str,
  protocol: str,
  *,
  loc_prefix: str = "",
) -> str:
  """泛型 ``@descriptor`` 内联后，对宿主具体值类型的 ``static_assert`` 文案。"""
  return (
    f"{loc_prefix}{COMPILE_DIAG_PREFIX}: 描述符值类型 {cpp_type} 须满足 @protocol {protocol}"
  )


def compile_diag_py2cpp_getattr(attr: str, *, loc_prefix: str = "") -> str:
  """``PY2CPP_GETATTR`` 完整 ``static_assert`` 文案（含可选 ``file:line: `` 前缀）。"""
  return (
    f"{loc_prefix}{COMPILE_DIAG_PREFIX}: PY2CPP_GETATTR: 无法读取成员 '{attr}'"
    f"{compile_diag_py2cpp_getattr_fail_hint()}"
  )


def compile_diag_py2cpp_getattr_fail_hint() -> str:
  """``PY2CPP_GETATTR`` 兜底 ``static_assert`` 后缀（成员名已在前文引号内）。"""
  return "（须有 get_<成员>()/@property，或公开字段；指针接收者用 ->）"


def compile_diag_py2cpp_setattr(attr: str, *, loc_prefix: str = "") -> str:
  """``PY2CPP_SETATTR`` 完整 ``static_assert`` 文案。"""
  return (
    f"{loc_prefix}{COMPILE_DIAG_PREFIX}: PY2CPP_SETATTR: 无法写入成员 '{attr}'"
    f"{compile_diag_py2cpp_setattr_fail_hint()}"
  )


def compile_diag_py2cpp_setattr_fail_hint() -> str:
  """``PY2CPP_SETATTR`` 兜底 ``static_assert`` 后缀。"""
  return "（须有 set_<成员>()/@property.setter，或可变字段；指针接收者用 ->）"


def compile_diag_py2cpp_call(method: str, *, loc_prefix: str = "", arg_count: int = 0) -> str:
  """``PY2CPP_CALL`` 完整 ``static_assert`` 文案。"""
  if arg_count <= 0:
    suffix = compile_diag_py2cpp_call_fail_hint()
  else:
    suffix = compile_diag_py2cpp_call_fail_hint_n(arg_count)
  return (
    f"{loc_prefix}{COMPILE_DIAG_PREFIX}: PY2CPP_CALL: 无法调用 '{method}'{suffix}"
  )


def compile_diag_py2cpp_call_fail_hint() -> str:
  """``PY2CPP_CALL`` 无参/零参探测失败后缀。"""
  return "（须为可调用的成员方法；指针接收者用 ->）"


def compile_diag_py2cpp_call_fail_hint_n(n: int) -> str:
  """``PY2CPP_CALL`` 带实参探测失败后缀。"""
  return f"（{n} 个实参无匹配的可调用成员）"


def compile_diag_cpp_string(message: str) -> str:
  """转义后嵌入 C++ ``\"...\"``（仅用于非宏、由译器直接写入的 ``static_assert``）。"""
  return message.replace("\\", "\\\\").replace('"', '\\"')


def compile_diag_c_utf8_literal(message: str) -> str:
  """ASCII 安全的 UTF-8 字面量（``\\xHH``）。

  用于 ``static_assert`` / 宏后缀，避免源文件内嵌中文 + 宏拼接在 MSVC 下显示为 ``?``。
  编译须 ``cl /utf-8``（见 ``compile._cmd_msvc_cl``）；终端建议 UTF-8（如 ``chcp 65001``）。
  """
  body = "".join(f"\\x{b:02x}" for b in message.encode("utf-8"))
  return f'"{body}"'
