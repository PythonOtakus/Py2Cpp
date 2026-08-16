"""Scan @enum/@union/@protocol/@mixin/@annotation/@descriptor and exception-like classes."""
from __future__ import annotations

import ast
from pathlib import Path


def _decorator_info(dec: ast.AST) -> tuple[str, bool] | None:
    """Return (kind, flag) where kind is enum|enum.mro|union|union.mro|protocol|mixin|annotation|descriptor."""
    if isinstance(dec, ast.Name) and dec.id in {
        "enum",
        "union",
        "protocol",
        "mixin",
        "annotation",
        "descriptor",
    }:
        return dec.id, False
    if (
        isinstance(dec, ast.Attribute)
        and isinstance(dec.value, ast.Name)
        and dec.value.id in {"enum", "union"}
        and dec.attr == "mro"
    ):
        return f"{dec.value.id}.mro", False
    if isinstance(dec, ast.Call):
        if isinstance(dec.func, ast.Name) and dec.func.id in {
            "enum",
            "union",
            "protocol",
            "mixin",
            "annotation",
            "descriptor",
        }:
            flag = False
            if dec.func.id == "enum":
                for kw in dec.keywords:
                    if (
                        kw.arg == "flag"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        flag = True
            return dec.func.id, flag
        if (
            isinstance(dec.func, ast.Attribute)
            and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id in {"enum", "union"}
            and dec.func.attr == "mro"
        ):
            return f"{dec.func.value.id}.mro", False
    return None


def _looks_like_exception(node: ast.ClassDef) -> bool:
    if node.name in {"Exception", "Error"}:
        return True
    if node.name.endswith(("Error", "Exception", "ExceptionGroup")):
        return True
    for b in node.bases:
        if isinstance(b, ast.Name) and b.id in {
            "Exception",
            "Error",
            "BaseException",
            "OSError",
            "ValueError",
            "RuntimeError",
            "BaseExceptionGroup",
            "ExceptionGroup",
            "ConsoleError",
            "OpenAIError",
            "YamlError",
            "DatabaseError",
            "APIError",
            "TaskError",
            "PymlError",
        }:
            return True
        if isinstance(b, ast.Name) and (
            b.id.endswith("Error") or b.id.endswith("Exception")
        ):
            return True
    return False


def main() -> None:
    roots = ["py2cpp", "test", "examples"]
    for root in roots:
        for p in Path(root).rglob("*.py"):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if not isinstance(n, ast.ClassDef):
                    continue
                kinds = []
                for d in n.decorator_list:
                    info = _decorator_info(d)
                    if info:
                        kinds.append(info)
                if kinds:
                    print(f"{p.as_posix()}:{n.lineno}\t{n.name}\t{kinds}")
                elif _looks_like_exception(n):
                    ok = n.name == "Exception" or n.name.endswith("Error")
                    print(
                        f"{p.as_posix()}:{n.lineno}\t{n.name}\texception ok={ok}"
                    )


if __name__ == "__main__":
    main()
