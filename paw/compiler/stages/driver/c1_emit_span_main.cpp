// Thin emit vertical: source + tokens (FileId/SourceSpan/TokenKind/makeSpan).
#include <cstdio>

#include "frontend/source.cpp"
#include "frontend/tokens.cpp"

int main() {
  if (static_cast<int>(PyTokenKindEnum::End) != 0) {
    std::printf("FAIL End != 0\n");
    return 1;
  }
  if (static_cast<int>(PyTokenKindEnum::Newline) != 1) {
    std::printf("FAIL Newline != 1\n");
    return 1;
  }
  if (static_cast<int>(PyTokenKindEnum::Name) != 4) {
    std::printf("FAIL Name != 4\n");
    return 1;
  }
  PyFileId fid{};
  if (fid.value != 0) {
    std::printf("FAIL FileId.value default\n");
    return 1;
  }
  PySourceSpan sp = makeSpan(7, 1, 3);
  if (sp.fileId.value != 7 || sp.start != 1 || sp.end != 3) {
    std::printf("FAIL makeSpan fields file=%lld start=%lld end=%lld\n",
                static_cast<long long>(sp.fileId.value),
                static_cast<long long>(sp.start),
                static_cast<long long>(sp.end));
    return 1;
  }
  bool threw = false;
  try {
    (void)makeSpan(1, 5, 2);
  } catch (const paw::core::exceptions::PyValueError&) {
    threw = true;
  } catch (...) {
    std::printf("FAIL makeSpan bad range wrong exception\n");
    return 1;
  }
  if (!threw) {
    std::printf("FAIL makeSpan bad range no throw\n");
    return 1;
  }
  PyToken tok = makeNameToken(7, 1, 3, PyStr("x"));
  if (tok.kind != PyTokenKindEnum::Name || tok.span.start != 1 ||
      tok.span.end != 3 || tok.text != PyStr("x")) {
    std::printf("FAIL makeNameToken fields\n");
    return 1;
  }
  if (static_cast<int>(PyTokenKindEnum::Ellipsis) < 20) {
    std::printf("FAIL Ellipsis ordinal too small\n");
    return 1;
  }
  std::printf("OK c1_emit_span_main enum+makeSpan\n");
  return 0;
}
