"""``alg.grid2d``：``Grid2D`` / ``WalkGrid`` / ``GridNav`` / ``GridConnectivityEnum``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.grid2d import Cell, Grid2D, GridConnectivityEnum, GridNav

class Grid2dBoundsTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        g: Grid2D = new(3, 2, 5)
        self.assertTrue(g.getWidth() == 3)
        self.assertTrue(g.getHeight() == 2)
        self.assertTrue(g.inBounds(2, 1))
        self.assertFalse(g.inBounds(3, 0))
        g.set(1, 0, 9)
        self.assertTrue(g.get(1, 0) == 9)

class WalkGridNavFourTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        w: Grid2D = new(3, 3, 1)
        w.set(1, 1, 0)
        nav: GridNav = new(w, GridConnectivityEnum.Four)
        self.assertTrue(nav.vertexCount() == 9)
        self.assertTrue(nav.toIndex(Cell(0, 0)) == 0)
        self.assertTrue(nav.fromIndex(4).x == 1)
        self.assertTrue(nav.fromIndex(4).y == 1)
        nbrs: list[Cell] = nav.neighbors(Cell(0, 0))
        self.assertTrue(len(nbrs) == 2)

class WalkGridNavEightTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        w: Grid2D = new(2, 2, 1)
        nav: GridNav = new(w, GridConnectivityEnum.Eight)
        nbrs: list[Cell] = nav.neighbors(Cell(0, 0))
        self.assertTrue(len(nbrs) == 3)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
