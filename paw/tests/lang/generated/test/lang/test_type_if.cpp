// 由 py2cpp 自动生成
// 源文件: C:\Users\Anantian\source\repos\Py2Cpp\test\lang\test_type_if.py
// 生成时间: 2026-06-19 14:53:22
#include "test_type_if.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

namespace test_type_if
{
  using namespace py2cpp;
  using ::py2cpp::test::unittest::TestCase;
  using ::py2cpp::test::unittest::TestSuite;
  using ::py2cpp::test::unittest::TextTestRunner;
  using ::py2cpp::test::unittest::TestCase;
  using ::py2cpp::test::unittest::TestResult;
  using ::py2cpp::test::unittest::TestSuite;
  using ::py2cpp::test::unittest::TextTestRunner;
  using ::py2cpp::core::exceptions::AssertionError;
  using ::py2cpp::core::exceptions::BaseExceptionGroup;
  using ::py2cpp::core::exceptions::ExcSlot;
  using ::py2cpp::core::exceptions::Exception;
  using ::py2cpp::core::exceptions::ExceptionGroup;
  using ::py2cpp::core::exceptions::FileExistsError;
  using ::py2cpp::core::exceptions::FileNotFoundError;
  using ::py2cpp::core::exceptions::IndexError;
  using ::py2cpp::core::exceptions::KeyError;
  using ::py2cpp::core::exceptions::LinAlgError;
  using ::py2cpp::core::exceptions::OSError;
  using ::py2cpp::core::exceptions::ReferenceError;
  using ::py2cpp::core::exceptions::RuntimeError;
  using ::py2cpp::core::exceptions::StatisticsError;
  using ::py2cpp::core::exceptions::StopIteration;
  using ::py2cpp::core::exceptions::TypeError;
  using ::py2cpp::core::exceptions::ValueError;
  using ::py2cpp::util::list::PyFrozenList;
  using ::py2cpp::util::list::PyFrozenListIterator;
  using ::py2cpp::util::list::PyList;
  using ::py2cpp::util::list::PyListIterator;
  using ::py2cpp::util::list::PyListReverseIterator;
  using ::py2cpp::util::dict::PyDict;
  using ::py2cpp::util::dict::PyDictEntry;
  using ::py2cpp::util::dict::PyDictItemsIterator;
  using ::py2cpp::util::dict::PyDictItemsView;
  using ::py2cpp::util::dict::PyDictKeyIterator;
  using ::py2cpp::util::dict::PyDictKeyReverseIterator;
  using ::py2cpp::util::dict::PyDictKeysView;
  using ::py2cpp::util::dict::PyDictValuesIterator;
  using ::py2cpp::util::dict::PyDictValuesView;
  using ::py2cpp::util::dict::PyFrozenDict;
  using ::py2cpp::util::dict::PyFrozenDictItemsIterator;
  using ::py2cpp::util::dict::PyFrozenDictItemsView;
  using ::py2cpp::util::dict::PyFrozenDictKeyIterator;
  using ::py2cpp::util::dict::PyFrozenDictKeyReverseIterator;
  using ::py2cpp::util::dict::PyFrozenDictKeysView;
  using ::py2cpp::util::dict::PyFrozenDictValuesIterator;
  using ::py2cpp::util::dict::PyFrozenDictValuesView;
  using ::py2cpp::util::range::PyRange;
  using ::py2cpp::util::range::PyRangeIterator;
  using ::py2cpp::numeric::complex::PyComplex;
  using ::py2cpp::util::slice::PySlice;
  using ::py2cpp::util::pool::PyPool;
  using ::py2cpp::util::pool::pool_slot_loc;
  using ::py2cpp::io::PyStringIO;
  using ::py2cpp::io::PyTextIOWrapper;
  using ::py2cpp::PyEnumerateIterator;
  using ::py2cpp::PyZipIterator;
  using ::py2cpp::VarStack;
  using ::py2cpp::_EnumMroDec;
  using ::py2cpp::_MacroProbe;
  using ::py2cpp::_UnionMroDec;
  using ::py2cpp::util::misc::Counter;
  using ::py2cpp::util::misc::CounterElementsIterator;
  using ::py2cpp::util::deque::PyDeque;
  using ::py2cpp::util::deque::PyDequeIterator;
  using ::py2cpp::util::deque::PyDequeNode;
  using ::py2cpp::util::deque::PyDequeReverseIterator;
  using ::py2cpp::core::iter_result::PyIterResult;
  using ::py2cpp::text::bytes::PyBytes;
  using ::py2cpp::text::bytes::bytes_xrsplit_generator;
  using ::py2cpp::text::bytes::bytes_xsplit_generator;
  using ::py2cpp::text::bytes::bytes_xsplitlines_generator;
  using ::py2cpp::util::array::PyArray;
  using ::py2cpp::util::array::PyArray2D;
  using ::py2cpp::util::array::PyArray3D;
  using ::py2cpp::system::time::c_time;
  using ::py2cpp::numeric::varint::PyVarInt;
  using ::py2cpp::core::never::PyNever;
  using ::py2cpp::util::py_set::PyFrozenSet;
  using ::py2cpp::util::py_set::PyFrozenSetEntry;
  using ::py2cpp::util::py_set::PyFrozenSetIterator;
  using ::py2cpp::util::py_set::PySet;
  using ::py2cpp::util::py_set::PySetIterator;
  using ::py2cpp::util::py_set::PySetReverseIterator;
  using ::py2cpp::text::str::PyStr;
  using ::py2cpp::text::str::PyStrIterator;
  using ::py2cpp::text::str::PyStrReverseIterator;
  using ::py2cpp::text::str::str_xrsplit_generator;
  using ::py2cpp::text::str::str_xsplit_generator;
  using ::py2cpp::text::str::str_xsplitlines_generator;

  void test_type_if::TypeIfModuleTests::test()
  {
    this->assertEqual(::test_type_if::type_tag<PyInt>(42), 1);
    this->assertEqual(::test_type_if::type_tag<PyStr>(PyStr("hi")), 2);
    this->assertEqual(::test_type_if::type_tag<bool>(true), 2);
    PyList<PyInt> xs;
    this->assertEqual(::test_type_if::type_tag<PyList<PyInt>>(xs), 3);
    this->assertEqual(::test_type_if::type_not_int<PyFloat>(1.0f), 0);
    this->assertEqual(::test_type_if::type_not_int<PyInt>(7), 1);
    this->assertEqual(::test_type_if::tally<PyInt>(), 3);
    this->assertEqual(::test_type_if::tally<PyStr>(), 6);
    this->assertEqual(::test_type_if::type_not_in_num<PyStr>(PyStr("x")), 0);
    this->assertEqual(::test_type_if::type_not_in_num<PyFloat>(3.14f), 1);
    PyList<PyInt> xs2;
    this->assertEqual(::test_type_if::type_list_wildcard<PyList<PyInt>>(xs2), 1);
    PyList<PyStr> ys;
    this->assertEqual(::test_type_if::type_list_wildcard<PyList<PyStr>>(ys), 2);
  }

  void test_type_if::TypeIfModuleTests::run(TestResult& result)
  {
    this->begin_test(result, TypeIfModuleTests::_test_tag, PyStr("TypeIfModuleTests"));
    this->test();
    this->end_test(result);
  }

  PyBool test_type_if::TypeIfModuleTests::__bool__() const
  {
    return true;
  }

  PyStr test_type_if::TypeIfModuleTests::__repr__() const
  {
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", "__main__", "TypeIfModuleTests", (unsigned long long)(size_t)(const void*)(this));
    return PyStr(buf);
  }

  PyStr test_type_if::TypeIfModuleTests::__str__() const
  {
    return this->__repr__();
  }

  const PyInt test_type_if::TypeIfModuleTests::__py2cpp_class_id__ = 2;

  PyInt test_type_if::TypeIfModuleTests::__class_id____get() const
  {
    return __py2cpp_class_id__;
  }

  PyInt test_type_if::TypeIfModuleTests::__id____get()
  {
    return __py2cpp_class_id__;
  }

  test_type_if::TypeIfModuleTests::operator PyStr() const
  {
    return __str__();
  }
  test_type_if::TypeIfModuleTests::operator PyBool() const
  {
    return __bool__();
  }
  test_type_if::TypeIfModuleTests::~TypeIfModuleTests()
  {
  }

  void test_type_if::ElementOfTests::test()
  {
    this->assertEqual(::test_type_if::elem_code<PyInt>(), 1);
    this->assertEqual(::test_type_if::elem_code<PyList<PyInt>>(), 2);
    this->assertEqual(::test_type_if::elem_code<PyStr>(), 3);
    this->assertEqual(::test_type_if::elem_code<PyList<PyStr>>(), 4);
    this->assertEqual(::test_type_if::inner_code<PyList<PyList<PyInt>>>(), 12);
    this->assertEqual(::test_type_if::inner_code<PyList<PyInt>>(), 11);
    this->assertEqual(::test_type_if::pointee_code<PyInt*>(), 1);
    this->assertEqual(::test_type_if::pointee_code<PyInt>(), 2);
    this->assertEqual(::test_type_if::pointee_code<PyStr*>(), 3);
    PyInt n = 7;
    this->assertEqual(::test_type_if::take_elem<PyInt>(n), 7);
    PyList<PyInt> xs;
    xs.append(1);
    xs.append(2);
    this->assertEqual(::test_type_if::take_elem<PyInt>(xs.__getitem__(0)), 1);
  }

  void test_type_if::ElementOfTests::run(TestResult& result)
  {
    this->begin_test(result, ElementOfTests::_test_tag, PyStr("ElementOfTests"));
    this->test();
    this->end_test(result);
  }

  PyBool test_type_if::ElementOfTests::__bool__() const
  {
    return true;
  }

  PyStr test_type_if::ElementOfTests::__repr__() const
  {
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", "__main__", "ElementOfTests", (unsigned long long)(size_t)(const void*)(this));
    return PyStr(buf);
  }

  PyStr test_type_if::ElementOfTests::__str__() const
  {
    return this->__repr__();
  }

  const PyInt test_type_if::ElementOfTests::__py2cpp_class_id__ = 3;

  PyInt test_type_if::ElementOfTests::__class_id____get() const
  {
    return __py2cpp_class_id__;
  }

  PyInt test_type_if::ElementOfTests::__id____get()
  {
    return __py2cpp_class_id__;
  }

  test_type_if::ElementOfTests::operator PyStr() const
  {
    return __str__();
  }
  test_type_if::ElementOfTests::operator PyBool() const
  {
    return __bool__();
  }
  test_type_if::ElementOfTests::~ElementOfTests()
  {
  }

  template<typename T, typename = void>
  struct __py2cpp_type_if_type_tag_9_pick;

  template<>
  struct __py2cpp_type_if_type_tag_9_pick<PyInt, void>
  {
    static PyInt __call__(PyInt x)
    {
      return 1;
    }
  };

  template<>
  struct __py2cpp_type_if_type_tag_9_pick<PyStr, void>
  {
    static PyInt __call__(PyStr x)
    {
      return 2;
    }
  };

  template<>
  struct __py2cpp_type_if_type_tag_9_pick<PyBool, void>
  {
    static PyInt __call__(PyBool x)
    {
      return 2;
    }
  };

  template<>
  struct __py2cpp_type_if_type_tag_9_pick<PyList<PyInt>, void>
  {
    static PyInt __call__(PyList<PyInt> x)
    {
      return 3;
    }
  };

  template<typename T>
  struct __py2cpp_type_if_type_tag_9_pick<T, void>
  {
    static PyInt __call__(T x)
    {
      return 0;
    }
  };

  template<typename T>
  PyInt type_tag(T x)
  {
    return __py2cpp_type_if_type_tag_9_pick<T, void>::__call__(x);
  }
  template<typename T, typename = void>
  struct __py2cpp_type_if_type_not_int_20_pick;

  template<typename T>
  struct __py2cpp_type_if_type_not_int_20_pick<T, typename std::enable_if<!std::is_same<T, PyInt>::value, void>::type>
  {
    static PyInt __call__(T x)
    {
      return 0;
    }
  };

  template<>
  struct __py2cpp_type_if_type_not_int_20_pick<PyInt, void>
  {
    static PyInt __call__(PyInt x)
    {
      return 1;
    }
  };

  template<typename T>
  PyInt type_not_int(T x)
  {
    return __py2cpp_type_if_type_not_int_20_pick<T, void>::__call__(x);
  }
  template<typename T, typename = void>
  struct __py2cpp_type_if_tally_27_pick;

  template<>
  struct __py2cpp_type_if_tally_27_pick<PyInt, void>
  {
    static PyInt __call__()
    {
      PyInt n = 0;
      for (int i = 0; i < 3; i += 1)
      {
        n += 1;
      }
      return n;
    }
  };

  template<>
  struct __py2cpp_type_if_tally_27_pick<PyStr, void>
  {
    static PyInt __call__()
    {
      PyInt n = 0;
      for (int i = 0; i < 3; i += 1)
      {
        n += 2;
      }
      return n;
    }
  };

  template<typename T>
  struct __py2cpp_type_if_tally_27_pick<T, void>
  {
    static PyInt __call__()
    {
      PyInt n = 0;
      for (int i = 0; i < 3; i += 1)
      {
      }
      return n;
    }
  };

  template<typename T>
  PyInt tally()
  {
    PyInt n = 0;
    return __py2cpp_type_if_tally_27_pick<T, void>::__call__();
  }
  template<typename T, typename = void>
  struct __py2cpp_type_if_type_not_in_num_39_pick;

  template<typename T>
  struct __py2cpp_type_if_type_not_in_num_39_pick<T, typename std::enable_if<!(std::is_same<T, PyInt>::value || std::is_same<T, PyFloat>::value), void>::type>
  {
    static PyInt __call__(T x)
    {
      return 0;
    }
  };

  template<>
  struct __py2cpp_type_if_type_not_in_num_39_pick<PyInt, void>
  {
    static PyInt __call__(PyInt x)
    {
      return 1;
    }
  };

  template<>
  struct __py2cpp_type_if_type_not_in_num_39_pick<PyFloat, void>
  {
    static PyInt __call__(PyFloat x)
    {
      return 1;
    }
  };

  template<typename T>
  PyInt type_not_in_num(T x)
  {
    return __py2cpp_type_if_type_not_in_num_39_pick<T, void>::__call__(x);
  }
  template<typename T, typename = void>
  struct __py2cpp_type_if_type_list_wildcard_46_pick;

  template<>
  struct __py2cpp_type_if_type_list_wildcard_46_pick<PyList<PyInt>, void>
  {
    static PyInt __call__(PyList<PyInt> x)
    {
      return 1;
    }
  };

  template<typename _Ty0>
  struct __py2cpp_type_if_type_list_wildcard_46_pick<PyList<_Ty0>, void>
  {
    static PyInt __call__(PyList<_Ty0> x)
    {
      return 2;
    }
  };

  template<typename T>
  struct __py2cpp_type_if_type_list_wildcard_46_pick<T, void>
  {
    static PyInt __call__(T x)
    {
      return 0;
    }
  };

  template<typename T>
  PyInt type_list_wildcard(T x)
  {
    return __py2cpp_type_if_type_list_wildcard_46_pick<T, void>::__call__(x);
  }
  template<typename T, typename = void>
  struct __py2cpp_type_if_elem_code_55_pick;

  template<>
  struct __py2cpp_type_if_elem_code_55_pick<PyInt, void>
  {
    static PyInt __call__()
    {
      return 1;
    }
  };

  template<>
  struct __py2cpp_type_if_elem_code_55_pick<PyList<PyInt>, void>
  {
    static PyInt __call__()
    {
      return 2;
    }
  };

  template<>
  struct __py2cpp_type_if_elem_code_55_pick<PyStr, void>
  {
    static PyInt __call__()
    {
      return 3;
    }
  };

  template<>
  struct __py2cpp_type_if_elem_code_55_pick<PyList<PyStr>, void>
  {
    static PyInt __call__()
    {
      return 4;
    }
  };

  template<typename T>
  struct __py2cpp_type_if_elem_code_55_pick<T, void>
  {
    static PyInt __call__()
    {
      return 0;
    }
  };

  template<typename T>
  PyInt elem_code()
  {
    return __py2cpp_type_if_elem_code_55_pick<T, void>::__call__();
  }
  template<typename T, typename = void>
  struct __py2cpp_type_if_inner_code_68_pick;

  template<>
  struct __py2cpp_type_if_inner_code_68_pick<PyInt, void>
  {
    static PyInt __call__()
    {
      return 10;
    }
  };

  template<>
  struct __py2cpp_type_if_inner_code_68_pick<PyList<PyInt>, void>
  {
    static PyInt __call__()
    {
      return 11;
    }
  };

  template<>
  struct __py2cpp_type_if_inner_code_68_pick<PyList<PyList<PyInt>>, void>
  {
    static PyInt __call__()
    {
      return 12;
    }
  };

  template<typename T>
  struct __py2cpp_type_if_inner_code_68_pick<T, void>
  {
    static PyInt __call__()
    {
      return 0;
    }
  };

  template<typename T>
  PyInt inner_code()
  {
    return __py2cpp_type_if_inner_code_68_pick<T, void>::__call__();
  }
  template<typename T, typename = void>
  struct __py2cpp_type_if_pointee_code_79_pick;

  template<>
  struct __py2cpp_type_if_pointee_code_79_pick<PyInt*, void>
  {
    static PyInt __call__()
    {
      return 1;
    }
  };

  template<>
  struct __py2cpp_type_if_pointee_code_79_pick<PyInt, void>
  {
    static PyInt __call__()
    {
      return 2;
    }
  };

  template<>
  struct __py2cpp_type_if_pointee_code_79_pick<PyStr*, void>
  {
    static PyInt __call__()
    {
      return 3;
    }
  };

  template<typename T>
  struct __py2cpp_type_if_pointee_code_79_pick<T, void>
  {
    static PyInt __call__()
    {
      return 0;
    }
  };

  template<typename T>
  PyInt pointee_code()
  {
    return __py2cpp_type_if_pointee_code_79_pick<T, void>::__call__();
  }
  template<typename T>
  T take_elem(ElementOf<T> x)
  {
    return static_cast<T>(x);
  }
} // namespace test_type_if
using namespace test_type_if;

