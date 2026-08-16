"""``py2cpp.ui.flow``：图模型、译期目录与 ``UIFlowMixin``。"""
from py2cpp import *
from py2cpp.core.exceptions import ValueError
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.ui.app import UIApp
from py2cpp.ui.flow.meta import FlowEventMeta, FlowNodeMeta, FlowPureMeta
from py2cpp.ui.flow.catalog import FlowNodeCatalog, FlowPinSpec
from py2cpp.ui.flow.builtins import BranchKind, ForLoopKind, registerFlowBuiltins
from py2cpp.ui.flow.model import FlowGraph, FlowNodeEnum, FlowPin, FlowPinEnum
from py2cpp.ui.flow.panel import UIFlowMixin
from py2cpp.ui.flow.runtime import FlowRuntime
from py2cpp.ui.flow.canvas import UIFlowCanvas
from py2cpp.ui.flow.layout import nodesInGraphRect
from py2cpp.ui.flow.history import FlowGraphHistory
from py2cpp.ui.flow.serialize import graphFromJson, graphToJson, pasteSubgraph, subgraphToJson
from py2cpp.ui.flow.shell import UIFlowShell
from py2cpp.ui.window import UIWindow

class FlowGraphConnectTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        g: FlowGraph = new()
        pins: list[FlowPin, 0] = []
        execIn: FlowPin = new()
        execIn.name = 'execute'
        execIn.kind = FlowPinEnum.ExecIn
        pins.append(execIn)
        execOut: FlowPin = new()
        execOut.name = 'then'
        execOut.kind = FlowPinEnum.ExecOut
        pins.append(execOut)
        dataIn: FlowPin = new()
        dataIn.name = 'x'
        dataIn.kind = FlowPinEnum.DataIn
        dataIn.typeId = 'int'
        pins.append(dataIn)
        dataOut: FlowPin = new()
        dataOut.name = 'Return Value'
        dataOut.kind = FlowPinEnum.DataOut
        dataOut.typeId = 'int'
        pins.append(dataOut)
        n1: int = g.addNode('A.call', 'Call', 0.0, 0.0, pins)
        n2: int = g.addNode('B.call', 'Call', 200.0, 0.0, pins)
        node1 = g.findNode(n1)
        node2 = g.findNode(n2)
        outPin: int = node1.pins[1].id
        inPin: int = node2.pins[0].id
        eid: int = g.connect(outPin, inPin)
        self.assertTrue(eid > 0)
        self.assertEqual(len(g.edges), 1)
        dataOutId: int = node1.pins[3].id
        dataInId: int = node2.pins[2].id
        g.connect(dataOutId, dataInId)
        self.assertEqual(len(g.edges), 2)
        failed: bool = False
        try:
            g.connect(dataOutId, inPin)
        except ValueError:
            failed = True
        self.assertTrue(failed)

class FlowCatalogTests(TestCaseMixin):
    _testTag = 2

    @override
    def test(self):
        host: FlowHost = new()
        host._ensureFlowCatalog()
        self.assertEqual(len(host._flowCatalog.templates), 5)
        tpl = host._flowCatalog.find('FlowHost.fire')
        self.assertEqual(tpl.title, 'Fire')
        self.assertEqual(tpl.category, 'Combat')
        self.assertEqual(len(tpl.pins), 4)
        pure = host._flowCatalog.find('FlowHost.getHp')
        self.assertEqual(len(pure.pins), 1)
        evt = host._flowCatalog.find('FlowHost.onBegin')
        self.assertEqual(len(evt.pins), 1)
        branch = host._flowCatalog.find(BranchKind)
        self.assertEqual(branch.nodeKind, FlowNodeEnum.Branch)
        loop = host._flowCatalog.find(ForLoopKind)
        self.assertEqual(loop.nodeKind, FlowNodeEnum.ForLoop)

class FlowGraphMoveNodeTests(TestCaseMixin):
    _testTag = 3

    @override
    def test(self):
        g: FlowGraph = new()
        pins: list[FlowPin, 0] = []
        execOut: FlowPin = new()
        execOut.name = 'then'
        execOut.kind = FlowPinEnum.ExecOut
        pins.append(execOut)
        nid: int = g.addNode('T.evt', 'Evt', 10.0, 20.0, pins)
        g.moveNode(nid, 5.0, -3.0)
        node = g.findNode(nid)
        self.assertEqual(node.x, 15.0)
        self.assertEqual(node.y, 17.0)

class FlowCanvasNodeTests(TestCaseMixin):
    _testTag = 4

    @override
    def test(self):
        host: FlowHost = new()
        host._ensureFlowCatalog()
        host._flowCanvas.catalog = host._flowCatalog
        nid: int = host._flowCanvas.addNodeFromKind('FlowHost.fire', 40.0, 40.0)
        self.assertTrue(nid > 0)
        self.assertEqual(len(host._flowCanvas.graph.nodes), 1)
        node = host._flowCanvas.graph.findNode(nid)
        self.assertEqual(node.title, 'Fire')
        self.assertEqual(len(node.pins), 4)

class FlowPanDragTests(TestCaseMixin):
    _testTag = 6

    @override
    def test(self):
        c: UIFlowCanvas = new()
        c.zoom = 1.0
        c.onPointerDown(2, 100, 100)
        for i in range(2000):
            c.onPointerMove(2, 100 + i, 100 + i)
        self.assertEqual(c.panX, 1999.0)
        self.assertEqual(c.panY, 1999.0)
        c.onPointerUp(2, 2100, 2100)

class FlowSerializeTests(TestCaseMixin):
    _testTag = 7

    @override
    def test(self):
        g: FlowGraph = new()
        pins: list[FlowPin, 0] = []
        execOut: FlowPin = new()
        execOut.name = 'then'
        execOut.kind = FlowPinEnum.ExecOut
        pins.append(execOut)
        nid: int = g.addNode('T.evt', 'Evt', 10.0, 20.0, pins)
        text: str = graphToJson(g)
        g2: FlowGraph = new()
        graphFromJson(g2, text)
        self.assertEqual(len(g2.nodes), 1)
        node = g2.findNode(nid)
        self.assertEqual(node.title, 'Evt')
        self.assertEqual(node.x, 10.0)
        self.assertEqual(node.y, 20.0)

class FlowMarqueeTests(TestCaseMixin):
    _testTag = 8

    @override
    def test(self):
        g: FlowGraph = new()
        pins: list[FlowPin, 0] = []
        execOut: FlowPin = new()
        execOut.name = 'then'
        execOut.kind = FlowPinEnum.ExecOut
        pins.append(execOut)
        n1: int = g.addNode('A.e', 'A', 10.0, 10.0, pins)
        n2: int = g.addNode('B.e', 'B', 300.0, 10.0, pins)
        inside = nodesInGraphRect(g, 0.0, 0.0, 250.0, 200.0)
        self.assertEqual(len(inside), 1)
        self.assertEqual(inside[0], n1)
        both = nodesInGraphRect(g, 0.0, 0.0, 500.0, 200.0)
        self.assertEqual(len(both), 2)
        self.assertTrue(n1 > 0)
        self.assertTrue(n2 > 0)

class FlowClipboardTests(TestCaseMixin):
    _testTag = 9

    @override
    def test(self):
        g: FlowGraph = new()
        pins: list[FlowPin, 0] = []
        execIn: FlowPin = new()
        execIn.name = 'execute'
        execIn.kind = FlowPinEnum.ExecIn
        pins.append(execIn)
        execOut: FlowPin = new()
        execOut.name = 'then'
        execOut.kind = FlowPinEnum.ExecOut
        pins.append(execOut)
        n1: int = g.addNode('A.c', 'A', 0.0, 0.0, pins)
        n2: int = g.addNode('B.c', 'B', 200.0, 0.0, pins)
        sel: list[int, 0] = []
        sel.append(n1)
        sel.append(n2)
        text: str = subgraphToJson(g, sel)
        g2: FlowGraph = new()
        newIds: list[int, 0] = pasteSubgraph(g2, text, 50.0, 50.0)
        self.assertEqual(len(newIds), 2)
        self.assertEqual(len(g2.nodes), 2)
        node = g2.findNode(newIds[0])
        self.assertEqual(node.x, 50.0)
        self.assertEqual(node.y, 50.0)

class FlowHistoryTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        hist: FlowGraphHistory = new()
        g: FlowGraph = new()
        pins: list[FlowPin, 0] = []
        execOut: FlowPin = new()
        execOut.name = 'then'
        execOut.kind = FlowPinEnum.ExecOut
        pins.append(execOut)
        hist.push(g)
        g.addNode('T.e', 'One', 1.0, 2.0, pins)
        self.assertEqual(len(g.nodes), 1)
        self.assertTrue(hist.undo(g))
        self.assertEqual(len(g.nodes), 0)
        self.assertTrue(hist.redo(g))
        self.assertEqual(len(g.nodes), 1)

class FlowShellMenuTests(TestCaseMixin):
    _testTag = 11

    @override
    def test(self):
        cv: UIFlowCanvas = new()
        shell: UIFlowShell = new()
        shell.bindCanvas(UIWindow(), cv)
        pins: list[FlowPin, 0] = []
        execOut: FlowPin = new()
        execOut.name = 'then'
        execOut.kind = FlowPinEnum.ExecOut
        pins.append(execOut)
        n1: int = cv.graph.addNode('A.e', 'A', 0.0, 0.0, pins)
        n2: int = cv.graph.addNode('B.e', 'B', 200.0, 0.0, pins)
        shell.runCanvasMenu(208)
        shell.runCanvasMenu(206)
        empty: str = ''
        self.assertTrue(cv.clipboardJson != empty)
        shell.runCanvasMenu(207)
        self.assertEqual(len(cv.graph.nodes), 4)
        shell.runCanvasMenu(208)
        shell.runCanvasMenu(201)
        self.assertEqual(len(cv.graph.nodes), 0)
        shell.runCanvasMenu(203)
        self.assertEqual(len(cv.graph.nodes), 4)

class FlowRuntimeLinearTests(TestCaseMixin):
    _testTag = 12

    @override
    def test(self):
        host: FlowRuntimeHost = new()
        host.prepare()
        g: FlowGraph @ ref = host.graph
        evt: int = host.addKind('host.onBegin', 0.0, 0.0)
        fire: int = host.addKind('host.fire', 200.0, 0.0)
        three: int = host.addKind('host.three', 200.0, 100.0)
        g.connect(g.findPinOnNode(evt, 'then', FlowPinEnum.ExecOut), g.findPinOnNode(fire, 'execute', FlowPinEnum.ExecIn))
        g.connect(g.findPinOnNode(three, 'Return Value', FlowPinEnum.DataOut), g.findPinOnNode(fire, 'shots', FlowPinEnum.DataIn))
        rt: FlowRuntime = new()
        cat: FlowNodeCatalog @ ref = host.catalog
        rt.runFromEvent(g, cat, host, evt)
        self.assertEqual(host.hp, 97)

class FlowRuntimeBranchTests(TestCaseMixin):
    _testTag = 13

    @override
    def test(self):
        host: FlowRuntimeHost = new()
        host.prepare()
        g: FlowGraph @ ref = host.graph
        cat: FlowNodeCatalog @ ref = host.catalog
        evt: int = host.addKind('host.onBegin', 0.0, 0.0)
        branch: int = host.addKind(BranchKind, 200.0, 0.0)
        fire: int = host.addKind('host.fire', 400.0, 0.0)
        three: int = host.addKind('host.three', 200.0, 100.0)
        yes: int = host.addKind('host.yes', 200.0, 200.0)
        g.connect(g.findPinOnNode(evt, 'then', FlowPinEnum.ExecOut), g.findPinOnNode(branch, 'execute', FlowPinEnum.ExecIn))
        g.connect(g.findPinOnNode(yes, 'Return Value', FlowPinEnum.DataOut), g.findPinOnNode(branch, 'condition', FlowPinEnum.DataIn))
        g.connect(g.findPinOnNode(branch, 'OnTrue', FlowPinEnum.ExecOut), g.findPinOnNode(fire, 'execute', FlowPinEnum.ExecIn))
        g.connect(g.findPinOnNode(three, 'Return Value', FlowPinEnum.DataOut), g.findPinOnNode(fire, 'shots', FlowPinEnum.DataIn))
        rt: FlowRuntime = new()
        rt.runFromEvent(g, cat, host, evt)
        self.assertEqual(host.hp, 97)

class FlowRuntimeForLoopTests(TestCaseMixin):
    _testTag = 14

    @override
    def test(self):
        host: FlowRuntimeHost = new()
        host.prepare()
        g: FlowGraph @ ref = host.graph
        cat: FlowNodeCatalog @ ref = host.catalog
        evt: int = host.addKind('host.onBegin', 0.0, 0.0)
        loop: int = host.addKind(ForLoopKind, 200.0, 0.0)
        fire: int = host.addKind('host.fire', 400.0, 0.0)
        three: int = host.addKind('host.three', 200.0, 100.0)
        g.connect(g.findPinOnNode(evt, 'then', FlowPinEnum.ExecOut), g.findPinOnNode(loop, 'execute', FlowPinEnum.ExecIn))
        g.connect(g.findPinOnNode(three, 'Return Value', FlowPinEnum.DataOut), g.findPinOnNode(loop, 'count', FlowPinEnum.DataIn))
        g.connect(g.findPinOnNode(loop, 'LoopBody', FlowPinEnum.ExecOut), g.findPinOnNode(fire, 'execute', FlowPinEnum.ExecIn))
        g.connect(g.findPinOnNode(three, 'Return Value', FlowPinEnum.DataOut), g.findPinOnNode(fire, 'shots', FlowPinEnum.DataIn))
        rt: FlowRuntime = new()
        rt.runFromEvent(g, cat, host, evt)
        self.assertEqual(host.hp, 91)

class FlowCreateTests(TestCaseMixin):
    _testTag = 5

    @override
    def test(self):
        if not UIApp.isAvailable():
            return
        host: FlowHost = new()
        win = host.createFlow('Flow Test', 640, 480)
        self.assertTrue(win.handle != 0)
        self.assertEqual(win.title, 'Flow Test')
        win.close()

@dataclass
class FlowHost(UIFlowMixin, friends=(FlowCatalogTests, FlowGraphMoveNodeTests, FlowCanvasNodeTests, FlowCreateTests, FlowPanDragTests)):
    hp: int = 100

    @FlowEventMeta('Begin Play')
    def onBegin(self) -> None:
        pass

    @FlowNodeMeta('Fire', category='Combat')
    def fire(self, shots: int) -> bool:
        if self.hp < shots:
            return False
        self.hp -= shots
        return True

    @FlowPureMeta('HP')
    def getHp(self) -> int:
        return self.hp

@dataclass(eq=False, repr=False)
class FlowRuntimeHost:
    """轻量宿主：只测 ``FlowRuntime``，不嵌入 ``UIFlowMixin`` 大对象。"""
    hp: int = 100
    catalog: FlowNodeCatalog = new()
    graph: FlowGraph = new()

    def _pin(self, name: str, kind: FlowPinEnum, typeId: str='') -> FlowPinSpec:
        p: FlowPinSpec = new()
        p.name = name
        p.kind = kind
        p.typeId = typeId
        return p

    def prepare(self) -> None:
        firePins: list[FlowPinSpec, 0] = []
        firePins.append(self._pin('execute', FlowPinEnum.ExecIn))
        firePins.append(self._pin('then', FlowPinEnum.ExecOut))
        firePins.append(self._pin('shots', FlowPinEnum.DataIn, 'int'))
        firePins.append(self._pin('Return Value', FlowPinEnum.DataOut, 'bool'))
        self.catalog.register('host.fire', 'Fire', 'Combat', FlowNodeEnum.Callable, 'fire', firePins)
        purePins: list[FlowPinSpec, 0] = []
        purePins.append(self._pin('Return Value', FlowPinEnum.DataOut, 'int'))
        self.catalog.register('host.three', 'Three', 'Host', FlowNodeEnum.Pure, 'three', purePins)
        yesPins: list[FlowPinSpec, 0] = []
        yesPins.append(self._pin('Return Value', FlowPinEnum.DataOut, 'bool'))
        self.catalog.register('host.yes', 'Yes', 'Host', FlowNodeEnum.Pure, 'yes', yesPins)
        evtPins: list[FlowPinSpec, 0] = []
        evtPins.append(self._pin('then', FlowPinEnum.ExecOut))
        self.catalog.register('host.onBegin', 'Begin', 'Events', FlowNodeEnum.Event, 'onBegin', evtPins)
        registerFlowBuiltins(self.catalog)

    def addKind(self, kindId: str, x: float64, y: float64) -> int:
        tpl = self.catalog.find(kindId)
        pins = self.catalog.clonePins(kindId)
        return self.graph.addNode(kindId, tpl.title, x, y, pins)

    def fire(self, shots: int) -> bool:
        if self.hp < shots:
            return False
        self.hp -= shots
        return True

    def three(self) -> int:
        return 3

    def yes(self) -> bool:
        return True

    def flowInvokeCallable(self, method: str, graph: FlowGraph @ ref, nodeId: int, rt: FlowRuntime @ ref) -> None:
        if method == 'fire':
            self.fire(rt.evalDataPin(graph, self.catalog, self, nodeId, 'shots'))

    def flowInvokePure(self, method: str) -> int:
        if method == 'three':
            return self.three()
        if method == 'yes':
            if self.yes():
                return 1
            return 0
        return 0

def main() -> int:
    suite: TestSuite = TestSuite()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
