"""``py2cpp.math.linalg``：``span`` / ``span2d`` 线性代数回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import fabs, isClose
from py2cpp.math.linalg import (
  cholesky,
  cond,
  cross,
  det,
  dot,
  eig,
  eigh,
  fnorm,
  inv,
  lstsq,
  matmul,
  matvec,
  matrixPower,
  matrixRank,
  multiDot,
  norm,
  outer,
  pinv,
  qr,
  solve,
  solveMulti,
  svd,
  trace,
  transpose,
  vdot,
)
from py2cpp.util.span import span, span2d

_Rel: float64 = 1e-9
_Abs: float64 = 1e-6


class LinalgDotTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    u: float64[:3] = [1.0, 2.0, 3.0]
    v: float64[:3] = [4.0, 5.0, 6.0]
    self.assertTrue(isClose(dot(u.view, v.view), 32.0, _Rel, _Abs))
    self.assertTrue(isClose(vdot(u.view, v.view), 32.0, _Rel, _Abs))
    self.assertTrue(isClose(norm(u.view), 3.741657387, _Rel, _Abs))


class LinalgMatmulTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    a: float64[:2, :2] = [[1.0, 2.0], [3.0, 4.0]]
    b: float64[:2, :2] = [[5.0, 6.0], [7.0, 8.0]]
    out: float64[:2, :2] = new()
    matmul(a.view, b.view, out.view)
    self.assertTrue(isClose(out[0, 0], 19.0, _Rel, _Abs))
    self.assertTrue(isClose(out[0, 1], 22.0, _Rel, _Abs))
    self.assertTrue(isClose(out[1, 0], 43.0, _Rel, _Abs))
    self.assertTrue(isClose(out[1, 1], 50.0, _Rel, _Abs))
    y: float64[:2] = new()
    x: float64[:2] = [1.0, 2.0]
    matvec(a.view, x.view, y.view)
    self.assertTrue(isClose(y[0], 5.0, _Rel, _Abs))
    self.assertTrue(isClose(y[1], 11.0, _Rel, _Abs))
    self.assertTrue(isClose(trace(a.view), 5.0, _Rel, _Abs))
    self.assertTrue(isClose(fnorm(a.view), 5.477225575, _Rel, _Abs))


class LinalgTransposeTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    m: float64[:2, :3] = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    t: float64[:3, :2] = new()
    transpose(m.view, t.view)
    self.assertTrue(isClose(t[0, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(t[2, 1], 6.0, _Rel, _Abs))


class LinalgDetSolveInvTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    a: float64[:2, :2] = [[4.0, 7.0], [2.0, 6.0]]
    self.assertTrue(isClose(det(a.view), 10.0, _Rel, _Abs))
    b: float64[:2] = [11.0, 8.0]
    out: float64[:2] = new()
    work: float64[:2, :2] = new()
    solve(a.view, b.view, out.view, work.view)
    self.assertTrue(isClose(out[0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(out[1], 1.0, _Rel, _Abs))
    invOut: float64[:2, :2] = new()
    inv(a.view, invOut.view, work.view)
    self.assertTrue(isClose(invOut[0, 0], 0.6, _Rel, _Abs))
    self.assertTrue(isClose(invOut[0, 1], -0.7, _Rel, _Abs))
    self.assertTrue(isClose(invOut[1, 0], -0.2, _Rel, _Abs))
    self.assertTrue(isClose(invOut[1, 1], 0.4, _Rel, _Abs))


class LinalgHeapViewTests(TestCaseMixin):
  _testTag = 40

  @override
  def test(self):
    heap: float64[:, :] = new(2, 2)
    heap[0, 0] = 2.0
    heap[0, 1] = 1.0
    heap[1, 0] = 1.0
    heap[1, 1] = 2.0
    vw: span2d[float64] = heap.view
    rhs: float64[:2] = [3.0, 3.0]
    sol: float64[:2] = new()
    wrk: float64[:2, :2] = new()
    solve(vw, rhs.view, sol.view, wrk.view)
    self.assertTrue(isClose(sol[0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(sol[1], 1.0, _Rel, _Abs))


class LinalgLstsqTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    a: float64[:3, :2] = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    b: float64[:3] = [1.0, 2.0, 3.0]
    x: float64[:2] = new()
    work: float64[:2, :2] = new()
    lstsq(a.view, b.view, x.view, work.view)
    self.assertTrue(isClose(x[0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(x[1], 2.0, _Rel, _Abs))


class LinalgRankCondTests(TestCaseMixin):
  _testTag = 60

  @override
  def test(self):
    eye: float64[:3, :3] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    wrk: float64[:3, :3] = new()
    self.assertEqual(matrixRank(eye.view, wrk.view), 3)
    dep: float64[:2, :2] = [[1.0, 2.0], [2.0, 4.0]]
    wrk2: float64[:2, :2] = new()
    self.assertEqual(matrixRank(dep.view, wrk2.view), 1)
    invOut: float64[:3, :3] = new()
    c: float64 = cond(eye.view, invOut.view, wrk.view)
    self.assertTrue(isClose(c, 3.0, _Rel, _Abs))


class LinalgMultiDotTests(TestCaseMixin):
  _testTag = 70

  @override
  def test(self):
    a: float64[:2, :2] = [[1.0, 0.0], [0.0, 1.0]]
    b: float64[:2, :2] = [[2.0, 0.0], [0.0, 2.0]]
    c: float64[:2, :2] = [[3.0, 0.0], [0.0, 3.0]]
    out: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    multiDot(a.view, b.view, c.view, out.view, work.view)
    self.assertTrue(isClose(out[0, 0], 6.0, _Rel, _Abs))
    self.assertTrue(isClose(out[1, 1], 6.0, _Rel, _Abs))
    self.assertTrue(isClose(out[0, 1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(out[1, 0], 0.0, _Rel, _Abs))


class LinalgOuterCrossTests(TestCaseMixin):
  _testTag = 80

  @override
  def test(self):
    u: float64[:2] = [1.0, 2.0]
    v: float64[:2] = [3.0, 4.0]
    o: float64[:2, :2] = new()
    outer(u.view, v.view, o.view)
    self.assertTrue(isClose(o[0, 0], 3.0, _Rel, _Abs))
    self.assertTrue(isClose(o[0, 1], 4.0, _Rel, _Abs))
    self.assertTrue(isClose(o[1, 0], 6.0, _Rel, _Abs))
    self.assertTrue(isClose(o[1, 1], 8.0, _Rel, _Abs))
    a: float64[:3] = [1.0, 0.0, 0.0]
    b: float64[:3] = [0.0, 1.0, 0.0]
    c: float64[:3] = new()
    cross(a.view, b.view, c.view)
    self.assertTrue(isClose(c[0], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(c[1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(c[2], 1.0, _Rel, _Abs))


class LinalgCholeskyQrTests(TestCaseMixin):
  _testTag = 90

  @override
  def test(self):
    spd: float64[:2, :2] = [[4.0, 2.0], [2.0, 2.0]]
    l: float64[:2, :2] = new()
    cholesky(spd.view, l.view)
    self.assertTrue(isClose(l[0, 0], 2.0, _Rel, _Abs))
    self.assertTrue(isClose(l[1, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(l[1, 1], 1.0, _Rel, _Abs))
    a: float64[:2, :2] = [[1.0, 2.0], [3.0, 4.0]]
    q: float64[:2, :2] = new()
    r: float64[:2, :2] = new()
    col: float64[:2] = new()
    qr(a.view, q.view, r.view, col.view)
    recon: float64[:2, :2] = new()
    matmul(q.view, r.view, recon.view)
    self.assertTrue(isClose(recon[0, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[0, 1], 2.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[1, 0], 3.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[1, 1], 4.0, _Rel, _Abs))


class LinalgPinvPowerTests(TestCaseMixin):
  _testTag = 100

  @override
  def test(self):
    a: float64[:3, :2] = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    p: float64[:2, :3] = new()
    gram: float64[:2, :2] = new()
    invG: float64[:2, :2] = new()
    wrk: float64[:2, :2] = new()
    pinv(a.view, p.view, gram.view, invG.view, wrk.view)
    check: float64[:2, :2] = new()
    matmul(p.view, a.view, check.view)
    self.assertTrue(isClose(check[0, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(check[1, 1], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(check[0, 1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(check[1, 0], 0.0, _Rel, _Abs))
    d: float64[:2, :2] = [[2.0, 0.0], [0.0, 3.0]]
    pwr: float64[:2, :2] = new()
    tmp: float64[:2, :2] = new()
    matrixPower(d.view, 2, pwr.view, tmp.view)
    self.assertTrue(isClose(pwr[0, 0], 4.0, _Rel, _Abs))
    self.assertTrue(isClose(pwr[1, 1], 9.0, _Rel, _Abs))
    eye: float64[:2, :2] = new()
    matrixPower(d.view, 0, eye.view, tmp.view)
    self.assertTrue(isClose(eye[0, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(eye[1, 1], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(eye[0, 1], 0.0, _Rel, _Abs))


class LinalgSolveMultiTests(TestCaseMixin):
  _testTag = 110

  @override
  def test(self):
    a: float64[:2, :2] = [[4.0, 7.0], [2.0, 6.0]]
    b: float64[:2, :2] = [[11.0, 22.0], [8.0, 16.0]]
    x: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    solveMulti(a.view, b.view, x.view, work.view)
    self.assertTrue(isClose(x[0, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(x[1, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(x[0, 1], 2.0, _Rel, _Abs))
    self.assertTrue(isClose(x[1, 1], 2.0, _Rel, _Abs))


class LinalgEighTests(TestCaseMixin):
  _testTag = 120

  @override
  def test(self):
    sym: float64[:2, :2] = [[2.0, 1.0], [1.0, 2.0]]
    w: float64[:2] = new()
    v: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    eigh(sym.view, w.view, v.view, work.view)
    self.assertTrue(isClose(w[0], 3.0, _Rel, _Abs) or isClose(w[0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(w[1], 3.0, _Rel, _Abs) or isClose(w[1], 1.0, _Rel, _Abs))
    self.assertFalse(isClose(w[0], w[1], _Rel, _Abs))
    v0: float64[:2] = [v[0, 0], v[1, 0]]
    av: float64[:2] = new()
    matvec(sym.view, v0.view, av.view)
    self.assertTrue(isClose(av[0], w[0] * v[0, 0], _Rel, _Abs))
    self.assertTrue(isClose(av[1], w[0] * v[1, 0], _Rel, _Abs))


class LinalgSvdTests(TestCaseMixin):
  _testTag = 130

  @override
  def test(self):
    a: float64[:2, :2] = [[3.0, 0.0], [0.0, 2.0]]
    s: float64[:2] = new()
    u: float64[:2, :2] = new()
    vt: float64[:2, :2] = new()
    gram: float64[:2, :2] = new()
    vmat: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    svd(a.view, s.view, u.view, vt.view, gram.view, vmat.view, work.view)
    self.assertTrue(isClose(s[0], 3.0, _Rel, _Abs) or isClose(s[0], 2.0, _Rel, _Abs))
    self.assertTrue(isClose(s[1], 3.0, _Rel, _Abs) or isClose(s[1], 2.0, _Rel, _Abs))
    sigma: float64[:2, :2] = new()
    for i in range(2):
      for j in range(2):
        sigma[i, j] = 0.0
    sigma[0, 0] = s[0]
    sigma[1, 1] = s[1]
    tmp: float64[:2, :2] = new()
    recon: float64[:2, :2] = new()
    matmul(u.view, sigma.view, tmp.view)
    matmul(tmp.view, vt.view, recon.view)
    self.assertTrue(isClose(recon[0, 0], 3.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[1, 1], 2.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[0, 1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[1, 0], 0.0, _Rel, _Abs))


class LinalgEigTests(TestCaseMixin):
  _testTag = 140

  @override
  def test(self):
    rot: float64[:2, :2] = [[0.0, -1.0], [1.0, 0.0]]
    wr: float64[:2] = new()
    wi: float64[:2] = new()
    work: float64[:2, :2] = new()
    q: float64[:2, :2] = new()
    r: float64[:2, :2] = new()
    col: float64[:2] = new()
    eig(rot.view, wr.view, wi.view, work.view, q.view, r.view, col.view)
    self.assertTrue(isClose(wr[0], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(wr[1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(fabs(wi[0]), 1.0, _Rel, _Abs))
    self.assertTrue(isClose(fabs(wi[1]), 1.0, _Rel, _Abs))
    sym: float64[:3, :3] = [[2.0, 1.0, 0.0], [1.0, 2.0, 0.0], [0.0, 0.0, 3.0]]
    wr3: float64[:3] = new()
    wi3: float64[:3] = new()
    work3: float64[:3, :3] = new()
    q3: float64[:3, :3] = new()
    r3: float64[:3, :3] = new()
    col3: float64[:3] = new()
    eig(sym.view, wr3.view, wi3.view, work3.view, q3.view, r3.view, col3.view)
    self.assertTrue(isClose(wi3[0], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(wi3[1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(wi3[2], 0.0, _Rel, _Abs))
    tri: float64[:3, :3] = [[1.0, 2.0, 3.0], [0.0, 4.0, 5.0], [0.0, 0.0, 6.0]]
    wrT: float64[:3] = new()
    wiT: float64[:3] = new()
    eig(tri.view, wrT.view, wiT.view, work3.view, q3.view, r3.view, col3.view)
    self.assertTrue(isClose(wrT[0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(wrT[1], 4.0, _Rel, _Abs))
    self.assertTrue(isClose(wrT[2], 6.0, _Rel, _Abs))


class LinalgPinvWideTests(TestCaseMixin):
  _testTag = 150

  @override
  def test(self):
    a: float64[:2, :3] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    p: float64[:3, :2] = new()
    gram: float64[:2, :2] = new()
    invG: float64[:2, :2] = new()
    wrk: float64[:2, :2] = new()
    pinv(a.view, p.view, gram.view, invG.view, wrk.view)
    prod: float64[:2, :2] = new()
    matmul(a.view, p.view, prod.view)
    self.assertTrue(isClose(prod[0, 0], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(prod[1, 1], 1.0, _Rel, _Abs))
    self.assertTrue(isClose(prod[0, 1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(prod[1, 0], 0.0, _Rel, _Abs))


class LinalgSvdWideTests(TestCaseMixin):
  _testTag = 160

  @override
  def test(self):
    a: float64[:2, :3] = [[3.0, 0.0, 0.0], [0.0, 2.0, 0.0]]
    s: float64[:2] = new()
    u: float64[:2, :2] = new()
    vt: float64[:2, :3] = new()
    gram: float64[:2, :2] = new()
    vmat: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    svd(a.view, s.view, u.view, vt.view, gram.view, vmat.view, work.view)
    self.assertTrue(isClose(s[0], 3.0, _Rel, _Abs) or isClose(s[0], 2.0, _Rel, _Abs))
    self.assertTrue(isClose(s[1], 3.0, _Rel, _Abs) or isClose(s[1], 2.0, _Rel, _Abs))
    sigma2: float64[:2, :2] = new()
    for i in range(2):
      for j in range(2):
        sigma2[i, j] = 0.0
    sigma2[0, 0] = s[0]
    sigma2[1, 1] = s[1]
    tmp: float64[:2, :2] = new()
    recon: float64[:2, :3] = new()
    matmul(u.view, sigma2.view, tmp.view)
    matmul(tmp.view, vt.view, recon.view)
    self.assertTrue(isClose(recon[0, 0], 3.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[1, 1], 2.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[0, 1], 0.0, _Rel, _Abs))
    self.assertTrue(isClose(recon[1, 0], 0.0, _Rel, _Abs))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
