"""头文件破环：C++ 前向声明与 ``apply_header_fixups`` 动作表。"""

HEADER_FORWARD_DECLS: dict[str, str] = {
  "pystr": "namespace py2cpp { namespace text { namespace str { class PyStr; } } }",
  "py_iter_result": (
    "namespace py2cpp { namespace core { namespace iter_result { "
    "template<typename YieldType, typename ReturnType> class PyIterResult; } } }"
  ),
  "pybytes": "namespace py2cpp { namespace text { namespace bytes { class PyBytes; } } }",
  "pylist_tpl": (
    "namespace py2cpp { namespace util { namespace list { "
    "template<typename T, PyInt _StackLength> class PyList; } } }"
  ),
  "pyfrozenlist_tpl": (
    "namespace py2cpp { namespace util { namespace list { "
    "template<typename T, PyInt _StackLength> class PyFrozenList; } } }"
  ),
  "pydict_tpl": (
    "namespace py2cpp { namespace util { namespace dict { "
    "template<typename K, typename V> class PyDict; } } }"
  ),
  "pyfrozendict_tpl": (
    "namespace py2cpp { namespace util { namespace dict { "
    "template<typename K, typename V> class PyFrozenDict; } } }"
  ),
  "pydeque_tpl": (
    "namespace py2cpp { namespace util { namespace deque { "
    "template<typename T> class PyDeque; } } }"
  ),
  "pyset_tpl": (
    "namespace py2cpp { namespace util { namespace py_set { "
    "template<typename T> class PySet; } } }"
  ),
  "pyfrozenset_tpl": (
    "namespace py2cpp { namespace util { namespace py_set { "
    "template<typename T> class PyFrozenSet; } } }"
  ),
  "ecs_component_table_tpl": (
    "namespace py2cpp { namespace design { namespace ecs { "
    "template<typename T> class PyECSComponentTable; } } }"
  ),
  "json_doc_cursor_tpl": (
    "namespace py2cpp { namespace serde { namespace json { "
    "template<typename T> class PyJsonDocCursor; } } }"
  ),
  "pytuple_tpl": "template<typename... Args> class PyTuple;",
  "path_walk_step": (
    "namespace py2cpp { namespace io { namespace path { class PyWalkStep; } } }"
  ),
  "file_walk_generator": (
    "namespace py2cpp { namespace io { namespace file { class PyWalk_generator; } } }"
  ),
  "task_slot_friend": "namespace py2cpp_concur_task_detail { struct TaskSlotFriend; }",
}

HEADER_FORWARD_GROUPS: dict[str, tuple[str, ...]] = {
  "text_str_post": ("pybytes", "pylist_tpl", "pydict_tpl", "pytuple_tpl"),
}

MODULE_HEADER_FIXUPS: dict[str, tuple[tuple, ...]] = {
  "text/str": (
    ("move_pre_to_post_mods", "text/bytes", "util/list", "util/dict", "util/tuple"),
    ("remove_pre_mod", "util/protocols"),
    ("remove_pre_traits",),
    ("remove_post_traits",),
    ("remove_pre_forward_mod", "core/iter_result", "py_iter_result"),
    ("forward_group_if_post", "text_str_post"),
    ("remove_both_key", "umbrella", "operators"),
  ),
  "text/bytes": (
    ("bytes_post_class_move",),
    ("forward", "pydict_tpl"),
  ),
  "util/deque": (("forward", "pydeque_tpl"),),
  "util/set": (("forward_multi", "pyset_tpl", "pyfrozenset_tpl"),),
  "util/list": (
    ("forward_multi", "pylist_tpl", "pyfrozenlist_tpl"),
  ),
  "design/ecs": (("forward", "ecs_component_table_tpl"),),
  "serde/json": (("forward", "json_doc_cursor_tpl"),),
  "util/dict": (
    ("forward_multi", "pydict_tpl", "pyfrozendict_tpl"),
    ("remove_pre_mod", "util/protocols"),
    ("remove_pre_traits",),
  ),
  "builtins": (
    ("remove_pre_traits",),
    ("insert_mod_after_mod", "core/iter_result", "text/str"),
  ),
  "py2cpp": (
    ("move_pre_to_post_mod", "text/str"),
    ("remove_pre_key", "operators"),
    ("remove_post_key", "operators"),
    ("forward_multi", "pystr"),
    ("insert_front_key_if_missing", "py_types"),
    ("reinsert_prot_at_1",),
  ),
  "core/protocols": (
    ("insert_front_mod_if_missing", "core/none"),
    ("remove_both_key", "umbrella", "operators"),
  ),
  "util/protocols": (
    ("remove_both_key", "umbrella", "operators"),
  ),
  "numeric/protocols": (
    ("remove_pre_mod", "core/protocols"),
    ("remove_both_key", "umbrella", "operators"),
  ),
  "core/iter_result": (
    ("insert_front_mod_if_missing", "core/exceptions"),
  ),
  "io": (("insert_front_hdr", "<stdio.h>"),),
  "web/http": (("insert_front_mod_if_missing", "web/url"),),
  "web/client": (("insert_front_mod_if_missing", "web/url"),),
  "web/server": (
    ("insert_front_mod_if_missing", "web/url"),
    ("insert_front_mod_if_missing", "web/http"),
  ),

  "io/path": (("forward", "path_walk_step"),),
  "concur/task": (("forward", "task_slot_friend"),),
  "system/environ": (("insert_front_mod_if_missing", "io/path"),),
  "ui/flow/shell": (
    ("insert_front_mod_if_missing", "ui/menu"),
    ("insert_front_mod_if_missing", "ui/tooltip"),
    ("insert_front_mod_if_missing", "ui/input"),
    ("insert_front_mod_if_missing", "io/path"),
    ("insert_front_mod_if_missing", "ui/file_dialog"),
    ("insert_front_mod_if_missing", "ui/flow/serialize"),
  ),
  "ui/flow/panel": (
    ("insert_front_mod_if_missing", "ui/flow/shell"),
  ),
}
