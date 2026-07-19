"""``py2cpp.ui.flow``：图模型、译期目录与 ``UIFlowMixin``。"""
from py2cpp import *
from py2cpp.core.exceptions import ValueError
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.app import UIApp
from py2cpp.ui.flow.meta import FlowEventMeta, FlowNodeMeta, FlowPureMeta
from py2cpp.ui.flow.catalog import FlowNodeCatalog, FlowPinSpec
from py2cpp.ui.flow.builtins import BRANCH_KIND, FOR_LOOP_KIND, register_flow_builtins
from py2cpp.ui.flow.model import FlowGraph, FlowNodeKind, FlowPin, FlowPinKind
from py2cpp.ui.flow.panel import UIFlowMixin
from py2cpp.ui.flow.runtime import FlowRuntime
from py2cpp.ui.flow.canvas import UIFlowCanvas
from py2cpp.ui.flow.layout import nodes_in_graph_rect
from py2cpp.ui.flow.history import FlowGraphHistory
from py2cpp.ui.flow.serialize import graph_from_json, graph_to_json, paste_subgraph, subgraph_to_json
from py2cpp.ui.flow.shell import UIFlowShell
from py2cpp.ui.window import UIWindow


class FlowGraphConnectTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    g: FlowGraph = new()
    pins: list[FlowPin, 0] = []
    exec_in: FlowPin = new()
    exec_in.name = "execute"
    exec_in.kind = FlowPinKind.ExecIn
    pins.append(exec_in)
    exec_out: FlowPin = new()
    exec_out.name = "then"
    exec_out.kind = FlowPinKind.ExecOut
    pins.append(exec_out)
    data_in: FlowPin = new()
    data_in.name = "x"
    data_in.kind = FlowPinKind.DataIn
    data_in.type_id = "int"
    pins.append(data_in)
    data_out: FlowPin = new()
    data_out.name = "Return Value"
    data_out.kind = FlowPinKind.DataOut
    data_out.type_id = "int"
    pins.append(data_out)
    n1: int = g.add_node("A.call", "Call", 0.0, 0.0, pins)
    n2: int = g.add_node("B.call", "Call", 200.0, 0.0, pins)
    node1 = g.find_node(n1)
    node2 = g.find_node(n2)
    out_pin: int = node1.pins[1].id
    in_pin: int = node2.pins[0].id
    eid: int = g.connect(out_pin, in_pin)
    self.assertTrue(eid > 0)
    self.assertEqual(len(g.edges), 1)
    data_out_id: int = node1.pins[3].id
    data_in_id: int = node2.pins[2].id
    g.connect(data_out_id, data_in_id)
    self.assertEqual(len(g.edges), 2)
    failed: bool = False
    try:
      g.connect(data_out_id, in_pin)
    except ValueError:
      failed = True
    self.assertTrue(failed)


class FlowCatalogTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    host: FlowHost = new()
    host._ensure_flow_catalog()
    self.assertEqual(len(host._flow_catalog.templates), 5)
    tpl = host._flow_catalog.find("FlowHost.fire")
    self.assertEqual(tpl.title, "Fire")
    self.assertEqual(tpl.category, "Combat")
    self.assertEqual(len(tpl.pins), 4)
    pure = host._flow_catalog.find("FlowHost.get_hp")
    self.assertEqual(len(pure.pins), 1)
    evt = host._flow_catalog.find("FlowHost.on_begin")
    self.assertEqual(len(evt.pins), 1)
    branch = host._flow_catalog.find(BRANCH_KIND)
    self.assertEqual(branch.node_kind, FlowNodeKind.Branch)
    loop = host._flow_catalog.find(FOR_LOOP_KIND)
    self.assertEqual(loop.node_kind, FlowNodeKind.ForLoop)


class FlowGraphMoveNodeTests(TestCaseMixin):
  _test_tag = 3

  @override
  def test(self):
    g: FlowGraph = new()
    pins: list[FlowPin, 0] = []
    exec_out: FlowPin = new()
    exec_out.name = "then"
    exec_out.kind = FlowPinKind.ExecOut
    pins.append(exec_out)
    nid: int = g.add_node("T.evt", "Evt", 10.0, 20.0, pins)
    g.move_node(nid, 5.0, -3.0)
    node = g.find_node(nid)
    self.assertEqual(node.x, 15.0)
    self.assertEqual(node.y, 17.0)


class FlowCanvasNodeTests(TestCaseMixin):
  _test_tag = 4

  @override
  def test(self):
    host: FlowHost = new()
    host._ensure_flow_catalog()
    host._flow_canvas.catalog = host._flow_catalog
    nid: int = host._flow_canvas.add_node_from_kind("FlowHost.fire", 40.0, 40.0)
    self.assertTrue(nid > 0)
    self.assertEqual(len(host._flow_canvas.graph.nodes), 1)
    node = host._flow_canvas.graph.find_node(nid)
    self.assertEqual(node.title, "Fire")
    self.assertEqual(len(node.pins), 4)


class FlowPanDragTests(TestCaseMixin):
  _test_tag = 6

  @override
  def test(self):
    c: UIFlowCanvas = new()
    c.zoom = 1.0
    c.on_pointer_down(2, 100, 100)
    for i in range(2000):
      c.on_pointer_move(2, 100 + i, 100 + i)
    self.assertEqual(c.pan_x, 1999.0)
    self.assertEqual(c.pan_y, 1999.0)
    c.on_pointer_up(2, 2100, 2100)


class FlowSerializeTests(TestCaseMixin):
  _test_tag = 7

  @override
  def test(self):
    g: FlowGraph = new()
    pins: list[FlowPin, 0] = []
    exec_out: FlowPin = new()
    exec_out.name = "then"
    exec_out.kind = FlowPinKind.ExecOut
    pins.append(exec_out)
    nid: int = g.add_node("T.evt", "Evt", 10.0, 20.0, pins)
    text: str = graph_to_json(g)
    g2: FlowGraph = new()
    graph_from_json(g2, text)
    self.assertEqual(len(g2.nodes), 1)
    node = g2.find_node(nid)
    self.assertEqual(node.title, "Evt")
    self.assertEqual(node.x, 10.0)
    self.assertEqual(node.y, 20.0)


class FlowMarqueeTests(TestCaseMixin):
  _test_tag = 8

  @override
  def test(self):
    g: FlowGraph = new()
    pins: list[FlowPin, 0] = []
    exec_out: FlowPin = new()
    exec_out.name = "then"
    exec_out.kind = FlowPinKind.ExecOut
    pins.append(exec_out)
    n1: int = g.add_node("A.e", "A", 10.0, 10.0, pins)
    n2: int = g.add_node("B.e", "B", 300.0, 10.0, pins)
    inside = nodes_in_graph_rect(g, 0.0, 0.0, 250.0, 200.0)
    self.assertEqual(len(inside), 1)
    self.assertEqual(inside[0], n1)
    both = nodes_in_graph_rect(g, 0.0, 0.0, 500.0, 200.0)
    self.assertEqual(len(both), 2)
    self.assertTrue(n1 > 0)
    self.assertTrue(n2 > 0)


class FlowClipboardTests(TestCaseMixin):
  _test_tag = 9

  @override
  def test(self):
    g: FlowGraph = new()
    pins: list[FlowPin, 0] = []
    exec_in: FlowPin = new()
    exec_in.name = "execute"
    exec_in.kind = FlowPinKind.ExecIn
    pins.append(exec_in)
    exec_out: FlowPin = new()
    exec_out.name = "then"
    exec_out.kind = FlowPinKind.ExecOut
    pins.append(exec_out)
    n1: int = g.add_node("A.c", "A", 0.0, 0.0, pins)
    n2: int = g.add_node("B.c", "B", 200.0, 0.0, pins)
    sel: list[int, 0] = []
    sel.append(n1)
    sel.append(n2)
    text: str = subgraph_to_json(g, sel)
    g2: FlowGraph = new()
    new_ids: list[int, 0] = paste_subgraph(g2, text, 50.0, 50.0)
    self.assertEqual(len(new_ids), 2)
    self.assertEqual(len(g2.nodes), 2)
    node = g2.find_node(new_ids[0])
    self.assertEqual(node.x, 50.0)
    self.assertEqual(node.y, 50.0)


class FlowHistoryTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    hist: FlowGraphHistory = new()
    g: FlowGraph = new()
    pins: list[FlowPin, 0] = []
    exec_out: FlowPin = new()
    exec_out.name = "then"
    exec_out.kind = FlowPinKind.ExecOut
    pins.append(exec_out)
    hist.push(g)
    g.add_node("T.e", "One", 1.0, 2.0, pins)
    self.assertEqual(len(g.nodes), 1)
    self.assertTrue(hist.undo(g))
    self.assertEqual(len(g.nodes), 0)
    self.assertTrue(hist.redo(g))
    self.assertEqual(len(g.nodes), 1)


class FlowShellMenuTests(TestCaseMixin):
  _test_tag = 11

  @override
  def test(self):
    cv: UIFlowCanvas = new()
    shell: UIFlowShell = new()
    win: UIWindow = new()
    shell.bind_canvas(win, cv)
    pins: list[FlowPin, 0] = []
    exec_out: FlowPin = new()
    exec_out.name = "then"
    exec_out.kind = FlowPinKind.ExecOut
    pins.append(exec_out)
    n1: int = cv.graph.add_node("A.e", "A", 0.0, 0.0, pins)
    n2: int = cv.graph.add_node("B.e", "B", 200.0, 0.0, pins)
    shell.run_canvas_menu(208)
    shell.run_canvas_menu(206)
    empty: str = ""
    self.assertTrue(cv.clipboard_json != empty)
    shell.run_canvas_menu(207)
    self.assertEqual(len(cv.graph.nodes), 4)
    shell.run_canvas_menu(208)
    shell.run_canvas_menu(201)
    self.assertEqual(len(cv.graph.nodes), 0)
    shell.run_canvas_menu(203)
    self.assertEqual(len(cv.graph.nodes), 4)


class FlowRuntimeLinearTests(TestCaseMixin):
  _test_tag = 12

  @override
  def test(self):
    host: FlowRuntimeHost = new()
    host.prepare()
    g: FlowGraph @ref = host.graph
    evt: int = host.add_kind("host.on_begin", 0.0, 0.0)
    fire: int = host.add_kind("host.fire", 200.0, 0.0)
    three: int = host.add_kind("host.three", 200.0, 100.0)
    g.connect(
      g.find_pin_on_node(evt, "then", FlowPinKind.ExecOut),
      g.find_pin_on_node(fire, "execute", FlowPinKind.ExecIn),
    )
    g.connect(
      g.find_pin_on_node(three, "Return Value", FlowPinKind.DataOut),
      g.find_pin_on_node(fire, "shots", FlowPinKind.DataIn),
    )
    rt: FlowRuntime = new()
    cat: FlowNodeCatalog @ref = host.catalog
    rt.run_from_event(g, cat, host, evt)
    self.assertEqual(host.hp, 97)


class FlowRuntimeBranchTests(TestCaseMixin):
  _test_tag = 13

  @override
  def test(self):
    host: FlowRuntimeHost = new()
    host.prepare()
    g: FlowGraph @ref = host.graph
    cat: FlowNodeCatalog @ref = host.catalog
    evt: int = host.add_kind("host.on_begin", 0.0, 0.0)
    branch: int = host.add_kind(BRANCH_KIND, 200.0, 0.0)
    fire: int = host.add_kind("host.fire", 400.0, 0.0)
    three: int = host.add_kind("host.three", 200.0, 100.0)
    yes: int = host.add_kind("host.yes", 200.0, 200.0)
    g.connect(
      g.find_pin_on_node(evt, "then", FlowPinKind.ExecOut),
      g.find_pin_on_node(branch, "execute", FlowPinKind.ExecIn),
    )
    g.connect(
      g.find_pin_on_node(yes, "Return Value", FlowPinKind.DataOut),
      g.find_pin_on_node(branch, "condition", FlowPinKind.DataIn),
    )
    g.connect(
      g.find_pin_on_node(branch, "OnTrue", FlowPinKind.ExecOut),
      g.find_pin_on_node(fire, "execute", FlowPinKind.ExecIn),
    )
    g.connect(
      g.find_pin_on_node(three, "Return Value", FlowPinKind.DataOut),
      g.find_pin_on_node(fire, "shots", FlowPinKind.DataIn),
    )
    rt: FlowRuntime = new()
    rt.run_from_event(g, cat, host, evt)
    self.assertEqual(host.hp, 97)


class FlowRuntimeForLoopTests(TestCaseMixin):
  _test_tag = 14

  @override
  def test(self):
    host: FlowRuntimeHost = new()
    host.prepare()
    g: FlowGraph @ref = host.graph
    cat: FlowNodeCatalog @ref = host.catalog
    evt: int = host.add_kind("host.on_begin", 0.0, 0.0)
    loop: int = host.add_kind(FOR_LOOP_KIND, 200.0, 0.0)
    fire: int = host.add_kind("host.fire", 400.0, 0.0)
    three: int = host.add_kind("host.three", 200.0, 100.0)
    g.connect(
      g.find_pin_on_node(evt, "then", FlowPinKind.ExecOut),
      g.find_pin_on_node(loop, "execute", FlowPinKind.ExecIn),
    )
    g.connect(
      g.find_pin_on_node(three, "Return Value", FlowPinKind.DataOut),
      g.find_pin_on_node(loop, "count", FlowPinKind.DataIn),
    )
    g.connect(
      g.find_pin_on_node(loop, "LoopBody", FlowPinKind.ExecOut),
      g.find_pin_on_node(fire, "execute", FlowPinKind.ExecIn),
    )
    g.connect(
      g.find_pin_on_node(three, "Return Value", FlowPinKind.DataOut),
      g.find_pin_on_node(fire, "shots", FlowPinKind.DataIn),
    )
    rt: FlowRuntime = new()
    rt.run_from_event(g, cat, host, evt)
    self.assertEqual(host.hp, 91)


class FlowCreateTests(TestCaseMixin):
  _test_tag = 5

  @override
  def test(self):
    if not UIApp.is_available():
      return
    host: FlowHost = new()
    win = host.create_flow("Flow Test", 640, 480)
    self.assertTrue(win.handle != 0)
    self.assertEqual(win.title, "Flow Test")
    win.close()


@dataclass
class FlowHost(UIFlowMixin, friends=(FlowCatalogTests, FlowGraphMoveNodeTests, FlowCanvasNodeTests, FlowCreateTests, FlowPanDragTests,)):
  hp: int = 100

  @FlowEventMeta("Begin Play")
  def on_begin(self) -> None:
    pass

  @FlowNodeMeta("Fire", category="Combat")
  def fire(self, shots: int) -> bool:
    if self.hp < shots:
      return False
    self.hp -= shots
    return True

  @FlowPureMeta("HP")
  def get_hp(self) -> int:
    return self.hp


@dataclass(eq=False, repr=False)
class FlowRuntimeHost:
  """轻量宿主：只测 ``FlowRuntime``，不嵌入 ``UIFlowMixin`` 大对象。"""

  hp: int = 100
  catalog: FlowNodeCatalog = new()
  graph: FlowGraph = new()

  def _pin(self, name: str, kind: FlowPinKind, type_id: str = "") -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = name
    p.kind = kind
    p.type_id = type_id
    return p

  def prepare(self) -> None:
    fire_pins: list[FlowPinSpec, 0] = []
    fire_pins.append(self._pin("execute", FlowPinKind.ExecIn))
    fire_pins.append(self._pin("then", FlowPinKind.ExecOut))
    fire_pins.append(self._pin("shots", FlowPinKind.DataIn, "int"))
    fire_pins.append(self._pin("Return Value", FlowPinKind.DataOut, "bool"))
    self.catalog.register("host.fire", "Fire", "Combat", FlowNodeKind.Callable, "fire", fire_pins)
    pure_pins: list[FlowPinSpec, 0] = []
    pure_pins.append(self._pin("Return Value", FlowPinKind.DataOut, "int"))
    self.catalog.register("host.three", "Three", "Host", FlowNodeKind.Pure, "three", pure_pins)
    yes_pins: list[FlowPinSpec, 0] = []
    yes_pins.append(self._pin("Return Value", FlowPinKind.DataOut, "bool"))
    self.catalog.register("host.yes", "Yes", "Host", FlowNodeKind.Pure, "yes", yes_pins)
    evt_pins: list[FlowPinSpec, 0] = []
    evt_pins.append(self._pin("then", FlowPinKind.ExecOut))
    self.catalog.register("host.on_begin", "Begin", "Events", FlowNodeKind.Event, "on_begin", evt_pins)
    register_flow_builtins(self.catalog)

  def add_kind(self, kind_id: str, x: float64, y: float64) -> int:
    tpl = self.catalog.find(kind_id)
    pins = self.catalog.clone_pins(kind_id)
    return self.graph.add_node(kind_id, tpl.title, x, y, pins)

  def fire(self, shots: int) -> bool:
    if self.hp < shots:
      return False
    self.hp -= shots
    return True

  def three(self) -> int:
    return 3

  def yes(self) -> bool:
    return True

  def flow_invoke_callable(
    self,
    method: str,
    graph: FlowGraph @ref,
    node_id: int,
    rt: FlowRuntime @ref,
  ) -> None:
    if method == "fire":
      self.fire(rt.eval_data_pin(graph, self.catalog, self, node_id, "shots"))

  def flow_invoke_pure(self, method: str) -> int:
    if method == "three":
      return self.three()
    if method == "yes":
      if self.yes():
        return 1
      return 0
    return 0


def main() -> int:
  suite: TestSuite = TestSuite()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
