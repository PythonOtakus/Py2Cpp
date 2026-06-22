#include "py2cpp/core/exceptions.h"

// 递归存储：Head + Tail...，与 std::tuple 相同的内存布局思路
template<typename... Args>
struct _PyTupleHolder;

template<>
struct _PyTupleHolder<> {};

template<typename Head, typename... Tail>
struct _PyTupleHolder<Head, Tail...>
{
  Head head;
  _PyTupleHolder<Tail...> tail;

  _PyTupleHolder() : head(), tail()
  {
  }
  _PyTupleHolder(Head h, Tail... rest) : head(h), tail(rest...)
  {
  }
};

// 以 Holder 为第二参数，避免 Clang 对 (I, Head, Tail...) 偏特化的拒收
template<int I, int N>
struct _PyTupleNormIdx
{
  static const int value = (I < 0 ? N + I : I);
};

template<int I, typename Holder>
struct _PyTupleElem;

template<typename Head, typename... Tail>
struct _PyTupleElem<0, _PyTupleHolder<Head, Tail...>>
{
  using elem_t = Head;
  static elem_t& get(_PyTupleHolder<Head, Tail...>& h)
  {
    return h.head;
  }
  static const elem_t& get(const _PyTupleHolder<Head, Tail...>& h)
  {
    return h.head;
  }
};

template<int I, typename Head, typename... Tail>
struct _PyTupleElem<I, _PyTupleHolder<Head, Tail...>>
{
  using elem_t = typename _PyTupleElem<I - 1, _PyTupleHolder<Tail...>>::elem_t;
  static elem_t& get(_PyTupleHolder<Head, Tail...>& h)
  {
    return _PyTupleElem<I - 1, _PyTupleHolder<Tail...>>::get(h.tail);
  }
  static const elem_t& get(const _PyTupleHolder<Head, Tail...>& h)
  {
    return _PyTupleElem<I - 1, _PyTupleHolder<Tail...>>::get(h.tail);
  }
};

template<typename A, typename B>
struct _PySameType
{
  static const bool value = false;
};
template<typename T>
struct _PySameType<T, T>
{
  static const bool value = true;
};

template<typename... Args>
struct _PyAllSame;

template<>
struct _PyAllSame<>
{
  static const bool value = true;
};

template<typename T>
struct _PyAllSame<T>
{
  static const bool value = true;
};

template<typename A, typename B, typename... Rest>
struct _PyAllSame<A, B, Rest...>
{
  static const bool value = _PySameType<A, B>::value && _PyAllSame<B, Rest...>::value;
};

template<typename... Args>
class PyTuple;

template<typename... Acc>
struct _PyTupleAccTag {};

template<int Start, int Stop, int Cur, typename AccTag, typename RemainingHolder>
struct _PyTupleSliceTypesWalk;

template<int Start, int Stop, int Cur, typename... Acc>
struct _PyTupleSliceTypesWalk<Start, Stop, Cur, _PyTupleAccTag<Acc...>, _PyTupleHolder<>>
{
  using type = PyTuple<Acc...>;
};

template<bool Pick, int Start, int Stop, int Cur, typename AccTag, typename RemainingHolder>
struct _PyTupleSliceTypesWalkPick;

template<int Start, int Stop, int Cur, typename... Acc, typename Head, typename... Tail>
struct _PyTupleSliceTypesWalkPick<true, Start, Stop, Cur, _PyTupleAccTag<Acc...>, _PyTupleHolder<Head, Tail...>>
{
  using type = typename _PyTupleSliceTypesWalk<
    Start, Stop, Cur + 1, _PyTupleAccTag<Acc..., Head>, _PyTupleHolder<Tail...>>::type;
};

template<int Start, int Stop, int Cur, typename... Acc, typename Head, typename... Tail>
struct _PyTupleSliceTypesWalkPick<false, Start, Stop, Cur, _PyTupleAccTag<Acc...>, _PyTupleHolder<Head, Tail...>>
{
  using type = typename _PyTupleSliceTypesWalk<
    Start, Stop, Cur + 1, _PyTupleAccTag<Acc...>, _PyTupleHolder<Tail...>>::type;
};

template<int Start, int Stop, int Cur, typename... Acc, typename Head, typename... Tail>
struct _PyTupleSliceTypesWalk<Start, Stop, Cur, _PyTupleAccTag<Acc...>, _PyTupleHolder<Head, Tail...>>
{
  static const bool kPick = (Cur >= Start) && (Cur < Stop);
  using type = typename _PyTupleSliceTypesWalkPick<
    kPick, Start, Stop, Cur, _PyTupleAccTag<Acc...>, _PyTupleHolder<Head, Tail...>>::type;
};

template<int Start, int Stop, typename... Args>
struct _PyTupleSliceTypes
{
  using type = typename _PyTupleSliceTypesWalk<
    Start, Stop, 0, _PyTupleAccTag<>, _PyTupleHolder<Args...>>::type;
};

template<int Start, int Stop, typename... Args>
struct _PyTupleSliceMake;

template<typename... Args>
class PyTuple
{
  _PyTupleHolder<Args...> _h;

public:
  explicit PyTuple()
  {
  }
  explicit PyTuple(Args... args) : _h(args...)
  {
  }

  int __len__() const
  {
    return (int)(sizeof...(Args));
  }

  template<int I>
  typename _PyTupleElem<
    _PyTupleNormIdx<I, (int)(sizeof...(Args))>::value,
    _PyTupleHolder<Args...>
  >::elem_t& get()
  {
    return _PyTupleElem<
      _PyTupleNormIdx<I, (int)(sizeof...(Args))>::value,
      _PyTupleHolder<Args...>
    >::get(_h);
  }

  template<int I>
  const typename _PyTupleElem<
    _PyTupleNormIdx<I, (int)(sizeof...(Args))>::value,
    _PyTupleHolder<Args...>
  >::elem_t& get() const
  {
    return _PyTupleElem<
      _PyTupleNormIdx<I, (int)(sizeof...(Args))>::value,
      _PyTupleHolder<Args...>
    >::get(_h);
  }

  template<int Start, int Stop>
  typename _PyTupleSliceTypes<
    _PyTupleNormIdx<Start, (int)(sizeof...(Args))>::value,
    _PyTupleNormIdx<Stop, (int)(sizeof...(Args))>::value,
    Args...
  >::type get_slice() const
  {
    return _PyTupleSliceMake<
      _PyTupleNormIdx<Start, (int)(sizeof...(Args))>::value,
      _PyTupleNormIdx<Stop, (int)(sizeof...(Args))>::value,
      Args...
    >::make(_h);
  }

  typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t& __getitem__(int index);
  const typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t& __getitem__(int index) const;
};

template<>
class PyTuple<>
{
public:
  explicit PyTuple()
  {
  }
  int __len__() const
  {
    return 0;
  }
};

template<typename... Values>
struct _PyTupleFromValues;

template<>
struct _PyTupleFromValues<>
{
  static PyTuple<> make()
  {
    return PyTuple<>();
  }
};

template<typename V0, typename... Rest>
struct _PyTupleFromValues<V0, Rest...>
{
  static PyTuple<V0, Rest...> make(V0 v0, Rest... rest)
  {
    return PyTuple<V0, Rest...>(v0, rest...);
  }
};

template<bool Pick, int Start, int Stop, int I, int N, typename Holder, typename... AccVals>
struct _PyTupleSliceMakeStep;

template<int Start, int Stop, int I, int N, typename... Args, typename... AccVals>
struct _PyTupleSliceMakeStep<true, Start, Stop, I, N, _PyTupleHolder<Args...>, AccVals...>
{
  static typename _PyTupleSliceTypes<Start, Stop, Args...>::type
  make(const _PyTupleHolder<Args...>& h, AccVals... acc)
  {
    return _PyTupleSliceMakeAt<
      Start, Stop, I + 1, N, _PyTupleHolder<Args...>, AccVals...,
      typename _PyTupleElem<I, _PyTupleHolder<Args...>>::elem_t
    >::make(h, acc..., _PyTupleElem<I, _PyTupleHolder<Args...>>::get(h));
  }
};

template<int Start, int Stop, int I, int N, typename... Args, typename... AccVals>
struct _PyTupleSliceMakeStep<false, Start, Stop, I, N, _PyTupleHolder<Args...>, AccVals...>
{
  static typename _PyTupleSliceTypes<Start, Stop, Args...>::type
  make(const _PyTupleHolder<Args...>& h, AccVals... acc)
  {
    return _PyTupleSliceMakeAt<Start, Stop, I + 1, N, _PyTupleHolder<Args...>, AccVals...>::make(
      h, acc...);
  }
};

template<int Start, int Stop, int I, int N, typename Holder, typename... AccVals>
struct _PyTupleSliceMakeAt;

template<int Start, int Stop, int N, typename... Args, typename... AccVals>
struct _PyTupleSliceMakeAt<Start, Stop, N, N, _PyTupleHolder<Args...>, AccVals...>
{
  static typename _PyTupleSliceTypes<Start, Stop, Args...>::type
  make(const _PyTupleHolder<Args...>&, AccVals... acc)
  {
    return _PyTupleFromValues<AccVals...>::make(acc...);
  }
};

template<int Start, int Stop, int I, int N, typename... Args, typename... AccVals>
struct _PyTupleSliceMakeAt<Start, Stop, I, N, _PyTupleHolder<Args...>, AccVals...>
{
  static typename _PyTupleSliceTypes<Start, Stop, Args...>::type
  make(const _PyTupleHolder<Args...>& h, AccVals... acc)
  {
    static const bool kPick = (I >= Start) && (I < Stop);
    return _PyTupleSliceMakeStep<kPick, Start, Stop, I, N, _PyTupleHolder<Args...>, AccVals...>::make(
      h, acc...);
  }
};

template<int Start, int Stop, typename... Args>
struct _PyTupleSliceMake
{
  static typename _PyTupleSliceTypes<Start, Stop, Args...>::type
  make(const _PyTupleHolder<Args...>& h)
  {
    return _PyTupleSliceMakeAt<
      Start, Stop, 0, (int)sizeof...(Args), _PyTupleHolder<Args...>>::make(h);
  }
};

/// ``"%d" % (1, 2)`` → ``__mod__(fmt, makeTuple(1, 2))``（单元素亦包一层元组）
template<typename T>
inline PyTuple<T> makeTuple(T value)
{
  return PyTuple<T>(value);
}

template<typename... Args>
inline PyTuple<Args...> makeTuple(Args... args)
{
  return PyTuple<Args...>(args...);
}
