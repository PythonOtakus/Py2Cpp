// Run thin-emitted fixture_foo (functions emitted by thin mid/emit_cpp).
#include <cstdio>

#include "mid/fixture_foo.cpp"

int main() {
  if (foo(42) != 42) {
    std::printf("FAIL thin foo(42)\n");
    return 1;
  }
  if (add1(41) != 42) {
    std::printf("FAIL thin add1(41)\n");
    return 1;
  }
  if (pick(7) != 7 || pick(-3) != 0) {
    std::printf("FAIL thin pick\n");
    return 1;
  }
  std::printf("OK c1_emit_thin_foo_main foo/add1/pick\n");
  return 0;
}
