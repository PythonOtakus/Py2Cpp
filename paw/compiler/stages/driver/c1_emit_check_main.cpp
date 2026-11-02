// Thin mid_emit check.paw against thin syntax_nodes (name-uniqueness).
#include <cstdio>

#include "frontend/source.cpp"
#include "frontend/syntax_nodes.cpp"
#include "passes/check.cpp"

int main() {
  PySyntaxModule mod{};
  PyFunctionBundle f1{};
  f1.name = PyStr("foo");
  PyFunctionBundle f2{};
  f2.name = PyStr("foo");
  (void)mod.functions.append(f1);
  if (!checkOk(mod)) {
    std::printf("FAIL checkOk single fn\n");
    return 1;
  }
  (void)mod.functions.append(f2);
  if (checkOk(mod)) {
    std::printf("FAIL checkOk duplicate fn should fail\n");
    return 1;
  }
  PyList<PyStr, 0> diags = checkModule(mod);
  if (diags.__len__() < 1) {
    std::printf("FAIL checkModule empty diags\n");
    return 1;
  }
  std::printf("OK c1_emit_check_main dup-detect\n");
  return 0;
}
