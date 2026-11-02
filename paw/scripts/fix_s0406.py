"""One-off: move literal self.field assigns from __init__/_init* to class body defaults."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _is_literal(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Constant):
        return True
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.USub):
        return isinstance(expr.operand, ast.Constant) and isinstance(expr.operand.value, (int, float))
    return False


def _field_from_target(target: ast.expr) -> str | None:
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self':
        return target.attr
    return None


def _init_method(name: str) -> bool:
    return name == '__init__' or name.startswith('_init')


def _literal_src(src: str, node: ast.expr) -> str:
    return ast.get_source_segment(src, node) or ast.unparse(node)


def _field_line(field: str, ann_src: str | None, val_src: str) -> str:
    if ann_src:
        return f'  {field}: {ann_src} = {val_src}'
    return f'  {field} = {val_src}'


def fix_file(path: Path) -> int:
    src = path.read_text(encoding='utf-8')
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    changed = 0

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        inserts: list[tuple[int, str]] = []
        removes: set[int] = set()
        existing_defaults = {
            stmt.target.id
            for stmt in node.body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None
        }
        existing_defaults |= {
            stmt.target.attr
            for stmt in node.body
            if isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Attribute)
            and isinstance(stmt.target.value, ast.Name)
            and stmt.target.value.id == 'self'
            and stmt.value is not None
        }

        for stmt in node.body:
            if not isinstance(stmt, ast.FunctionDef) or not _init_method(stmt.name):
                continue
            for inner in stmt.body:
                field: str | None = None
                val_src: str | None = None
                ann_src: str | None = None
                if isinstance(inner, ast.Assign) and len(inner.targets) == 1:
                    field = _field_from_target(inner.targets[0])
                    if field and _is_literal(inner.value):
                        val_src = _literal_src(src, inner.value)
                elif isinstance(inner, ast.AnnAssign) and _is_literal(inner.value or ast.Constant(value=None)):
                    field = _field_from_target(inner.target)
                    if field and inner.value is not None and _is_literal(inner.value):
                        ann_src = ast.get_source_segment(src, inner.annotation) or ast.unparse(inner.annotation)
                        val_src = _literal_src(src, inner.value)
                if not field or not val_src or field in existing_defaults:
                    continue
                # insert before first method or at end of fields
                insert_at = node.body[0].lineno - 1
                for i, child in enumerate(node.body):
                    if isinstance(child, ast.FunctionDef):
                        insert_at = child.lineno - 1
                        break
                    insert_at = child.end_lineno
                inserts.append((insert_at, _field_line(field, ann_src, val_src) + '\n'))
                removes.add(inner.lineno - 1)
                existing_defaults.add(field)
                changed += 1

        if not inserts and not removes:
            continue
        new_lines = list(lines)
        for lineno in sorted(removes, reverse=True):
            new_lines[lineno] = ''
        for insert_at, text in sorted(inserts, key=lambda x: x[0], reverse=True):
            new_lines.insert(insert_at, text)
        lines = new_lines

    if changed:
        path.write_text(''.join(lines), encoding='utf-8')
    return changed


def main(argv: list[str]) -> int:
    files = [Path(p) for p in argv[1:]] if len(argv) > 1 else []
    if not files:
        files = [ROOT / 's0406_violations.txt']
        text = files[0].read_text(encoding='utf-8')
        files = sorted({ROOT / line.split(':', 1)[0] for line in text.splitlines() if line.strip()})
    total = 0
    for path in files:
        n = fix_file(path)
        if n:
            print(f'{path.relative_to(ROOT)}: {n}')
            total += n
    print(f'total: {total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
