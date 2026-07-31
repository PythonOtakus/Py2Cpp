// PY2CPP_EVAL：内联为 C++ 对应类型字面量（int/bool/带引号字符串）；无引号片段用 PY2CPP_ECHO()
PY2CPP_IGNORE
#define ctx_DebugBlock
#define ctx_UmbrellaBodyBefore
#define ctx_UmbrellaBodyMid
#define ctx_UmbrellaBodyIoLate
PY2CPP_END
PY2CPP_BEGIN( def fn_EmitMsvcUndefMacros(in_Macros) )
#ifdef _MSC_VER
PY2CPP_BEGIN( for macro in in_Macros )
#ifdef PY2CPP_EVAL(macro)
#undef PY2CPP_EVAL(macro)
#endif
PY2CPP_END
#endif
PY2CPP_END
PY2CPP_EXEC(fn_EmitMsvcUndefMacros(msvc_undef_macros_early))
PY2CPP_ECHO(ctx_DebugBlock)
// C++11，无 STL
PY2CPP_ECHO(ctx_UmbrellaBodyBefore)
PY2CPP_EXEC(fn_EmitMsvcUndefMacros(msvc_undef_macros))
PY2CPP_ECHO(ctx_UmbrellaBodyMid)
// UI/windows.h 等可能重新定义 ``stat``/``min``/``max``；io/path 须在再一轮 ``#undef`` 之后
PY2CPP_EXEC(fn_EmitMsvcUndefMacros(msvc_undef_macros))
PY2CPP_ECHO(ctx_UmbrellaBodyIoLate)
PY2CPP_EXEC(fn_EmitMsvcUndefMacros(msvc_undef_macros))
