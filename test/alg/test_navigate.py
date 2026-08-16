"""``alg.navigate``：``astar`` / ``dijkstra`` + ``NavigatableType``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.grid2d import Cell, Grid2D, GridConnectivityEnum, GridNav
from py2cpp.alg.graph import AdjList, GraphNav
from py2cpp.alg.navigate import astar, dijkstra

class AstarGridTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        w: Grid2D = new(5, 5, 1)
        for x in range(1, 4):
            w.set(x, 0, 0)
        for x in range(5):
            w.set(x, 2, 0)
        w.set(2, 2, 1)
        path: list[Cell] = astar(GridNav(w, GridConnectivityEnum.Four), Cell(0, 0), Cell(4, 0))
        self.assertTrue(len(path) == 7)
        self.assertTrue(path[0].x == 0 and path[0].y == 0)
        last: int = len(path) - 1
        self.assertTrue(path[last].x == 4 and path[last].y == 0)

class AstarGridUnreachableTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        w: Grid2D = new(3, 1, 1)
        w.set(1, 0, 0)
        path: list[Cell] = astar(GridNav(w, GridConnectivityEnum.Four), Cell(0, 0), Cell(2, 0))
        self.assertFalse(path)

class AstarGraphTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        g: AdjList = new(4)
        g.addEdge(0, 1, 1)
        g.addEdge(1, 2, 1)
        g.addEdge(2, 3, 1)
        g.addEdge(0, 3, 10)
        emptyH: list[int] = []
        path: list[int] = astar(GraphNav(g, emptyH), 0, 3)
        self.assertTrue(len(path) == 4)
        self.assertTrue(path[0] == 0)
        self.assertTrue(path[-1] == 3)

class DijkstraGraphTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        g: AdjList = new(3)
        g.addEdge(0, 1, 5)
        g.addEdge(0, 2, 1)
        g.addEdge(2, 1, 1)
        emptyH: list[int] = []
        path: list[int] = dijkstra(GraphNav(g, emptyH), 0, 1)
        self.assertTrue(len(path) == 3)
        self.assertTrue(path[1] == 2)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
