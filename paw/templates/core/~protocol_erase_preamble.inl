namespace py2cpp_protocol_erase_detail
{
  struct model_hdr
  {
    int refcount;
    model_hdr() : refcount(1) {}
    void add_ref() { refcount += 1; }
    void release()
    {
      refcount -= 1;
      if (refcount <= 0) { delete this; }
    }
  };
}

template<typename Erased, typename Impl>
struct py2cpp_protocol_erase_model;
