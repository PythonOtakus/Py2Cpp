// Host-only EXEC / BEGIN(def) — expand_py2cpp_template tests; native gate SKIP.
PY2CPP_EXEC(MARKER = 42)
PY2CPP_BEGIN( for k in range(0, 2) )
  PY2CPP_EXEC(if k == 0: __py2cpp_echo('// first'))
  mark[PY2CPP_EVAL(k)] = PY2CPP_EVAL(k);
PY2CPP_END
PY2CPP_BEGIN( def fn_EmitLines(in_Items) )
PY2CPP_BEGIN( for x in in_Items )
line PY2CPP_EVAL(x);
PY2CPP_END
PY2CPP_END
PY2CPP_EXEC(fn_EmitLines(items))
