"""``alg.navigate``：``astar`` / ``dijkstra`` + ``Navigatable``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.grid2d import Cell, Grid2D, GridConnectivity, GridNav
from py2cpp.alg.graph import AdjList, GraphNav
from py2cpp.alg.navigate import astar, dijkstra


class AstarGridTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    w: Grid2D = new(5, 5, 1)
    for x in range(1, 4):
      w.set(x, 0, 0)
    for x in range(5):
      w.set(x, 2, 0)
    w.set(2, 2, 1)
    nav: GridNav = new(w, GridConnectivity.Four)
    path: list[Cell] = astar(nav, Cell(0, 0), Cell(4, 0))
    self.assertTrue(len(path) == 7)
    self.assertTrue(path[0].x == 0 and path[0].y == 0)
    last: int = len(path) - 1
    self.assertTrue(path[last].x == 4 and path[last].y == 0)


class AstarGridUnreachableTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    w: Grid2D = new(3, 1, 1)
    w.set(1, 0, 0)
    nav: GridNav = new(w, GridConnectivity.Four)
    path: list[Cell] = astar(nav, Cell(0, 0), Cell(2, 0))
    self.assertFalse(path)


class AstarGraphTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    g: AdjList = new(4)
    g.add_edge(0, 1, 1)
    g.add_edge(1, 2, 1)
    g.add_edge(2, 3, 1)
    g.add_edge(0, 3, 10)
    empty_h: list[int] = []
    nav: GraphNav = new(g, empty_h)
    path: list[int] = astar(nav, 0, 3)
    self.assertTrue(len(path) == 4)
    self.assertTrue(path[0] == 0)
    self.assertTrue(path[-1] == 3)


class DijkstraGraphTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    g: AdjList = new(3)
    g.add_edge(0, 1, 5)
    g.add_edge(0, 2, 1)
    g.add_edge(2, 1, 1)
    empty_h: list[int] = []
    nav: GraphNav = new(g, empty_h)
    path: list[int] = dijkstra(nav, 0, 1)
    self.assertTrue(len(path) == 3)
    self.assertTrue(path[1] == 2)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
