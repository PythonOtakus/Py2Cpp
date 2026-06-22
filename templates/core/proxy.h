// PyProxy<StorageT>：组合 ``_target``；成员转发与 ``super`` 由译器剥壳（见 py2cpp/core/proxy.py）。

template<typename StorageT>
class PyProxy {
 public:
  StorageT _target;

  explicit PyProxy() : _target() {}

  explicit PyProxy(const StorageT& t) : _target(t) {}

  explicit PyProxy(StorageT&& t) : _target(static_cast<StorageT&&>(t)) {}

  PyProxy(const PyProxy& o) : _target(o._target) {}

  PyProxy& operator=(const PyProxy& o) {
    if (this != &o) {
      _target = o._target;
    }
    return *this;
  }

  StorageT& _target_ref() { return _target; }
  const StorageT& _target_ref() const { return _target; }
};
