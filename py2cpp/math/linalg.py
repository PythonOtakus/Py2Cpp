"""线性代数（``Scalar`` 向量 ``span`` / 矩阵 ``span2d``，参考 ``numpy.linalg`` 子集）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import LinAlgError, ValueError
from ..util.span import span, span2d
from . import atan2, cos, fabs, sin, sqrt

_Eps: float64 = 1e-12


def _requireVec[Scalar: oneof[float, float64] = float](v: span[Scalar]) -> int:
  n: int = len(v)
  if n <= 0:
    raise ValueError("vector must be non-empty")
  return n


def _requireSquare[Scalar: oneof[float, float64] = float](a: span2d[Scalar]) -> int:
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if rows <= 0 or cols <= 0:
    raise ValueError("matrix must be non-empty")
  if rows != cols:
    raise ValueError("matrix must be square")
  return rows


def _copyMat[Scalar: oneof[float, float64] = float](src: span2d[Scalar], out: span2d[Scalar]) -> None:
  rows: int = src.shape[0]
  cols: int = src.shape[1]
  if out.shape[0] != rows or out.shape[1] != cols:
    raise ValueError("matrix copy shape mismatch")
  for r in range(rows):
    for c in range(cols):
      out[r, c] = src[r, c]


def _swapRows[Scalar: oneof[float, float64] = float](out: span2d[Scalar], r0: int, r1: int) -> None:
  cols: int = out.shape[1]
  for c in range(cols):
    t: Scalar = out[r0, c]
    out[r0, c] = out[r1, c]
    out[r1, c] = t


def _swapVec[Scalar: oneof[float, float64] = float](out: span[Scalar], i0: int, i1: int) -> None:
  t: Scalar = out[i0]
  out[i0] = out[i1]
  out[i1] = t


def _luFactorInplace[Scalar: oneof[float, float64] = float](work: span2d[Scalar], piv: span[int], n: int) -> None:
  for k in range(n):
    pivRow: int = k
    pivVal: Scalar = fabs[Scalar](work[k, k])
    for r in range(k + 1, n):
      v: Scalar = fabs[Scalar](work[r, k])
      if v > pivVal:
        pivVal = v
        pivRow = r
    if pivVal < _Eps:
      raise LinAlgError("singular matrix")
    piv[k] = pivRow
    if pivRow != k:
      _swapRows[Scalar](work, k, pivRow)
    pivot: Scalar = work[k, k]
    for r in range(k + 1, n):
      factor: Scalar = work[r, k] / pivot
      work[r, k] = factor
      for c in range(k + 1, n):
        work[r, c] -= factor * work[k, c]


def _luSolveVecInplace[Scalar: oneof[float, float64] = float](
  work: span2d[Scalar],
  x: span[Scalar],
  piv: span[int],
  n: int,
) -> None:
  for k in range(n):
    if piv[k] != k:
      _swapVec[Scalar](x, k, piv[k])
  for k in range(n):
    for r in range(k + 1, n):
      x[r] -= work[r, k] * x[k]
  for r in range(n - 1, -1, -1):
    s: Scalar = x[r]
    for c in range(r + 1, n):
      s -= work[r, c] * x[c]
    x[r] = s / work[r, r]


def _luSolveInplace[Scalar: oneof[float, float64] = float](work: span2d[Scalar], x: span[Scalar]) -> None:
  n: int = work.shape[0]
  piv: int[:] = new(n)
  _luFactorInplace[Scalar](work, piv.view, n)
  _luSolveVecInplace[Scalar](work, x, piv.view, n)


def _symmetrize[Scalar: oneof[float, float64] = float](a: span2d[Scalar], out: span2d[Scalar], n: int) -> None:
  for i in range(n):
    for j in range(i, n):
      if i == j:
        out[i, j] = a[i, j]
      else:
        v: Scalar = 0.5 * (a[i, j] + a[j, i])
        out[i, j] = v
        out[j, i] = v


def _jacobiEighInplace[Scalar: oneof[float, float64] = float](
  work: span2d[Scalar],
  vOut: span2d[Scalar],
  w: span[Scalar],
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
    maxOff: Scalar = 0.0
    for i in range(n):
      for j in range(i + 1, n):
        v: Scalar = fabs[Scalar](work[i, j])
        if v > maxOff:
          maxOff = v
          p = i
          q = j
    if maxOff <= _Eps:
      break
    apq: Scalar = work[p, q]
    if fabs[Scalar](apq) <= _Eps:
      continue
    app: Scalar = work[p, p]
    aqq: Scalar = work[q, q]
    theta: Scalar = 0.5 * atan2[Scalar](2.0 * apq, aqq - app)
    c: Scalar = cos[Scalar](theta)
    s: Scalar = sin[Scalar](theta)
    for k in range(n):
      if k in {p, q}:
        continue
      wkp: Scalar = work[k, p]
      wkq: Scalar = work[k, q]
      work[k, p] = c * wkp - s * wkq
      work[p, k] = work[k, p]
      work[k, q] = s * wkp + c * wkq
      work[q, k] = work[k, q]
    work[p, p] = c * c * app - 2.0 * s * c * apq + s * s * aqq
    work[q, q] = s * s * app + 2.0 * s * c * apq + c * c * aqq
    work[p, q] = 0.0
    work[q, p] = 0.0
    for k in range(n):
      vkp: Scalar = vOut[k, p]
      vkq: Scalar = vOut[k, q]
      vOut[k, p] = c * vkp - s * vkq
      vOut[k, q] = s * vkp + c * vkq
  for i in range(n):
    w[i] = work[i, i]


def _gramAt[Scalar: oneof[float, float64] = float](a: span2d[Scalar], out: span2d[Scalar]) -> None:
  """``out = a @ a.T``（``a`` 为 ``m×n``，``out`` 为 ``m×m``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if out.shape[0] != m or out.shape[1] != m:
    raise ValueError("gram_at: out shape mismatch")
  for i in range(m):
    for j in range(m):
      s: Scalar = 0.0
      for k in range(n):
        s += a[i, k] * a[j, k]
      out[i, j] = s


def _fillEig2[Scalar: oneof[float, float64] = float](
  a: Scalar,
  b: Scalar,
  c: Scalar,
  d: Scalar,
  wr: span[Scalar],
  wi: span[Scalar],
  i0: int,
) -> None:
  tr: Scalar = a + d
  det: Scalar = a * d - b * c
  disc: Scalar = tr * tr - 4.0 * det
  if disc >= 0.0:
    s: Scalar = sqrt[Scalar](disc)
    wr[i0] = (tr + s) * 0.5
    wi[i0] = 0.0
    wr[i0 + 1] = (tr - s) * 0.5
    wi[i0 + 1] = 0.0
  else:
    half: Scalar = tr * 0.5
    root: Scalar = sqrt[Scalar](-disc)
    im: Scalar = root * 0.5
    wr[i0] = half
    wi[i0] = im
    wr[i0 + 1] = half
    wi[i0 + 1] = -im


def _wilkinsonShift[Scalar: oneof[float, float64] = float](h: span2d[Scalar], active: int) -> Scalar:
  if active == 1:
    return h[0, 0]
  a: Scalar = h[active - 2, active - 2]
  b: Scalar = h[active - 2, active - 1]
  d: Scalar = h[active - 1, active - 1]
  tr: Scalar = a + d
  det: Scalar = a * d - b * h[active - 1, active - 2]
  disc: Scalar = tr * tr - 4.0 * det
  if disc >= 0.0:
    s: Scalar = sqrt[Scalar](disc)
    e0: Scalar = (tr + s) * 0.5
    e1: Scalar = (tr - s) * 0.5
    if fabs[Scalar](d - e0) <= fabs[Scalar](d - e1):
      return e0
    return e1
  return d


def _schurConverged[Scalar: oneof[float, float64] = float](h: span2d[Scalar], n: int) -> bool:
  for i in range(1, n):
    scale: Scalar = fabs[Scalar](h[i - 1, i - 1]) + fabs[Scalar](h[i, i])
    if fabs[Scalar](h[i, i - 1]) > _Eps * scale:
      return False
  return True


def _extractEigvalsSchur[Scalar: oneof[float, float64] = float](
  h: span2d[Scalar],
  wr: span[Scalar],
  wi: span[Scalar],
  n: int,
) -> None:
  i: int = 0
  while i < n:
    if i + 1 < n:
      scale: Scalar = fabs[Scalar](h[i, i]) + fabs[Scalar](h[i + 1, i + 1])
      if fabs[Scalar](h[i + 1, i]) > _Eps * scale:
        _fillEig2[Scalar](h[i, i], h[i, i + 1], h[i + 1, i], h[i + 1, i + 1], wr, wi, i)
        i += 2
        continue
    wr[i] = h[i, i]
    wi[i] = 0.0
    i += 1


def _isSymmetric[Scalar: oneof[float, float64] = float](a: span2d[Scalar], n: int) -> bool:
  for i in range(n):
    for j in range(i + 1, n):
      if fabs[Scalar](a[i, j] - a[j, i]) > _Eps:
        return False
  return True


def _schurEigvals[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  wr: span[Scalar],
  wi: span[Scalar],
  work: span2d[Scalar],
  q: span2d[Scalar],
  r: span2d[Scalar],
  col: span[Scalar],
) -> None:
  n: int = _requireSquare[Scalar](a)
  _copyMat[Scalar](a, work)
  maxIter: int = 50 * n + 200
  for _ in range(maxIter):
    if _schurConverged[Scalar](work, n):
      break
    mu: Scalar = _wilkinsonShift[Scalar](work, n)
    for i in range(n):
      work[i, i] -= mu
    qr(work, q, r, col)
    matmul[Scalar](r, q, work)
    for i in range(n):
      work[i, i] += mu
  _extractEigvalsSchur[Scalar](work, wr, wi, n)


def dot[Scalar: oneof[float, float64] = float](a: span[Scalar], b: span[Scalar]) -> Scalar:
  """一维向量内积。"""
  na: int = _requireVec[Scalar](a)
  nb: int = _requireVec[Scalar](b)
  if na != nb:
    raise ValueError("dot: size mismatch")
  s: Scalar = 0.0
  for i in range(na):
    s += a[i] * b[i]
  return s


def vdot[Scalar: oneof[float, float64] = float](a: span[Scalar], b: span[Scalar]) -> Scalar:
  """实向量内积（与 ``dot`` 相同）。"""
  return dot[Scalar](a, b)


def matvec[Scalar: oneof[float, float64] = float](a: span2d[Scalar], x: span[Scalar], out: span[Scalar]) -> None:
  """``out = a @ x``。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  nx: int = _requireVec[Scalar](x)
  ny: int = _requireVec[Scalar](out)
  if n != nx or m != ny:
    raise ValueError("matvec: shape mismatch")
  for r in range(m):
    s: Scalar = 0.0
    for c in range(n):
      s += a[r, c] * x[c]
    out[r] = s


def matmul[Scalar: oneof[float, float64] = float](a: span2d[Scalar], b: span2d[Scalar], out: span2d[Scalar]) -> None:
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
      s: Scalar = 0.0
      for t in range(k):
        s += a[r, t] * b[t, c]
      out[r, c] = s


def transpose[Scalar: oneof[float, float64] = float](a: span2d[Scalar], out: span2d[Scalar]) -> None:
  """``out = a.T``。"""
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if out.shape[0] != cols or out.shape[1] != rows:
    raise ValueError("transpose: out shape mismatch")
  for r in range(rows):
    for c in range(cols):
      out[c, r] = a[r, c]


def trace[Scalar: oneof[float, float64] = float](a: span2d[Scalar]) -> Scalar:
  """主对角线之和。"""
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if rows <= 0 or cols <= 0:
    raise ValueError("trace: empty matrix")
  n: int = rows
  if cols < n:
    n = cols
  s: Scalar = 0.0
  for i in range(n):
    s += a[i, i]
  return s


def norm[Scalar: oneof[float, float64] = float](x: span[Scalar]) -> Scalar:
  """向量欧几里得范数。"""
  n: int = _requireVec[Scalar](x)
  s: Scalar = 0.0
  for i in range(n):
    v: Scalar = x[i]
    s += v * v
  return sqrt[Scalar](s)


def fnorm[Scalar: oneof[float, float64] = float](a: span2d[Scalar]) -> Scalar:
  """矩阵 Frobenius 范数。"""
  rows: int = a.shape[0]
  cols: int = a.shape[1]
  if rows <= 0 or cols <= 0:
    raise ValueError("fnorm: empty matrix")
  s: Scalar = 0.0
  for r in range(rows):
    for c in range(cols):
      v: Scalar = a[r, c]
      s += v * v
  return sqrt[Scalar](s)


def det[Scalar: oneof[float, float64] = float](a: span2d[Scalar]) -> Scalar:
  """方阵行列式（内部拷贝，不修改 ``a``）。"""
  n: int = _requireSquare[Scalar](a)
  tmp: Scalar[:, :] = new(n, n)
  work: span2d[Scalar] = tmp.view
  _copyMat[Scalar](a, work)
  sign: Scalar = 1.0
  prod: Scalar = 1.0
  for k in range(n):
    pivRow: int = k
    pivVal: Scalar = fabs[Scalar](work[k, k])
    for r in range(k + 1, n):
      v: Scalar = fabs[Scalar](work[r, k])
      if v > pivVal:
        pivVal = v
        pivRow = r
    if pivVal < _Eps:
      raise LinAlgError("singular matrix")
    if pivRow != k:
      sign = -sign
      _swapRows[Scalar](work, k, pivRow)
    pivot: Scalar = work[k, k]
    prod *= pivot
    for r in range(k + 1, n):
      factor: Scalar = work[r, k] / pivot
      work[r, k] = 0.0
      for c in range(k + 1, n):
        work[r, c] -= factor * work[k, c]
  return sign * prod


def solve[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  b: span[Scalar],
  out: span[Scalar],
  work: span2d[Scalar],
) -> None:
  """解 ``a @ out = b``；``work`` 为 ``n×n`` 工作区，``a`` 不被修改。"""
  n: int = _requireSquare[Scalar](a)
  nb: int = _requireVec[Scalar](b)
  nx: int = _requireVec[Scalar](out)
  if n != nb or n != nx:
    raise ValueError("solve: shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("solve: work shape mismatch")
  _copyMat[Scalar](a, work)
  for i in range(n):
    out[i] = b[i]
  _luSolveInplace[Scalar](work, out)


def solveMulti[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  b: span2d[Scalar],
  out: span2d[Scalar],
  work: span2d[Scalar],
) -> None:
  """解 ``a @ out = b``（``b``/``out`` 为 ``n×k`` 多列右端项）。"""
  n: int = _requireSquare[Scalar](a)
  k: int = b.shape[1]
  if b.shape[0] != n or out.shape[0] != n or out.shape[1] != k:
    raise ValueError("solveMulti: shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("solveMulti: work shape mismatch")
  piv: int[:] = new(n)
  col: Scalar[:] = new(n)
  _copyMat[Scalar](a, work)
  _luFactorInplace[Scalar](work, piv.view, n)
  for j in range(k):
    for i in range(n):
      col[i] = b[i, j]
    _luSolveVecInplace[Scalar](work, col.view, piv.view, n)
    for i in range(n):
      out[i, j] = col[i]


def inv[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  out: span2d[Scalar],
  work: span2d[Scalar],
) -> None:
  """``out = inv(a)``；``work`` 为 ``n×n`` 工作区，``a`` 不被修改。"""
  n: int = _requireSquare[Scalar](a)
  if out.shape[0] != n or out.shape[1] != n:
    raise ValueError("inv: out shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("inv: work shape mismatch")
  e: Scalar[:] = new(n)
  x: Scalar[:] = new(n)
  for j in range(n):
    for i in range(n):
      e[i] = 0.0
    e[j] = 1.0
    solve(a, e.view, x.view, work)
    for i in range(n):
      out[i, j] = x[i]


def _gramA[Scalar: oneof[float, float64] = float](a: span2d[Scalar], out: span2d[Scalar]) -> None:
  """``out = a.T @ a``（``a`` 为 ``m×n``，``out`` 为 ``n×n``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if out.shape[0] != n or out.shape[1] != n:
    raise ValueError("gram: out shape mismatch")
  for i in range(n):
    for j in range(n):
      s: Scalar = 0.0
      for r in range(m):
        s += a[r, i] * a[r, j]
      out[i, j] = s


def _mulAtVec[Scalar: oneof[float, float64] = float](a: span2d[Scalar], b: span[Scalar], out: span[Scalar]) -> None:
  """``out = a.T @ b``（``a`` 为 ``m×n``，``b`` 为 ``m``，``out`` 为 ``n``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  nb: int = _requireVec[Scalar](b)
  nx: int = _requireVec[Scalar](out)
  if m != nb or n != nx:
    raise ValueError("mul_at_vec: shape mismatch")
  for i in range(n):
    s: Scalar = 0.0
    for r in range(m):
      s += a[r, i] * b[r]
    out[i] = s


def lstsq[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  b: span[Scalar],
  out: span[Scalar],
  work: span2d[Scalar],
) -> None:
  """最小二乘 ``min ||a @ out - b||``（``m >= n`` 满秩；正规方程 + ``solve``）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    raise ValueError("lstsq: empty matrix")
  if m < n:
    raise ValueError("lstsq requires m >= n")
  nb: int = _requireVec[Scalar](b)
  nx: int = _requireVec[Scalar](out)
  if m != nb or n != nx:
    raise ValueError("lstsq: shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("lstsq: work shape mismatch")
  rhs: Scalar[:] = new(n)
  _gramA[Scalar](a, work)
  _mulAtVec[Scalar](a, b, rhs.view)
  for i in range(n):
    out[i] = rhs[i]
  _luSolveInplace[Scalar](work, out)


def matrixRank[Scalar: oneof[float, float64] = float](a: span2d[Scalar], work: span2d[Scalar], tol: Scalar = 1e-12) -> int:
  """列主元消元估计秩（``work`` 为与 ``a`` 同形工作区）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    return 0
  if work.shape[0] != m or work.shape[1] != n:
    raise ValueError("matrixRank: work shape mismatch")
  _copyMat[Scalar](a, work)
  rank: int = 0
  row: int = 0
  for col in range(n):
    if row >= m:
      break
    pivRow: int = row
    pivVal: Scalar = fabs[Scalar](work[row, col])
    for r in range(row + 1, m):
      v: Scalar = fabs[Scalar](work[r, col])
      if v > pivVal:
        pivVal = v
        pivRow = r
    if pivVal <= tol:
      continue
    if pivRow != row:
      _swapRows[Scalar](work, row, pivRow)
    pivot: Scalar = work[row, col]
    for r in range(row + 1, m):
      factor: Scalar = work[r, col] / pivot
      for c in range(col + 1, n):
        work[r, c] -= factor * work[row, c]
    row += 1
    rank += 1
  return rank


def cond[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  invOut: span2d[Scalar],
  work: span2d[Scalar],
) -> Scalar:
  """Frobenius 条件数 ``fnorm(a) * fnorm(inv(a))``（``invOut``/``work`` 同 ``inv``）。"""
  n: int = _requireSquare[Scalar](a)
  if invOut.shape[0] != n or invOut.shape[1] != n:
    raise ValueError("cond: invOut shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("cond: work shape mismatch")
  fa: Scalar = fnorm(a)
  inv(a, invOut, work)
  fi: Scalar = fnorm(invOut)
  return fa * fi


def multiDot[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  b: span2d[Scalar],
  c: span2d[Scalar],
  out: span2d[Scalar],
  work: span2d[Scalar],
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
  matmul[Scalar](a, b, work)
  matmul[Scalar](work, c, out)


def outer[Scalar: oneof[float, float64] = float](a: span[Scalar], b: span[Scalar], out: span2d[Scalar]) -> None:
  """``out = a[:, None] * b[None, :]``（外积，``out`` 为 ``len(a) × len(b)``）。"""
  na: int = _requireVec[Scalar](a)
  nb: int = _requireVec[Scalar](b)
  if out.shape[0] != na or out.shape[1] != nb:
    raise ValueError("outer: out shape mismatch")
  for i in range(na):
    ai: Scalar = a[i]
    for j in range(nb):
      out[i, j] = ai * b[j]


def cross[Scalar: oneof[float, float64] = float](a: span[Scalar], b: span[Scalar], out: span[Scalar]) -> None:
  """三维向量叉积 ``out = a × b``。"""
  if _requireVec[Scalar](a) != 3 or _requireVec[Scalar](b) != 3 or _requireVec[Scalar](out) != 3:
    raise ValueError("cross: vectors must have length 3")
  out[0] = a[1] * b[2] - a[2] * b[1]
  out[1] = a[2] * b[0] - a[0] * b[2]
  out[2] = a[0] * b[1] - a[1] * b[0]


def cholesky[Scalar: oneof[float, float64] = float](a: span2d[Scalar], out: span2d[Scalar]) -> None:
  """对称正定方阵的 Cholesky 分解 ``a ≈ out @ out.T``（``out`` 下三角）。"""
  n: int = _requireSquare[Scalar](a)
  if out.shape[0] != n or out.shape[1] != n:
    raise ValueError("cholesky: out shape mismatch")
  for i in range(n):
    for j in range(n):
      out[i, j] = 0.0
  for i in range(n):
    for j in range(i + 1):
      s: Scalar = a[i, j]
      for k in range(j):
        s -= out[i, k] * out[j, k]
      if i == j:
        if s <= _Eps:
          raise LinAlgError("matrix not positive definite")
        out[i, j] = sqrt[Scalar](s)
      else:
        out[i, j] = s / out[j, j]


def qr[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  qOut: span2d[Scalar],
  rOut: span2d[Scalar],
  work: span[Scalar],
) -> None:
  """经济型 QR：``a ≈ qOut @ rOut``（``m >= n``；修正 Gram-Schmidt）。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    raise ValueError("qr: empty matrix")
  if m < n:
    raise ValueError("qr requires m >= n")
  nw: int = _requireVec[Scalar](work)
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
      s: Scalar = 0.0
      for i in range(m):
        s += qOut[i, k] * work[i]
      rOut[k, j] = s
      for i in range(m):
        work[i] -= s * qOut[i, k]
    rn: Scalar = norm(work)
    if rn < _Eps:
      raise LinAlgError("rank deficient matrix in QR")
    rOut[j, j] = rn
    invRn: Scalar = 1.0 / rn
    for i in range(m):
      qOut[i, j] = work[i] * invRn


def pinv[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  out: span2d[Scalar],
  gram: span2d[Scalar],
  invGram: span2d[Scalar],
  work: span2d[Scalar],
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
    _gramA[Scalar](a, gram)
    inv(gram, invGram, work)
    for i in range(n):
      for j in range(m):
        s: Scalar = 0.0
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
  _gramAt[Scalar](a, gram)
  inv(gram, invGram, work)
  for i in range(n):
    for j in range(m):
      s: Scalar = 0.0
      for k in range(m):
        s += a[k, i] * invGram[k, j]
      out[i, j] = s


def matrixPower[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  exp: int,
  out: span2d[Scalar],
  work: span2d[Scalar],
) -> None:
  """方阵整数幂 ``out = a ** exp``（``exp >= 0``）。"""
  n: int = _requireSquare[Scalar](a)
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
  _copyMat[Scalar](a, out)
  if exp == 1:
    return
  for _ in range(exp - 1):
    matmul[Scalar](out, a, work)
    _copyMat[Scalar](work, out)


def eigh[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  w: span[Scalar],
  vOut: span2d[Scalar],
  work: span2d[Scalar],
) -> None:
  """实对称阵特征分解 ``a ≈ vOut @ diag(w) @ vOut.T``（Jacobi）。"""
  n: int = _requireSquare[Scalar](a)
  nw: int = _requireVec[Scalar](w)
  if n != nw:
    raise ValueError("eigh: w length mismatch")
  if vOut.shape[0] != n or vOut.shape[1] != n:
    raise ValueError("eigh: vOut shape mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("eigh: work shape mismatch")
  _symmetrize[Scalar](a, work, n)
  _jacobiEighInplace[Scalar](work, vOut, w, n)


def svd[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  s: span[Scalar],
  uOut: span2d[Scalar],
  vtOut: span2d[Scalar],
  gram: span2d[Scalar],
  vMat: span2d[Scalar],
  work: span2d[Scalar],
) -> None:
  """经济型 SVD：``m >= n`` 时 ``u`` 为 ``m×n``、``vt`` 为 ``n×n``；``m < n`` 时 ``u`` 为 ``m×m``、``vt`` 为 ``m×n``。"""
  m: int = a.shape[0]
  n: int = a.shape[1]
  if m <= 0 or n <= 0:
    raise ValueError("svd: empty matrix")
  k: int = m
  if n < k:
    k = n
  ns: int = _requireVec[Scalar](s)
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
    evals: Scalar[:] = new(n)
    _gramA[Scalar](a, gram)
    eigh[Scalar](gram, evals.view, vMat, work)
    for j in range(n):
      ev: Scalar = evals[j]
      if ev < 0.0:
        ev = 0.0
      s[j] = sqrt[Scalar](ev)
    transpose[Scalar](vMat, vtOut)
    for j in range(n):
      sj: Scalar = s[j]
      for i in range(m):
        uOut[i, j] = 0.0
      if sj <= _Eps:
        continue
      invSj: Scalar = 1.0 / sj
      for i in range(m):
        t: Scalar = 0.0
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
  at: Scalar[:, :] = new(n, m)
  atView: span2d[Scalar] = at.view
  transpose[Scalar](a, atView)
  uT: Scalar[:, :] = new(n, m)
  vtT: Scalar[:, :] = new(m, m)
  uTView: span2d[Scalar] = uT.view
  vtTView: span2d[Scalar] = vtT.view
  svd[Scalar](atView, s, uTView, vtTView, gram, vMat, work)
  transpose[Scalar](vtTView, uOut)
  transpose[Scalar](uTView, vtOut)


def eig[Scalar: oneof[float, float64] = float](
  a: span2d[Scalar],
  wr: span[Scalar],
  wi: span[Scalar],
  work: span2d[Scalar],
  q: span2d[Scalar],
  r: span2d[Scalar],
  col: span[Scalar],
) -> None:
  """实方阵特征值（``wr``/``wi`` 为实/虚部；``n>=3`` 用 QR Schur 迭代）。"""
  n: int = _requireSquare[Scalar](a)
  nr: int = _requireVec[Scalar](wr)
  ni: int = _requireVec[Scalar](wi)
  if n != nr or n != ni:
    raise ValueError("eig: eigenvalue buffer length mismatch")
  if work.shape[0] != n or work.shape[1] != n:
    raise ValueError("eig: work shape mismatch")
  if q.shape[0] != n or q.shape[1] != n:
    raise ValueError("eig: q shape mismatch")
  if r.shape[0] != n or r.shape[1] != n:
    raise ValueError("eig: r shape mismatch")
  nc: int = _requireVec[Scalar](col)
  if n != nc:
    raise ValueError("eig: col length mismatch")
  if n == 1:
    wr[0] = a[0, 0]
    wi[0] = 0.0
    return
  if n == 2:
    _fillEig2[Scalar](a[0, 0], a[0, 1], a[1, 0], a[1, 1], wr, wi, 0)
    return
  if _isSymmetric[Scalar](a, n):
    eigh[Scalar](a, wr, q, work)
    for i in range(n):
      wi[i] = 0.0
    return
  _schurEigvals[Scalar](a, wr, wi, work, q, r, col)
