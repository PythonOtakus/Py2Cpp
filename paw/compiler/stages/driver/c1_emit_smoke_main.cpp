// Single-TU runner for thin mid_emit smoke (avoid LNK2005 on runtime .inl).
#include <cstdio>

#include "frontend/smoke.cpp"

int main() {
  const PyInt got = foo(42);
  if (got != 42) {
    std::printf("FAIL c1_emit_smoke_main foo(42)=%lld\n",
                static_cast<long long>(got));
    return 1;
  }
  bar();
  std::printf("OK c1_emit_smoke_main foo(42)=42\n");
  return 0;
}
