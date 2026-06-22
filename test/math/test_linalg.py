"""``py2cpp.math.linalg``：``span`` / ``span2d`` 线性代数回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.math import fabs, isclose
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
  matrix_power,
  matrix_rank,
  multi_dot,
  norm,
  outer,
  pinv,
  qr,
  solve,
  solve_multi,
  svd,
  trace,
  transpose,
  vdot,
)
from py2cpp.util.span import span, span2d

_REL: float64 = 1e-9
_ABS: float64 = 1e-6


class LinalgDotTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    u: float64[:3] = [1.0, 2.0, 3.0]
    v: float64[:3] = [4.0, 5.0, 6.0]
    self.assertTrue(isclose(dot(u.view, v.view), 32.0, _REL, _ABS))
    self.assertTrue(isclose(vdot(u.view, v.view), 32.0, _REL, _ABS))
    self.assertTrue(isclose(norm(u.view), 3.741657387, _REL, _ABS))


class LinalgMatmulTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    a: float64[:2, :2] = [[1.0, 2.0], [3.0, 4.0]]
    b: float64[:2, :2] = [[5.0, 6.0], [7.0, 8.0]]
    out: float64[:2, :2] = new()
    matmul(a.view, b.view, out.view)
    self.assertTrue(isclose(out[0, 0], 19.0, _REL, _ABS))
    self.assertTrue(isclose(out[0, 1], 22.0, _REL, _ABS))
    self.assertTrue(isclose(out[1, 0], 43.0, _REL, _ABS))
    self.assertTrue(isclose(out[1, 1], 50.0, _REL, _ABS))
    y: float64[:2] = new()
    x: float64[:2] = [1.0, 2.0]
    matvec(a.view, x.view, y.view)
    self.assertTrue(isclose(y[0], 5.0, _REL, _ABS))
    self.assertTrue(isclose(y[1], 11.0, _REL, _ABS))
    self.assertTrue(isclose(trace(a.view), 5.0, _REL, _ABS))
    self.assertTrue(isclose(fnorm(a.view), 5.477225575, _REL, _ABS))


class LinalgTransposeTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    m: float64[:2, :3] = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    t: float64[:3, :2] = new()
    transpose(m.view, t.view)
    self.assertTrue(isclose(t[0, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(t[2, 1], 6.0, _REL, _ABS))


class LinalgDetSolveInvTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    a: float64[:2, :2] = [[4.0, 7.0], [2.0, 6.0]]
    self.assertTrue(isclose(det(a.view), 10.0, _REL, _ABS))
    b: float64[:2] = [11.0, 8.0]
    out: float64[:2] = new()
    work: float64[:2, :2] = new()
    solve(a.view, b.view, out.view, work.view)
    self.assertTrue(isclose(out[0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(out[1], 1.0, _REL, _ABS))
    inv_out: float64[:2, :2] = new()
    inv(a.view, inv_out.view, work.view)
    self.assertTrue(isclose(inv_out[0, 0], 0.6, _REL, _ABS))
    self.assertTrue(isclose(inv_out[0, 1], -0.7, _REL, _ABS))
    self.assertTrue(isclose(inv_out[1, 0], -0.2, _REL, _ABS))
    self.assertTrue(isclose(inv_out[1, 1], 0.4, _REL, _ABS))


class LinalgHeapViewTests(TestCaseMixin):
  _test_tag = 40

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
    self.assertTrue(isclose(sol[0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(sol[1], 1.0, _REL, _ABS))


class LinalgLstsqTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    a: float64[:3, :2] = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    b: float64[:3] = [1.0, 2.0, 3.0]
    x: float64[:2] = new()
    work: float64[:2, :2] = new()
    lstsq(a.view, b.view, x.view, work.view)
    self.assertTrue(isclose(x[0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(x[1], 2.0, _REL, _ABS))


class LinalgRankCondTests(TestCaseMixin):
  _test_tag = 60

  @override
  def test(self):
    eye: float64[:3, :3] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    wrk: float64[:3, :3] = new()
    self.assertEqual(matrix_rank(eye.view, wrk.view), 3)
    dep: float64[:2, :2] = [[1.0, 2.0], [2.0, 4.0]]
    wrk2: float64[:2, :2] = new()
    self.assertEqual(matrix_rank(dep.view, wrk2.view), 1)
    inv_out: float64[:3, :3] = new()
    c: float64 = cond(eye.view, inv_out.view, wrk.view)
    self.assertTrue(isclose(c, 3.0, _REL, _ABS))


class LinalgMultiDotTests(TestCaseMixin):
  _test_tag = 70

  @override
  def test(self):
    a: float64[:2, :2] = [[1.0, 0.0], [0.0, 1.0]]
    b: float64[:2, :2] = [[2.0, 0.0], [0.0, 2.0]]
    c: float64[:2, :2] = [[3.0, 0.0], [0.0, 3.0]]
    out: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    multi_dot(a.view, b.view, c.view, out.view, work.view)
    self.assertTrue(isclose(out[0, 0], 6.0, _REL, _ABS))
    self.assertTrue(isclose(out[1, 1], 6.0, _REL, _ABS))
    self.assertTrue(isclose(out[0, 1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(out[1, 0], 0.0, _REL, _ABS))


class LinalgOuterCrossTests(TestCaseMixin):
  _test_tag = 80

  @override
  def test(self):
    u: float64[:2] = [1.0, 2.0]
    v: float64[:2] = [3.0, 4.0]
    o: float64[:2, :2] = new()
    outer(u.view, v.view, o.view)
    self.assertTrue(isclose(o[0, 0], 3.0, _REL, _ABS))
    self.assertTrue(isclose(o[0, 1], 4.0, _REL, _ABS))
    self.assertTrue(isclose(o[1, 0], 6.0, _REL, _ABS))
    self.assertTrue(isclose(o[1, 1], 8.0, _REL, _ABS))
    a: float64[:3] = [1.0, 0.0, 0.0]
    b: float64[:3] = [0.0, 1.0, 0.0]
    c: float64[:3] = new()
    cross(a.view, b.view, c.view)
    self.assertTrue(isclose(c[0], 0.0, _REL, _ABS))
    self.assertTrue(isclose(c[1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(c[2], 1.0, _REL, _ABS))


class LinalgCholeskyQrTests(TestCaseMixin):
  _test_tag = 90

  @override
  def test(self):
    spd: float64[:2, :2] = [[4.0, 2.0], [2.0, 2.0]]
    l: float64[:2, :2] = new()
    cholesky(spd.view, l.view)
    self.assertTrue(isclose(l[0, 0], 2.0, _REL, _ABS))
    self.assertTrue(isclose(l[1, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(l[1, 1], 1.0, _REL, _ABS))
    a: float64[:2, :2] = [[1.0, 2.0], [3.0, 4.0]]
    q: float64[:2, :2] = new()
    r: float64[:2, :2] = new()
    col: float64[:2] = new()
    qr(a.view, q.view, r.view, col.view)
    recon: float64[:2, :2] = new()
    matmul(q.view, r.view, recon.view)
    self.assertTrue(isclose(recon[0, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(recon[0, 1], 2.0, _REL, _ABS))
    self.assertTrue(isclose(recon[1, 0], 3.0, _REL, _ABS))
    self.assertTrue(isclose(recon[1, 1], 4.0, _REL, _ABS))


class LinalgPinvPowerTests(TestCaseMixin):
  _test_tag = 100

  @override
  def test(self):
    a: float64[:3, :2] = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    p: float64[:2, :3] = new()
    gram: float64[:2, :2] = new()
    inv_g: float64[:2, :2] = new()
    wrk: float64[:2, :2] = new()
    pinv(a.view, p.view, gram.view, inv_g.view, wrk.view)
    check: float64[:2, :2] = new()
    matmul(p.view, a.view, check.view)
    self.assertTrue(isclose(check[0, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(check[1, 1], 1.0, _REL, _ABS))
    self.assertTrue(isclose(check[0, 1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(check[1, 0], 0.0, _REL, _ABS))
    d: float64[:2, :2] = [[2.0, 0.0], [0.0, 3.0]]
    pwr: float64[:2, :2] = new()
    tmp: float64[:2, :2] = new()
    matrix_power(d.view, 2, pwr.view, tmp.view)
    self.assertTrue(isclose(pwr[0, 0], 4.0, _REL, _ABS))
    self.assertTrue(isclose(pwr[1, 1], 9.0, _REL, _ABS))
    eye: float64[:2, :2] = new()
    matrix_power(d.view, 0, eye.view, tmp.view)
    self.assertTrue(isclose(eye[0, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(eye[1, 1], 1.0, _REL, _ABS))
    self.assertTrue(isclose(eye[0, 1], 0.0, _REL, _ABS))


class LinalgSolveMultiTests(TestCaseMixin):
  _test_tag = 110

  @override
  def test(self):
    a: float64[:2, :2] = [[4.0, 7.0], [2.0, 6.0]]
    b: float64[:2, :2] = [[11.0, 22.0], [8.0, 16.0]]
    x: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    solve_multi(a.view, b.view, x.view, work.view)
    self.assertTrue(isclose(x[0, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(x[1, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(x[0, 1], 2.0, _REL, _ABS))
    self.assertTrue(isclose(x[1, 1], 2.0, _REL, _ABS))


class LinalgEighTests(TestCaseMixin):
  _test_tag = 120

  @override
  def test(self):
    sym: float64[:2, :2] = [[2.0, 1.0], [1.0, 2.0]]
    w: float64[:2] = new()
    v: float64[:2, :2] = new()
    work: float64[:2, :2] = new()
    eigh(sym.view, w.view, v.view, work.view)
    self.assertTrue(isclose(w[0], 3.0, _REL, _ABS) or isclose(w[0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(w[1], 3.0, _REL, _ABS) or isclose(w[1], 1.0, _REL, _ABS))
    self.assertFalse(isclose(w[0], w[1], _REL, _ABS))
    v0: float64[:2] = [v[0, 0], v[1, 0]]
    av: float64[:2] = new()
    matvec(sym.view, v0.view, av.view)
    self.assertTrue(isclose(av[0], w[0] * v[0, 0], _REL, _ABS))
    self.assertTrue(isclose(av[1], w[0] * v[1, 0], _REL, _ABS))


class LinalgSvdTests(TestCaseMixin):
  _test_tag = 130

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
    self.assertTrue(isclose(s[0], 3.0, _REL, _ABS) or isclose(s[0], 2.0, _REL, _ABS))
    self.assertTrue(isclose(s[1], 3.0, _REL, _ABS) or isclose(s[1], 2.0, _REL, _ABS))
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
    self.assertTrue(isclose(recon[0, 0], 3.0, _REL, _ABS))
    self.assertTrue(isclose(recon[1, 1], 2.0, _REL, _ABS))
    self.assertTrue(isclose(recon[0, 1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(recon[1, 0], 0.0, _REL, _ABS))


class LinalgEigTests(TestCaseMixin):
  _test_tag = 140

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
    self.assertTrue(isclose(wr[0], 0.0, _REL, _ABS))
    self.assertTrue(isclose(wr[1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(fabs(wi[0]), 1.0, _REL, _ABS))
    self.assertTrue(isclose(fabs(wi[1]), 1.0, _REL, _ABS))
    sym: float64[:3, :3] = [[2.0, 1.0, 0.0], [1.0, 2.0, 0.0], [0.0, 0.0, 3.0]]
    wr3: float64[:3] = new()
    wi3: float64[:3] = new()
    work3: float64[:3, :3] = new()
    q3: float64[:3, :3] = new()
    r3: float64[:3, :3] = new()
    col3: float64[:3] = new()
    eig(sym.view, wr3.view, wi3.view, work3.view, q3.view, r3.view, col3.view)
    self.assertTrue(isclose(wi3[0], 0.0, _REL, _ABS))
    self.assertTrue(isclose(wi3[1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(wi3[2], 0.0, _REL, _ABS))
    tri: float64[:3, :3] = [[1.0, 2.0, 3.0], [0.0, 4.0, 5.0], [0.0, 0.0, 6.0]]
    wr_t: float64[:3] = new()
    wi_t: float64[:3] = new()
    eig(tri.view, wr_t.view, wi_t.view, work3.view, q3.view, r3.view, col3.view)
    self.assertTrue(isclose(wr_t[0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(wr_t[1], 4.0, _REL, _ABS))
    self.assertTrue(isclose(wr_t[2], 6.0, _REL, _ABS))


class LinalgPinvWideTests(TestCaseMixin):
  _test_tag = 150

  @override
  def test(self):
    a: float64[:2, :3] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    p: float64[:3, :2] = new()
    gram: float64[:2, :2] = new()
    inv_g: float64[:2, :2] = new()
    wrk: float64[:2, :2] = new()
    pinv(a.view, p.view, gram.view, inv_g.view, wrk.view)
    prod: float64[:2, :2] = new()
    matmul(a.view, p.view, prod.view)
    self.assertTrue(isclose(prod[0, 0], 1.0, _REL, _ABS))
    self.assertTrue(isclose(prod[1, 1], 1.0, _REL, _ABS))
    self.assertTrue(isclose(prod[0, 1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(prod[1, 0], 0.0, _REL, _ABS))


class LinalgSvdWideTests(TestCaseMixin):
  _test_tag = 160

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
    self.assertTrue(isclose(s[0], 3.0, _REL, _ABS) or isclose(s[0], 2.0, _REL, _ABS))
    self.assertTrue(isclose(s[1], 3.0, _REL, _ABS) or isclose(s[1], 2.0, _REL, _ABS))
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
    self.assertTrue(isclose(recon[0, 0], 3.0, _REL, _ABS))
    self.assertTrue(isclose(recon[1, 1], 2.0, _REL, _ABS))
    self.assertTrue(isclose(recon[0, 1], 0.0, _REL, _ABS))
    self.assertTrue(isclose(recon[1, 0], 0.0, _REL, _ABS))


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
