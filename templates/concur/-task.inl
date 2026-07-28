PY2CPP_IGNORE
#include "py2cpp/concur/task.h"
#include "py2cpp/core/coroutine.h"
#include "py2cpp/core/iter_result.h"
#include "py2cpp/core/none.h"
#include "py2cpp/core/refcount.h"
#include <type_traits>
PY2CPP_END

namespace py2cpp_concur_task_detail
{
  template<typename YT, typename ST, typename RT>
  void coro_reset(PyCoroutine<YT, ST, RT>& coro)
  {
    coro.reset();
  }

  template<typename YT, typename ReturnType>
  struct task_coro_drive_policy
  {
    static const bool kPassYieldToScheduler = false;
  };

  template<typename ReturnType>
  struct task_coro_drive_policy<py2cpp::concur::task::LoopHandle, ReturnType>
  {
    static const bool kPassYieldToScheduler = true;
  };

  template<typename G, bool kPassYieldToScheduler>
  struct task_coro_drive_impl;

  /// 将任意 ``*_coroutine`` 适配为 ``Coroutine[LoopHandle, None, R]``：
  /// 仅 ``Element == LoopHandle`` 的 yield 交给调度器；其余在桥内继续 ``send``。
  template<typename G>
  struct task_coro_bridge
  {
    G gen;
    bool use_send;

    typedef py2cpp::concur::task::LoopHandle Element;
    typedef PY2CPP_TYPE(PyNone) SendType;
    typedef typename G::ReturnType ReturnType;

    explicit task_coro_bridge() : use_send(false)
    {
    }

    explicit task_coro_bridge(G g) : gen(g), use_send(false)
    {
    }

    task_coro_bridge& __iter__()
    {
      return *this;
    }

    task_coro_bridge __await__()
    {
      return *this;
    }

    typedef PY2CPP_TYPE(PyIterResult)<
      typename G::Element, ReturnType> InnerResult;
    typedef PY2CPP_TYPE(PyIterResult)<
      Element, ReturnType> OuterResult;

    OuterResult send(SendType value)
    {
      InnerResult step = gen.send(value);
      return drive_loop(step);
    }

    OuterResult __next__()
    {
      InnerResult step = gen.__next__();
      use_send = true;
      return drive_loop(step);
    }

  private:
    OuterResult drive_loop(InnerResult step)
    {
      return task_coro_drive_impl<
        G,
        task_coro_drive_policy<
          typename G::Element, ReturnType>::kPassYieldToScheduler>::run(
        *this, step);
    }
  };

  template<typename G>
  struct task_coro_drive_impl<G, false>
  {
    typedef typename task_coro_bridge<G>::InnerResult InnerResult;
    typedef typename task_coro_bridge<G>::OuterResult OuterResult;

    static OuterResult run(task_coro_bridge<G>& self, InnerResult step)
    {
      while (!step.PY2CPP_GETTER(done)())
      {
        step = self.gen.send(
          py2cpp_coroutine_detail::default_send_value<typename G::SendType>());
      }
      return OuterResult::Return(step.PY2CPP_GETTER(return_value)());
    }
  };

  template<typename G>
  struct task_coro_drive_impl<G, true>
  {
    typedef typename task_coro_bridge<G>::InnerResult InnerResult;
    typedef typename task_coro_bridge<G>::OuterResult OuterResult;

    static OuterResult run(task_coro_bridge<G>& self, InnerResult step)
    {
      while (!step.PY2CPP_GETTER(done)())
      {
        return OuterResult::Yield(step.PY2CPP_GETTER(value)());
      }
      return OuterResult::Return(step.PY2CPP_GETTER(return_value)());
    }
  };

  template<typename G>
  PyRefCount<py2cpp::concur::task::_SlotBase> make_coro_slot_from_gen(G gen)
  {
    using RT = typename G::ReturnType;
    using LH = py2cpp::concur::task::LoopHandle;
    task_coro_bridge<G> bridge(gen);
    PyRefCount<py2cpp::concur::task::_SlotBase> slot =
      makeRefCount<py2cpp::concur::task::_CoroSlot<RT>>(
        makeCoroutine<LH, PY2CPP_TYPE(PyNone), RT>(bridge));
    (*slot).kind = TASK_CORO;
    return slot;
  }

  template<typename T>
  struct SlotResultCopy
  {
    static T apply(const T& value)
    {
      return value;
    }
  };

  template<typename U>
  struct SlotResultCopy<PyList<U>>
  {
    static PyList<U> apply(const PyList<U>& value)
    {
      PyList<U> ret;
      ret.__copy__(value);
      return ret;
    }
  };

  template<typename G>
  typename G::ReturnType slot_result_for_coro(
    const PyRefCount<py2cpp::concur::task::_SlotBase>& slot)
  {
    using RT = typename G::ReturnType;
    const py2cpp::concur::task::_CoroSlot<RT>& coro_slot =
      static_cast<const py2cpp::concur::task::_CoroSlot<RT>&>(*slot);
    return SlotResultCopy<RT>::apply(coro_slot.PY2CPP_GETTER(result)());
  }
}
