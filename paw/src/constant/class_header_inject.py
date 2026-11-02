"""类声明 public 段末尾注入规格（异常类等；``str`` 等见 ``templates/**/+*.h``）。"""

CLASS_HEADER_INJECT_SPECS: dict[str, tuple[str, ...]] = {
  "ExceptionGroup": ("exception_group_header",),
}
