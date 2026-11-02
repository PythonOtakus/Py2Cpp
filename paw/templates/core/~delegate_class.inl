PY2CPP_IGNORE
#include "py2cpp/core/delegate.h"
#define ctx_Name _PyDelegateClangdSmoke
#define ctx_Base PyDelegate<int, int>
#define ctx_TplDecl
#define ctx_OperatorDecl int operator()(int x) const {
#define ctx_InvokeBody return Base::_invoke(x);
PY2CPP_END

PY2CPP_ECHO(ctx_TplDecl)
class PY2CPP_ECHO(ctx_Name) : public PY2CPP_ECHO(ctx_Base) {
public:
  using Base = PY2CPP_ECHO(ctx_Base);
  explicit PY2CPP_ECHO(ctx_Name)() : Base() {}
  using Base::operator+=;
  using Base::operator-=;
  using Base::operator bool;
  PY2CPP_ECHO(ctx_OperatorDecl)
    PY2CPP_ECHO(ctx_InvokeBody)
  }
};
