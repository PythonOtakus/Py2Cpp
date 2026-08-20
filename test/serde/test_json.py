"""``@serializable`` + ``json.dumps`` / ``json.loads``；``JsonDecoder``/``JsonEncoder`` 叶子与快路径。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import open
from py2cpp.io import StringIO
from py2cpp.io.path import Path
from py2cpp.serde.json import Json, JsonDecoder, JsonEncoder
from py2cpp.test.test_temp import _TestTemp, ensureTestTemp

@serializable
@copyable
@dataclass
class User:
    id: int
    name: str
    active: bool = True
    tags: list[str] @ optional = []

@serializable
@copyable
@dataclass
class Team:
    name: str
    members: list[User] @ optional = []

@serializable
@copyable
@dataclass
class Org:
    title: str
    teams: list[Team] @ optional = []

@serializable
@union
class RequestUnion:

    @variant
    class Login:
        user: str
        ttl: int

    @variant
    class Logout:
        pass

@serializable
@union
class TickPacketUnion:
    """含 ``list[int]`` 变体：覆盖 union 拷贝构造（首变体非 unit）。"""

    @variant
    class Body:
        seq: int
        values: list[int]

@serializable
@copyable
@dataclass
class BigRecord:
    n: long

class JsonScalarTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        self.assertEqual(Json.dumps(True), 'true')
        self.assertEqual(Json.dumps(False), 'false')
        self.assertEqual(Json.dumps(42), '42')
        self.assertEqual(Json.dumps(1.5), '1.5')
        self.assertEqual(Json.dumps('hi'), '"hi"')
        n: int = Json.loads('99')
        self.assertEqual(n, 99)
        x: float = Json.loads('1.5')
        self.assertEqual(x, 1.5)
        s: str = Json.loads('"a"')
        self.assertEqual(s, 'a')
        b: bool = Json.loads('true')
        self.assertTrue(b)

class JsonContainerTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        xs: list[int] = [1, 2, 3]
        self.assertEqual(Json.dumps(xs), '[1,2,3]')
        ys: list[int] = Json.loads('[1,2,3]')
        self.assertEqual(ys[1], 2)
        d: dict[str, int] = {'a': 1, 'b': 2}
        self.assertEqual(Json.dumps(d), '{"a":1,"b":2}')
        d2: dict[str, int] = Json.loads('{"a":1,"b":2}')
        self.assertEqual(d2['b'], 2)
        nestedDict: dict[str, dict[str, int]] = Json.loads[dict[str, dict[str, int]]]('{"outer":{"value":7}}')
        self.assertEqual(nestedDict['outer']['value'], 7)
        nestedList: list[list[int]] = Json.loads[list[list[int]]]('[[1,2],[3,4]]')
        self.assertEqual(nestedList[1][0], 3)
        items: list[str] = []
        items.append('x')
        items.append('y')
        self.assertEqual(Json.dumps(items), '["x","y"]')
        items2: list[str] = Json.loads(Json.dumps(items))
        self.assertEqual(items2[0], 'x')
        self.assertEqual(items2[1], 'y')
        many: list[str] = []
        for i in range(200):
            many.append('item')
        manyBack: list[str] = Json.loads(Json.dumps(many))
        self.assertEqual(len(manyBack), 200)
        fs: list[float] = []
        fs.append(1.5)
        fs.append(2.0)
        fs.append(-0.5)
        self.assertEqual(Json.dumps(fs), '[1.5,2,-0.5]')
        fs2: list[float] = Json.loads(Json.dumps(fs))
        self.assertEqual(fs2[0], 1.5)
        self.assertEqual(fs2[2], -0.5)
        labels: dict[str, str] = {}
        labels['a'] = 'x'
        labels['b'] = 'y'
        self.assertEqual(Json.dumps(labels), '{"a":"x","b":"y"}')
        labels2: dict[str, str] = Json.loads(Json.dumps(labels))
        self.assertEqual(labels2['a'], 'x')
        self.assertEqual(labels2['b'], 'y')
        scores: dict[str, float] = {}
        scores['pi'] = 3.14
        scores['neg'] = -1.0
        self.assertEqual(Json.dumps(scores), '{"pi":3.14,"neg":-1}')
        scores2: dict[str, float] = Json.loads(Json.dumps(scores))
        self.assertEqual(scores2['pi'], 3.14)
        self.assertEqual(scores2['neg'], -1.0)
        sio: StringIO = StringIO()
        Json.dump(fs, sio)
        self.assertEqual(sio.take(), '[1.5,2,-0.5]')

class JsonDataclassTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        u: User = new(id=1, name='ada', active=True, tags=['py', 'cpp'])
        exp: str = '{"id":1,"name":"ada","active":true,"tags":["py","cpp"]}'
        self.assertEqual(Json.dumps(u), exp)
        u2: User = Json.loads[User](exp)
        self.assertEqual(u2.id, 1)
        self.assertEqual(u2.name, 'ada')
        self.assertEqual(u2.tags[0], 'py')
        self.assertEqual(u2.tags[1], 'cpp')
        reordered: str = '{"name":"ada","id":1,"active":true,"tags":["py","cpp"]}'
        u3: User = Json.loads[User](reordered)
        self.assertEqual(u3.id, 1)
        self.assertEqual(u3.name, 'ada')

class JsonNestedTests(TestCaseMixin):
    _testTag = 25

    @override
    def test(self):
        u1: User = new(id=1, name='ada', tags=['py'])
        u2: User = new(id=2, name='bob', tags=['cpp'])
        team: Team = new(name='core', members=[u1, u2])
        js: str = Json.dumps(Org(title='acme', teams=[team]))
        self.assertTrue(js.find('"title":"acme"') >= 0)
        self.assertTrue(js.find('"name":"core"') >= 0)
        self.assertTrue(js.find('"name":"ada"') >= 0)
        org2: Org = Json.loads[Org](js)
        self.assertEqual(org2.title, 'acme')
        self.assertEqual(len(org2.teams), 1)
        self.assertEqual(org2.teams[0].name, 'core')
        self.assertEqual(len(org2.teams[0].members), 2)
        self.assertEqual(org2.teams[0].members[0].name, 'ada')
        self.assertEqual(org2.teams[0].members[1].tags[0], 'cpp')

class JsonUnionTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        js: str = Json.dumps(RequestUnion.Login(user='bob', ttl=3600))
        self.assertTrue(js.find('"tag":"Login"') >= 0)
        self.assertTrue(js.find('"user":"bob"') >= 0)
        req: RequestUnion = Json.loads[RequestUnion](js)
        enc: JsonEncoder = new()
        req.serialize(enc)
        jsBack: str = enc.finish()
        self.assertTrue(jsBack.find('"ttl":3600') >= 0)
        js2: str = Json.dumps(RequestUnion.Logout())
        self.assertEqual(js2, '{"tag":"Logout","payload":{}}')
        req2: RequestUnion = Json.loads[RequestUnion](js2)
        js3: str = Json.dumps(req2)
        self.assertEqual(js3, '{"tag":"Logout","payload":{}}')
        vals: list[int] = []
        vals.append(10)
        vals.append(20)
        jsPkt: str = Json.dumps(TickPacketUnion.Body(seq=1, values=vals))
        self.assertTrue(jsPkt.find('"values":[10,20]') >= 0)

class JsonIndentTests(TestCaseMixin):
    _testTag = 35

    @override
    def test(self):
        self.assertEqual(Json.dumps(42), '42')
        self.assertEqual(Json.dumps(42, 2), '42')
        u: User = new(id=1, name='ada', tags=['py'])
        compact: str = Json.dumps(u)
        self.assertTrue(compact.find('"id":1') >= 0)
        pretty: str = Json.dumps(u, 2)
        self.assertTrue(pretty.find('\n') >= 0)
        self.assertTrue(pretty.find('"id": 1') >= 0)
        self.assertTrue(pretty.find('"name": "ada"') >= 0)
        u2: User = Json.loads[User](pretty)
        self.assertEqual(u2.id, 1)
        self.assertEqual(u2.name, 'ada')
        js: str = Json.dumps(RequestUnion.Login(user='bob', ttl=9), 2)
        self.assertTrue(js.find('\n') >= 0)
        req: RequestUnion = Json.loads[RequestUnion](js)
        self.assertTrue(Json.dumps(req).find('"user":"bob"') >= 0)

class JsonFileTests(TestCaseMixin):
    _testTag = 40

    @override
    def test(self):
        ensureTestTemp()
        xs: list[int] = [1, 2, 3]
        w = open(str(Path(_TestTemp) / 'test_json_tmp.json'), 'w')
        Json.dump(xs, w)
        w.close()
        r = open(str(Path(_TestTemp) / 'test_json_tmp.json'), 'r')
        ys: list[int] = Json.load(r)
        r.close()
        self.assertEqual(ys[1], 2)
        u: User = new(id=3, name='eve', tags=['json'])
        w2 = open(str(Path(_TestTemp) / 'test_json_tmp.json'), 'w')
        Json.dump(u, w2, 2)
        w2.close()
        r2 = open(str(Path(_TestTemp) / 'test_json_tmp.json'), 'r')
        u2: User = Json.load(r2)
        r2.close()
        self.assertEqual(u2.id, 3)
        self.assertEqual(u2.name, 'eve')
        self.assertEqual(len(u2.tags), 1)
        jsU: str = Json.dumps(u2, 2)
        self.assertTrue(jsU.find('\n') >= 0)
        login: RequestUnion = new.Login(user='ann', ttl=60)
        w3 = open(str(Path(_TestTemp) / 'test_json_tmp.json'), 'w')
        Json.dump(login, w3, 4)
        w3.close()
        r3 = open(str(Path(_TestTemp) / 'test_json_tmp.json'), 'r')
        req: RequestUnion = Json.load(r3)
        r3.close()
        js: str = Json.dumps(req)
        self.assertTrue(js.find('"user":"ann"') >= 0)
        self.assertTrue(js.find('"ttl":60') >= 0)

class JsonMemoryAppendIntTests(TestCaseMixin):
    _testTag = 110

    @override
    def test(self):
        cases: list[int] = [0, 1, -1, 42, -12345, 2147483647]
        for v in cases:
            buf: char[:] = new(64)
            at: int = JsonEncoder.appendIntAt(buf, 0, v)
            got: str = str.fromArray(buf, at)
            self.assertEqual(got, str(v))

class JsonMemoryAppendQuotedTests(TestCaseMixin):
    _testTag = 120

    @override
    def test(self):
        samples: list[str] = ['', 'hi', 'a"b', 'back\\slash', 'a\nb', 'a\rb', 'a\tb']
        expects: list[str] = ['""', '"hi"', '"a\\"b"', '"back\\\\slash"', '"a\\nb"', '"a\\rb"', '"a\\tb"']
        for i in range(len(samples)):
            buf: char[:] = new(128)
            at: int = JsonEncoder.appendQuotedAt(buf, 0, samples[i])
            self.assertEqual(str.fromArray(buf, at), expects[i])

class JsonMemoryAppendRangeTests(TestCaseMixin):
    _testTag = 130

    @override
    def test(self):
        src: str = 'abcdef'
        buf: char[:] = new(32)
        at: int = src.copySliceTo(buf, 0, 1, 4)
        self.assertEqual(str.fromArray(buf, at), 'bcd')

class JsonMemoryAppendListTests(TestCaseMixin):
    _testTag = 140

    @override
    def test(self):
        ints: list[int] = [1, -2, 0, 42]
        strs: list[str] = ['a', 'b"c', '']
        floats: list[float] = [1.5, 2.0, 3.25]
        buf: char[:] = new(256)
        at: int = JsonEncoder.appendListAt(buf, 0, ints)
        self.assertEqual(str.fromArray(buf, at), '[1,-2,0,42]')
        buf = new(256)
        at = JsonEncoder.appendListAt(buf, 0, strs)
        self.assertEqual(str.fromArray(buf, at), '["a","b\\"c",""]')
        buf = new(256)
        at = JsonEncoder.appendListAt(buf, 0, floats)
        self.assertEqual(str.fromArray(buf, at), '[1.5,2,3.25]')

class JsonMemoryAppendListLongTests(TestCaseMixin):
    _testTag = 145

    @override
    def test(self):
        vars: list[long] = [long('1'), long('-99')]
        buf: char[:] = new(128)
        at: int = JsonEncoder.appendListLongAt(buf, 0, vars)
        self.assertEqual(str.fromArray(buf, at), '[1,-99]')

class JsonMemoryFastEncodeTests(TestCaseMixin):
    _testTag = 150

    @override
    def test(self):
        ints: list[int] = [1, -2, 0]
        strs: list[str] = ['x', 'y"z']
        floats: list[float] = [1.0, -2.5]
        vars: list[long] = [long('99'), long('-1')]
        dInt: dict[str, int] = {'a': 1, 'b': -2}
        dStr: dict[str, str] = {'k': 'v', 'q': 'a"b'}
        dVar: dict[str, long] = {'n': long('42')}
        dFloat: dict[str, float] = {'f': 1.5}
        self.assertEqual(JsonEncoder.fastEncode(ints), '[1,-2,0]')
        self.assertEqual(JsonEncoder.fastEncode(strs), '["x","y\\"z"]')
        self.assertEqual(JsonEncoder.fastEncode(floats), '[1,-2.5]')
        self.assertEqual(JsonEncoder.fastEncode(vars), '[99,-1]')
        self.assertEqual(JsonEncoder.fastEncode(dInt), '{"a":1,"b":-2}')
        self.assertEqual(JsonEncoder.fastEncode(dStr), '{"k":"v","q":"a\\"b"}')
        self.assertEqual(JsonEncoder.fastEncode(dVar), '{"n":42}')
        self.assertEqual(JsonEncoder.fastEncode(dFloat), '{"f":1.5}')

class JsonScanParseIntLeafTests(TestCaseMixin):
    _testTag = 200

    @override
    def test(self):
        raw: str = '12345,'
        decF: JsonDecoder = new.fromText(raw)
        decR: JsonDecoder = new.fromText(raw)
        decF.tryBindAscii()
        decR.tryBindAscii()
        gotF: int = decF.parseIntAtAscii()
        gotR: int = decR.parseIntAtAsciiRef()
        self.assertEqual(gotF, 12345)
        self.assertEqual(gotR, 12345)
        self.assertEqual(decF.pos, decR.pos)

class JsonScanSkipWsLeafTests(TestCaseMixin):
    _testTag = 201

    @override
    def test(self):
        raw: str = '  \t42'
        decF: JsonDecoder = new.fromText(raw)
        decR: JsonDecoder = new.fromText(raw)
        decF.tryBindAscii()
        decR.tryBindAscii()
        decF.skipWsBound()
        decR.skipWsBoundRef()
        self.assertEqual(decF.pos, decR.pos)
        self.assertEqual(decF.parseIntAtAscii(), 42)

class JsonScanParseIntTests(TestCaseMixin):
    _testTag = 202

    @override
    def test(self):
        raw: str = '123,'
        decR: JsonDecoder = new.fromText(raw)
        gotR: int = decR.parseIntAt()
        decN: JsonDecoder = new.fromText(raw)
        decN.tryBindAscii()
        gotN: int = decN.scanTestParseIntAtBound()
        self.assertEqual(gotR, 123)
        self.assertEqual(gotN, 123)
        self.assertEqual(decR.pos, decN.pos)

class JsonScanLoadStrSpanLeafTests(TestCaseMixin):
    _testTag = 203

    @override
    def test(self):
        raw: str = '"hello"'
        decF: JsonDecoder = new.fromText(raw)
        decR: JsonDecoder = new.fromText(raw)
        decF.tryBindAscii()
        decR.tryBindAscii()
        gotF: str = str.fromSpan(decF.loadStrSpanAscii())
        gotR: str = str.fromSpan(decR.loadStrSpanAsciiRef())
        self.assertEqual(gotF, 'hello')
        self.assertEqual(gotR, 'hello')
        self.assertEqual(decF.pos, decR.pos)

class JsonScanStrAssignLeafTests(TestCaseMixin):
    _testTag = 204

    @override
    def test(self):
        raw: str = '"hi"'
        decF: JsonDecoder = new.fromText(raw)
        decR: JsonDecoder = new.fromText(raw)
        decF.tryBindAscii()
        decR.tryBindAscii()
        decF.pos = 1
        decR.pos = 1
        segF = decF.srcView()[1:3]
        segR = decR.srcView()[1:3]
        gotF: str = decF.strAssignFromSeg(segF)
        gotR: str = decR.strAssignFromSegRef(segR)
        self.assertEqual(gotF, 'hi')
        self.assertEqual(gotR, 'hi')

class JsonScanTrySkipValueTests(TestCaseMixin):
    _testTag = 205

    @override
    def test(self):
        raw: str = ' 123 , 456'
        decF: JsonDecoder = new.fromText(raw)
        decR: JsonDecoder = new.fromText(raw)
        decF.tryBindAscii()
        decR.tryBindAscii()
        ok: bool = decF.trySkipValueAscii()
        decR.skipValue()
        self.assertTrue(ok)
        self.assertEqual(decF.pos, decR.pos)
        self.assertEqual(decF.pos, 4)

class JsonScanTrySkipFieldTests(TestCaseMixin):
    _testTag = 206

    @override
    def test(self):
        raw: str = '{"a":1,"b":2}'
        decF: JsonDecoder = new.fromText(raw)
        decR: JsonDecoder = new.fromText(raw)
        decF.tryBindAscii()
        decR.tryBindAscii()
        decF.pos = 1
        decR.pos = 1
        ok: bool = decF.trySkipFieldAscii()
        decR.skipField()
        self.assertTrue(ok)
        self.assertEqual(decF.pos, decR.pos)

class JsonScanLoadStrSpanTests(TestCaseMixin):
    _testTag = 207

    @override
    def test(self):
        raw: str = '"hello"'
        decR: JsonDecoder = new.fromText(raw)
        gotR: str = str.fromSpan(decR.loadStrSpan())
        decN: JsonDecoder = new.fromText(raw)
        decN.tryBindAscii()
        gotN: str = str.fromSpan(decN.loadStrSpan())
        self.assertEqual(gotR, 'hello')
        self.assertEqual(gotN, 'hello')
        self.assertEqual(decR.pos, decN.pos)

class JsonScanListIntLoopTests(TestCaseMixin):
    _testTag = 208

    @override
    def test(self):
        raw: str = '[1,2,3]'
        decR: JsonDecoder = new.fromText(raw)
        decR.pos = 1
        outR: list[int] = []
        decR.scanTestLoadListIntAsciiLoopRef(outR)
        decN: JsonDecoder = new.fromText(raw)
        decN.tryBindAscii()
        decN.pos = 1
        outN: list[int] = []
        decN.scanTestLoadListIntAsciiLoop(outN)
        self.assertEqual(len(outR), 3)
        self.assertEqual(outR[0], 1)
        self.assertEqual(outR[2], 3)
        self.assertEqual(len(outN), 3)
        self.assertEqual(outN[1], 2)
        self.assertEqual(decR.pos, decN.pos)

class JsonScanListStrLoopTests(TestCaseMixin):
    _testTag = 209

    @override
    def test(self):
        raw: str = '["a","b"]'
        decR: JsonDecoder = new.fromText(raw)
        decR.pos = 1
        outR: list[str] = []
        decR.scanTestLoadListStrAsciiLoopRef(outR)
        decN: JsonDecoder = new.fromText(raw)
        decN.tryBindAscii()
        decN.pos = 1
        outN: list[str] = []
        decN.scanTestLoadListStrAsciiLoop(outN)
        self.assertEqual(len(outR), 2)
        self.assertEqual(outR[0], 'a')
        self.assertEqual(outN[1], 'b')
        self.assertEqual(decR.pos, decN.pos)

class JsonScanDictStrIntLoopTests(TestCaseMixin):
    _testTag = 210

    @override
    def test(self):
        raw: str = '{"k0":0,"k1":1,"k2":2}'
        decR: JsonDecoder = new.fromText(raw)
        decR.pos = 1
        outR: dict[str, int] = {}
        decR.scanTestLoadDictStrIntAsciiLoopRef(outR)
        decN: JsonDecoder = new.fromText(raw)
        decN.tryBindAscii()
        decN.pos = 1
        outN: dict[str, int] = {}
        decN.scanTestLoadDictStrIntAsciiLoop(outN)
        self.assertEqual(len(outR), 3)
        self.assertEqual(outR['k1'], 1)
        self.assertEqual(len(outN), 3)
        self.assertEqual(outN['k2'], 2)
        self.assertEqual(decR.pos, decN.pos)

class JsonScanDictStrStrLoopTests(TestCaseMixin):
    _testTag = 211

    @override
    def test(self):
        raw: str = '{"f0":"v","f1":"w"}'
        decR: JsonDecoder = new.fromText(raw)
        decR.pos = 1
        outR: dict[str, str] = {}
        decR.scanTestLoadDictStrStrAsciiLoopRef(outR)
        decN: JsonDecoder = new.fromText(raw)
        decN.tryBindAscii()
        decN.pos = 1
        outN: dict[str, str] = {}
        decN.scanTestLoadDictStrStrAsciiLoop(outN)
        self.assertEqual(len(outR), 2)
        self.assertEqual(outR['f0'], 'v')
        self.assertEqual(len(outN), 2)
        self.assertEqual(outN['f1'], 'w')
        self.assertEqual(decR.pos, decN.pos)

class JsonScanTryMatchKeyTests(TestCaseMixin):
    _testTag = 212

    @override
    def test(self):
        raw: str = '{"id":1,"name":"a"}'
        decR: JsonDecoder = new.fromText(raw)
        decR.pos = 1
        okR: bool = decR.tryMatchKey('id')
        decN: JsonDecoder = new.fromText(raw)
        decN.tryBindAscii()
        decN.pos = 1
        okN: bool = decN.tryMatchKey('id')
        self.assertTrue(okR)
        self.assertTrue(okN)
        self.assertEqual(decR.pos, decN.pos)

class JsonNestedNavigationTests(TestCaseMixin):
    _testTag = 214

    @override
    def test(self):
        raw: str = '{"id":"cmpl-1","choices":[{"index":0,"message":{"role":"assistant","content":"pong"}}]}'
        dec: JsonDecoder = new.fromText(raw)
        dec.beginRootObject()
        key: str = dec.loadKey()
        self.assertEqual(key, 'id')
        dec.skipValue()
        key = dec.loadKey()
        self.assertEqual(key, 'choices')
        dec.beginArray()
        self.assertFalse(dec.atArrayEnd())
        dec.beginRootObject()
        key = dec.loadKey()
        self.assertEqual(key, 'index')
        dec.skipValue()
        key = dec.loadKey()
        self.assertEqual(key, 'message')
        dec.beginRootObject()
        key = dec.loadKey()
        self.assertEqual(key, 'role')
        dec.skipValue()
        key = dec.loadKey()
        self.assertEqual(key, 'content')
        self.assertEqual(dec.loadStr(), 'pong')

class JsonScanTryBindTests(TestCaseMixin):
    _testTag = 213

    @override
    def test(self):
        asciiText: str = '[1,2]'
        dec: JsonDecoder = new.fromText(asciiText)
        dec.tryBindAscii()
        self.assertTrue(dec.asciiOk)
        nonAscii: str = '"中"'
        decU: JsonDecoder = new.fromText(nonAscii)
        decU.tryBindAscii()
        self.assertFalse(decU.asciiOk)

class JsonEncoderSmokeTests(TestCaseMixin):
    _testTag = 300

    @override
    def test(self):
        enc: JsonEncoder = new()
        enc.beginObject()
        enc.endObject()
        self.assertEqual(enc.finish(), '{}')
        enc2: JsonEncoder = new()
        enc2.beginObject()
        enc2.dumpKey('id')
        enc2.dumpInt(1)
        enc2.endObject()
        self.assertEqual(enc2.finish(), '{"id":1}')

class JsonLongScalarTests(TestCaseMixin):
    _testTag = 310

    @override
    def test(self):
        small: long = 42
        self.assertEqual(Json.dumps(small), '42')
        back: long = Json.loads[long]('42')
        self.assertEqual(str(back), '42')
        over: long = 9223372036854775808
        self.assertEqual(Json.dumps(over), '9223372036854775808')
        over2: long = Json.loads[long]('9223372036854775808')
        self.assertTrue(over2 == over)
        neg: long = -10000000000000000000
        self.assertEqual(Json.dumps(neg), '-10000000000000000000')
        neg2: long = Json.loads[long]('-10000000000000000000')
        self.assertTrue(neg2 == neg)

class JsonLongContainerTests(TestCaseMixin):
    _testTag = 320

    @override
    def test(self):
        one: long = 1
        over: long = 9223372036854775808
        seven: long = -7
        xs: list[long] = []
        xs.append(one)
        xs.append(over)
        xs.append(seven)
        self.assertEqual(Json.dumps(xs), '[1,9223372036854775808,-7]')
        ys: list[long] = Json.loads[list[long]](Json.dumps(xs))
        self.assertEqual(str(ys[0]), '1')
        self.assertEqual(str(ys[1]), '9223372036854775808')
        self.assertEqual(str(ys[2]), '-7')
        ten: long = 10
        dec20: long = 10000000000000000000
        d: dict[str, long] = {}
        d['a'] = ten
        d['big'] = dec20
        self.assertEqual(Json.dumps(d), '{"a":10,"big":10000000000000000000}')
        d2: dict[str, long] = Json.loads[dict[str, long]](Json.dumps(d))
        self.assertEqual(str(d2['a']), '10')
        self.assertEqual(str(d2['big']), '10000000000000000000')

class JsonLongDataclassTests(TestCaseMixin):
    _testTag = 330

    @override
    def test(self):
        over: long = 9223372036854775808
        rec: BigRecord = new(n=over)
        exp: str = '{"n":9223372036854775808}'
        self.assertEqual(Json.dumps(rec), exp)
        rec2: BigRecord = Json.loads[BigRecord](exp)
        self.assertEqual(str(rec2.n), '9223372036854775808')

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
