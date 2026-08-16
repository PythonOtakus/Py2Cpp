"""线性代数（``float64`` 向量 ``span`` / 矩阵 ``span2d``，参考 ``numpy.linalg`` 子集）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import LinAlgError, ValueError
from ..util.span import span, span2d
from . import atan2, cos, fabs, sin, sqrt

_Eps: float64 = 1e-12


def _requireVec(v: span[float64]) -> int:
  n: int = len(v)
  if n <= 0:
    raise ValueError("vector must be non-empty")
  return n


def _requireSquare(a: span2d[float64]) -> int:
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if rows <= 0 or cols <= 0:
    raise ValueError("matrix must be non-empty")
  if rows != cols:
    raise ValueError("matrix must be square")
  return rows


def _copyMat(src: span2d[float64], out: span2d[float64]) -> None:
  rows: int = src.shape[0]
  cols: int = src.shape[1]
  if out.shape[0] != rows or out.shape[1] != cols:
    raise ValueError("matrix copy shape mismatch")
  for r in range(rows):
    for c in range(cols):
      out[r, c] = src[r, c]


def _swapRows(out: span2d[float64], r0: int, r1: int) -> None:
  cols: int = out.shape[1]
  for c in range(cols):
    t: float64 = out[r0, c]
    out[r0, c] = out[r1, c]
    out[r1, c] = t


def _swapVec(out: span[float64], i0: int, i1: int) -> None:
  t: float64 = out[i0]
  out[i0] = out[i1]
  out[i1] = t


def _luFactorInplace(work: span2d[float64], piv: span[int], n: int) -> None:
  for k in range(n):
    pivRow: int = k
    pivVal: float64 = fabs(work[k, k])
    for r in range(k + 1, n):
      v: float64 = fabs(work[r, k])
      if v > pivVal:
        pivVal = v
        pivRow = r
    if pivVal < _Eps:
      raise LinAlgError("singular matrix")
    piv[k] = pivRow
    if pivRow != k:
      _swapRows(work, k, pivRow)
    pivot: float64 = work[k, k]
    for r in range(k + 1, n):
      factor: float64 = work[r, k] / pivot
      work[r, k] = factor
      for c in range(k + 1, n):
        work[r, c] -= factor * work[k, c]


def _luSolveVecInplace(
  work: span2d[float64],
  x: span[float64],
  piv: span[int],
  n: int,
) -> None:
  for k in range(n):
    if piv[k] != k:
      _swapVec(x, k, piv[k])
  for k in range(n):
    for r in range(k + 1, n):
      x[r] -= work[r, k] * x[k]
  for r in range(n - 1, -1, -1):
    s: float64 = x[r]
    for c in range(r + 1, n):
      s -= work[r, c] * x[c]
    x[r] = s / work[r, r]


def _luSolveInplace(work: span2d[float64], x: span[float64]) -> None:
  n: int = work.shape[0]
  piv: int[:] = new(n)
  _luFactorInplace(work, piv.view, n)
  _luSolveVecInplace(work, x, piv.view, n)


def _symmetrize(a: span2d[float64], out: span2d[float64], n: int) -> None:
  for i in range(n):
    for j in range(i, n):
      if i == j:
        out[i, j] = a[i, j]
      else:
        v: float64 = 0.5 * (a[i, j] + a[j, i])
        out[i, j] = v
        out[j, i] = v


def _jacobiEighInplace(
  work: span2d[float64],
  vOut: span2d[float64],
  w: span[float64],
  n: int,
) -> None:
  for i in range(n):
    for j in range(n):
      if i == j:
        vOut[i, j] = 1.0
      else:
        vOut[i, j] = 0.0
  maxIter: int = 100 * n
  for _ in range(maxIter):
    p: int = 0
    q: int = 1
    maxOff: float64 = 0.0
    for i in range(n):
      for j in range(i + 1, n):
        v: float64 = fabs(work[i, j])
        if v > maxOff:
          maxOff = v
          p = i
          q = j
    if maxOff <= _Eps:
      break
    apq: float64 = work[p, q]
    if fabs(apq) <= _Eps:
      continue
    app: float64 = work[p, p]
    aqq: float64 = work[q, q]
    theta: float64 = 0.5 * atan2(2.0 * apq, aqq - app)
    c: float64 = cos(theta)
    s: float64 = sin(theta)
    for k in range(n):
      if k in {p, q}:
        continue
      wkp: float64 = work[k, p]
      wkq: float64 = work[k, q]
      work[k, p] = c * wkp - s * wkq
      work[p, k] = work[k, p]
      work[k, q] = s * wkp + c * wkq
      work[q, k] = work[k, q]
    work[p, p] = c * c * app - 2.0 * s * c * apq + s * s * aqq
    work[q, q] = s * s * app + 2.0 * s * c * apq + c * c * aqq
    work[p, q] = 0.0
    work[q, p] = 0.0
    for k in range(n):
      vkp: float64 = vOut[k, p]
      vkq: float64 = vOut[k, q]
      vOut[k, p] = c * vkp - s * vkq
      vOut[k, q] = s * vkp + c * vkq
  for i in range(n):
    w[i] = work[i, i]


def _gramAt(a: span2d[float64], out: span2d[float64]) -> None:
  """``out = a @ a.T``（``a`` 为 ``m×n``，``out`` 为 ``m×m``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if out.shape[0] != m or out.shape[1] != m:
    raise ValueError("gram_at: out shape mismatch")
  for i in range(m):
    for j in range(m):
      s: float64 = 0.0
      for k in range(n):
        s += a[i, k] * a[j, k]
      out[i, j] = s


def _fillEig2(
  a: float64,
  b: float64,
  c: float64,
  d: float64,
  wr: span[float64],
  wi: span[float64],
  i0: int,
) -> None:
  tr: float64 = a + d
  det: float64 = a * d - b * c
  disc: float64 = tr * tr - 4.0 * det
  if disc >= 0.0:
    s: float64 = sqrt(disc)
    wr[i0] = (tr + s) * 0.5
    wi[i0] = 0.0
    wr[i0 + 1] = (tr - s) * 0.5
    wi[i0 + 1] = 0.0
  else:
    half: float64 = tr * 0.5
    root: float64 = sqrt(-disc)
    im: float64 = root * 0.5
    wr[i0] = half
    wi[i0] = im
    wr[i0 + 1] = half
    wi[i0 + 1] = -im


def _wilkinsonShift(h: span2d[float64], active: int) -> float64:
  if active == 1:
    return h[0, 0]
  a: float64 = h[active - 2, active - 2]
  b: float64 = h[active - 2, active - 1]
  d: float64 = h[active - 1, active - 1]
  tr: float64 = a + d
  det: float64 = a * d - b * h[active - 1, active - 2]
  disc: float64 = tr * tr - 4.0 * det
  if disc >= 0.0:
    s: float64 = sqrt(disc)
    e0: float64 = (tr + s) * 0.5
    e1: float64 = (tr - s) * 0.5
    if fabs(d - e0) <= fabs(d - e1):
      return e0
    return e1
  return d


def _schurConverged(h: span2d[float64], n: int) -> bool:
  for i in range(1, n):
    scale: float64 = fabs(h[i - 1, i - 1]) + fabs(h[i, i])
    if fabs(h[i, i - 1]) > _Eps * scale:
      return False
  return True


def _extractEigvalsSchur(
  h: span2d[float64],
  wr: span[float64],
  wi: span[float64],
  n: int,
) -> None:
  i: int = 0
  while i < n:
    if i + 1 < n:
      scale: float64 = fabs(h[i, i]) + fabs(h[i + 1, i + 1])
      if fabs(h[i + 1, i]) > _Eps * scale:
        _fillEig2(h[i, i], h[i, i + 1], h[i + 1, i], h[i + 1, i + 1], wr, wi, i)
        i += 2
        continue
    wr[i] = h[i, i]
    wi[i] = 0.0
    i += 1


def _isSymmetric(a: span2d[float64], n: int) -> bool:
  for i in range(n):
    for j in range(i + 1, n):
      if fabs(a[i, j] - a[j, i]) > _Eps:
        return False
  return True


def _schurEigvals(
  a: span2d[float64],
  wr: span[float64],
  wi: span[float64],
  work: span2d[float64],
  q: span2d[float64],
  r: span2d[float64],
  col: span[float64],
) -> None:
  n: int = _requireSquare(a)
  _copyMat(a, work)
  maxIter: int = 50 * n + 200
  for _ in range(maxIter):
    if _schurConverged(work, n):
      break
    mu: float64 = _wilkinsonShift(work, n)
    for i in range(n):
      work[i, i] -= mu
    qr(work, q, r, col)
    matmul(r, q, work)
    for i in range(n):
      work[i, i] += mu
  _extractEigvalsSchur(work, wr, wi, n)


def dot(a: span[float64], b: span[float64]) -> float64:
  """一维向量内积。"""
  na: int = _requireVec(a)
  nb: int = _requireVec(b)
  if na != nb:
    raise ValueError("dot: size mismatch")
  s: float64 = 0.0
  for i in range(na):
    s += a[i] * b[i]
  return s


def vdot(a: span[float64], b: span[float64]) -> float64:
  """实向量内积（与 ``dot`` 相同）。"""
  return dot(a, b)


def matvec(a: span2d[float64], x: span[float64], out: span[float64]) -> None:
  """``out = a @ x``。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  nx: int = _requireVec(x)
  ny: int = _requireVec(out)
  if n != nx or m != ny:
    raise ValueError("matvec: shape mismatch")
  for r in range(m):
    s: float64 = 0.0
    for c in range(n):
      s += a[r, c] * x[c]
    out[r] = s


def matmul(a: span2d[float64], b: span2d[float64], out: span2d[float64]) -> None:
  """``out = a @ b``。"""
  m: int = a.shape[0]
  k: int = a.shape[1]
  kb: int = b.shape[0]
  n: int = b.shape[1]
  if k != kb:
    raise ValueError("matmul: inner dimension mismatch")
  if out.shape[0] != m or out.shape[1] != n:
    raise ValueError("matmul: out shape mismatch")
  for r in range(m):
    for c in range(n):
      s: float64 = 0.0
      for t in range(k):
        s += a[r, t] * b[t, c]
      out[r, c] = s


def transpose(a: span2d[float64], out: span2d[float64]) -> None:
  """``out = a.T``。"""
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if out.shape[0] != cols or out.shape[1] != rows:
    raise ValueError("transpose: out shape mismatch")
  for r in range(rows):
    for c in range(cols):
      out[c, r] = a[r, c]


def trace(a: span2d[float64]) -> float64:
  """主对角线之和。"""
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if rows <= 0 or cols <= 0:
    raise ValueError("trace: empty matrix")
  n: int = rows
  if cols < n:
    n = cols
  s: float64 = 0.0
  for i in range(n):
    s += a[i, i]
  return s


def norm(x: span[float64]) -> float64:
  """向量欧几里得范数。"""
  n: int = _requireVec(x)
  s: float64 = 0.0
  for i in range(n):
    v: float64 = x[i]
    s += v * v
  return sqrt(s)


def fnorm(a: span2d[float64]) -> float64:
  """矩阵 Frobenius 范数。"""
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if rows <= 0 or cols <= 0:
    raise ValueError("fnorm: empty matrix")
  s: float64 = 0.0
  for r in range(rows):
    for c in range(cols):
      v: float64 = a[r, c]
      s += v * v
  return sqrt(s)


def det(a: span2d[float64]) -> float64:
  """方阵行列式（内部拷贝，不修改 ``a``）。"""
  n: int = _requireSquare(a)
  tmp: float64[:, :] = new(n, n)
  work: span2d[float64] = tmp.view
  _copyMat(a, work)
  sign: float64 = 1.0
  prod: float64 = 1.0
  for k in range(n):
    pivRow: int = k
    pivVal: float64 = fabs(work[k, k])
    for r in range(k + 1, n):
      v: float64 = fabs(work[r, k])
      if v > pivVal:
        pivVal = v
        pivRow = r
    if pivVal < _Eps:
      raise LinAlgError("singular matrix")
    if pivRow != k:
      sign = -sign
      _swapRows(work, k, pivRow)
    pivot: float64 = work[k, k]
    prod *= pivot
    for r in range(k + 1, n):
      factor: float64 = work[r, k] / pivot
      work[r, k] = 0.0
      for c in range(k + 1, n):
        work[r, c] -= factor * work[k, c]
  return sign * prod


def solve(
  a: span2d[float64],
  b: span[float64],
  out: span[float64],
  work: span2d[float64],
) -> None:
  """解 ``a @ out = b``；``work`` 为 ``n×n`` 工作区，``a`` 不被修改。"""
  n: int = _requireSquare(a)
  nb: int = _requireVec(b)
  nx: int = _requireVec(out)
  if n != nb or n != nx:
    raise ValueError("solve: shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("solve: work shape mismatch")
  _copyMat(a, work)
  for i in range(n):
    out[i] = b[i]
  _luSolveInplace(work, out)


def solveMulti(
  a: span2d[float64],
  b: span2d[float64],
  out: span2d[float64],
  work: span2d[float64],
) -> None:
  """解 ``a @ out = b``（``b``/``out`` 为 ``n×k`` 多列右端项）。"""
  n: int = _requireSquare(a)
  k: int = b.shape[1]
  if b.shape[0] != n or out.shape[0] != n or out.shape[1] != k:
    raise ValueError("solveMulti: shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("solveMulti: work shape mismatch")
  piv: int[:] = new(n)
  col: float64[:] = new(n)
  _copyMat(a, work)
  _luFactorInplace(work, piv.view, n)
  for j in range(k):
    for i in range(n):
      col[i] = b[i, j]
    _luSolveVecInplace(work, col.view, piv.view, n)
    for i in range(n):
      out[i, j] = col[i]


def inv(
  a: span2d[float64],
  out: span2d[float64],
  work: span2d[float64],
) -> None:
  """``out = inv(a)``；``work`` 为 ``n×n`` 工作区，``a`` 不被修改。"""
  n: int = _requireSquare(a)
  if out.shape[0] != n or out.shape[1] != n:
    raise ValueError("inv: out shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("inv: work shape mismatch")
  e: float64[:] = new(n)
  x: float64[:] = new(n)
  for j in range(n):
    for i in range(n):
      e[i] = 0.0
    e[j] = 1.0
    solve(a, e.view, x.view, work)
    for i in range(n):
      out[i, j] = x[i]


def _gramA(a: span2d[float64], out: span2d[float64]) -> None:
  """``out = a.T @ a``（``a`` 为 ``m×n``，``out`` 为 ``n×n``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if out.shape[0] != n or out.shape[1] != n:
    raise ValueError("gram: out shape mismatch")
  for i in range(n):
    for j in range(n):
      s: float64 = 0.0
      for r in range(m):
        s += a[r, i] * a[r, j]
      out[i, j] = s


def _mulAtVec(a: span2d[float64], b: span[float64], out: span[float64]) -> None:
  """``out = a.T @ b``（``a`` 为 ``m×n``，``b`` 为 ``m``，``out`` 为 ``n``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  nb: int = _requireVec(b)
  nx: int = _requireVec(out)
  if m != nb or n != nx:
    raise ValueError("mul_at_vec: shape mismatch")
  for i in range(n):
    s: float64 = 0.0
    for r in range(m):
      s += a[r, i] * b[r]
    out[i] = s


def lstsq(
  a: span2d[float64],
  b: span[float64],
  out: span[float64],
  work: span2d[float64],
) -> None:
  """最小二乘 ``min ||a @ out - b||``（``m >= n`` 满秩；正规方程 + ``solve``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    raise ValueError("lstsq: empty matrix")
  if m < n:
    raise ValueError("lstsq requires m >= n")
  nb: int = _requireVec(b)
  nx: int = _requireVec(out)
  if m != nb or n != nx:
    raise ValueError("lstsq: shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("lstsq: work shape mismatch")
  rhs: float64[:] = new(n)
  _gramA(a, work)
  _mulAtVec(a, b, rhs.view)
  for i in range(n):
    out[i] = rhs[i]
  _luSolveInplace(work, out)


def matrixRank(a: span2d[float64], work: span2d[float64], tol: float64 = 1e-12) -> int:
  """列主元消元估计秩（``work`` 为与 ``a`` 同形工作区）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    return 0
  if work.shape[0] != m or work.shape[1] != n:
    raise ValueError("matrixRank: work shape mismatch")
  _copyMat(a, work)
  rank: int = 0
  row: int = 0
  for col in range(n):
    if row >= m:
      break
    pivRow: int = row
    pivVal: float64 = fabs(work[row, col])
    for r in range(row + 1, m):
      v: float64 = fabs(work[r, col])
      if v > pivVal:
        pivVal = v
        pivRow = r
    if pivVal <= tol:
      continue
    if pivRow != row:
      _swapRows(work, row, pivRow)
    pivot: float64 = work[row, col]
    for r in range(row + 1, m):
      factor: float64 = work[r, col] / pivot
      for c in range(col + 1, n):
        work[r, c] -= factor * work[row, c]
    row += 1
    rank += 1
  return rank


def cond(
  a: span2d[float64],
  invOut: span2d[float64],
  work: span2d[float64],
) -> float64:
  """Frobenius 条件数 ``fnorm(a) * fnorm(inv(a))``（``invOut``/``work`` 同 ``inv``）。"""
  n: int = _requireSquare(a)
  if invOut.shape[0] != n or invOut.shape[1] != n:
    raise ValueError("cond: invOut shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("cond: work shape mismatch")
  fa: float64 = fnorm(a)
  inv(a, invOut, work)
  fi: float64 = fnorm(invOut)
  return fa * fi


def multiDot(
  a: span2d[float64],
  b: span2d[float64],
  c: span2d[float64],
  out: span2d[float64],
  work: span2d[float64],
) -> None:
  """``out = a @ b @ c``；``work`` 为 ``a.shape[0] × b.shape[1]``。"""
  m: int = a.shape[0]
  p: int = a.shape[1]
  kb: int = b.shape[0]
  k: int = b.shape[1]
  kc: int = c.shape[0]
  n: int = c.shape[1]
  if p != kb or k != kc:
    raise ValueError("multiDot: inner dimension mismatch")
  if work.shape[0] != m or work.shape[1] != k:
    raise ValueError("multiDot: work shape mismatch")
  if out.shape[0] != m or out.shape[1] != n:
    raise ValueError("multiDot: out shape mismatch")
  matmul(a, b, work)
  matmul(work, c, out)


def outer(a: span[float64], b: span[float64], out: span2d[float64]) -> None:
  """``out = a[:, None] * b[None, :]``（外积，``out`` 为 ``len(a) × len(b)``）。"""
  na: int = _requireVec(a)
  nb: int = _requireVec(b)
  if out.shape[0] != na or out.shape[1] != nb:
    raise ValueError("outer: out shape mismatch")
  for i in range(na):
    ai: float64 = a[i]
    for j in range(nb):
      out[i, j] = ai * b[j]


def cross(a: span[float64], b: span[float64], out: span[float64]) -> None:
  """三维向量叉积 ``out = a × b``。"""
  if _requireVec(a) != 3 or _requireVec(b) != 3 or _requireVec(out) != 3:
    raise ValueError("cross: vectors must have length 3")
  out[0] = a[1] * b[2] - a[2] * b[1]
  out[1] = a[2] * b[0] - a[0] * b[2]
  out[2] = a[0] * b[1] - a[1] * b[0]


def cholesky(a: span2d[float64], out: span2d[float64]) -> None:
  """对称正定方阵的 Cholesky 分解 ``a ≈ out @ out.T``（``out`` 下三角）。"""
  n: int = _requireSquare(a)
  if out.shape[0] != n or out.shape[1] != n:
    raise ValueError("cholesky: out shape mismatch")
  for i in range(n):
    for j in range(n):
      out[i, j] = 0.0
  for i in range(n):
    for j in range(i + 1):
      s: float64 = a[i, j]
      for k in range(j):
        s -= out[i, k] * out[j, k]
      if i == j:
        if s <= _Eps:
          raise LinAlgError("matrix not positive definite")
        out[i, j] = sqrt(s)
      else:
        out[i, j] = s / out[j, j]


def qr(
  a: span2d[float64],
  qOut: span2d[float64],
  rOut: span2d[float64],
  work: span[float64],
) -> None:
  """经济型 QR：``a ≈ qOut @ rOut``（``m >= n``；修正 Gram-Schmidt）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    raise ValueError("qr: empty matrix")
  if m < n:
    raise ValueError("qr requires m >= n")
  nw: int = _requireVec(work)
  if m != nw:
    raise ValueError("qr: work length mismatch")
  if qOut.shape[0] != m or qOut.shape[1] != n:
    raise ValueError("qr: qOut shape mismatch")
  if rOut.shape[0] != n or rOut.shape[1] != n:
    raise ValueError("qr: rOut shape mismatch")
  for i in range(n):
    for j in range(n):
      rOut[i, j] = 0.0
  for j in range(n):
    for i in range(m):
      work[i] = a[i, j]
    for k in range(j):
      s: float64 = 0.0
      for i in range(m):
        s += qOut[i, k] * work[i]
      rOut[k, j] = s
      for i in range(m):
        work[i] -= s * qOut[i, k]
    rn: float64 = norm(work)
    if rn < _Eps:
      raise LinAlgError("rank deficient matrix in QR")
    rOut[j, j] = rn
    invRn: float64 = 1.0 / rn
    for i in range(m):
      qOut[i, j] = work[i] * invRn


def pinv(
  a: span2d[float64],
  out: span2d[float64],
  gram: span2d[float64],
  invGram: span2d[float64],
  work: span2d[float64],
) -> None:
  """Moore-Penrose 伪逆（满秩：``m>=n`` 用 ``A.T@A``，``m<n`` 用 ``A@A.T``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    raise ValueError("pinv: empty matrix")
  if out.shape[0] != n or out.shape[1] != m:
    raise ValueError("pinv: out shape mismatch")
  if m >= n:
    if gram.shape[0] != n or gram.shape[1] != n:
      raise ValueError("pinv: gram shape mismatch")
    if invGram.shape[0] != n or invGram.shape[1] != n:
      raise ValueError("pinv: invGram shape mismatch")
    if work.shape[0] != n or work.shape[1] != n:
      raise ValueError("pinv: work shape mismatch")
    _gramA(a, gram)
    inv(gram, invGram, work)
    for i in range(n):
      for j in range(m):
        s: float64 = 0.0
        for k in range(n):
          s += invGram[i, k] * a[j, k]
        out[i, j] = s
    return
  if gram.shape[0] != m or gram.shape[1] != m:
    raise ValueError("pinv: gram shape mismatch")
  if invGram.shape[0] != m or invGram.shape[1] != m:
    raise ValueError("pinv: invGram shape mismatch")
  if work.shape[0] != m or work.shape[1] != m:
    raise ValueError("pinv: work shape mismatch")
  _gramAt(a, gram)
  inv(gram, invGram, work)
  for i in range(n):
    for j in range(m):
      s: float64 = 0.0
      for k in range(m):
        s += a[k, i] * invGram[k, j]
      out[i, j] = s


def matrixPower(
  a: span2d[float64],
  exp: int,
  out: span2d[float64],
  work: span2d[float64],
) -> None:
  """方阵整数幂 ``out = a ** exp``（``exp >= 0``）。"""
  n: int = _requireSquare(a)
  if out.shape[0] != n or out.shape[1] != n:
    raise ValueError("matrixPower: out shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("matrixPower: work shape mismatch")
  if exp < 0:
    raise ValueError("matrixPower: exp must be non-negative")
  for i in range(n):
    for j in range(n):
      if i == j:
        out[i, j] = 1.0
      else:
        out[i, j] = 0.0
  if exp == 0:
    return
  _copyMat(a, out)
  if exp == 1:
    return
  for _ in range(exp - 1):
    matmul(out, a, work)
    _copyMat(work, out)


def eigh(
  a: span2d[float64],
  w: span[float64],
  vOut: span2d[float64],
  work: span2d[float64],
) -> None:
  """实对称阵特征分解 ``a ≈ vOut @ diag(w) @ vOut.T``（Jacobi）。"""
  n: int = _requireSquare(a)
  nw: int = _requireVec(w)
  if n != nw:
    raise ValueError("eigh: w length mismatch")
  if vOut.shape[0] != n or vOut.shape[1] != n:
    raise ValueError("eigh: vOut shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("eigh: work shape mismatch")
  _symmetrize(a, work, n)
  _jacobiEighInplace(work, vOut, w, n)


def svd(
  a: span2d[float64],
  s: span[float64],
  uOut: span2d[float64],
  vtOut: span2d[float64],
  gram: span2d[float64],
  vMat: span2d[float64],
  work: span2d[float64],
) -> None:
  """经济型 SVD：``m >= n`` 时 ``u`` 为 ``m×n``、``vt`` 为 ``n×n``；``m < n`` 时 ``u`` 为 ``m×m``、``vt`` 为 ``m×n``。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    raise ValueError("svd: empty matrix")
  k: int = m
  if n < k:
    k = n
  ns: int = _requireVec(s)
  if k != ns:
    raise ValueError("svd: s length mismatch")
  if m >= n:
    if uOut.shape[0] != m or uOut.shape[1] != n:
      raise ValueError("svd: uOut shape mismatch")
    if vtOut.shape[0] != n or vtOut.shape[1] != n:
      raise ValueError("svd: vtOut shape mismatch")
    if gram.shape[0] != n or gram.shape[1] != n:
      raise ValueError("svd: gram shape mismatch")
    if vMat.shape[0] != n or vMat.shape[1] != n:
      raise ValueError("svd: vMat shape mismatch")
    if work.shape[0] != n or work.shape[1] != n:
      raise ValueError("svd: work shape mismatch")
    evals: float64[:] = new(n)
    _gramA(a, gram)
    eigh(gram, evals.view, vMat, work)
    for j in range(n):
      ev: float64 = evals[j]
      if ev < 0.0:
        ev = 0.0
      s[j] = sqrt(ev)
    transpose(vMat, vtOut)
    for j in range(n):
      sj: float64 = s[j]
      for i in range(m):
        uOut[i, j] = 0.0
      if sj <= _Eps:
        continue
      invSj: float64 = 1.0 / sj
      for i in range(m):
        t: float64 = 0.0
        for tcol in range(n):
          t += a[i, tcol] * vMat[tcol, j]
        uOut[i, j] = t * invSj
    return
  if uOut.shape[0] != m or uOut.shape[1] != m:
    raise ValueError("svd: uOut shape mismatch")
  if vtOut.shape[0] != m or vtOut.shape[1] != n:
    raise ValueError("svd: vtOut shape mismatch")
  if gram.shape[0] != m or gram.shape[1] != m:
    raise ValueError("svd: gram shape mismatch")
  if vMat.shape[0] != m or vMat.shape[1] != m:
    raise ValueError("svd: vMat shape mismatch")
  if work.shape[0] != m or work.shape[1] != m:
    raise ValueError("svd: work shape mismatch")
  at: float64[:, :] = new(n, m)
  atView: span2d[float64] = at.view
  transpose(a, atView)
  uT: float64[:, :] = new(n, m)
  vtT: float64[:, :] = new(m, m)
  uTView: span2d[float64] = uT.view
  vtTView: span2d[float64] = vtT.view
  svd(atView, s, uTView, vtTView, gram, vMat, work)
  transpose(vtTView, uOut)
  transpose(uTView, vtOut)


def eig(
  a: span2d[float64],
  wr: span[float64],
  wi: span[float64],
  work: span2d[float64],
  q: span2d[float64],
  r: span2d[float64],
  col: span[float64],
) -> None:
  """实方阵特征值（``wr``/``wi`` 为实/虚部；``n>=3`` 用 QR Schur 迭代）。"""
  n: int = _requireSquare(a)
  nr: int = _requireVec(wr)
  ni: int = _requireVec(wi)
  if n != nr or n != ni:
    raise ValueError("eig: eigenvalue buffer length mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("eig: work shape mismatch")
  if q.shape[0] != n or q.shape[1] != n:
    raise ValueError("eig: q shape mismatch")
  if r.shape[0] != n or r.shape[1] != n:
    raise ValueError("eig: r shape mismatch")
  nc: int = _requireVec(col)
  if n != nc:
    raise ValueError("eig: col length mismatch")
  if n == 1:
    wr[0] = a[0, 0]
    wi[0] = 0.0
    return
  if n == 2:
    _fillEig2(a[0, 0], a[0, 1], a[1, 0], a[1, 1], wr, wi, 0)
    return
  if _isSymmetric(a, n):
    eigh(a, wr, q, work)
    for i in range(n):
      wi[i] = 0.0
    return
  _schurEigvals(a, wr, wi, work, q, r, col)
