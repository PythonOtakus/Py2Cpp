#include <type_traits>

struct _PyRefCountBlockHeader {
  int strong_count;
  int weak_count;
  void (*destroy_fn)(void*);
  void* object;
};

template<typename U>
struct _PyRefCountBlock : _PyRefCountBlockHeader {
  alignas(U) unsigned char storage[sizeof(U)];

  U* object_ptr() { return reinterpret_cast<U*>(storage); }
  const U* object_ptr() const { return reinterpret_cast<const U*>(storage); }
};

template<typename T>
T* alloc() {
  return static_cast<T*>(::operator new(sizeof(T)));
}

template<typename T>
void free(T* p) {
  ::operator delete(p);
}

template<typename T>
T* allocArray(int count) {
  if (count <= 0) {
    return nullptr;
  }
  T* p = static_cast<T*>(::operator new(sizeof(T) * static_cast<size_t>(count)));
  for (int i = 0; i < count; ++i) {
    new (p + i) T();
  }
  return p;
}

/// 仅分配 ``count`` 个 ``T`` 的原始存储，不默认构造；由调用方对 ``[0, active)`` 使用 ``init``。
template<typename T>
T* allocRawArray(int count) {
  if (count <= 0) {
    return nullptr;
  }
  return static_cast<T*>(::operator new(sizeof(T) * static_cast<size_t>(count)));
}

/// 释放 ``allocArray`` 返回的原始存储；调用方须已对范围内元素调用 ``destroy``。
template<typename T>
void freeArray(T* p) {
  ::operator delete(p);
}

template<typename T>
void init(T* p) {
  new (p) T();
}

template<typename T, typename... Args>
void init(T* p, Args... args) {
  new (p) T(args...);
}

template<typename T, bool = std::is_trivially_destructible<T>::value>
struct _destroy_impl;

template<typename T>
struct _destroy_impl<T, true> {
  static void go(T*) {}
};

template<typename T>
struct _destroy_impl<T, false> {
  static void go(T* p) {
    if (p) {
      p->~T();
    }
  }
};

template<typename T>
void destroy(T* p) {
  _destroy_impl<T>::go(p);
}

template<typename U>
void _py_refcount_destroy(void* p) {
  destroy<U>(static_cast<U*>(p));
}

template<typename T>
class PyRefCount;

template<typename T>
class PyWeakRef;

template<typename T, typename... Args>
PyRefCount<T> makeRefCount(Args... args);

// PEP 695 ``T: refcount`` / ``copyable`` / ``boxing`` 装饰器约束（Py2Cpp 扩展）
template<typename T>
struct py2cpp_refcount_check : std::false_type {};

template<typename T>
struct py2cpp_copyable_check : std::false_type {};

template<> struct py2cpp_copyable_check<PyByte> : std::true_type {};
template<> struct py2cpp_copyable_check<PyChar> : std::true_type {};
template<> struct py2cpp_copyable_check<PyBool> : std::true_type {};
template<> struct py2cpp_copyable_check<PyInt> : std::true_type {};
template<> struct py2cpp_copyable_check<PyInt64> : std::true_type {};
template<> struct py2cpp_copyable_check<PyUInt> : std::true_type {};
template<> struct py2cpp_copyable_check<PyUInt64> : std::true_type {};
template<> struct py2cpp_copyable_check<PyFloat> : std::true_type {};
template<> struct py2cpp_copyable_check<PyFloat64> : std::true_type {};

template<typename T>
struct py2cpp_boxing_check : std::false_type {};

template<typename U>
struct py2cpp_boxing_check<U*> : py2cpp_boxing_check<U> {};

template<typename T>
using py2cpp_refcount_requires = typename std::enable_if<py2cpp_refcount_check<T>::value, int>::type;

template<typename T>
using py2cpp_copyable_requires = typename std::enable_if<py2cpp_copyable_check<T>::value, int>::type;

template<typename T>
using py2cpp_boxing_requires = typename std::enable_if<py2cpp_boxing_check<T>::value, int>::type;

template<typename T>
class PyRefCount {
  _PyRefCountBlockHeader* block_;

  T* ptr() { return block_ ? static_cast<T*>(block_->object) : 0; }
  const T* ptr() const { return block_ ? static_cast<const T*>(block_->object) : 0; }

  void release() {
    if (!block_) {
      return;
    }
    _PyRefCountBlockHeader* b = block_;
    block_ = 0;
    if ((--(b->strong_count)) == 0) {
      if (b->destroy_fn && b->object) {
        b->destroy_fn(b->object);
        b->object = 0;
      }
      if (b->weak_count == 0) {
        ::operator delete(b);
      }
    }
  }

  void acquire(_PyRefCountBlockHeader* b) {
    release();
    block_ = b;
    if (block_) {
      ++(block_->strong_count);
    }
  }

  template<typename U, typename... A>
  friend PyRefCount<U> makeRefCount(A...);
  template<typename U>
  friend class PyRefCount;
  friend class PyWeakRef<T>;
  template<typename U>
  friend PyWeakRef<U> makeWeakRef(const PyRefCount<U>&);

  explicit PyRefCount(_PyRefCountBlockHeader* b) : block_(b) {}

public:
  explicit PyRefCount() : block_(0) {}

  explicit PyRefCount(std::nullptr_t) : block_(0) {}

  template<typename Arg0, typename... Args>
  explicit PyRefCount(Arg0 arg0, Args... args) : block_(0) {
    typedef typename std::decay<Arg0>::type Arg0D;
    static_assert(!std::is_same<Arg0D, std::nullptr_t>::value,
      "PyRefCount: use PyRefCount() for null, not nullptr");
    void* mem = ::operator new(sizeof(_PyRefCountBlock<T>));
    _PyRefCountBlock<T>* typed = static_cast<_PyRefCountBlock<T>*>(mem);
    typed->strong_count = 1;
    typed->weak_count = 0;
    typed->destroy_fn = &_py_refcount_destroy<T>;
    init<T>(typed->object_ptr(), arg0, args...);
    typed->object = typed->object_ptr();
    block_ = typed;
  }

  PyRefCount(const PyRefCount& other) : block_(other.block_) {
    if (block_) {
      ++(block_->strong_count);
    }
  }

  /// ``U`` 须为 ``T`` 的公有派生；共享控制块并以 ``T*`` 访问（析构仍按真实类型 ``U``）。
  template<typename U>
  PyRefCount(const PyRefCount<U>& other) : block_(other.block_) {
    static_assert(std::is_base_of<T, U>::value, "PyRefCount upcast requires U to derive from T");
    if (block_) {
      ++(block_->strong_count);
    }
  }

  PyRefCount& operator=(const PyRefCount& other) {
    if (this != &other) {
      acquire(other.block_);
    }
    return *this;
  }

  template<typename U>
  typename std::enable_if<std::is_base_of<T, U>::value, PyRefCount&>::type
  operator=(const PyRefCount<U>& other) {
    acquire(other.block_);
    return *this;
  }

  PyRefCount(PyRefCount&& other) : block_(other.block_) {
    other.block_ = 0;
  }

  PyRefCount& operator=(PyRefCount&& other) {
    if (this != &other) {
      release();
      block_ = other.block_;
      other.block_ = 0;
    }
    return *this;
  }

  ~PyRefCount() {
    release();
  }

  T* operator->() { return ptr(); }
  const T* operator->() const { return ptr(); }
  T& operator*() { return *ptr(); }
  const T& operator*() const { return *ptr(); }
  bool __bool__() const { return block_ != 0; }
  explicit operator PyBool() const { return __bool__(); }

  static PyRefCount from_object(const T* obj) {
    PyRefCount rc;
    if (!obj) {
      return rc;
    }
    _PyRefCountBlock<T>* block = reinterpret_cast<_PyRefCountBlock<T>*>(
      reinterpret_cast<char*>(const_cast<T*>(obj)) - offsetof(_PyRefCountBlock<T>, storage)
    );
    rc.block_ = block;
    ++(block->strong_count);
    return rc;
  }
};

template<typename T>
struct py2cpp_refcount_check<PyRefCount<T>> : std::true_type {};

template<typename T>
struct py2cpp_refcount_unwrap {
  typedef T type;
};

template<typename T>
struct py2cpp_refcount_unwrap<PyRefCount<T>> {
  typedef T type;
};

template<typename T, typename... Args>
PyRefCount<T> makeRefCount(Args... args) {
  void* mem = ::operator new(sizeof(_PyRefCountBlock<T>));
  _PyRefCountBlock<T>* block = static_cast<_PyRefCountBlock<T>*>(mem);
  block->strong_count = 1;
  block->weak_count = 0;
  block->destroy_fn = &_py_refcount_destroy<T>;
  init<T>(block->object_ptr(), args...);
  block->object = block->object_ptr();
  PyRefCount<T> result;
  result.block_ = block;
  return result;
}

template<typename T>
class PyWeakRef
{
  _PyRefCountBlockHeader* block_;

  template<typename U, typename... A>
  friend PyRefCount<U> makeRefCount(A...);
  template<typename U>
  friend class PyRefCount;
  template<typename U>
  friend PyWeakRef<U> makeWeakRef(const PyRefCount<U>&);

public:
  explicit PyWeakRef() : block_(0)
  {
  }

  explicit PyWeakRef(const PyRefCount<T>& strong) : block_(strong.block_)
  {
    if (block_)
    {
      ++(block_->weak_count);
    }
  }

  PyWeakRef(const PyWeakRef& other) : block_(other.block_)
  {
    if (block_)
    {
      ++(block_->weak_count);
    }
  }

  PyWeakRef& operator=(const PyWeakRef& other)
  {
    if (this != &other)
    {
      if (block_)
      {
        if ((--(block_->weak_count)) == 0 && block_->strong_count == 0)
        {
          ::operator delete(block_);
        }
      }
      block_ = other.block_;
      if (block_)
      {
        ++(block_->weak_count);
      }
    }
    return *this;
  }

  ~PyWeakRef()
  {
    if (block_)
    {
      if ((--(block_->weak_count)) == 0 && block_->strong_count == 0)
      {
        ::operator delete(block_);
      }
      block_ = 0;
    }
  }

  bool alive__get() const
  {
    return block_ && block_->strong_count > 0;
  }

  PyRefCount<T> value__get() const
  {
    PyRefCount<T> rc;
    if (block_ && block_->strong_count > 0)
    {
      rc.block_ = block_;
      ++(block_->strong_count);
    }
    return rc;
  }

  bool operator==(const PyWeakRef& other) const
  {
    return block_ == other.block_;
  }
};
template<typename T>
PyWeakRef<T> makeWeakRef(const PyRefCount<T>& strong) {
  PyWeakRef<T> w;
  w.block_ = strong.block_;
  if (w.block_) {
    ++(w.block_->weak_count);
  }
  return w;
}
