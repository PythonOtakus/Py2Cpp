// 由 py2cpp 自动生成，请勿手动编辑
// 源文件: C:\Users\Anantian\source\repos\Py2Cpp\test\lang\test_lazy_param.py
// 生成时间: 2026-06-15 18:55:15

#ifndef TEST_LAZY_PARAM_H
#define TEST_LAZY_PARAM_H

// C++11，无 STL；运行时见 runtime/py2cpp/，编译时 -I 该 runtime 目录
#include "py2cpp/minimal.h"
#include "py2cpp/test/unittest.h"

PyInt main();

/// ``T @lazy`` 形参：惰性 default、first-touch memo、supplier 透传。
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

  class LazyParamSkipDefaultTests;
  class LazyParamRunDefaultTests;
  class LazyParamLiteralDefaultTests;
  class LazyParamMissingArgTests;
  class LazyParamForwardTests;

  static PyInt _side = 0;

  class LazyParamSkipDefaultTests : public py2cpp::test::unittest::TestCase
  {
  public:
    using __base__ = TestCase;
    void test() override;
    void run(TestResult& result);
    PyBool __bool__() const;
    virtual ~LazyParamSkipDefaultTests();
    virtual PyStr __repr__() const;
    virtual PyStr __str__() const;
    operator PyStr() const;
    operator PyBool() const;
    static const PyInt __py2cpp_class_id__;
    static PyInt __id____get();
    virtual PyInt __class_id____get() const;
  protected:
    static const PyInt _test_tag = 10;
  };

  class LazyParamRunDefaultTests : public py2cpp::test::unittest::TestCase
  {
  public:
    using __base__ = TestCase;
    void test() override;
    void run(TestResult& result);
    PyBool __bool__() const;
    virtual ~LazyParamRunDefaultTests();
    virtual PyStr __repr__() const;
    virtual PyStr __str__() const;
    operator PyStr() const;
    operator PyBool() const;
    static const PyInt __py2cpp_class_id__;
    static PyInt __id____get();
    virtual PyInt __class_id____get() const;
  protected:
    static const PyInt _test_tag = 20;
  };

  class LazyParamLiteralDefaultTests : public py2cpp::test::unittest::TestCase
  {
  public:
    using __base__ = TestCase;
    void test() override;
    void run(TestResult& result);
    PyBool __bool__() const;
    virtual ~LazyParamLiteralDefaultTests();
    virtual PyStr __repr__() const;
    virtual PyStr __str__() const;
    operator PyStr() const;
    operator PyBool() const;
    static const PyInt __py2cpp_class_id__;
    static PyInt __id____get();
    virtual PyInt __class_id____get() const;
  protected:
    static const PyInt _test_tag = 30;
  };

  class LazyParamMissingArgTests : public py2cpp::test::unittest::TestCase
  {
  public:
    using __base__ = TestCase;
    void test() override;
    void run(TestResult& result);
    PyBool __bool__() const;
    virtual ~LazyParamMissingArgTests();
    virtual PyStr __repr__() const;
    virtual PyStr __str__() const;
    operator PyStr() const;
    operator PyBool() const;
    static const PyInt __py2cpp_class_id__;
    static PyInt __id____get();
    virtual PyInt __class_id____get() const;
  protected:
    static const PyInt _test_tag = 40;
  };

  class LazyParamForwardTests : public py2cpp::test::unittest::TestCase
  {
  public:
    using __base__ = TestCase;
    void test() override;
    void run(TestResult& result);
    PyBool __bool__() const;
    virtual ~LazyParamForwardTests();
    virtual PyStr __repr__() const;
    virtual PyStr __str__() const;
    operator PyStr() const;
    operator PyBool() const;
    static const PyInt __py2cpp_class_id__;
    static PyInt __id____get();
    virtual PyInt __class_id____get() const;
  protected:
    static const PyInt _test_tag = 50;
  };

  PyInt _bump();
  PyInt _wrap_get(const PyDict<PyInt, PyInt>& d, PyInt key, PyCallable<PyInt> default_value = PyCallable<PyInt>());

} // namespace test_lazy_param
#endif // TEST_LAZY_PARAM_H
