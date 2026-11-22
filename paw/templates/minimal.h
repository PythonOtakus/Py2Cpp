// PY2CPP_EVAL：内联为 C++ 对应类型字面量（int/bool/带引号字符串）；无引号片段用 PY2CPP_ECHO()
// MSVC 宏冲突：冻结 for-list（无 def/EXEC），ctx 注入 msvc_undef_macros(_early)
PY2CPP_IGNORE
#define ctx_DebugBlock
#define ctx_UmbrellaBodyBefore
#define ctx_UmbrellaBodyMid
#define ctx_UmbrellaBodyIoLate
PY2CPP_END
#ifdef _MSC_VER
PY2CPP_BEGIN( for macro in msvc_undef_macros_early )
#ifdef PY2CPP_EVAL(macro)
#undef PY2CPP_EVAL(macro)
#endif
PY2CPP_END
#endif
PY2CPP_ECHO(ctx_DebugBlock)
// C++11，无 STL
PY2CPP_ECHO(ctx_UmbrellaBodyBefore)
#ifdef _MSC_VER
PY2CPP_BEGIN( for macro in msvc_undef_macros )
#ifdef PY2CPP_EVAL(macro)
#undef PY2CPP_EVAL(macro)
#endif
PY2CPP_END
#endif
PY2CPP_ECHO(ctx_UmbrellaBodyMid)
// UI/windows.h 等可能重新定义 ``stat``/``min``/``max``；io/path 须在再一轮 ``#undef`` 之后
#ifdef _MSC_VER
PY2CPP_BEGIN( for macro in msvc_undef_macros )
#ifdef PY2CPP_EVAL(macro)
#undef PY2CPP_EVAL(macro)
#endif
PY2CPP_END
#endif
PY2CPP_ECHO(ctx_UmbrellaBodyIoLate)
#ifdef _MSC_VER
PY2CPP_BEGIN( for macro in msvc_undef_macros )
#ifdef PY2CPP_EVAL(macro)
#undef PY2CPP_EVAL(macro)
#endif
PY2CPP_END
#endif
