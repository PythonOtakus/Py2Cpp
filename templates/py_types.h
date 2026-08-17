
#include <cstdint>
#include <cfloat>
#include <cmath>

/// Python ``int`` / ``float`` / ``bool`` 注解对应的 C++ 标量别名（与 ``PyStr`` 等命名一致）
typedef int PyInt;
typedef float PyFloat;
typedef bool PyBool;
/// 高精度标量：``int64`` → ``int64_t``，``float64`` → ``double``（与 ``int``/``float`` 并存）
typedef int64_t PyInt64;
typedef uint32_t PyUInt;
typedef uint64_t PyUInt64;
typedef uintptr_t PyUPtr;
typedef double PyFloat64;
/// 标量静态属性（译器 ``visit_Attribute`` 直映）：``float.Inf`` / ``int.Min`` 等
#define PY2CPP_FLOAT_INF ((PyFloat)INFINITY)
#define PY2CPP_FLOAT_NAN ((PyFloat)NAN)
#define PY2CPP_FLOAT64_INF ((PyFloat64)INFINITY)
#define PY2CPP_FLOAT64_NAN ((PyFloat64)NAN)
/// ``int.Min``；勿写 ``-2147483648``（MSVC C4146：一元 ``-`` 作用于无符号字面量）。
#define PY2CPP_INT_MIN ((PyInt)(-2147483647 - 1))
#define PY2CPP_INT_MAX ((PyInt)2147483647)
#define PY2CPP_INT64_MIN ((PyInt64)INT64_MIN)
#define PY2CPP_INT64_MAX ((PyInt64)INT64_MAX)
#define PY2CPP_UINT_MIN ((PyUInt)0)
#define PY2CPP_UINT_MAX ((PyUInt)UINT32_MAX)
#define PY2CPP_UINT64_MIN ((PyUInt64)0)
#define PY2CPP_UINT64_MAX ((PyUInt64)UINT64_MAX)
#define PY2CPP_FLOAT_MIN ((PyFloat)(-FLT_MAX))
#define PY2CPP_FLOAT_MAX ((PyFloat)FLT_MAX)
#define PY2CPP_FLOAT64_MIN ((PyFloat64)(-DBL_MAX))
#define PY2CPP_FLOAT64_MAX ((PyFloat64)DBL_MAX)
/// 手写 C++ 模板中访问 ``@property`` / ``@staticproperty`` / ``postsetter`` 的统一拼接宏。
#define PY2CPP_GETTER(name) name##__get
#define PY2CPP_SETTER(name) name##__set
#define PY2CPP_POSTSETTER(name) name##__postset
/// 标量静态方法：``float64.isInf(x)`` 等（译器 ``visit_Call`` 直映）
#define PY2CPP_ISFINITE_F(x) ((PyBool)::isfinite((double)(x)))
#define PY2CPP_ISINF_F(x) ((PyBool)::isinf((double)(x)))
#define PY2CPP_ISNAN_F(x) ((PyBool)::isnan((double)(x)))
#define PY2CPP_ISFINITE_F64(x) ((PyBool)::isfinite((double)(x)))
#define PY2CPP_ISINF_F64(x) ((PyBool)::isinf((double)(x)))
#define PY2CPP_ISNAN_F64(x) ((PyBool)::isnan((double)(x)))
