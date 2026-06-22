
#include <type_traits>

namespace py2cpp {
namespace access {
namespace detail {

/* C++11：``static_assert(false)`` 在未实例化分支不可靠；用依赖 false 承载自定义文案。 */
template<typename T>
struct access_dependent_false {
  enum { value = 0 };
};

template<typename T>
struct access_is_raw_pointer : std::false_type {};
template<typename T>
struct access_is_raw_pointer<T*> : std::true_type {};

struct py2cpp_invoke_tag0 {};
struct py2cpp_invoke_tag1 {};
struct py2cpp_invoke_tag2 {};
struct py2cpp_invoke_tag3 {};

} // namespace detail
} // namespace access
} // namespace py2cpp

/* 译器在无法可靠选定 ``.``/``->`` 时使用；每条宏调用前 ``#line`` + 前置 ``static_assert``（见 ``translator._emit_py2cpp_dispatch_check``）。 */
#define PY2CPP_GETATTR(obj, attr) \
  (::py2cpp::access::py2cpp_invoke_get_##attr((obj), 0))
#define PY2CPP_SETATTR(obj, attr, val) \
  (::py2cpp::access::py2cpp_invoke_set_##attr((obj), (val), 0))
#define PY2CPP_CALL(obj, method) \
  (::py2cpp::access::py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag0(), (obj)))
#define PY2CPP_CALL1(obj, method, a1) \
  (::py2cpp::access::py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag1(), (obj), (a1)))
#define PY2CPP_CALL2(obj, method, a1, a2) \
  (::py2cpp::access::py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag2(), (obj), (a1), (a2)))
#define PY2CPP_CALL3(obj, method, a1, a2, a3) \
  (::py2cpp::access::py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag3(), (obj), (a1), (a2), (a3)))

/* 每个翻译单元在首次使用某 attr/method 前须展开（由译器写入 ``namespace py2cpp::access``）。 */
#define PY2CPP_DECLARE_GETATTR(attr) \
  template<typename T> \
  auto get_##attr(T& o, int) -> decltype(o.attr##__get()) { return o.attr##__get(); } \
  template<typename T> \
  auto get_##attr(const T& o, int) -> decltype(o.attr##__get()) { return o.attr##__get(); } \
  template<typename T> \
  auto get_##attr(T* o, int) -> decltype(o->attr##__get()) { return o->attr##__get(); } \
  template<typename T> \
  auto get_##attr(const T* o, int) -> decltype(o->attr##__get()) { return o->attr##__get(); } \
  template<typename T> \
  auto get_##attr(T& o, long) -> decltype((o.attr)) { return o.attr; } \
  template<typename T> \
  auto get_##attr(const T& o, long) -> decltype((o.attr)) { return o.attr; } \
  template<typename T> \
  auto get_##attr(T* o, long) -> decltype(o->attr) { return o->attr; } \
  template<typename T> \
  auto get_##attr(const T* o, long) -> decltype(o->attr) { return o->attr; } \
template<typename T> \
  struct py2cpp_get_##attr##_detect_int_val { \
    template<typename U> \
    static auto test(int) -> decltype(get_##attr(std::declval<U&>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T> \
  struct py2cpp_get_##attr##_detect_long_val { \
    template<typename U> \
    static auto test(long) -> decltype(get_##attr(std::declval<U&>(), long()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T> \
  struct py2cpp_get_##attr##_detect_int_ptr { \
    template<typename U> \
    static auto test(int) -> decltype(get_##attr(std::declval<U*>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T> \
  struct py2cpp_get_##attr##_detect_long_ptr { \
    template<typename U> \
    static auto test(long) -> decltype(get_##attr(std::declval<U*>(), long()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T> \
  struct can_get_##attr { \
    static const bool value = \
      ::py2cpp::access::detail::access_is_raw_pointer<T>::value \
        ? (py2cpp_get_##attr##_detect_int_ptr<typename std::remove_pointer<T>::type>::value || \
           py2cpp_get_##attr##_detect_long_ptr<typename std::remove_pointer<T>::type>::value) \
        : (py2cpp_get_##attr##_detect_int_val<T>::value || \
           py2cpp_get_##attr##_detect_long_val<T>::value); \
  }; \
  template<typename T, bool IntOk, bool LongOk> struct py2cpp_get_##attr##_pick_val; \
  template<typename T> struct py2cpp_get_##attr##_pick_val<T, true, false> { \
    static auto run(T& o) -> decltype(get_##attr(o, 0)) { return get_##attr(o, 0); } \
  }; \
  template<typename T> struct py2cpp_get_##attr##_pick_val<T, false, true> { \
    static auto run(T& o) -> decltype(get_##attr(o, 1L)) { return get_##attr(o, 1L); } \
  }; \
  template<typename T> struct py2cpp_get_##attr##_pick_val<T, true, true> { \
    static auto run(T& o) -> decltype(get_##attr(o, 0)) { return get_##attr(o, 0); } \
  }; \
  template<typename T> struct py2cpp_get_##attr##_pick_val<T, false, false> { \
    struct __py2cpp_get_##attr##_no_match {}; \
    static __py2cpp_get_##attr##_no_match run(T&); \
  }; \
  template<typename T, bool IntOk, bool LongOk> struct py2cpp_get_##attr##_pick_ptr; \
  template<typename T> struct py2cpp_get_##attr##_pick_ptr<T, true, false> { \
    static auto run_ptr(T* o) -> decltype(get_##attr(o, 0)) { return get_##attr(o, 0); } \
  }; \
  template<typename T> struct py2cpp_get_##attr##_pick_ptr<T, false, true> { \
    static auto run_ptr(T* o) -> decltype(get_##attr(o, 1L)) { return get_##attr(o, 1L); } \
  }; \
  template<typename T> struct py2cpp_get_##attr##_pick_ptr<T, true, true> { \
    static auto run_ptr(T* o) -> decltype(get_##attr(o, 0)) { return get_##attr(o, 0); } \
  }; \
  template<typename T> struct py2cpp_get_##attr##_pick_ptr<T, false, false> { \
    struct __py2cpp_get_##attr##_no_match {}; \
    static __py2cpp_get_##attr##_no_match run_ptr(T*); \
  }; \
  template<typename T> \
  typename std::enable_if< \
    !::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_get_##attr##_pick_val<T, \
      py2cpp_get_##attr##_detect_int_val<T>::value, \
      py2cpp_get_##attr##_detect_long_val<T>::value>::run(std::declval<T&>()))>::type \
  get_##attr(T& o) { \
    return py2cpp_get_##attr##_pick_val<T, \
      py2cpp_get_##attr##_detect_int_val<T>::value, \
      py2cpp_get_##attr##_detect_long_val<T>::value>::run(o); \
  } \
  template<typename T> \
  typename std::enable_if< \
    ::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_get_##attr##_pick_ptr<typename std::remove_pointer<T>::type, \
      py2cpp_get_##attr##_detect_int_ptr<typename std::remove_pointer<T>::type>::value, \
      py2cpp_get_##attr##_detect_long_ptr<typename std::remove_pointer<T>::type>::value \
      >::run_ptr(std::declval<T>()))>::type \
  get_##attr(T o) { \
    typedef typename std::remove_pointer<T>::type Pointee; \
    return py2cpp_get_##attr##_pick_ptr<Pointee, \
      py2cpp_get_##attr##_detect_int_ptr<Pointee>::value, \
      py2cpp_get_##attr##_detect_long_ptr<Pointee>::value>::run_ptr(o); \
  } \
  template<typename T> \
  auto get_##attr(const T& o) -> decltype(py2cpp_get_##attr##_pick_val<const T, \
    py2cpp_get_##attr##_detect_int_val<const T>::value, \
    py2cpp_get_##attr##_detect_long_val<const T>::value>::run(const_cast<T&>(o))) { \
    return py2cpp_get_##attr##_pick_val<const T, \
      py2cpp_get_##attr##_detect_int_val<const T>::value, \
      py2cpp_get_##attr##_detect_long_val<const T>::value>::run(const_cast<T&>(o)); \
  } \
  template<typename T> \
  auto get_##attr(T* o) -> decltype(py2cpp_get_##attr##_pick_ptr<T, \
    py2cpp_get_##attr##_detect_int_ptr<T>::value, \
    py2cpp_get_##attr##_detect_long_ptr<T>::value>::run_ptr(o)) { \
    return py2cpp_get_##attr##_pick_ptr<T, \
      py2cpp_get_##attr##_detect_int_ptr<T>::value, \
      py2cpp_get_##attr##_detect_long_ptr<T>::value>::run_ptr(o); \
  } \
  template<typename T> \
  auto get_##attr(const T* o) -> decltype(py2cpp_get_##attr##_pick_ptr<const T, \
    py2cpp_get_##attr##_detect_int_ptr<const T>::value, \
    py2cpp_get_##attr##_detect_long_ptr<const T>::value>::run_ptr(o)) { \
    return py2cpp_get_##attr##_pick_ptr<const T, \
      py2cpp_get_##attr##_detect_int_ptr<const T>::value, \
      py2cpp_get_##attr##_detect_long_ptr<const T>::value>::run_ptr(o); \
  } \
  template<typename T> \
  typename std::enable_if<can_get_##attr<T>::value, \
    decltype(get_##attr(std::declval<T&>()))>::type \
  py2cpp_invoke_get_##attr(T& o, int) { \
    return get_##attr(o); \
  } \
  template<typename T> \
  typename std::enable_if<!can_get_##attr<T>::value, int>::type \
  py2cpp_invoke_get_##attr(T&, int) { return 0; }

#define PY2CPP_DECLARE_SETATTR(attr) \
  template<typename T, typename V> \
  auto set_##attr(T& o, V v, int) -> decltype(o.attr##__set(v), void()) { o.attr##__set(v); } \
  template<typename T, typename V> \
  auto set_##attr(T* o, V v, int) -> decltype(o->attr##__set(v), void()) { o->attr##__set(v); } \
  template<typename T, typename V> \
  auto set_##attr(T& o, V v, long) -> decltype((o.attr = v), void()) { o.attr = v; } \
  template<typename T, typename V> \
  auto set_##attr(T* o, V v, long) -> decltype((o->attr = v), void()) { o->attr = v; } \
template<typename T, typename V> \
  struct py2cpp_set_##attr##_detect_int_val { \
    template<typename U> \
    static auto test(int) -> decltype(set_##attr(std::declval<U&>(), std::declval<V>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename V> \
  struct py2cpp_set_##attr##_detect_long_val { \
    template<typename U> \
    static auto test(long) -> decltype(set_##attr(std::declval<U&>(), std::declval<V>(), long()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename V> \
  struct py2cpp_set_##attr##_detect_int_ptr { \
    template<typename U> \
    static auto test(int) -> decltype(set_##attr(std::declval<U*>(), std::declval<V>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename V> \
  struct py2cpp_set_##attr##_detect_long_ptr { \
    template<typename U> \
    static auto test(long) -> decltype(set_##attr(std::declval<U*>(), std::declval<V>(), long()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename V> \
  struct can_set_##attr { \
    static const bool value = \
      ::py2cpp::access::detail::access_is_raw_pointer<T>::value \
        ? (py2cpp_set_##attr##_detect_int_ptr<typename std::remove_pointer<T>::type, V>::value || \
           py2cpp_set_##attr##_detect_long_ptr<typename std::remove_pointer<T>::type, V>::value) \
        : (py2cpp_set_##attr##_detect_int_val<T, V>::value || \
           py2cpp_set_##attr##_detect_long_val<T, V>::value); \
  }; \
  template<typename T, typename V, bool IntOk, bool LongOk> struct py2cpp_set_##attr##_pick_val; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_val<T, V, true, false> { \
    static void run(T& o, V v) { set_##attr(o, v, 0); } \
  }; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_val<T, V, false, true> { \
    static void run(T& o, V v) { set_##attr(o, v, 1L); } \
  }; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_val<T, V, true, true> { \
    static void run(T& o, V v) { set_##attr(o, v, 0); } \
  }; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_val<T, V, false, false> { \
    struct __py2cpp_set_##attr##_no_match {}; \
    static __py2cpp_set_##attr##_no_match run(T&, V); \
  }; \
  template<typename T, typename V, bool IntOk, bool LongOk> struct py2cpp_set_##attr##_pick_ptr; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_ptr<T, V, true, false> { \
    static void run_ptr(T* o, V v) { set_##attr(o, v, 0); } \
  }; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_ptr<T, V, false, true> { \
    static void run_ptr(T* o, V v) { set_##attr(o, v, 1L); } \
  }; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_ptr<T, V, true, true> { \
    static void run_ptr(T* o, V v) { set_##attr(o, v, 0); } \
  }; \
  template<typename T, typename V> struct py2cpp_set_##attr##_pick_ptr<T, V, false, false> { \
    struct __py2cpp_set_##attr##_no_match {}; \
    static __py2cpp_set_##attr##_no_match run_ptr(T*, V); \
  }; \
  template<typename T, typename V> \
  typename std::enable_if< \
    !::py2cpp::access::detail::access_is_raw_pointer<T>::value, void>::type \
  set_##attr(T& o, V v) { \
    py2cpp_set_##attr##_pick_val<T, V, \
      py2cpp_set_##attr##_detect_int_val<T, V>::value, \
      py2cpp_set_##attr##_detect_long_val<T, V>::value>::run(o, v); \
  } \
  template<typename T, typename V> \
  typename std::enable_if< \
    ::py2cpp::access::detail::access_is_raw_pointer<T>::value, void>::type \
  set_##attr(T o, V v) { \
    typedef typename std::remove_pointer<T>::type Pointee; \
    py2cpp_set_##attr##_pick_ptr<Pointee, V, \
      py2cpp_set_##attr##_detect_int_ptr<Pointee, V>::value, \
      py2cpp_set_##attr##_detect_long_ptr<Pointee, V>::value>::run_ptr(o, v); \
  } \
  template<typename T, typename V> \
  void set_##attr(T* o, V v) { \
    py2cpp_set_##attr##_pick_ptr<T, V, \
      py2cpp_set_##attr##_detect_int_ptr<T, V>::value, \
      py2cpp_set_##attr##_detect_long_ptr<T, V>::value>::run_ptr(o, v); \
  } \
  template<typename T, typename V> \
  typename std::enable_if<can_set_##attr<T, V>::value, void>::type \
  py2cpp_invoke_set_##attr(T& o, V&& v, int) { \
    set_##attr(o, std::forward<V>(v)); \
  } \
  template<typename T, typename V> \
  typename std::enable_if<!can_set_##attr<T, V>::value, void>::type \
  py2cpp_invoke_set_##attr(T&, V&&, int) {}

#define PY2CPP_DECLARE_CALL(method) \
  template<typename T> \
  auto call_##method(T& o, int) -> decltype(o.method()) { return o.method(); } \
  template<typename T> \
  auto call_##method(T* o, int) -> decltype(o->method()) { return o->method(); } \
  template<typename T, typename A1> \
  auto call_##method(T& o, A1&& a1, int) -> decltype(o.method(a1)) { return o.method(a1); } \
  template<typename T, typename A1> \
  auto call_##method(T* o, A1&& a1, int) -> decltype(o->method(a1)) { return o->method(a1); } \
  template<typename T, typename A1, typename A2> \
  auto call_##method(T& o, A1&& a1, A2&& a2, int) \
    -> decltype(o.method(a1, a2)) { return o.method(a1, a2); } \
  template<typename T, typename A1, typename A2> \
  auto call_##method(T* o, A1&& a1, A2&& a2, int) \
    -> decltype(o->method(a1, a2)) { return o->method(a1, a2); } \
  template<typename T, typename A1, typename A2, typename A3> \
  auto call_##method(T& o, A1&& a1, A2&& a2, A3&& a3, int) \
    -> decltype(o.method(a1, a2, a3)) { return o.method(a1, a2, a3); } \
  template<typename T, typename A1, typename A2, typename A3> \
  auto call_##method(T* o, A1&& a1, A2&& a2, A3&& a3, int) \
    -> decltype(o->method(a1, a2, a3)) { return o->method(a1, a2, a3); } \
template<typename T> \
  struct py2cpp_call_##method##_detect_int_val { \
    template<typename U> \
    static auto test(int) -> decltype(call_##method(std::declval<U&>()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T> \
  struct py2cpp_call_##method##_detect_int_ptr { \
    template<typename U> \
    static auto test(int) -> decltype(call_##method(std::declval<U*>()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T> \
  struct can_call0_##method { \
    static const bool value = \
      ::py2cpp::access::detail::access_is_raw_pointer<T>::value \
        ? py2cpp_call_##method##_detect_int_ptr<typename std::remove_pointer<T>::type>::value \
        : py2cpp_call_##method##_detect_int_val<T>::value; \
  }; \
  template<typename T, bool IntOk> struct py2cpp_call_##method##_pick0_val; \
  template<typename T> struct py2cpp_call_##method##_pick0_val<T, true> { \
    static auto run(T& o) -> decltype(call_##method(o, 0)) { return call_##method(o, 0); } \
  }; \
  template<typename T> struct py2cpp_call_##method##_pick0_val<T, false> { \
    struct __py2cpp_call0_##method##_no_match {}; \
    static __py2cpp_call0_##method##_no_match run(T&); \
  }; \
  template<typename T, bool IntOk> struct py2cpp_call_##method##_pick0_ptr; \
  template<typename T> struct py2cpp_call_##method##_pick0_ptr<T, true> { \
    static auto run_ptr(T* o) -> decltype(call_##method(o, 0)) { return call_##method(o, 0); } \
  }; \
  template<typename T> struct py2cpp_call_##method##_pick0_ptr<T, false> { \
    struct __py2cpp_call0_##method##_no_match {}; \
    static __py2cpp_call0_##method##_no_match run_ptr(T*); \
  }; \
  template<typename T> \
  typename std::enable_if< \
    !::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick0_val<T, \
      py2cpp_call_##method##_detect_int_val<T>::value>::run(std::declval<T&>()))>::type \
  call_##method(T& o) { \
    return py2cpp_call_##method##_pick0_val<T, \
      py2cpp_call_##method##_detect_int_val<T>::value>::run(o); \
  } \
  template<typename T> \
  typename std::enable_if< \
    ::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick0_ptr<typename std::remove_pointer<T>::type, \
      py2cpp_call_##method##_detect_int_ptr<typename std::remove_pointer<T>::type>::value \
      >::run_ptr(std::declval<T>()))>::type \
  call_##method(T o) { \
    typedef typename std::remove_pointer<T>::type Pointee; \
    return py2cpp_call_##method##_pick0_ptr<Pointee, \
      py2cpp_call_##method##_detect_int_ptr<Pointee>::value>::run_ptr(o); \
  } \
  template<typename T> \
  auto call_##method(T* o) -> decltype(py2cpp_call_##method##_pick0_ptr<T, \
    py2cpp_call_##method##_detect_int_ptr<T>::value>::run_ptr(o)) { \
    return py2cpp_call_##method##_pick0_ptr<T, \
      py2cpp_call_##method##_detect_int_ptr<T>::value>::run_ptr(o); \
  } \
  template<typename T> \
  typename std::enable_if<can_call0_##method<T>::value, \
    decltype(call_##method(std::declval<T&>()))>::type \
  py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag0, T& o) { \
    return call_##method(o); \
  } \
  template<typename T> \
  typename std::enable_if<!can_call0_##method<T>::value, int>::type \
  py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag0, T&) { return 0; } \
template<typename T, typename A1> \
  struct py2cpp_call_##method##_detect_int_1_val { \
    template<typename U> \
    static auto test(int) -> decltype( \
      call_##method(std::declval<U&>(), std::declval<A1>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename A1> \
  struct py2cpp_call_##method##_detect_int_1_ptr { \
    template<typename U> \
    static auto test(int) -> decltype( \
      call_##method(std::declval<U*>(), std::declval<A1>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename A1> \
  struct can_call1_##method { \
    static const bool value = \
      ::py2cpp::access::detail::access_is_raw_pointer<T>::value \
        ? py2cpp_call_##method##_detect_int_1_ptr<typename std::remove_pointer<T>::type, A1>::value \
        : py2cpp_call_##method##_detect_int_1_val<T, A1>::value; \
  }; \
  template<typename T, typename A1, bool IntOk> struct py2cpp_call_##method##_pick1_val; \
  template<typename T, typename A1> struct py2cpp_call_##method##_pick1_val<T, A1, true> { \
    static auto run(T& o, A1&& a1) -> decltype(call_##method(o, std::forward<A1>(a1), 0)) { \
      return call_##method(o, std::forward<A1>(a1), 0); \
    } \
  }; \
  template<typename T, typename A1> struct py2cpp_call_##method##_pick1_val<T, A1, false> { \
    struct __py2cpp_call1_##method##_no_match {}; \
    static __py2cpp_call1_##method##_no_match run(T&, A1&&); \
  }; \
  template<typename T, typename A1, bool IntOk> struct py2cpp_call_##method##_pick1_ptr; \
  template<typename T, typename A1> struct py2cpp_call_##method##_pick1_ptr<T, A1, true> { \
    static auto run_ptr(T* o, A1&& a1) -> decltype(call_##method(o, std::forward<A1>(a1), 0)) { \
      return call_##method(o, std::forward<A1>(a1), 0); \
    } \
  }; \
  template<typename T, typename A1> struct py2cpp_call_##method##_pick1_ptr<T, A1, false> { \
    struct __py2cpp_call1_##method##_no_match {}; \
    static __py2cpp_call1_##method##_no_match run_ptr(T*, A1&&); \
  }; \
  template<typename T, typename A1> \
  typename std::enable_if< \
    !::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick1_val<T, A1, \
      py2cpp_call_##method##_detect_int_1_val<T, A1>::value>::run( \
        std::declval<T&>(), std::declval<A1>()))>::type \
  call_##method(T& o, A1&& a1) { \
    return py2cpp_call_##method##_pick1_val<T, A1, \
      py2cpp_call_##method##_detect_int_1_val<T, A1>::value>::run(o, std::forward<A1>(a1)); \
  } \
  template<typename T, typename A1> \
  typename std::enable_if< \
    ::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick1_ptr<typename std::remove_pointer<T>::type, A1, \
      py2cpp_call_##method##_detect_int_1_ptr<typename std::remove_pointer<T>::type, A1>::value \
      >::run_ptr(std::declval<T>(), std::declval<A1>()))>::type \
  call_##method(T o, A1&& a1) { \
    typedef typename std::remove_pointer<T>::type Pointee; \
    return py2cpp_call_##method##_pick1_ptr<Pointee, A1, \
      py2cpp_call_##method##_detect_int_1_ptr<Pointee, A1>::value>::run_ptr(o, std::forward<A1>(a1)); \
  } \
  template<typename T, typename A1> \
  auto call_##method(T* o, A1&& a1) -> decltype(py2cpp_call_##method##_pick1_ptr<T, A1, \
    py2cpp_call_##method##_detect_int_1_ptr<T, A1>::value>::run_ptr(o, std::forward<A1>(a1))) { \
    return py2cpp_call_##method##_pick1_ptr<T, A1, \
      py2cpp_call_##method##_detect_int_1_ptr<T, A1>::value>::run_ptr(o, std::forward<A1>(a1)); \
  } \
  template<typename T, typename A1> \
  typename std::enable_if<can_call1_##method<T, A1>::value, \
    decltype(call_##method(std::declval<T&>(), std::declval<A1>()))>::type \
  py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag1, T& o, A1&& a1) { \
    return call_##method(o, std::forward<A1>(a1)); \
  } \
  template<typename T, typename A1> \
  typename std::enable_if<!can_call1_##method<T, A1>::value, int>::type \
  py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag1, T&, A1&&) { return 0; } \
template<typename T, typename A1, typename A2> \
  struct py2cpp_call_##method##_detect_int_2_val { \
    template<typename U> \
    static auto test(int) -> decltype( \
      call_##method(std::declval<U&>(), std::declval<A1>(), std::declval<A2>(), int()), \
      std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename A1, typename A2> \
  struct py2cpp_call_##method##_detect_int_2_ptr { \
    template<typename U> \
    static auto test(int) -> decltype( \
      call_##method(std::declval<U*>(), std::declval<A1>(), std::declval<A2>(), int()), \
      std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename A1, typename A2> \
  struct can_call2_##method { \
    static const bool value = \
      ::py2cpp::access::detail::access_is_raw_pointer<T>::value \
        ? py2cpp_call_##method##_detect_int_2_ptr<typename std::remove_pointer<T>::type, A1, A2>::value \
        : py2cpp_call_##method##_detect_int_2_val<T, A1, A2>::value; \
  }; \
  template<typename T, typename A1, typename A2, bool IntOk> struct py2cpp_call_##method##_pick2_val; \
  template<typename T, typename A1, typename A2> struct py2cpp_call_##method##_pick2_val<T, A1, A2, true> { \
    static auto run(T& o, A1&& a1, A2&& a2) \
      -> decltype(call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), 0)) { \
      return call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), 0); \
    } \
  }; \
  template<typename T, typename A1, typename A2> struct py2cpp_call_##method##_pick2_val<T, A1, A2, false> { \
    struct __py2cpp_call2_##method##_no_match {}; \
    static __py2cpp_call2_##method##_no_match run(T&, A1&&, A2&&); \
  }; \
  template<typename T, typename A1, typename A2, bool IntOk> struct py2cpp_call_##method##_pick2_ptr; \
  template<typename T, typename A1, typename A2> struct py2cpp_call_##method##_pick2_ptr<T, A1, A2, true> { \
    static auto run_ptr(T* o, A1&& a1, A2&& a2) \
      -> decltype(call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), 0)) { \
      return call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), 0); \
    } \
  }; \
  template<typename T, typename A1, typename A2> struct py2cpp_call_##method##_pick2_ptr<T, A1, A2, false> { \
    struct __py2cpp_call2_##method##_no_match {}; \
    static __py2cpp_call2_##method##_no_match run_ptr(T*, A1&&, A2&&); \
  }; \
  template<typename T, typename A1, typename A2> \
  typename std::enable_if< \
    !::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick2_val<T, A1, A2, \
      py2cpp_call_##method##_detect_int_2_val<T, A1, A2>::value>::run( \
        std::declval<T&>(), std::declval<A1>(), std::declval<A2>()))>::type \
  call_##method(T& o, A1&& a1, A2&& a2) { \
    return py2cpp_call_##method##_pick2_val<T, A1, A2, \
      py2cpp_call_##method##_detect_int_2_val<T, A1, A2>::value>::run( \
        o, std::forward<A1>(a1), std::forward<A2>(a2)); \
  } \
  template<typename T, typename A1, typename A2> \
  typename std::enable_if< \
    ::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick2_ptr<typename std::remove_pointer<T>::type, A1, A2, \
      py2cpp_call_##method##_detect_int_2_ptr<typename std::remove_pointer<T>::type, A1, A2>::value \
      >::run_ptr(std::declval<T>(), std::declval<A1>(), std::declval<A2>()))>::type \
  call_##method(T o, A1&& a1, A2&& a2) { \
    typedef typename std::remove_pointer<T>::type Pointee; \
    return py2cpp_call_##method##_pick2_ptr<Pointee, A1, A2, \
      py2cpp_call_##method##_detect_int_2_ptr<Pointee, A1, A2>::value>::run_ptr( \
        o, std::forward<A1>(a1), std::forward<A2>(a2)); \
  } \
  template<typename T, typename A1, typename A2> \
  auto call_##method(T* o, A1&& a1, A2&& a2) \
    -> decltype(py2cpp_call_##method##_pick2_ptr<T, A1, A2, \
      py2cpp_call_##method##_detect_int_2_ptr<T, A1, A2>::value>::run_ptr( \
        o, std::forward<A1>(a1), std::forward<A2>(a2))) { \
    return py2cpp_call_##method##_pick2_ptr<T, A1, A2, \
      py2cpp_call_##method##_detect_int_2_ptr<T, A1, A2>::value>::run_ptr( \
        o, std::forward<A1>(a1), std::forward<A2>(a2)); \
  } \
  template<typename T, typename A1, typename A2> \
  typename std::enable_if<can_call2_##method<T, A1, A2>::value, \
    decltype(call_##method(std::declval<T&>(), std::declval<A1>(), std::declval<A2>()))>::type \
  py2cpp_invoke_call_##method(T& o, A1&& a1, A2&& a2, int) { \
    return call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2)); \
  } \
  template<typename T, typename A1, typename A2> \
  typename std::enable_if<!can_call2_##method<T, A1, A2>::value, int>::type \
  py2cpp_invoke_call_##method(T&, A1&&, A2&&, int) { return 0; } \
template<typename T, typename A1, typename A2, typename A3> \
  struct py2cpp_call_##method##_detect_int_3_val { \
    template<typename U> \
    static auto test(int) -> decltype( \
      call_##method(std::declval<U&>(), std::declval<A1>(), std::declval<A2>(), \
        std::declval<A3>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename A1, typename A2, typename A3> \
  struct py2cpp_call_##method##_detect_int_3_ptr { \
    template<typename U> \
    static auto test(int) -> decltype( \
      call_##method(std::declval<U*>(), std::declval<A1>(), std::declval<A2>(), \
        std::declval<A3>(), int()), std::true_type()); \
    template<typename> static std::false_type test(...); \
    static const bool value = decltype(test<T>(0))::value; \
  }; \
  template<typename T, typename A1, typename A2, typename A3> \
  struct can_call3_##method { \
    static const bool value = \
      ::py2cpp::access::detail::access_is_raw_pointer<T>::value \
        ? py2cpp_call_##method##_detect_int_3_ptr<typename std::remove_pointer<T>::type, A1, A2, A3>::value \
        : py2cpp_call_##method##_detect_int_3_val<T, A1, A2, A3>::value; \
  }; \
  template<typename T, typename A1, typename A2, typename A3, bool IntOk> struct py2cpp_call_##method##_pick3_val; \
  template<typename T, typename A1, typename A2, typename A3> \
  struct py2cpp_call_##method##_pick3_val<T, A1, A2, A3, true> { \
    static auto run(T& o, A1&& a1, A2&& a2, A3&& a3) \
      -> decltype(call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), \
        std::forward<A3>(a3), 0)) { \
      return call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), std::forward<A3>(a3), 0); \
    } \
  }; \
  template<typename T, typename A1, typename A2, typename A3> \
  struct py2cpp_call_##method##_pick3_val<T, A1, A2, A3, false> { \
    struct __py2cpp_call3_##method##_no_match {}; \
    static __py2cpp_call3_##method##_no_match run(T&, A1&&, A2&&, A3&&); \
  }; \
  template<typename T, typename A1, typename A2, typename A3, bool IntOk> struct py2cpp_call_##method##_pick3_ptr; \
  template<typename T, typename A1, typename A2, typename A3> \
  struct py2cpp_call_##method##_pick3_ptr<T, A1, A2, A3, true> { \
    static auto run_ptr(T* o, A1&& a1, A2&& a2, A3&& a3) \
      -> decltype(call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), \
        std::forward<A3>(a3), 0)) { \
      return call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), std::forward<A3>(a3), 0); \
    } \
  }; \
  template<typename T, typename A1, typename A2, typename A3> \
  struct py2cpp_call_##method##_pick3_ptr<T, A1, A2, A3, false> { \
    struct __py2cpp_call3_##method##_no_match {}; \
    static __py2cpp_call3_##method##_no_match run_ptr(T*, A1&&, A2&&, A3&&); \
  }; \
  template<typename T, typename A1, typename A2, typename A3> \
  typename std::enable_if< \
    !::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick3_val<T, A1, A2, A3, \
      py2cpp_call_##method##_detect_int_3_val<T, A1, A2, A3>::value>::run( \
        std::declval<T&>(), std::declval<A1>(), std::declval<A2>(), std::declval<A3>()))>::type \
  call_##method(T& o, A1&& a1, A2&& a2, A3&& a3) { \
    return py2cpp_call_##method##_pick3_val<T, A1, A2, A3, \
      py2cpp_call_##method##_detect_int_3_val<T, A1, A2, A3>::value>::run( \
        o, std::forward<A1>(a1), std::forward<A2>(a2), std::forward<A3>(a3)); \
  } \
  template<typename T, typename A1, typename A2, typename A3> \
  typename std::enable_if< \
    ::py2cpp::access::detail::access_is_raw_pointer<T>::value, \
    decltype(py2cpp_call_##method##_pick3_ptr<typename std::remove_pointer<T>::type, A1, A2, A3, \
      py2cpp_call_##method##_detect_int_3_ptr<typename std::remove_pointer<T>::type, A1, A2, A3>::value \
      >::run_ptr(std::declval<T>(), std::declval<A1>(), std::declval<A2>(), std::declval<A3>()))>::type \
  call_##method(T o, A1&& a1, A2&& a2, A3&& a3) { \
    typedef typename std::remove_pointer<T>::type Pointee; \
    return py2cpp_call_##method##_pick3_ptr<Pointee, A1, A2, A3, \
      py2cpp_call_##method##_detect_int_3_ptr<Pointee, A1, A2, A3>::value>::run_ptr( \
        o, std::forward<A1>(a1), std::forward<A2>(a2), std::forward<A3>(a3)); \
  } \
  template<typename T, typename A1, typename A2, typename A3> \
  auto call_##method(T* o, A1&& a1, A2&& a2, A3&& a3) \
    -> decltype(py2cpp_call_##method##_pick3_ptr<T, A1, A2, A3, \
      py2cpp_call_##method##_detect_int_3_ptr<T, A1, A2, A3>::value>::run_ptr( \
        o, std::forward<A1>(a1), std::forward<A2>(a2), std::forward<A3>(a3))) { \
    return py2cpp_call_##method##_pick3_ptr<T, A1, A2, A3, \
      py2cpp_call_##method##_detect_int_3_ptr<T, A1, A2, A3>::value>::run_ptr( \
        o, std::forward<A1>(a1), std::forward<A2>(a2), std::forward<A3>(a3)); \
  } \
  template<typename T, typename A1, typename A2, typename A3> \
  typename std::enable_if<can_call3_##method<T, A1, A2, A3>::value, \
    decltype(call_##method(std::declval<T&>(), std::declval<A1>(), std::declval<A2>(), \
      std::declval<A3>()))>::type \
  py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag3, T& o, A1&& a1, A2&& a2, A3&& a3) { \
    return call_##method(o, std::forward<A1>(a1), std::forward<A2>(a2), std::forward<A3>(a3)); \
  } \
  template<typename T, typename A1, typename A2, typename A3> \
  typename std::enable_if<!can_call3_##method<T, A1, A2, A3>::value, int>::type \
  py2cpp_invoke_call_##method(::py2cpp::access::detail::py2cpp_invoke_tag3, T&, A1&&, A2&&, A3&&) { return 0; }

