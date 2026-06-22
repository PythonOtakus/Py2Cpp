PY2CPP_IGNORE
#include <type_traits>
#include "py2cpp/py_types.h"
#define ctx_ProtocolName Iterable
#define ctx_StaticAssertLit "Iterable unsatisfied"
#define ctx_ProbePrivate
PY2CPP_END

/* @protocol PY2CPP_ECHO(ctx_ProtocolName) */
template<typename T>
struct PY2CPP_ECHO(ctx_ProtocolName)_check {
private:
PY2CPP_ECHO(ctx_ProbePrivate)
public:
PY2CPP_BEGIN(if ctx_HasProbes)
  static constexpr bool value = decltype(probe_ops<T>(0))::value;
PY2CPP_END
PY2CPP_BEGIN(else)
  static constexpr bool value = false;
PY2CPP_END
};

/* 显式触发可读 static_assert（可选：``sizeof(PY2CPP_ECHO(ctx_ProtocolName)_verify<T>)``） */
template<typename T>
struct PY2CPP_ECHO(ctx_ProtocolName)_verify {
  static_assert(PY2CPP_ECHO(ctx_ProtocolName)_check<T>::value,
    PY2CPP_ECHO(ctx_StaticAssertLit));
  enum { ok = 1 };
};

template<typename T, typename Enable = void>
struct PY2CPP_ECHO(ctx_ProtocolName)_impl;

template<typename T>
struct PY2CPP_ECHO(ctx_ProtocolName)_impl<T, typename std::enable_if<PY2CPP_ECHO(ctx_ProtocolName)_check<T>::value>::type> {
  static constexpr bool applies = true;
};

template<typename T>
struct PY2CPP_ECHO(ctx_ProtocolName)_impl<T, typename std::enable_if<!PY2CPP_ECHO(ctx_ProtocolName)_check<T>::value>::type> {
  static constexpr bool applies = false;
};

template<typename T>
using PY2CPP_ECHO(ctx_ProtocolName)_requires = typename std::enable_if<PY2CPP_ECHO(ctx_ProtocolName)_impl<T>::applies, int>::type;

template<typename T>
using PY2CPP_ECHO(ctx_ProtocolName)_enable = typename std::enable_if<PY2CPP_ECHO(ctx_ProtocolName)_impl<T>::applies>::type;
