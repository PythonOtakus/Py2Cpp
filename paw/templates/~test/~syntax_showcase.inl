// templates/~test/~syntax_showcase.inl
// 七宏 + IGNORE / INCLUDE / SCOPE / TYPE 对照表（单测 ctx 见 test_expand_py2cpp_template._SHOWCASE_CTX）
// 勿 mirror 到 out/；供 expand_py2cpp_template 单测与 clangd 阅读。
// 冻结子集可原生展开（无 EXEC/def）；宿主专属 EXEC/def 见 ~exec_def_host.inl。
//
// | 设施 | 下文标记 |
// | IGNORE 块 + ctx_* 桩 | 块首 |
// | INCLUDE | §include |
// | BEGIN_SCOPE | §scope（ctx 须含 module_rel） |
// | TYPE | §type |
// | EVAL 字面量 / 循环变量 | §eval-lit / §for-* |
// | ECHO 整块 / 行内 / 表达式 / registry | §echo-* |
// | BEGIN(for) 静态 / 运行时 / 名称列表 | §for-static / §for-runtime / §for-names |
// | BEGIN(if/elif/else) | §if-chain |
// | for-list（替代旧 helper 展开） | §for-list / §for-items |
// | 纯 C++（无宏） | §pure-cpp |

PY2CPP_IGNORE
#include "paw/text/str.h"
#define ctx_Block
#define ctx_Suffix , y(0)
#define ctx_Base PyStr
#define ctx_Name ValueError
#define var_Name ValueError
PY2CPP_END

// §include
PY2CPP_INCLUDE("~snippet.inl")

PY2CPP_BEGIN_SCOPE

// §eval-lit（MARKER 由 ctx 注入，勿 EXEC）
PyStr lit = PY2CPP_EVAL("hello");
PyStr s = PY2CPP_EVAL("ab");
PyInt num = PY2CPP_EVAL(42);
PyBool flag = PY2CPP_EVAL(True);
PyFloat64 rate = PY2CPP_EVAL(1.5);
PyInt marker = PY2CPP_EVAL(MARKER);

// §type
void throw_sample()
{
  throw PY2CPP_TYPE(IndexError)();
}

// §echo-block（整块 ctx 粘贴；IGNORE 内 ctx_Block 为空宏）
PY2CPP_ECHO(ctx_Block)

// §echo-inline / §echo-expr
void fn() : x(0)PY2CPP_ECHO(ctx_Suffix)
{
}
joined PY2CPP_ECHO(a + b);
first PY2CPP_ECHO(parts_0);

// §echo-registry（ctx 覆盖 IGNORE 范例；短名经 registry 限定）
class PY2CPP_ECHO(ctx_Base) {};
void catch_(const PY2CPP_ECHO(ctx_Name)& e);

// §for-static
PY2CPP_BEGIN( for i in range(0, 3) )
  buf[PY2CPP_EVAL(i)] = PY2CPP_EVAL(i + 1);
PY2CPP_END

// §for-static（宿主 for 体不递归 BEGIN；EXEC-in-for 见 ~exec_def_host）
// first
PY2CPP_BEGIN( for k in range(0, 2) )
  mark[PY2CPP_EVAL(k)] = PY2CPP_EVAL(k);
PY2CPP_END

// §if-chain
PY2CPP_BEGIN( if typ == 1 )
  sqlite3_bind_int(stmt, PY2CPP_EVAL(1), PY2CPP_EVAL(2));
PY2CPP_END
PY2CPP_BEGIN( elif typ == 2 )
  sqlite3_bind_null(stmt, PY2CPP_EVAL(3));
PY2CPP_END
PY2CPP_BEGIN( else )
  sqlite3_bind_null(stmt, PY2CPP_EVAL(0));
PY2CPP_END

// §for-runtime（stop 为 ctx 中的 C++ 标识符时回退 while）
PY2CPP_BEGIN( for j in range(0, n) )
  x[PY2CPP_EVAL(j)] = PY2CPP_EVAL(j);
PY2CPP_END

// §for-names（同 exception convert ctor：for var_Name in type_names）
PY2CPP_BEGIN( for var_Name in type_names )
void handle(const PY2CPP_ECHO(var_Name)& e);
PY2CPP_END

// §for-list + EVAL（ctx 元组迭代）
PY2CPP_BEGIN( for tag in tags )
line PY2CPP_EVAL(tag);
PY2CPP_END

// §for-items
PY2CPP_BEGIN( for x in items )
line PY2CPP_EVAL(x);
PY2CPP_END

// §pure-cpp
int pure_cpp_only = 0;

PY2CPP_END_SCOPE
