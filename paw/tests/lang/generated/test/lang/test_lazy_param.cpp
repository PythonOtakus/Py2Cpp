// 由 py2cpp 自动生成
// 源文件: C:\Users\Anantian\source\repos\Py2Cpp\test\lang\test_lazy_param.py
// 生成时间: 2026-06-15 18:55:15
#include "test_lazy_param.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

namespace test_lazy_param
{
  using namespace py2cpp;
  using ::py2cpp::test::unittest::TestCase;
  using ::py2cpp::test::unittest::TestSuite;
  using ::py2cpp::test::unittest::TextTestRunner;
  using ::py2cpp::test::unittest::TestCase;
  using ::py2cpp::test::unittest::TestResult;
  using ::py2cpp::test::unittest::TestSuite;
  using ::py2cpp::test::unittest::TextTestRunner;
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
  using ::py2cpp::util::py_set::PyFrozenSet;
  using ::py2cpp::util::py_set::PyFrozenSetEntry;
  using ::py2cpp::util::py_set::PyFrozenSetIterator;
  using ::py2cpp::util::py_set::PySet;
  using ::py2cpp::util::py_set::PySetIterator;
  using ::py2cpp::util::py_set::PySetReverseIterator;
  using ::py2cpp::text::bytes::PyBytes;
  using ::py2cpp::text::bytes::bytes_xrsplit_generator;
  using ::py2cpp::text::bytes::bytes_xsplit_generator;
  using ::py2cpp::text::bytes::bytes_xsplitlines_generator;
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
  using ::py2cpp::util::deque::PyDeque;
  using ::py2cpp::util::deque::PyDequeIterator;
  using ::py2cpp::util::deque::PyDequeNode;
  using ::py2cpp::util::deque::PyDequeReverseIterator;
  using ::py2cpp::util::array::PyArray;
  using ::py2cpp::util::array::PyArray2D;
  using ::py2cpp::util::array::PyArray3D;
  using ::py2cpp::util::slice::PySlice;
  using ::py2cpp::util::misc::Counter;
  using ::py2cpp::util::misc::CounterElementsIterator;
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
  using ::py2cpp::util::list::PyFrozenList;
  using ::py2cpp::util::list::PyFrozenListIterator;
  using ::py2cpp::util::list::PyList;
  using ::py2cpp::util::list::PyListIterator;
  using ::py2cpp::util::list::PyListReverseIterator;
  using ::py2cpp::io::PyStringIO;
  using ::py2cpp::io::PyTextIOWrapper;
  using ::py2cpp::util::pool::PyPool;
  using ::py2cpp::util::pool::pool_slot_loc;
  using ::py2cpp::numeric::varint::PyVarInt;
  using ::py2cpp::core::iter_result::PyIterResult;
  using ::py2cpp::text::str::PyStr;
  using ::py2cpp::text::str::PyStrIterator;
  using ::py2cpp::text::str::PyStrReverseIterator;
  using ::py2cpp::text::str::str_xrsplit_generator;
  using ::py2cpp::text::str::str_xsplit_generator;
  using ::py2cpp::text::str::str_xsplitlines_generator;
  using ::py2cpp::numeric::complex::PyComplex;
  using ::py2cpp::system::time::c_time;
  using ::py2cpp::PyEnumerateIterator;
  using ::py2cpp::PyZipIterator;
  using ::py2cpp::VarStack;
  using ::py2cpp::_EnumMroDec;
  using ::py2cpp::_MacroProbe;
  using ::py2cpp::_UnionMroDec;

  void test_lazy_param::LazyParamSkipDefaultTests::test()
  {
    PyInt _side = 0;
    PyDict<PyInt, PyInt> d;
    d.__setitem__(10, 100);
    this->assertEqual(d.get(10, ([&]() { auto _lazy_lam_2 = [&]() { return _bump(); }; return PyCallable<PyInt>{ (void*)&_lazy_lam_2, &py_callable_lambda_invoke<decltype(_lazy_lam_2), PyInt>::call }; })()), 100);
    this->assertEqual(_side, 0);
  }

  void test_lazy_param::LazyParamSkipDefaultTests::run(TestResult& result)
  {
    this->begin_test(result, LazyParamSkipDefaultTests::_test_tag, PyStr("LazyParamSkipDefaultTests"));
    this->test();
    this->end_test(result);
  }

  PyBool test_lazy_param::LazyParamSkipDefaultTests::__bool__() const
  {
    return true;
  }

  PyStr test_lazy_param::LazyParamSkipDefaultTests::__repr__() const
  {
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", "__main__", "LazyParamSkipDefaultTests", (unsigned long long)(size_t)(const void*)(this));
    return PyStr(buf);
  }

  PyStr test_lazy_param::LazyParamSkipDefaultTests::__str__() const
  {
    return this->__repr__();
  }

  const PyInt test_lazy_param::LazyParamSkipDefaultTests::__py2cpp_class_id__ = 2;

  PyInt test_lazy_param::LazyParamSkipDefaultTests::__class_id____get() const
  {
    return __py2cpp_class_id__;
  }

  PyInt test_lazy_param::LazyParamSkipDefaultTests::__id____get()
  {
    return __py2cpp_class_id__;
  }

  test_lazy_param::LazyParamSkipDefaultTests::operator PyStr() const
  {
    return __str__();
  }
  test_lazy_param::LazyParamSkipDefaultTests::operator PyBool() const
  {
    return __bool__();
  }
  test_lazy_param::LazyParamSkipDefaultTests::~LazyParamSkipDefaultTests()
  {
  }

  void test_lazy_param::LazyParamRunDefaultTests::test()
  {
    PyInt _side = 0;
    PyDict<PyInt, PyInt> d;
    d.__setitem__(10, 100);
    this->assertEqual(d.get(99, ([&]() { auto _lazy_lam_4 = [&]() { return _bump(); }; return PyCallable<PyInt>{ (void*)&_lazy_lam_4, &py_callable_lambda_invoke<decltype(_lazy_lam_4), PyInt>::call }; })()), 1);
    this->assertEqual(_side, 1);
  }

  void test_lazy_param::LazyParamRunDefaultTests::run(TestResult& result)
  {
    this->begin_test(result, LazyParamRunDefaultTests::_test_tag, PyStr("LazyParamRunDefaultTests"));
    this->test();
    this->end_test(result);
  }

  PyBool test_lazy_param::LazyParamRunDefaultTests::__bool__() const
  {
    return true;
  }

  PyStr test_lazy_param::LazyParamRunDefaultTests::__repr__() const
  {
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", "__main__", "LazyParamRunDefaultTests", (unsigned long long)(size_t)(const void*)(this));
    return PyStr(buf);
  }

  PyStr test_lazy_param::LazyParamRunDefaultTests::__str__() const
  {
    return this->__repr__();
  }

  const PyInt test_lazy_param::LazyParamRunDefaultTests::__py2cpp_class_id__ = 3;

  PyInt test_lazy_param::LazyParamRunDefaultTests::__class_id____get() const
  {
    return __py2cpp_class_id__;
  }

  PyInt test_lazy_param::LazyParamRunDefaultTests::__id____get()
  {
    return __py2cpp_class_id__;
  }

  test_lazy_param::LazyParamRunDefaultTests::operator PyStr() const
  {
    return __str__();
  }
  test_lazy_param::LazyParamRunDefaultTests::operator PyBool() const
  {
    return __bool__();
  }
  test_lazy_param::LazyParamRunDefaultTests::~LazyParamRunDefaultTests()
  {
  }

  void test_lazy_param::LazyParamLiteralDefaultTests::test()
  {
    PyDict<PyInt, PyInt> d;
    d.__setitem__(1, 2);
    this->assertEqual(d.get(9, ([&]() { auto _lazy_lam_6 = [&]() { return 0; }; return PyCallable<PyInt>{ (void*)&_lazy_lam_6, &py_callable_lambda_invoke<decltype(_lazy_lam_6), PyInt>::call }; })()), 0);
  }

  void test_lazy_param::LazyParamLiteralDefaultTests::run(TestResult& result)
  {
    this->begin_test(result, LazyParamLiteralDefaultTests::_test_tag, PyStr("LazyParamLiteralDefaultTests"));
    this->test();
    this->end_test(result);
  }

  PyBool test_lazy_param::LazyParamLiteralDefaultTests::__bool__() const
  {
    return true;
  }

  PyStr test_lazy_param::LazyParamLiteralDefaultTests::__repr__() const
  {
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", "__main__", "LazyParamLiteralDefaultTests", (unsigned long long)(size_t)(const void*)(this));
    return PyStr(buf);
  }

  PyStr test_lazy_param::LazyParamLiteralDefaultTests::__str__() const
  {
    return this->__repr__();
  }

  const PyInt test_lazy_param::LazyParamLiteralDefaultTests::__py2cpp_class_id__ = 4;

  PyInt test_lazy_param::LazyParamLiteralDefaultTests::__class_id____get() const
  {
    return __py2cpp_class_id__;
  }

  PyInt test_lazy_param::LazyParamLiteralDefaultTests::__id____get()
  {
    return __py2cpp_class_id__;
  }

  test_lazy_param::LazyParamLiteralDefaultTests::operator PyStr() const
  {
    return __str__();
  }
  test_lazy_param::LazyParamLiteralDefaultTests::operator PyBool() const
  {
    return __bool__();
  }
  test_lazy_param::LazyParamLiteralDefaultTests::~LazyParamLiteralDefaultTests()
  {
  }

  void test_lazy_param::LazyParamMissingArgTests::test()
  {
    PyDict<PyInt, PyInt> d;
    d.__setitem__(1, 2);
    PyInt v = d.get(9);
    this->assertEqual(v, 0);
  }

  void test_lazy_param::LazyParamMissingArgTests::run(TestResult& result)
  {
    this->begin_test(result, LazyParamMissingArgTests::_test_tag, PyStr("LazyParamMissingArgTests"));
    this->test();
    this->end_test(result);
  }

  PyBool test_lazy_param::LazyParamMissingArgTests::__bool__() const
  {
    return true;
  }

  PyStr test_lazy_param::LazyParamMissingArgTests::__repr__() const
  {
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", "__main__", "LazyParamMissingArgTests", (unsigned long long)(size_t)(const void*)(this));
    return PyStr(buf);
  }

  PyStr test_lazy_param::LazyParamMissingArgTests::__str__() const
  {
    return this->__repr__();
  }

  const PyInt test_lazy_param::LazyParamMissingArgTests::__py2cpp_class_id__ = 5;

  PyInt test_lazy_param::LazyParamMissingArgTests::__class_id____get() const
  {
    return __py2cpp_class_id__;
  }

  PyInt test_lazy_param::LazyParamMissingArgTests::__id____get()
  {
    return __py2cpp_class_id__;
  }

  test_lazy_param::LazyParamMissingArgTests::operator PyStr() const
  {
    return __str__();
  }
  test_lazy_param::LazyParamMissingArgTests::operator PyBool() const
  {
    return __bool__();
  }
  test_lazy_param::LazyParamMissingArgTests::~LazyParamMissingArgTests()
  {
  }

  void test_lazy_param::LazyParamForwardTests::test()
  {
    PyInt _side = 0;
    PyDict<PyInt, PyInt> d;
    d.__setitem__(5, 50);
    this->assertEqual(_wrap_get(d, 5, ([&]() { auto _lazy_lam_8 = [&]() { return _bump(); }; return PyCallable<PyInt>{ (void*)&_lazy_lam_8, &py_callable_lambda_invoke<decltype(_lazy_lam_8), PyInt>::call }; })()), 50);
    this->assertEqual(_side, 0);
    this->assertEqual(_wrap_get(d, 1, ([&]() { auto _lazy_lam_10 = [&]() { return _bump(); }; return PyCallable<PyInt>{ (void*)&_lazy_lam_10, &py_callable_lambda_invoke<decltype(_lazy_lam_10), PyInt>::call }; })()), 1);
    this->assertEqual(_side, 1);
  }

  void test_lazy_param::LazyParamForwardTests::run(TestResult& result)
  {
    this->begin_test(result, LazyParamForwardTests::_test_tag, PyStr("LazyParamForwardTests"));
    this->test();
    this->end_test(result);
  }

  PyBool test_lazy_param::LazyParamForwardTests::__bool__() const
  {
    return true;
  }

  PyStr test_lazy_param::LazyParamForwardTests::__repr__() const
  {
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s.%s object at 0x%llx>", "__main__", "LazyParamForwardTests", (unsigned long long)(size_t)(const void*)(this));
    return PyStr(buf);
  }

  PyStr test_lazy_param::LazyParamForwardTests::__str__() const
  {
    return this->__repr__();
  }

  const PyInt test_lazy_param::LazyParamForwardTests::__py2cpp_class_id__ = 6;

  PyInt test_lazy_param::LazyParamForwardTests::__class_id____get() const
  {
    return __py2cpp_class_id__;
  }

  PyInt test_lazy_param::LazyParamForwardTests::__id____get()
  {
    return __py2cpp_class_id__;
  }

  test_lazy_param::LazyParamForwardTests::operator PyStr() const
  {
    return __str__();
  }
  test_lazy_param::LazyParamForwardTests::operator PyBool() const
  {
    return __bool__();
  }
  test_lazy_param::LazyParamForwardTests::~LazyParamForwardTests()
  {
  }

  PyInt _bump()
  {
    PyInt _side = (_side + 1);
    return _side;
  }
  PyInt _wrap_get(const PyDict<PyInt, PyInt>& d, PyInt key, PyCallable<PyInt> default_value)
  {
    return d.get(key, ([&]() { auto _lazy_lam_11 = [&]() { return default_value; }; return PyCallable<PyInt>{ (void*)&_lazy_lam_11, &py_callable_lambda_invoke<decltype(_lazy_lam_11), PyInt>::call }; })());
  }
} // namespace test_lazy_param
using namespace test_lazy_param;

PyInt main()
{
  TestSuite suite = TestSuite();
  suite.addTest(makeRefCount<LazyParamSkipDefaultTests>());
  suite.addTest(makeRefCount<LazyParamRunDefaultTests>());
  suite.addTest(makeRefCount<LazyParamLiteralDefaultTests>());
  suite.addTest(makeRefCount<LazyParamMissingArgTests>());
  suite.addTest(makeRefCount<LazyParamForwardTests>());
  return (::py2cpp::test::unittest::TextTestRunner()).run(suite);
}
