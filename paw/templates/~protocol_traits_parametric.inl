PY2CPP_IGNORE
#include <type_traits>
#include "py2cpp/py_types.h"
#define ctx_ProtocolName Navigatable
#define ctx_ImplTpl Impl
#define ctx_NodeTpl Node
#define ctx_StaticAssertLit "Navigatable unsatisfied"
#define ctx_ProbePrivate
PY2CPP_END

/* @protocol PY2CPP_ECHO(ctx_ProtocolName) */
template<typename PY2CPP_ECHO(ctx_ImplTpl), typename PY2CPP_ECHO(ctx_NodeTpl)>
struct PY2CPP_ECHO(ctx_ProtocolName)_check {
private:
PY2CPP_ECHO(ctx_ProbePrivate)
public:
PY2CPP_BEGIN(if ctx_HasProbes)
  static constexpr bool value = decltype(probe_ops<PY2CPP_ECHO(ctx_ImplTpl)>(0))::value;
PY2CPP_END
PY2CPP_BEGIN(else)
  static constexpr bool value = false;
PY2CPP_END
};

template<typename PY2CPP_ECHO(ctx_ImplTpl), typename PY2CPP_ECHO(ctx_NodeTpl)>
struct PY2CPP_ECHO(ctx_ProtocolName)_verify {
  static_assert(PY2CPP_ECHO(ctx_ProtocolName)_check<PY2CPP_ECHO(ctx_ImplTpl), PY2CPP_ECHO(ctx_NodeTpl)>::value,
    PY2CPP_ECHO(ctx_StaticAssertLit));
  enum { ok = 1 };
};

template<typename PY2CPP_ECHO(ctx_ImplTpl), typename PY2CPP_ECHO(ctx_NodeTpl), typename Enable = void>
struct PY2CPP_ECHO(ctx_ProtocolName)_impl;

template<typename PY2CPP_ECHO(ctx_ImplTpl), typename PY2CPP_ECHO(ctx_NodeTpl)>
struct PY2CPP_ECHO(ctx_ProtocolName)_impl<PY2CPP_ECHO(ctx_ImplTpl), PY2CPP_ECHO(ctx_NodeTpl), typename std::enable_if<PY2CPP_ECHO(ctx_ProtocolName)_check<PY2CPP_ECHO(ctx_ImplTpl), PY2CPP_ECHO(ctx_NodeTpl)>::value>::type> {
  static constexpr bool applies = true;
};

template<typename PY2CPP_ECHO(ctx_ImplTpl), typename PY2CPP_ECHO(ctx_NodeTpl)>
struct PY2CPP_ECHO(ctx_ProtocolName)_impl<PY2CPP_ECHO(ctx_ImplTpl), PY2CPP_ECHO(ctx_NodeTpl), typename std::enable_if<!PY2CPP_ECHO(ctx_ProtocolName)_check<PY2CPP_ECHO(ctx_ImplTpl), PY2CPP_ECHO(ctx_NodeTpl)>::value>::type> {
  static constexpr bool applies = false;
};

template<typename PY2CPP_ECHO(ctx_ImplTpl), typename PY2CPP_ECHO(ctx_NodeTpl)>
using PY2CPP_ECHO(ctx_ProtocolName)_requires = typename std::enable_if<PY2CPP_ECHO(ctx_ProtocolName)_impl<PY2CPP_ECHO(ctx_ImplTpl), PY2CPP_ECHO(ctx_NodeTpl)>::applies, int>::type;

template<typename PY2CPP_ECHO(ctx_ImplTpl), typename PY2CPP_ECHO(ctx_NodeTpl)>
using PY2CPP_ECHO(ctx_ProtocolName)_enable = typename std::enable_if<PY2CPP_ECHO(ctx_ProtocolName)_impl<PY2CPP_ECHO(ctx_ImplTpl), PY2CPP_ECHO(ctx_NodeTpl)>::applies>::type;
