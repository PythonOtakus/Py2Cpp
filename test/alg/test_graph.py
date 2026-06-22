"""``alg.graph``：``AdjList`` / ``GraphNav``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.graph import AdjList, GraphNav


class AdjListTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    g: AdjList = new(3)
    g.add_undirected(0, 1, 2)
    g.add_edge(1, 2, 1)
    empty_h: list[int] = []
    nav: GraphNav = new(g, empty_h)
    self.assertTrue(nav.vertex_count() == 3)
    nbrs: list[int] = nav.neighbors(0)
    self.assertTrue(len(nbrs) == 1)
    self.assertTrue(nav.move_cost(0, 1) == 2)


class GraphNavHeuristicTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    g: AdjList = new(2)
    g.add_edge(0, 1, 1)
    h: list[int] = [3, 0]
    nav: GraphNav = new(g, h)
    self.assertTrue(nav.heuristic(0, 1) == 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
