"""SyntaxModule → HirModule → MidModule。"""
from __future__ import annotations

from compiler.py.frontend.syntax_nodes import (
  ClassDecl,
  ConstField,
  EnumDecl,
  FieldDecl,
  FunctionDecl,
  ImportStmt,
  ModuleConstDecl,
  OpaqueMember,
  OpaqueStmt,
  SyntaxModule,
)
from compiler.py.hir.nodes import (
  HirClass,
  HirEnum,
  HirEnumMember,
  HirFunction,
  HirImport,
  HirModule,
  HirModuleConst,
  HirOpaque,
)
from compiler.py.mid.nodes import (
  MidClass,
  MidEnum,
  MidFunction,
  MidImport,
  MidModule,
  MidModuleConst,
  MidOpaque,
)


def bind_module(syntax: SyntaxModule, *, path: str = "<memory>") -> HirModule:
  decls = []
  next_id = 1
  diagnostics = list(syntax.unsupported)

  for item in syntax.items:
    if isinstance(item, EnumDecl):
      decls.append(
        HirEnum(
          decl_id=next_id,
          name=item.name,
          is_type_enum=item.is_type_enum,
          flag=item.flag,
          members=[
            HirEnumMember(m.name, m.value_source, m.span) for m in item.members
          ],
          span=item.span,
          base_source=item.base_source,
        )
      )
      next_id += 1
    elif isinstance(item, ClassDecl):
      consts: list[tuple[str, str | None, str, object]] = []
      fields: list[tuple[str, str | None, str, object]] = []
      opaques: list[tuple[str, object]] = []
      methods: list[HirFunction] = []
      for mem in item.members:
        if isinstance(mem, ConstField):
          typ = None
          if mem.type_syntax is not None:
            from compiler.py.frontend.type_parse import type_syntax_to_source

            typ = type_syntax_to_source(mem.type_syntax)
          consts.append((mem.name, typ, mem.value_source, mem.span))
        elif isinstance(mem, FieldDecl):
          typ = None
          if mem.type_syntax is not None:
            from compiler.py.frontend.type_parse import type_syntax_to_source

            typ = type_syntax_to_source(mem.type_syntax)
          fields.append((mem.name, typ, mem.value_source, mem.span))
        elif isinstance(mem, FunctionDecl):
          methods.append(
            HirFunction(
              decl_id=next_id,
              name=mem.name,
              decorators_source=mem.decorators_source,
              params_source=mem.params_source,
              return_source=mem.return_source,
              body_source=mem.body_source,
              is_async=mem.is_async,
              span=mem.span,
              is_static=mem.is_static,
              is_native=mem.is_native,
              is_override=mem.is_override,
              is_final=mem.is_final,
              is_abstract=mem.is_abstract,
              is_virtual=mem.is_virtual,
              is_delegate=mem.is_delegate,
              is_property=mem.is_property,
              params=list(mem.params),
              body=list(mem.body),
              type_params_source=mem.type_params_source,
            )
          )
          next_id += 1
        elif isinstance(mem, OpaqueMember):
          opaques.append((mem.source, mem.span))
      decls.append(
        HirClass(
          decl_id=next_id,
          name=item.name,
          object_model=item.object_model,
          is_final=item.is_final,
          is_record=item.is_record,
          is_frozen=item.is_frozen,
          is_ordered=item.is_ordered,
          is_lazy=item.is_lazy,
          is_protocol=item.is_protocol,
          is_mixin=item.is_mixin,
          is_union=item.is_union,
          is_variant=item.is_variant,
          bases_source=item.bases_source,
          const_fields=consts,  # type: ignore[arg-type]
          fields=fields,  # type: ignore[arg-type]
          opaque_members=opaques,  # type: ignore[arg-type]
          span=item.span,
          decorators_source=item.decorators_source,
          is_native=item.is_native,
          methods=methods,
          type_params_source=item.type_params_source,
        )
      )
      next_id += 1
    elif isinstance(item, FunctionDecl):
      decls.append(
        HirFunction(
          decl_id=next_id,
          name=item.name,
          decorators_source=item.decorators_source,
          params_source=item.params_source,
          return_source=item.return_source,
          body_source=item.body_source,
          is_async=item.is_async,
          span=item.span,
          is_static=item.is_static,
          is_native=item.is_native,
          is_override=item.is_override,
          is_final=item.is_final,
          is_abstract=item.is_abstract,
          is_virtual=item.is_virtual,
          is_delegate=item.is_delegate,
          is_property=item.is_property,
          params=list(item.params),
          body=list(item.body),
          type_params_source=item.type_params_source,
        )
      )
      next_id += 1
    elif isinstance(item, ImportStmt):
      decls.append(HirImport(source=item.source, span=item.span))
    elif isinstance(item, ModuleConstDecl):
      typ = None
      if item.type_syntax is not None:
        from compiler.py.frontend.type_parse import type_syntax_to_source

        typ = type_syntax_to_source(item.type_syntax)
      decls.append(
        HirModuleConst(
          name=item.name,
          type_name=typ,
          value_source=item.value_source,
          span=item.span,
        )
      )
    elif isinstance(item, OpaqueStmt):
      decls.append(HirOpaque(source=item.source, span=item.span))
    else:
      diagnostics.append(f"unbound syntax item: {type(item).__name__}")

  return HirModule(
    path=path,
    decls=decls,
    span=syntax.span,
    diagnostics=diagnostics,
  )


def lower_to_mid(hir: HirModule) -> MidModule:
  items = []
  for d in hir.decls:
    if isinstance(d, HirEnum):
      items.append(
        MidEnum(
          decl_id=d.decl_id,
          name=d.name,
          is_type_enum=d.is_type_enum,
          flag=d.flag,
          members=[(m.name, m.value_source) for m in d.members],
          span=d.span,
          base_source=d.base_source,
        )
      )
    elif isinstance(d, HirClass):
      items.append(
        MidClass(
          decl_id=d.decl_id,
          name=d.name,
          object_model=d.object_model,
          is_final=d.is_final,
          is_record=d.is_record,
          is_frozen=d.is_frozen,
          is_ordered=d.is_ordered,
          is_lazy=d.is_lazy,
          is_protocol=d.is_protocol,
          is_mixin=d.is_mixin,
          is_union=d.is_union,
          is_variant=d.is_variant,
          bases_source=d.bases_source,
          const_fields=[(n, t, v) for n, t, v, _sp in d.const_fields],
          fields=[(n, t, v) for n, t, v, _sp in d.fields],
          opaque_members=[src for src, _sp in d.opaque_members],
          span=d.span,
          decorators_source=d.decorators_source,
          is_native=d.is_native,
          methods=[
            MidFunction(
              decl_id=m.decl_id,
              name=m.name,
              decorators_source=m.decorators_source,
              params_source=m.params_source,
              return_source=m.return_source,
              body_source=m.body_source,
              is_async=m.is_async,
              span=m.span,
              is_static=m.is_static,
              is_native=m.is_native,
              is_override=m.is_override,
              is_final=m.is_final,
              is_abstract=m.is_abstract,
              is_virtual=m.is_virtual,
              is_delegate=m.is_delegate,
              is_property=m.is_property,
              params=list(m.params),
              body=list(m.body),
              type_params_source=m.type_params_source,
            )
            for m in d.methods
          ],
          type_params_source=d.type_params_source,
        )
      )
    elif isinstance(d, HirFunction):
      items.append(
        MidFunction(
          decl_id=d.decl_id,
          name=d.name,
          decorators_source=d.decorators_source,
          params_source=d.params_source,
          return_source=d.return_source,
          body_source=d.body_source,
          is_async=d.is_async,
          span=d.span,
          is_static=d.is_static,
          is_native=d.is_native,
          is_override=d.is_override,
          is_final=d.is_final,
          is_abstract=d.is_abstract,
          is_virtual=d.is_virtual,
          is_delegate=d.is_delegate,
          is_property=d.is_property,
          params=list(d.params),
          body=list(d.body),
          type_params_source=d.type_params_source,
        )
      )
    elif isinstance(d, HirImport):
      items.append(MidImport(source=d.source, span=d.span))
    elif isinstance(d, HirModuleConst):
      items.append(
        MidModuleConst(
          name=d.name,
          type_name=d.type_name,
          value_source=d.value_source,
          span=d.span,
        )
      )
    elif isinstance(d, HirOpaque):
      items.append(MidOpaque(source=d.source, span=d.span))
  return MidModule(
    path=hir.path,
    items=items,
    span=hir.span,
    diagnostics=list(hir.diagnostics),
  )
