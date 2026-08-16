"""``alg.graph``：``AdjList`` / ``GraphNav``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.alg.graph import AdjList, GraphNav


class AdjListTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    g: AdjList = new(3)
    g.addUndirected(0, 1, 2)
    g.addEdge(1, 2, 1)
    emptyH: list[int] = []
    nav: GraphNav = new(g, emptyH)
    self.assertTrue(nav.vertexCount() == 3)
    nbrs: list[int] = nav.neighbors(0)
    self.assertTrue(len(nbrs) == 1)
    self.assertTrue(nav.moveCost(0, 1) == 2)


class GraphNavHeuristicTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    g: AdjList = new(2)
    g.addEdge(0, 1, 1)
    h: list[int] = [3, 0]
    nav: GraphNav = new(g, h)
    self.assertTrue(nav.heuristic(0, 1) == 3)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
