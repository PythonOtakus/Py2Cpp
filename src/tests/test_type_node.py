"""TypeNode Phase 0：往返、storage、结构匹配。"""
from __future__ import annotations
import ast
import unittest
from src.analysis.analyzer import SignatureBuilder, TypeParser
from src.analysis.ir import ClassInfo
from src.analysis.ir import ClassInfo, cpp_ident
from src.analysis.type_compat import type_node_from_cpp_string, type_node_to_cpp_string
from src.analysis.type_node import TypeKind, TypeNode, structural_match_type_nodes, type_param_names_equivalent
from src.analysis.type_render import CLASS_BODY, TEMPLATE_HEADER
from src.analysis.type_storage import apply_full_storage_type_node, apply_storage_type_node

def _parser_with_dict_entry() -> tuple[TypeParser, dict[str, ClassInfo]]:
    src = '\nfrom py2cpp import DictKey, Self, boxing\n\n@boxing\n@native_name("PyDictEntry")\nclass dict_entry[Key: DictKey, Value]:\n  def __init__(self, key: Key, value: Value, next_entry: Self):\n    self.next: Self = next_entry\n'
    tree = ast.parse(src)
    info = ClassInfo(tree.body[-1], module_path='py2cpp/util/dict.py')
    classes = {'dict_entry': info}
    parser = TypeParser()
    parser.set_classes(classes)
    return (parser, classes)

class TestTypeNodeRoundtrip(unittest.TestCase):

    def test_scalar_and_template_roundtrip(self):
        parser = TypeParser()
        for src, expect_cpp in (('int', cpp_ident('int')), ('str', cpp_ident('str')), ('list[int]', f"{cpp_ident('list')}<{cpp_ident('int')}>")):
            node = ast.parse(src).body[0].value
            tn = parser.parse_type_node(node, set())
            self.assertEqual(tn.render(CLASS_BODY), expect_cpp)
            self.assertEqual(type_node_to_cpp_string(type_node_from_cpp_string(expect_cpp)), expect_cpp)

    def test_template_header_naming(self):
        tn = TypeNode.template('list', cpp_ident('list'), TypeNode.type_param('Element'))
        self.assertEqual(tn.render(TEMPLATE_HEADER), f"{cpp_ident('list')}<_Element>")
        self.assertEqual(tn.render(CLASS_BODY), f"{cpp_ident('list')}<Element>")

    def test_pointer_and_ref_roundtrip(self):
        ptr = type_node_from_cpp_string('PyDictEntry<Key, Value>*')
        self.assertEqual(ptr.render(CLASS_BODY), 'PyDictEntry<Key, Value>*')
        ref = type_node_from_cpp_string('PyTextIOWrapper&')
        self.assertEqual(ref.kind, TypeKind.REF)
        self.assertEqual(ref.render(CLASS_BODY), 'PyTextIOWrapper&')

    def test_pointer_and_array(self):
        inner = TypeNode.template('dict_entry', 'PyDictEntry', TypeNode.type_param('Key'), TypeNode.type_param('Value'))
        ptr = TypeNode.pointer(inner)
        arr = TypeNode.array(ptr, kind='heap')
        self.assertEqual(ptr.render(CLASS_BODY), 'PyDictEntry<Key, Value>*')
        from src.analysis.ir import CPP_ARRAY_PREFIX
        self.assertEqual(arr.render(CLASS_BODY), f'{CPP_ARRAY_PREFIX}PyDictEntry<Key, Value>*>')

class TestTypeNodeStorage(unittest.TestCase):

    def test_boxing_generic_template(self):
        _, classes = _parser_with_dict_entry()
        inner = TypeNode.template('dict_entry', 'PyDictEntry', TypeNode.type_param('Key'), TypeNode.type_param('Value'))
        stored = apply_storage_type_node(inner, classes)
        self.assertEqual(stored.kind, TypeKind.POINTER)
        self.assertEqual(stored.render(CLASS_BODY), 'PyDictEntry<Key, Value>*')

    def test_boxing_array_inner(self):
        _, classes = _parser_with_dict_entry()
        inner = TypeNode.template('dict_entry', 'PyDictEntry', TypeNode.type_param('Key'), TypeNode.type_param('Value'))
        arr = TypeNode.array(inner, kind='heap')
        stored = apply_storage_type_node(arr, classes)
        from src.analysis.ir import CPP_ARRAY_PREFIX
        self.assertEqual(stored.render(CLASS_BODY), f'{CPP_ARRAY_PREFIX}PyDictEntry<Key, Value>*>')

class TestTypeNodeParseBridge(unittest.TestCase):

    def test_parse_type_node_matches_parse_type(self):
        parser, _ = _parser_with_dict_entry()
        for src in (
            'list[int]',
            'dict[str, int]',
            'Function[[int], int]',
            'Callable[[int], int]',
            'Pointer[list[int]]',
            'int | None',
        ):
            ann = ast.parse(src).body[0].value
            self.assertEqual(
                parser.parse_type_node(ann, set()).render(CLASS_BODY),
                parser.parse_type(ann, set()),
                msg=src,
            )

    def test_parse_storage_type_node_matches_parse_storage_type(self):
        parser, classes = _parser_with_dict_entry()
        for src in ('list[int]', 'dict[str, int]', 'Self'):
            ann = ast.parse(src).body[0].value
            tparams = set(classes['dict_entry'].type_params)
            self_class = classes['dict_entry'].template_cpp_type()
            got = parser.parse_storage_type_node(
                ann, tparams, self_class=self_class,
            ).render(CLASS_BODY)
            expect = parser.parse_storage_type(ann, tparams, self_class=self_class)
            self.assertEqual(got, expect, msg=src)

    def test_self_field_storage_matches_string_path(self):
        parser, classes = _parser_with_dict_entry()
        info = classes['dict_entry']
        ann = ast.Name(id='Self')
        tparams = set(info.type_params)
        self_class = info.template_cpp_type()
        semantic = parser.parse_type_node(ann, tparams, self_class=self_class)
        stored_node = apply_full_storage_type_node(semantic, classes)
        semantic_cpp = parser.parse_type(ann, tparams, self_class=self_class)
        from src.analysis.ir import ClassInfo
        stored_cpp = ClassInfo.apply_refcount_storage_cpp_type(semantic_cpp, classes)
        self.assertEqual(stored_node.render(CLASS_BODY), stored_cpp)
        self.assertEqual(stored_node.render(CLASS_BODY), 'PyDictEntry<Key, Value>*')

class TestTypeNodeStructuralMatch(unittest.TestCase):

    def test_type_param_equivalence(self):
        self.assertTrue(type_param_names_equivalent('Key', '_Key'))
        self.assertTrue(type_param_names_equivalent('_Value', 'Value'))

    def test_list_wildcard_bind(self):
        concrete = type_node_from_cpp_string(f"{cpp_ident('list')}<{cpp_ident('int')}>")
        pattern = TypeNode.template('list', cpp_ident('list'), TypeNode.type_param('_V'))
        binds = structural_match_type_nodes(concrete, pattern, frozenset({'_V'}))
        self.assertIsNotNone(binds)
        assert binds is not None
        self.assertEqual(binds['_V'].render(CLASS_BODY), cpp_ident('int'))

class TestTypeNodePhase1DualWrite(unittest.TestCase):

    def test_dict_entry_field_type_nodes_match_strings(self):
        src = '\nfrom py2cpp import DictKey, Self, boxing\n\n@boxing\n@native_name("PyDictEntry")\nclass dict_entry[Key: DictKey, Value]:\n  def __init__(self, key: Key, value: Value, next_entry: Self):\n    self.key: Key = key\n    self.value: Value = value\n    self.next: Self = next_entry\n'
        tree = ast.parse(src)
        info = ClassInfo(tree.body[-1], module_path='py2cpp/util/dict.py')
        classes = {'dict_entry': info}
        parser = TypeParser()
        parser.set_classes(classes)
        sigs = SignatureBuilder(parser)
        sigs.set_classes(classes)
        sigs.resolve_class_field_types(info)
        from src.analysis.type_emit import field_storage_cpp
        from src.analysis.type_render import CLASS_BODY
        for field in info.fields:
            if field.startswith('__ann__'):
                continue
            self.assertIn(field, info.field_type_nodes)
            self.assertEqual(
                info.field_type_nodes[field].render(CLASS_BODY),
                field_storage_cpp(info, field),
            )

class TestParseStorageStackArrayAliasImport(unittest.TestCase):

    def test_float64_slice_not_type_alias_subscript(self):
        import ast
        from src.analysis.analyzer import TypeParser
        from src.analysis.imports import ImportBinding
        from src.analysis.type_pred import is_stack_array_type
        tp = TypeParser()
        tp.set_import_bindings({'float64': ImportBinding(local_name='float64', symbol='float64', module_path='py2cpp/builtins.py', kind='type_alias', cpp_name='float64')})
        ann = ast.parse('u: float64[:3] = [1.0]').body[0].annotation
        cpp = tp.parse_storage_type(ann, set())
        self.assertTrue(is_stack_array_type(cpp))
        self.assertIn('PyStackArray', cpp)

class TestTypeNodePhase3EmitBoundary(unittest.TestCase):

    def _dict_entry_setup(self):
        src = '\nfrom py2cpp import DictKey, Self, boxing\n\n@boxing\n@native_name("PyDictEntry")\nclass dict_entry[Key: DictKey, Value]:\n  def __init__(self, key: Key, value: Value, next_entry: Self):\n    self.key: Key = key\n    self.value: Value = value\n    self.next: Self = next_entry\n'
        tree = ast.parse(src)
        info = ClassInfo(tree.body[-1], module_path='py2cpp/util/dict.py')
        classes = {'dict_entry': info}
        parser = TypeParser()
        parser.set_classes(classes)
        sigs = SignatureBuilder(parser)
        sigs.set_classes(classes)
        sigs.resolve_class_field_types(info)
        init = info.inits[0]
        msig = sigs.build_method_sig(info, init)
        return (info, msig, sigs)

    def test_method_param_and_return_nodes_match_strings(self):
        info, msig, _ = self._dict_entry_setup()
        for name, cpp in msig.param_types.items():
            self.assertIn(name, msig.param_type_nodes)
            self.assertEqual(msig.param_type_nodes[name].render(CLASS_BODY), cpp)
        self.assertEqual(msig.return_type_node.render(CLASS_BODY), msig.ret_lead)

    def test_function_param_type_nodes_match_strings(self):
        src = '\ndef add(a: int, b: int) -> int:\n  return a + b\n'
        func = ast.parse(src).body[0]
        parser = TypeParser()
        sigs = SignatureBuilder(parser)
        fsig = sigs.build_function_sig(func)
        for name, cpp in fsig.param_types.items():
            self.assertIn(name, fsig.param_type_nodes)
            self.assertEqual(fsig.param_type_nodes[name].render(CLASS_BODY), cpp)
        self.assertEqual(fsig.return_type_node.render(CLASS_BODY), fsig.ret_lead)

class TestTypeNodePhase20ScopeStorage(unittest.TestCase):

    def _translator_with_scope(self, scope):
        from src.translator import Translator
        tr = Translator('m', 'm.py')
        tr.scope = scope
        tr.scopes = [scope]
        return tr

    def test_scope_read_prefers_node_over_stale_string_cache(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_emit import (
            lookup_scope_storage_cpp,
            scope_binding_storage_cpp,
            scope_has_param,
            scope_storage_cpp,
        )
        from src.analysis.ir import cpp_ident
        from src.translator import Scope

        scope = Scope(ast.parse('pass').body[0])
        node = type_node_from_cpp_string(cpp_ident('int'))
        scope.param_type_nodes['x'] = node
        scope.param_types['x'] = 'PyStr'

        tr = self._translator_with_scope(scope)
        expect = cpp_ident('int')
        self.assertEqual(scope_binding_storage_cpp(scope, 'x'), expect)
        self.assertEqual(scope_storage_cpp(tr, 'x'), expect)
        self.assertEqual(lookup_scope_storage_cpp(tr, 'x'), expect)
        self.assertTrue(scope_has_param(scope, 'x'))

    def test_scope_has_param_with_node_only(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_emit import scope_has_param
        from src.analysis.ir import cpp_ident
        from src.translator import Scope

        scope = Scope(ast.parse('pass').body[0])
        scope.param_type_nodes['p'] = type_node_from_cpp_string(cpp_ident('float'))
        self.assertTrue(scope_has_param(scope, 'p'))

    def test_bind_scope_var_dual_writes_node(self):
        from src.analysis.type_emit import bind_scope_var, scope_storage_cpp
        from src.analysis.ir import cpp_ident
        from src.translator import Scope, Translator

        scope = Scope(ast.parse('pass').body[0])
        tr = Translator('m', 'm.py')
        tr.scope = scope
        bind_scope_var(scope, 'x', cpp_ident('int'), classes=tr.classes)
        self.assertIn('x', scope.var_type_nodes)
        self.assertEqual(scope_storage_cpp(tr, 'x'), cpp_ident('int'))
        scope.var_types['x'] = 'PyStr'
        self.assertEqual(scope_storage_cpp(tr, 'x'), cpp_ident('int'))

class TestTypeNodePhase4Helpers(unittest.TestCase):

    def test_write_field_storage_does_not_cache_cpp_string(self):
        from src.analysis.type_emit import write_field_storage
        from src.analysis.ir import ClassInfo, cpp_ident
        from src.analysis.type_compat import type_node_from_cpp_string
        info = ClassInfo(ast.parse('class C: pass').body[0], module_path='m.py')
        write_field_storage(info, 'x', type_node_from_cpp_string(cpp_ident('int')))
        self.assertIn('x', info.field_type_nodes)
        self.assertNotIn('x', info.field_types)

    def test_field_storage_cpp_ignores_stale_string_cache(self):
        from src.analysis.type_emit import field_storage_cpp, write_field_storage
        from src.analysis.ir import ClassInfo, cpp_ident
        from src.analysis.type_compat import type_node_from_cpp_string
        info = ClassInfo(ast.parse('class C: pass').body[0], module_path='m.py')
        write_field_storage(info, 'x', type_node_from_cpp_string(cpp_ident('int')))
        info.field_types['x'] = 'void*'
        self.assertEqual(field_storage_cpp(info, 'x'), cpp_ident('int'))

    def test_method_param_types_map_node_only(self):
        from src.analysis.ir import MethodSig, FuncTypeParams
        from src.analysis.type_emit import method_param_storage_cpp, method_param_types_map
        from src.analysis.type_compat import type_node_from_cpp_string
        node = type_node_from_cpp_string('PyInt')
        sig = MethodSig(func_ft=FuncTypeParams.collect(ast.parse('def f(x: int): pass').body[0]), ret_lead='void', ret_trail='', params_decl='PyInt x', params_def='PyInt x', param_types={'x': 'void*', 'y': 'void*'}, param_type_nodes={'x': node}, doc_lines=(), is_next=False, result_cpp_type='void*')
        self.assertEqual(method_param_storage_cpp(sig, 'x'), 'PyInt')
        self.assertEqual(method_param_types_map(sig), {'x': 'PyInt'})

    def test_field_storage_values_node_only(self):
        from src.analysis.type_emit import field_storage_values, write_field_storage
        from src.analysis.ir import ClassInfo, cpp_ident
        from src.analysis.type_compat import type_node_from_cpp_string
        info = ClassInfo(ast.parse('class C: pass').body[0], module_path='m.py')
        info.fields = ['x', 'y']
        write_field_storage(info, 'x', type_node_from_cpp_string(cpp_ident('int')))
        info.field_types['x'] = 'void*'
        info.field_types['y'] = 'void*'
        self.assertEqual(field_storage_values(info), [cpp_ident('int')])

    def test_return_type_node_from_method_annotation(self):
        from src.analysis.analyzer import SignatureBuilder, TypeParser
        from src.analysis.ir import ClassInfo, cpp_ident
        from src.analysis.type_emit import sig_return_storage_cpp
        from src.analysis.type_node import TypeKind
        src = 'class Box:\n  def items(self) -> list[int]:\n    pass'
        info = ClassInfo(ast.parse(src).body[0], module_path='m.py')
        sb = SignatureBuilder(TypeParser())
        sb.set_classes({info.name: info})
        sig = sb.build_method_sig(info, info.methods['items'])
        self.assertEqual(sig.return_type_node.kind, TypeKind.TEMPLATE)
        self.assertEqual(
            sig.return_type_node.render(CLASS_BODY),
            f"{cpp_ident('list')}<{cpp_ident('int')}>",
        )
        self.assertEqual(sig_return_storage_cpp(sig), f"{cpp_ident('list')}<{cpp_ident('int')}>")

    def test_sig_return_storage_cpp_ignores_stale_ret_lead(self):
        from src.analysis.ir import MethodSig, FuncTypeParams
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_emit import sig_return_storage_cpp
        node = type_node_from_cpp_string('PyList<PyInt>')
        sig = MethodSig(
            func_ft=FuncTypeParams.collect(ast.parse('def f(x: int) -> list[int]: pass').body[0]),
            ret_lead='void*',
            ret_trail='',
            params_decl='PyInt x',
            params_def='PyInt x',
            param_types={},
            param_type_nodes={},
            return_type_node=node,
            doc_lines=(),
            is_next=False,
            result_cpp_type='void*',
        )
        self.assertEqual(sig_return_storage_cpp(sig), 'PyList<PyInt>')

    def test_write_field_ann_ast_roundtrip(self):
        from src.analysis.type_emit import clear_field_ann_ast, field_ann_ast, write_field_ann_ast
        info = ClassInfo(ast.parse('class C: pass').body[0], module_path='m.py')
        ann = ast.parse('int', mode='eval').body
        write_field_ann_ast(info, 'x', ann)
        self.assertIs(field_ann_ast(info, 'x'), ann)
        clear_field_ann_ast(info, 'x')
        self.assertIsNone(field_ann_ast(info, 'x'))

    def test_method_param_node_reconciles_boxing_pointer(self):
        import ast
        from src.analysis.analyzer import SignatureBuilder, TypeParser
        from src.analysis.ir import ClassInfo
        from src.analysis.type_render import CLASS_BODY
        with open('py2cpp/util/deque.py', encoding='utf-8') as f:
            src = f.read()
        tree = ast.parse(src)
        rev_cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'deque_reverse_iterator'))
        info = ClassInfo(rev_cls, module_path='py2cpp/util/deque.py')
        classes = {n.name: ClassInfo(n, module_path='py2cpp/util/deque.py') for n in tree.body if isinstance(n, ast.ClassDef)}
        parser = TypeParser()
        parser.set_classes(classes)
        sigs = SignatureBuilder(parser)
        sigs.set_classes(classes)
        init = info.inits[0]
        msig = sigs.build_method_sig(info, init)
        self.assertEqual(msig.param_type_nodes['dq'].render(CLASS_BODY), msig.param_types['dq'])

    def test_sync_sig_cache_aligns_ret_and_params(self):
        import ast
        from src.analysis.type_emit import collect_sig_type_texts, sync_sig_cache
        from src.analysis.ir import FuncTypeParams, MethodSig
        from src.analysis.type_compat import type_node_from_cpp_string
        node = type_node_from_cpp_string('PyList<PyInt>')
        sig = MethodSig(func_ft=FuncTypeParams.collect(ast.parse('def f(x: int) -> list[int]: pass').body[0]), ret_lead='void', ret_trail='&', params_decl='PyInt x', params_def='PyInt x', param_types={'x': 'void*'}, param_type_nodes={'x': type_node_from_cpp_string('PyInt')}, return_type_node=node, doc_lines=(), is_next=False, result_cpp_type='void*')
        synced = sync_sig_cache(sig)
        self.assertEqual(synced.ret_lead, 'PyList<PyInt>')
        self.assertEqual(synced.param_types['x'], 'PyInt')
        self.assertIn('PyList<PyInt>&', collect_sig_type_texts(synced))

class TestTypePred(unittest.TestCase):

    def test_container_predicates_match_is_cpp(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_pred import coerce_type_node, is_container_type, is_dict_type, is_list_type, is_optional_type, is_str_type, is_tuple_type, is_char_type, is_varint_type
        samples = [('PyList<PyInt>', is_list_type), ('PyDict<PyStr, PyInt>', is_dict_type), ('PyStr', is_str_type), ('PyOptional<PyTuple<PyInt>>', is_optional_type)]
        for cpp, pred in samples:
            self.assertTrue(pred(cpp), cpp)
            node = type_node_from_cpp_string(cpp)
            self.assertTrue(pred(node), cpp)
            self.assertEqual(pred(cpp), pred(node))
        self.assertTrue(is_container_type('PyList<PyInt>'))
        self.assertTrue(is_container_type(coerce_type_node('PyList<PyInt>')))
        self.assertFalse(is_tuple_type('PyOptional<PyTuple<PyInt>>'))
        self.assertFalse(is_char_type('PyChar*'))
        self.assertTrue(is_char_type('PyChar'))
        self.assertTrue(is_char_type('PyChar&'))
        self.assertTrue(is_varint_type('PyVarInt'))

    def test_result_and_complex_predicates(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_pred import is_complex_type, is_fault_result_type, is_iter_result_type
        samples = [
            ('PyIterResult<PyInt, PyNone>', is_iter_result_type),
            ('PyResult<PyInt, PyStr>', is_fault_result_type),
            ('PyComplex', is_complex_type),
            ('PyComplex<PyFloat64>', is_complex_type),
        ]
        for cpp, pred in samples:
            self.assertTrue(pred(cpp), cpp)
            node = type_node_from_cpp_string(cpp)
            self.assertTrue(pred(node), cpp)
            self.assertEqual(pred(cpp), pred(node))
        self.assertFalse(is_iter_result_type('PyList<PyInt>'))
        self.assertFalse(is_complex_type('PyFloat64'))

    def test_peel_storage_strips_pointer(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_pred import is_list_type, peel_storage
        from src.analysis.type_node import TypeKind
        node = type_node_from_cpp_string('PyList<PyInt>*')
        core = peel_storage(node)
        self.assertEqual(core.kind, TypeKind.TEMPLATE)
        self.assertFalse(is_list_type(node))
        ref_node = type_node_from_cpp_string('PyList<PyInt>&')
        self.assertTrue(is_list_type(ref_node))

class TestTypeExtractInvokable(unittest.TestCase):

    def test_generator_predicates_and_extract(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_extract import generator_type_args, optional_inner_type, template_fixed_inners
        from src.analysis.type_pred import is_py_generator_type
        cpp = 'PyGenerator<PyInt, PyNone, PyNone>'
        self.assertTrue(is_py_generator_type(cpp))
        node = type_node_from_cpp_string(cpp)
        self.assertTrue(is_py_generator_type(node))
        self.assertEqual(generator_type_args(cpp), ('PyInt', 'PyNone', 'PyNone'))
        self.assertEqual(template_fixed_inners(node, 'PyGenerator', 3), ('PyInt', 'PyNone', 'PyNone'))
        self.assertFalse(is_py_generator_type('PyOptional<PyTuple<PyInt>>'))

    def test_optional_inner_via_extract(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_extract import optional_inner_type
        cpp = 'PyOptional<PyTuple<PyInt>>'
        self.assertEqual(optional_inner_type(cpp), 'PyTuple<PyInt>')
        node = type_node_from_cpp_string(cpp)
        self.assertEqual(optional_inner_type(node), 'PyTuple<PyInt>')

    def test_callable_and_erased_protocol_predicates(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_extract import dict_type_args, template_inner_text
        from src.analysis.type_pred import is_callable_type, is_erased_protocol_storage_type
        fn_ptr = 'PyInt (*)(PyInt)'
        self.assertTrue(is_callable_type(fn_ptr))
        fn_node = type_node_from_cpp_string(fn_ptr)
        self.assertTrue(is_callable_type(fn_node))
        self.assertEqual(type_node_to_cpp_string(fn_node), fn_ptr)
        self.assertFalse(is_callable_type('PyCallable<PyInt, PyInt>'))
        gen = 'PyGenerator<PyInt, PyNone, PyNone>'
        self.assertTrue(is_erased_protocol_storage_type(gen))
        self.assertTrue(is_erased_protocol_storage_type(type_node_from_cpp_string(gen)))
        ctx = 'PyContextManager<PyInt>'
        self.assertTrue(is_erased_protocol_storage_type(ctx))
        d = 'PyDict<PyStr, PyInt>'
        self.assertEqual(dict_type_args(d), 'PyStr, PyInt')
        node = type_node_from_cpp_string(d)
        self.assertEqual(template_inner_text(node, 'PyDict<'), 'PyStr, PyInt')

    def test_invokable_type_predicate(self):
        from src.analysis.type_compat import type_node_from_cpp_string
        from src.analysis.type_pred import is_invokable_type
        fn_ptr = 'PyInt (*)(PyInt)'
        callable_t = 'PyCallable<PyInt, PyInt>'
        self.assertTrue(is_invokable_type(fn_ptr))
        self.assertTrue(is_invokable_type(type_node_from_cpp_string(fn_ptr)))
        self.assertTrue(is_invokable_type(callable_t))
        self.assertTrue(is_invokable_type(type_node_from_cpp_string(callable_t)))
        self.assertFalse(is_invokable_type('PyInt'))
        self.assertTrue(
            is_invokable_type('PyDelegate', delegate_names=frozenset({'PyDelegate'}))
        )
if __name__ == '__main__':
    unittest.main()
