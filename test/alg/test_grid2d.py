"""``alg.grid2d``：``Grid2D`` / ``WalkGrid`` / ``GridNav`` / ``GridConnectivity``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.grid2d import Cell, Grid2D, GridConnectivity, GridNav

class Grid2dBoundsTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        g: Grid2D = new(3, 2, 5)
        self.assertTrue(g.get_width() == 3)
        self.assertTrue(g.get_height() == 2)
        self.assertTrue(g.in_bounds(2, 1))
        self.assertFalse(g.in_bounds(3, 0))
        g.set(1, 0, 9)
        self.assertTrue(g.get(1, 0) == 9)

class WalkGridNavFourTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        w: Grid2D = new(3, 3, 1)
        w.set(1, 1, 0)
        nav: GridNav = new(w, GridConnectivity.Four)
        self.assertTrue(nav.vertex_count() == 9)
        self.assertTrue(nav.to_index(Cell(0, 0)) == 0)
        self.assertTrue(nav.from_index(4).x == 1)
        self.assertTrue(nav.from_index(4).y == 1)
        nbrs: list[Cell] = nav.neighbors(Cell(0, 0))
        self.assertTrue(len(nbrs) == 2)

class WalkGridNavEightTests(TestCaseMixin):
    _test_tag = 20

    @override
    def test(self):
        w: Grid2D = new(2, 2, 1)
        nav: GridNav = new(w, GridConnectivity.Eight)
        nbrs: list[Cell] = nav.neighbors(Cell(0, 0))
        self.assertTrue(len(nbrs) == 3)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
