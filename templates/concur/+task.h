PY2CPP_IGNORE
namespace py2cpp { namespace concur { namespace task {
template<typename _T>
class Task
{
PY2CPP_END

PY2CPP_INJECT_CLASS(Task)
public:
  template<typename Coro>
  static Task<typename Coro::ReturnType> create(Coro coro);
PY2CPP_END

PY2CPP_IGNORE
};
} } }
PY2CPP_END
