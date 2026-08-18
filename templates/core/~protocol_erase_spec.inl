PY2CPP_IGNORE
#define ctx_Base PyIterator
#define ctx_Qualified PyIterator<T>
#define ctx_TplArgs <T>
#define ctx_TplDecl template<typename T>
#define ctx_MakeFn makeIterator
#define ctx_Access IteratorAccess
#define ctx_TypeParamsWithImpl typename T, typename Impl
#define ctx_TypeParamsMakeArgs T
#define ctx_CtorVtableInits , _fn___iter__(0), _fn___next__(0)
#define ctx_CopyCtorInits , _fn___iter__(other._fn___iter__), _fn___next__(other._fn___next__)
#define ctx_MoveCtorInits , _fn___iter__(other._fn___iter__), _fn___next__(other._fn___next__)
#define ctx_PublicMethods
#define ctx_VtableDecls
#define ctx_ModelThunks
#define ctx_ResetClears
#define ctx_CopyAssignStmts
#define ctx_MoveCtorOtherClears
#define ctx_MoveAssignStmts
#define ctx_MoveAssignOtherClears
#define ctx_MakeLvalueFnAssigns
#define ctx_MakeRvalueFnAssigns
PY2CPP_END

PY2CPP_ECHO(ctx_TplDecl)
class PY2CPP_ECHO(ctx_Base)
{
public:
PY2CPP_ECHO(ctx_PublicMethods)

  explicit PY2CPP_ECHO(ctx_Base)() : _ctx(0), _destroy_fn(0)PY2CPP_ECHO(ctx_CtorVtableInits)
  {
  }

  ~PY2CPP_ECHO(ctx_Base)();
  void reset();
  PY2CPP_ECHO(ctx_Base)(const PY2CPP_ECHO(ctx_Base)& other);
  PY2CPP_ECHO(ctx_Base)& operator=(const PY2CPP_ECHO(ctx_Base)& other);
  PY2CPP_ECHO(ctx_Base)(PY2CPP_ECHO(ctx_Base)&& other);
  PY2CPP_ECHO(ctx_Base)& operator=(PY2CPP_ECHO(ctx_Base)&& other);

private:
  void* _ctx;
  void (*_destroy_fn)(void* ctx);
PY2CPP_ECHO(ctx_VtableDecls)

  friend struct PY2CPP_ECHO(ctx_Access);
};

PY2CPP_BEGIN(if ctx_HasTypeParams)
template<PY2CPP_ECHO(ctx_TypeParamsWithImpl)>
PY2CPP_END
PY2CPP_BEGIN(else)
template<typename Impl>
PY2CPP_END
struct py2cpp_protocol_erase_model<PY2CPP_ECHO(ctx_Qualified), Impl> : py2cpp_protocol_erase_detail::model_hdr
{
  typedef py2cpp_protocol_erase_model<PY2CPP_ECHO(ctx_Qualified), Impl> model_t;
  Impl* impl;
  bool owns_impl;
PY2CPP_ECHO(ctx_ModelThunks)
  static void destroy(void* ctx)
  {
    model_t* self = static_cast<model_t*>(ctx);
    if (self->owns_impl) { delete self->impl; }
    self->release();
  }
};

PY2CPP_ECHO(ctx_TplDecl)
inline PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)::~PY2CPP_ECHO(ctx_Base)()
{
  reset();
}

PY2CPP_ECHO(ctx_TplDecl)
inline void PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)::reset()
{
  if (_ctx != 0 && _destroy_fn != 0) { _destroy_fn(_ctx); }
  _ctx = 0;
  _destroy_fn = 0;
PY2CPP_ECHO(ctx_ResetClears)
}

PY2CPP_ECHO(ctx_TplDecl)
inline PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)::PY2CPP_ECHO(ctx_Base)(const PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)& other)
  : _ctx(other._ctx), _destroy_fn(other._destroy_fn)PY2CPP_ECHO(ctx_CopyCtorInits)
{
  if (_ctx != 0) { static_cast<py2cpp_protocol_erase_detail::model_hdr*>(_ctx)->add_ref(); }
}

PY2CPP_ECHO(ctx_TplDecl)
inline PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)& PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)::operator=(const PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)& other)
{
  if (this != &other)
  {
    reset();
    _ctx = other._ctx;
    _destroy_fn = other._destroy_fn;
PY2CPP_ECHO(ctx_CopyAssignStmts)
    if (_ctx != 0) { static_cast<py2cpp_protocol_erase_detail::model_hdr*>(_ctx)->add_ref(); }
  }
  return *this;
}

PY2CPP_ECHO(ctx_TplDecl)
inline PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)::PY2CPP_ECHO(ctx_Base)(PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)&& other)
  : _ctx(other._ctx), _destroy_fn(other._destroy_fn)PY2CPP_ECHO(ctx_MoveCtorInits)
{
  other._ctx = 0;
  other._destroy_fn = 0;
PY2CPP_ECHO(ctx_MoveCtorOtherClears)
}

PY2CPP_ECHO(ctx_TplDecl)
inline PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)& PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)::operator=(PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs)&& other)
{
  if (this != &other)
  {
    reset();
    _ctx = other._ctx;
    _destroy_fn = other._destroy_fn;
PY2CPP_ECHO(ctx_MoveAssignStmts)
    other._ctx = 0;
    other._destroy_fn = 0;
PY2CPP_ECHO(ctx_MoveAssignOtherClears)
  }
  return *this;
}

struct PY2CPP_ECHO(ctx_Access)
{
PY2CPP_BEGIN(if ctx_HasTypeParams)
  template<PY2CPP_ECHO(ctx_TypeParamsWithImpl)>
PY2CPP_END
PY2CPP_BEGIN(else)
  template<typename Impl>
PY2CPP_END
  static PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs) make(Impl& impl)
  {
    typedef py2cpp_protocol_erase_model<PY2CPP_ECHO(ctx_Qualified), Impl> model_t;
    model_t* m = new model_t();
    m->impl = &impl;
    m->owns_impl = false;
    PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs) out;
PY2CPP_ECHO(ctx_MakeLvalueFnAssigns)
    out._destroy_fn = &model_t::destroy;
    out._ctx = m;
    return out;
  }
PY2CPP_BEGIN(if ctx_HasTypeParams)
  template<PY2CPP_ECHO(ctx_TypeParamsWithImpl)>
PY2CPP_END
PY2CPP_BEGIN(else)
  template<typename Impl>
PY2CPP_END
  static PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs) make(Impl&& impl)
  {
    typedef py2cpp_protocol_erase_model<PY2CPP_ECHO(ctx_Qualified), Impl> model_t;
    model_t* m = new model_t();
    m->impl = new Impl(static_cast<Impl&&>(impl));
    m->owns_impl = true;
    PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs) out;
PY2CPP_ECHO(ctx_MakeRvalueFnAssigns)
    out._destroy_fn = &model_t::destroy;
    out._ctx = m;
    return out;
  }
};

PY2CPP_BEGIN(if ctx_HasTypeParams)
template<PY2CPP_ECHO(ctx_TypeParamsWithImpl)>
PY2CPP_END
PY2CPP_BEGIN(else)
template<typename Impl>
PY2CPP_END
PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs) PY2CPP_ECHO(ctx_MakeFn)(Impl& impl)
{
PY2CPP_BEGIN(if ctx_HasTypeParams)
  return PY2CPP_ECHO(ctx_Access)::template make<PY2CPP_ECHO(ctx_TypeParamsMakeArgs)>(impl);
PY2CPP_END
PY2CPP_BEGIN(else)
  return PY2CPP_ECHO(ctx_Access)::make(impl);
PY2CPP_END
}

PY2CPP_BEGIN(if ctx_HasTypeParams)
template<PY2CPP_ECHO(ctx_TypeParamsWithImpl)>
PY2CPP_END
PY2CPP_BEGIN(else)
template<typename Impl>
PY2CPP_END
PY2CPP_ECHO(ctx_Base)PY2CPP_ECHO(ctx_TplArgs) PY2CPP_ECHO(ctx_MakeFn)(Impl&& impl)
{
PY2CPP_BEGIN(if ctx_HasTypeParams)
  return PY2CPP_ECHO(ctx_Access)::template make<PY2CPP_ECHO(ctx_TypeParamsMakeArgs)>(static_cast<Impl&&>(impl));
PY2CPP_END
PY2CPP_BEGIN(else)
  return PY2CPP_ECHO(ctx_Access)::make(static_cast<Impl&&>(impl));
PY2CPP_END
}
