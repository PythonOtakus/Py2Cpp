"""One-off: merge ``x: T = new(); x.f = …`` into ``x: T = new(f=…)``."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _is_empty_new(expr: ast.expr | None) -> bool:
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == 'new'
        and not expr.args
        and not expr.keywords
    )


def _try_field_assign(stmt: ast.stmt, var_name: str) -> tuple[str, ast.expr] | None:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Attribute):
        return None
    if not isinstance(tgt.value, ast.Name) or tgt.value.id != var_name:
        return None
    if tgt.attr.startswith('_'):
        return None
    return tgt.attr, stmt.value


def _walk_stmt_lists(node: ast.AST):
    if isinstance(node, ast.Module):
        yield node.body
        for stmt in node.body:
            yield from _walk_stmt_lists(stmt)
    elif isinstance(node, ast.ClassDef):
        for stmt in node.body:
            yield from _walk_stmt_lists(stmt)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        yield node.body
        for stmt in node.body:
            yield from _walk_stmt_lists(stmt)
    elif isinstance(node, ast.If):
        yield node.body
        yield node.orelse
        for stmt in node.body + node.orelse:
            yield from _walk_stmt_lists(stmt)
    elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        yield node.body
        yield node.orelse
        for stmt in node.body + node.orelse:
            yield from _walk_stmt_lists(stmt)
    elif isinstance(node, ast.With) or (hasattr(ast, 'AsyncWith') and isinstance(node, ast.AsyncWith)):
        yield node.body
        for stmt in node.body:
            yield from _walk_stmt_lists(stmt)
    elif isinstance(node, ast.Try):
        yield node.body
        yield node.orelse
        yield node.finalbody
        for stmt in node.body + node.orelse + node.finalbody:
            yield from _walk_stmt_lists(stmt)
        for handler in node.handlers:
            yield handler.body
            for stmt in handler.body:
                yield from _walk_stmt_lists(stmt)
    elif isinstance(node, ast.Match):
        for case in node.cases:
            yield case.body
            for stmt in case.body:
                yield from _walk_stmt_lists(stmt)


def _segment(src: str, node: ast.AST) -> str:
    seg = ast.get_source_segment(src, node)
    if seg is not None:
        return seg
    return ast.unparse(node)


def fix_file(path: Path) -> int:
    src = path.read_text(encoding='utf-8')
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    removes: set[int] = set()
    replacements: dict[int, str] = {}
    changed = 0

    for body in _walk_stmt_lists(tree):
        i = 0
        while i < len(body):
            stmt = body[i]
            if not (
                isinstance(stmt, ast.AnnAssign)
                and stmt.value is not None
                and _is_empty_new(stmt.value)
                and isinstance(stmt.target, ast.Name)
            ):
                i += 1
                continue
            var_name = stmt.target.id
            assigns: list[tuple[str, ast.expr]] = []
            j = i + 1
            while j < len(body):
                hit = _try_field_assign(body[j], var_name)
                if hit is None:
                    break
                assigns.append(hit)
                j += 1
            if not assigns:
                i += 1
                continue
            lineno = stmt.lineno
            line = lines[lineno - 1]
            indent = line[: len(line) - len(line.lstrip())]
            ann = _segment(src, stmt.annotation)
            kws = ', '.join(f'{field}={_segment(src, rhs)}' for field, rhs in assigns)
            replacements[lineno] = f'{indent}{var_name}: {ann} = new({kws})\n'
            for k in range(i + 1, j):
                removes.add(body[k].lineno)
            changed += 1
            i = j

    if not changed:
        return 0
    out: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if idx in removes:
            continue
        if idx in replacements:
            out.append(replacements[idx])
        else:
            out.append(line)
    path.write_text(''.join(out), encoding='utf-8')
    return changed


def main(argv: list[str]) -> int:
    targets = [Path(p) for p in argv[1:]] if len(argv) > 1 else [ROOT / 'py2cpp']
    total = 0
    for target in targets:
        files = [target] if target.is_file() else sorted(target.rglob('*.py'))
        for path in files:
            n = fix_file(path)
            if n:
                rel = path
                try:
                    rel = path.relative_to(ROOT)
                except ValueError:
                    pass
                print(f'{rel}: {n}')
                total += n
    print(f'fixed {total} site(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
