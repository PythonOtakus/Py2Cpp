// Thin emit lexer vertical + dual tokenize dump (D1).
#include <cstdio>

#include "frontend/source.cpp"
#include "frontend/tokens.cpp"
#include "frontend/diagnostic.cpp"
#include "frontend/lexer.cpp"

static const char* kindName(PyTokenKindEnum k) {
  switch (k) {
    case PyTokenKindEnum::End:
      return "End";
    case PyTokenKindEnum::Newline:
      return "Newline";
    case PyTokenKindEnum::Indent:
      return "Indent";
    case PyTokenKindEnum::Dedent:
      return "Dedent";
    case PyTokenKindEnum::Name:
      return "Name";
    case PyTokenKindEnum::Number:
      return "Number";
    case PyTokenKindEnum::String:
      return "String";
    case PyTokenKindEnum::Op:
      return "Op";
    case PyTokenKindEnum::Comment:
      return "Comment";
    case PyTokenKindEnum::KwEnum:
      return "KwEnum";
    case PyTokenKindEnum::KwUnion:
      return "KwUnion";
    case PyTokenKindEnum::Colon:
      return "Colon";
    case PyTokenKindEnum::Comma:
      return "Comma";
    case PyTokenKindEnum::Dot:
      return "Dot";
    case PyTokenKindEnum::Lpar:
      return "Lpar";
    case PyTokenKindEnum::Rpar:
      return "Rpar";
    case PyTokenKindEnum::Lsqb:
      return "Lsqb";
    case PyTokenKindEnum::Rsqb:
      return "Rsqb";
    case PyTokenKindEnum::Lbrace:
      return "Lbrace";
    case PyTokenKindEnum::Rbrace:
      return "Rbrace";
    case PyTokenKindEnum::Eq:
      return "Eq";
    case PyTokenKindEnum::Arrow:
      return "Arrow";
    case PyTokenKindEnum::Rarrow:
      return "Rarrow";
    case PyTokenKindEnum::At:
      return "At";
    case PyTokenKindEnum::Question:
      return "Question";
    case PyTokenKindEnum::Bang:
      return "Bang";
    case PyTokenKindEnum::Ellipsis:
      return "Ellipsis";
    default:
      return "?";
  }
}

static void printEscaped(const PyStr& s) {
  for (PyInt i = 0; i < s.__len__(); i += 1) {
    const int32_t cp = static_cast<int32_t>(s.__getitem__(i));
    if (cp == '\\') {
      std::printf("\\\\");
    } else if (cp == '\n') {
      std::printf("\\n");
    } else if (cp == '\r') {
      std::printf("\\r");
    } else if (cp == '\t') {
      std::printf("\\t");
    } else if (cp >= 32 && cp < 127) {
      std::printf("%c", static_cast<char>(cp));
    } else {
      std::printf("\\u{%x}", static_cast<unsigned>(cp));
    }
  }
}

int main() {
  PyFileId fid{};
  fid.value = 0;
  PyLexer lx(PyStr("x = 1\n"), fid);
  PyList<PyToken, 0> toks = lx.tokenize();
  if (toks.__len__() < 4) {
    std::printf("FAIL tokenize too short len=%lld\n",
                static_cast<long long>(toks.__len__()));
    return 1;
  }
  PyToken t0 = toks.__getitem__(0);
  if (t0.kind != PyTokenKindEnum::Name || t0.text != PyStr("x")) {
    std::printf("FAIL tok0 Name x\n");
    return 1;
  }
  PyToken t1 = toks.__getitem__(1);
  if (t1.kind != PyTokenKindEnum::Eq) {
    std::printf("FAIL tok1 Eq\n");
    return 1;
  }
  PyToken t2 = toks.__getitem__(2);
  if (t2.kind != PyTokenKindEnum::Number || t2.text != PyStr("1")) {
    std::printf("FAIL tok2 Number 1\n");
    return 1;
  }
  PyToken last = toks.__getitem__(toks.__len__() - 1);
  if (last.kind != PyTokenKindEnum::End) {
    std::printf("FAIL last End\n");
    return 1;
  }

  std::printf("===TOKEN_DUMP===\n");
  for (PyInt i = 0; i < toks.__len__(); i += 1) {
    PyToken t = toks.__getitem__(i);
    std::printf("%s\t%lld\t%lld\t", kindName(t.kind),
                static_cast<long long>(t.span.start),
                static_cast<long long>(t.span.end));
    printEscaped(t.text);
    std::printf("\n");
  }
  std::printf("===END_DUMP===\n");
  std::printf("OK c1_emit_lexer_main tokenize x=1\n");
  return 0;
}
