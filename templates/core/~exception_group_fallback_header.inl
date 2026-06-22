enum class ExcKind : int
{
  StopIteration,
  TypeError,
  KeyError,
  IndexError,
  ValueError,
  StatisticsError,
  LinAlgError,
  RuntimeError,
  OSError,
  FileNotFoundError,
  FileExistsError,
  AssertionError,
};

explicit ExceptionGroup() : slots_len_(0) { }
void split_for_except_star(
    const ExcKind* kinds,
    PyInt kind_count,
    ExceptionGroup& matched,
    ExceptionGroup& rest) const;

private:
struct ExcSlot
{
  ExcKind kind;
  StopIteration stop_iteration;
  TypeError type_error;
  KeyError key_error;
  IndexError index_error;
  ValueError value_error;
  StatisticsError statistics_error;
  LinAlgError linalg_error;
  RuntimeError runtime_error;
  OSError os_error;
  FileNotFoundError file_not_found_error;
  FileExistsError file_exists_error;
  AssertionError assertion_error;
};
static const PyInt kMaxSlots = 8;
ExcSlot slots_[8];
PyInt slots_len_;
void push_slot_impl(const ExcSlot& slot);
