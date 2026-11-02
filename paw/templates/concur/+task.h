PY2CPP_IGNORE
namespace py2cpp { namespace concur { namespace task {
template<typename _Value>
class PyTask
{
PY2CPP_END

PY2CPP_INJECT_CLASS(PyTask)
public:
  template<typename Coro>
  static PyTask<typename Coro::ReturnType> create(Coro coro);
PY2CPP_END

PY2CPP_IGNORE
};
} } }
PY2CPP_END
