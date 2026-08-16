enum class ExcKind : int
{
  PyStopIteration,
  PyTypeError,
  PyKeyError,
  PyIndexError,
  PyValueError,
  PyStatisticsError,
  PyLinAlgError,
  PyRuntimeError,
  PyOSError,
  PyFileNotFoundError,
  PyFileExistsError,
  PyAssertionError,
};

explicit PyExceptionGroup() : slots_len_(0) { }
void split_for_except_star(
    const ExcKind* kinds,
    PyInt kind_count,
    PyExceptionGroup& matched,
    PyExceptionGroup& rest) const;

private:
struct PyExcTypeUnion
{
  ExcKind kind;
  PyStopIteration stop_iteration;
  PyTypeError type_error;
  PyKeyError key_error;
  PyIndexError index_error;
  PyValueError value_error;
  PyStatisticsError statistics_error;
  PyLinAlgError linalg_error;
  PyRuntimeError runtime_error;
  PyOSError os_error;
  PyFileNotFoundError file_not_found_error;
  PyFileExistsError file_exists_error;
  PyAssertionError assertion_error;
};
static const PyInt kMaxSlots = 8;
PyExcTypeUnion slots_[8];
PyInt slots_len_;
void push_slot_impl(const PyExcTypeUnion& slot);
