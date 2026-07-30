"""``@serializable`` + ``json.dumps`` / ``json.loads``；``JsonDecoder``/``JsonEncoder`` 叶子与快路径。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io import open
from py2cpp.io import StringIO
from py2cpp.io.file.path import join
from py2cpp.serde.json import Json, JsonDecoder, JsonEncoder
from py2cpp.test.test_temp import _TEST_TEMP, ensure_test_temp

_JSON_TMP: str = join(_TEST_TEMP, "test_json_tmp.json")
@serializable
@copyable
@dataclass
class User:
  id: int
  name: str
  active: bool = True
  tags: list[str] @optional = []


@serializable
@copyable
@dataclass
class Team:
  name: str
  members: list[User] @optional = []


@serializable
@copyable
@dataclass
class Org:
  title: str
  teams: list[Team] @optional = []


@serializable
@union
class Request:
  @variant
  class Login:
    user: str
    ttl: int

  @variant
  class Logout:
    pass


@serializable
@union
class TickPacket:
  """含 ``list[int]`` 变体：覆盖 union 拷贝构造（首变体非 unit）。"""

  @variant
  class Body:
    seq: int
    values: list[int]


@serializable
@copyable
@dataclass
class BigRecord:
  n: varint


class JsonScalarTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Json.dumps(True), "true")
    self.assertEqual(Json.dumps(False), "false")
    self.assertEqual(Json.dumps(42), "42")
    self.assertEqual(Json.dumps(1.5), "1.5")
    self.assertEqual(Json.dumps("hi"), '"hi"')
    n: int = Json.loads("99")
    self.assertEqual(n, 99)
    x: float = Json.loads("1.5")
    self.assertEqual(x, 1.5)
    s: str = Json.loads('"a"')
    self.assertEqual(s, "a")
    b: bool = Json.loads("true")
    self.assertTrue(b)


class JsonContainerTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    xs: list[int] = [1, 2, 3]
    self.assertEqual(Json.dumps(xs), "[1,2,3]")
    ys: list[int] = Json.loads("[1,2,3]")
    self.assertEqual(ys[1], 2)
    d: dict[str, int] = {"a": 1, "b": 2}
    self.assertEqual(Json.dumps(d), '{"a":1,"b":2}')
    d2: dict[str, int] = Json.loads('{"a":1,"b":2}')
    self.assertEqual(d2["b"], 2)
    items: list[str] = []
    items.append("x")
    items.append("y")
    self.assertEqual(Json.dumps(items), '["x","y"]')
    items2: list[str] = Json.loads(Json.dumps(items))
    self.assertEqual(items2[0], "x")
    self.assertEqual(items2[1], "y")
    many: list[str] = []
    for i in range(200):
      many.append("item")
    many_back: list[str] = Json.loads(Json.dumps(many))
    self.assertEqual(len(many_back), 200)
    fs: list[float] = []
    fs.append(1.5)
    fs.append(2.0)
    fs.append(-0.5)
    self.assertEqual(Json.dumps(fs), "[1.5,2,-0.5]")
    fs2: list[float] = Json.loads(Json.dumps(fs))
    self.assertEqual(fs2[0], 1.5)
    self.assertEqual(fs2[2], -0.5)
    labels: dict[str, str] = {}
    labels["a"] = "x"
    labels["b"] = "y"
    self.assertEqual(Json.dumps(labels), '{"a":"x","b":"y"}')
    labels2: dict[str, str] = Json.loads(Json.dumps(labels))
    self.assertEqual(labels2["a"], "x")
    self.assertEqual(labels2["b"], "y")
    scores: dict[str, float] = {}
    scores["pi"] = 3.14
    scores["neg"] = -1.0
    self.assertEqual(Json.dumps(scores), '{"pi":3.14,"neg":-1}')
    scores2: dict[str, float] = Json.loads(Json.dumps(scores))
    self.assertEqual(scores2["pi"], 3.14)
    self.assertEqual(scores2["neg"], -1.0)
    sio: StringIO = StringIO()
    Json.dump(fs, sio)
    self.assertEqual(sio.take(), "[1.5,2,-0.5]")


class JsonDataclassTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    u: User = new(id=1, name="ada", active=True, tags=["py", "cpp"])
    exp: str = '{"id":1,"name":"ada","active":true,"tags":["py","cpp"]}'
    self.assertEqual(Json.dumps(u), exp)
    u2: User = Json.loads[User](exp)
    self.assertEqual(u2.id, 1)
    self.assertEqual(u2.name, "ada")
    self.assertEqual(u2.tags[0], "py")
    self.assertEqual(u2.tags[1], "cpp")
    reordered: str = '{"name":"ada","id":1,"active":true,"tags":["py","cpp"]}'
    u3: User = Json.loads[User](reordered)
    self.assertEqual(u3.id, 1)
    self.assertEqual(u3.name, "ada")


class JsonNestedTests(TestCaseMixin):
  _test_tag = 25

  @override
  def test(self):
    u1: User = new(id=1, name="ada", tags=["py"])
    u2: User = new(id=2, name="bob", tags=["cpp"])
    team: Team = new(name="core", members=[u1, u2])
    org: Org = new(title="acme", teams=[team])
    js: str = Json.dumps(org)
    self.assertTrue(js.find('"title":"acme"') >= 0)
    self.assertTrue(js.find('"name":"core"') >= 0)
    self.assertTrue(js.find('"name":"ada"') >= 0)
    org2: Org = Json.loads[Org](js)
    self.assertEqual(org2.title, "acme")
    self.assertEqual(len(org2.teams), 1)
    self.assertEqual(org2.teams[0].name, "core")
    self.assertEqual(len(org2.teams[0].members), 2)
    self.assertEqual(org2.teams[0].members[0].name, "ada")
    self.assertEqual(org2.teams[0].members[1].tags[0], "cpp")


class JsonUnionTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    login: Request = new.Login(user="bob", ttl=3600)
    js: str = Json.dumps(login)
    self.assertTrue(js.find('"tag":"Login"') >= 0)
    self.assertTrue(js.find('"user":"bob"') >= 0)
    req: Request = Json.loads[Request](js)
    enc: JsonEncoder = new()
    req.serialize(enc)
    js_back: str = enc.finish()
    self.assertTrue(js_back.find('"ttl":3600') >= 0)
    out: Request = new.Logout()
    js2: str = Json.dumps(out)
    self.assertEqual(js2, '{"tag":"Logout","payload":{}}')
    req2: Request = Json.loads[Request](js2)
    js3: str = Json.dumps(req2)
    self.assertEqual(js3, '{"tag":"Logout","payload":{}}')
    vals: list[int] = []
    vals.append(10)
    vals.append(20)
    pkt: TickPacket = new.Body(seq=1, values=vals)
    pkt2: TickPacket = pkt
    js_pkt: str = Json.dumps(pkt2)
    self.assertTrue(js_pkt.find('"values":[10,20]') >= 0)


class JsonIndentTests(TestCaseMixin):
  _test_tag = 35

  @override
  def test(self):
    self.assertEqual(Json.dumps(42), "42")
    self.assertEqual(Json.dumps(42, 2), "42")
    u: User = new(id=1, name="ada", tags=["py"])
    compact: str = Json.dumps(u)
    self.assertTrue(compact.find('"id":1') >= 0)
    pretty: str = Json.dumps(u, 2)
    self.assertTrue(pretty.find("\n") >= 0)
    self.assertTrue(pretty.find('"id": 1') >= 0)
    self.assertTrue(pretty.find('"name": "ada"') >= 0)
    u2: User = Json.loads[User](pretty)
    self.assertEqual(u2.id, 1)
    self.assertEqual(u2.name, "ada")
    login: Request = new.Login(user="bob", ttl=9)
    js: str = Json.dumps(login, 2)
    self.assertTrue(js.find("\n") >= 0)
    req: Request = Json.loads[Request](js)
    self.assertTrue(Json.dumps(req).find('"user":"bob"') >= 0)


class JsonFileTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    ensure_test_temp()
    xs: list[int] = [1, 2, 3]
    w = open(_JSON_TMP, "w")
    Json.dump(xs, w)
    w.close()
    r = open(_JSON_TMP, "r")
    ys: list[int] = Json.load(r)
    r.close()
    self.assertEqual(ys[1], 2)

    u: User = new(id=3, name="eve", tags=["json"])
    w2 = open(_JSON_TMP, "w")
    Json.dump(u, w2, 2)
    w2.close()
    r2 = open(_JSON_TMP, "r")
    u2: User = Json.load(r2)
    r2.close()
    self.assertEqual(u2.id, 3)
    self.assertEqual(u2.name, "eve")
    self.assertEqual(len(u2.tags), 1)
    js_u: str = Json.dumps(u2, 2)
    self.assertTrue(js_u.find("\n") >= 0)

    login: Request = new.Login(user="ann", ttl=60)
    w3 = open(_JSON_TMP, "w")
    Json.dump(login, w3, 4)
    w3.close()
    r3 = open(_JSON_TMP, "r")
    req: Request = Json.load(r3)
    r3.close()
    js: str = Json.dumps(req)
    self.assertTrue(js.find('"user":"ann"') >= 0)
    self.assertTrue(js.find('"ttl":60') >= 0)


class JsonMemoryAppendIntTests(TestCaseMixin):
  _test_tag = 110

  @override
  def test(self):
    cases: list[int] = [0, 1, -1, 42, -12345, 2147483647]
    for v in cases:
      buf: char[:] = new(64)
      at: int = JsonEncoder.append_int_at(buf, 0, v)
      got: str = str.from_buf(buf, at)
      self.assertEqual(got, str(v))


class JsonMemoryAppendQuotedTests(TestCaseMixin):
  _test_tag = 120

  @override
  def test(self):
    samples: list[str] = ['', 'hi', 'a"b', 'back\\slash', "a\nb", "a\rb", "a\tb"]
    expects: list[str] = ['""', '"hi"', '"a\\"b"', '"back\\\\slash"', '"a\\nb"', '"a\\rb"', '"a\\tb"']
    for i in range(len(samples)):
      buf: char[:] = new(128)
      at: int = JsonEncoder.append_quoted_at(buf, 0, samples[i])
      self.assertEqual(str.from_buf(buf, at), expects[i])


class JsonMemoryAppendRangeTests(TestCaseMixin):
  _test_tag = 130

  @override
  def test(self):
    src: str = "abcdef"
    buf: char[:] = new(32)
    at: int = src.copy_slice_to(1, 4, buf, 0)
    self.assertEqual(str.from_buf(buf, at), "bcd")


class JsonMemoryAppendListTests(TestCaseMixin):
  _test_tag = 140

  @override
  def test(self):
    ints: list[int] = [1, -2, 0, 42]
    strs: list[str] = ["a", 'b"c', ""]
    floats: list[float] = [1.5, 2.0, 3.25]
    buf: char[:] = new(256)
    at: int = JsonEncoder.append_list_at(buf, 0, ints)
    self.assertEqual(str.from_buf(buf, at), "[1,-2,0,42]")
    buf = new(256)
    at = JsonEncoder.append_list_at(buf, 0, strs)
    self.assertEqual(str.from_buf(buf, at), '["a","b\\"c",""]')
    buf = new(256)
    at = JsonEncoder.append_list_at(buf, 0, floats)
    self.assertEqual(str.from_buf(buf, at), "[1.5,2,3.25]")


class JsonMemoryAppendListVarintTests(TestCaseMixin):
  _test_tag = 145

  @override
  def test(self):
    vars: list[varint] = [varint("1"), varint("-99")]
    buf: char[:] = new(128)
    at: int = JsonEncoder.append_list_varint_at(buf, 0, vars)
    self.assertEqual(str.from_buf(buf, at), "[1,-99]")


class JsonMemoryFastEncodeTests(TestCaseMixin):
  _test_tag = 150

  @override
  def test(self):
    ints: list[int] = [1, -2, 0]
    strs: list[str] = ["x", 'y"z']
    floats: list[float] = [1.0, -2.5]
    vars: list[varint] = [varint("99"), varint("-1")]
    d_int: dict[str, int] = {"a": 1, "b": -2}
    d_str: dict[str, str] = {"k": "v", 'q': 'a"b'}
    d_var: dict[str, varint] = {"n": varint("42")}
    d_float: dict[str, float] = {"f": 1.5}
    self.assertEqual(JsonEncoder.fast_encode(ints), "[1,-2,0]")
    self.assertEqual(JsonEncoder.fast_encode(strs), '["x","y\\"z"]')
    self.assertEqual(JsonEncoder.fast_encode(floats), "[1,-2.5]")
    self.assertEqual(JsonEncoder.fast_encode(vars), "[99,-1]")
    self.assertEqual(JsonEncoder.fast_encode(d_int), '{"a":1,"b":-2}')
    self.assertEqual(JsonEncoder.fast_encode(d_str), '{"k":"v","q":"a\\"b"}')
    self.assertEqual(JsonEncoder.fast_encode(d_var), '{"n":42}')
    self.assertEqual(JsonEncoder.fast_encode(d_float), '{"f":1.5}')


class JsonScanParseIntLeafTests(TestCaseMixin):
  _test_tag = 200

  @override
  def test(self):
    raw: str = "12345,"
    dec_f: JsonDecoder = new.from_text(raw)
    dec_r: JsonDecoder = new.from_text(raw)
    dec_f.try_bind_ascii()
    dec_r.try_bind_ascii()
    got_f: int = dec_f.parse_int_at_ascii()
    got_r: int = dec_r.parse_int_at_ascii_ref()
    self.assertEqual(got_f, 12345)
    self.assertEqual(got_r, 12345)
    self.assertEqual(dec_f.pos, dec_r.pos)


class JsonScanSkipWsLeafTests(TestCaseMixin):
  _test_tag = 201

  @override
  def test(self):
    raw: str = "  \t42"
    dec_f: JsonDecoder = new.from_text(raw)
    dec_r: JsonDecoder = new.from_text(raw)
    dec_f.try_bind_ascii()
    dec_r.try_bind_ascii()
    dec_f.skip_ws_bound()
    dec_r.skip_ws_bound_ref()
    self.assertEqual(dec_f.pos, dec_r.pos)
    self.assertEqual(dec_f.parse_int_at_ascii(), 42)


class JsonScanParseIntTests(TestCaseMixin):
  _test_tag = 202

  @override
  def test(self):
    raw: str = "123,"
    dec_r: JsonDecoder = new.from_text(raw)
    got_r: int = dec_r.parse_int_at()
    dec_n: JsonDecoder = new.from_text(raw)
    dec_n.try_bind_ascii()
    got_n: int = dec_n.scan_test_parse_int_at_bound()
    self.assertEqual(got_r, 123)
    self.assertEqual(got_n, 123)
    self.assertEqual(dec_r.pos, dec_n.pos)


class JsonScanLoadStrSpanLeafTests(TestCaseMixin):
  _test_tag = 203

  @override
  def test(self):
    raw: str = '"hello"'
    dec_f: JsonDecoder = new.from_text(raw)
    dec_r: JsonDecoder = new.from_text(raw)
    dec_f.try_bind_ascii()
    dec_r.try_bind_ascii()
    got_f: str = str.from_span(dec_f.load_str_span_ascii())
    got_r: str = str.from_span(dec_r.load_str_span_ascii_ref())
    self.assertEqual(got_f, "hello")
    self.assertEqual(got_r, "hello")
    self.assertEqual(dec_f.pos, dec_r.pos)


class JsonScanStrAssignLeafTests(TestCaseMixin):
  _test_tag = 204

  @override
  def test(self):
    raw: str = '"hi"'
    dec_f: JsonDecoder = new.from_text(raw)
    dec_r: JsonDecoder = new.from_text(raw)
    dec_f.try_bind_ascii()
    dec_r.try_bind_ascii()
    dec_f.pos = 1
    dec_r.pos = 1
    seg_f = dec_f.src_view()[1:3]
    seg_r = dec_r.src_view()[1:3]
    got_f: str = dec_f.str_assign_from_seg(seg_f)
    got_r: str = dec_r.str_assign_from_seg_ref(seg_r)
    self.assertEqual(got_f, "hi")
    self.assertEqual(got_r, "hi")


class JsonScanTrySkipValueTests(TestCaseMixin):
  _test_tag = 205

  @override
  def test(self):
    raw: str = " 123 , 456"
    dec_f: JsonDecoder = new.from_text(raw)
    dec_r: JsonDecoder = new.from_text(raw)
    dec_f.try_bind_ascii()
    dec_r.try_bind_ascii()
    ok: bool = dec_f.try_skip_value_ascii()
    dec_r.skip_value()
    self.assertTrue(ok)
    self.assertEqual(dec_f.pos, dec_r.pos)
    self.assertEqual(dec_f.pos, 4)


class JsonScanTrySkipFieldTests(TestCaseMixin):
  _test_tag = 206

  @override
  def test(self):
    raw: str = '{"a":1,"b":2}'
    dec_f: JsonDecoder = new.from_text(raw)
    dec_r: JsonDecoder = new.from_text(raw)
    dec_f.try_bind_ascii()
    dec_r.try_bind_ascii()
    dec_f.pos = 1
    dec_r.pos = 1
    ok: bool = dec_f.try_skip_field_ascii()
    dec_r.skip_field()
    self.assertTrue(ok)
    self.assertEqual(dec_f.pos, dec_r.pos)


class JsonScanLoadStrSpanTests(TestCaseMixin):
  _test_tag = 207

  @override
  def test(self):
    raw: str = '"hello"'
    dec_r: JsonDecoder = new.from_text(raw)
    got_r: str = str.from_span(dec_r.load_str_span())
    dec_n: JsonDecoder = new.from_text(raw)
    dec_n.try_bind_ascii()
    got_n: str = str.from_span(dec_n.load_str_span())
    self.assertEqual(got_r, "hello")
    self.assertEqual(got_n, "hello")
    self.assertEqual(dec_r.pos, dec_n.pos)


class JsonScanListIntLoopTests(TestCaseMixin):
  _test_tag = 208

  @override
  def test(self):
    raw: str = "[1,2,3]"
    dec_r: JsonDecoder = new.from_text(raw)
    dec_r.pos = 1
    out_r: list[int] = []
    dec_r.scan_test_load_list_int_ascii_loop_ref(out_r)
    dec_n: JsonDecoder = new.from_text(raw)
    dec_n.try_bind_ascii()
    dec_n.pos = 1
    out_n: list[int] = []
    dec_n.scan_test_load_list_int_ascii_loop(out_n)
    self.assertEqual(len(out_r), 3)
    self.assertEqual(out_r[0], 1)
    self.assertEqual(out_r[2], 3)
    self.assertEqual(len(out_n), 3)
    self.assertEqual(out_n[1], 2)
    self.assertEqual(dec_r.pos, dec_n.pos)


class JsonScanListStrLoopTests(TestCaseMixin):
  _test_tag = 209

  @override
  def test(self):
    raw: str = '["a","b"]'
    dec_r: JsonDecoder = new.from_text(raw)
    dec_r.pos = 1
    out_r: list[str] = []
    dec_r.scan_test_load_list_str_ascii_loop_ref(out_r)
    dec_n: JsonDecoder = new.from_text(raw)
    dec_n.try_bind_ascii()
    dec_n.pos = 1
    out_n: list[str] = []
    dec_n.scan_test_load_list_str_ascii_loop(out_n)
    self.assertEqual(len(out_r), 2)
    self.assertEqual(out_r[0], "a")
    self.assertEqual(out_n[1], "b")
    self.assertEqual(dec_r.pos, dec_n.pos)


class JsonScanDictStrIntLoopTests(TestCaseMixin):
  _test_tag = 210

  @override
  def test(self):
    raw: str = '{"k0":0,"k1":1,"k2":2}'
    dec_r: JsonDecoder = new.from_text(raw)
    dec_r.pos = 1
    out_r: dict[str, int] = {}
    dec_r.scan_test_load_dict_str_int_ascii_loop_ref(out_r)
    dec_n: JsonDecoder = new.from_text(raw)
    dec_n.try_bind_ascii()
    dec_n.pos = 1
    out_n: dict[str, int] = {}
    dec_n.scan_test_load_dict_str_int_ascii_loop(out_n)
    self.assertEqual(len(out_r), 3)
    self.assertEqual(out_r["k1"], 1)
    self.assertEqual(len(out_n), 3)
    self.assertEqual(out_n["k2"], 2)
    self.assertEqual(dec_r.pos, dec_n.pos)


class JsonScanDictStrStrLoopTests(TestCaseMixin):
  _test_tag = 211

  @override
  def test(self):
    raw: str = '{"f0":"v","f1":"w"}'
    dec_r: JsonDecoder = new.from_text(raw)
    dec_r.pos = 1
    out_r: dict[str, str] = {}
    dec_r.scan_test_load_dict_str_str_ascii_loop_ref(out_r)
    dec_n: JsonDecoder = new.from_text(raw)
    dec_n.try_bind_ascii()
    dec_n.pos = 1
    out_n: dict[str, str] = {}
    dec_n.scan_test_load_dict_str_str_ascii_loop(out_n)
    self.assertEqual(len(out_r), 2)
    self.assertEqual(out_r["f0"], "v")
    self.assertEqual(len(out_n), 2)
    self.assertEqual(out_n["f1"], "w")
    self.assertEqual(dec_r.pos, dec_n.pos)


class JsonScanTryMatchKeyTests(TestCaseMixin):
  _test_tag = 212

  @override
  def test(self):
    raw: str = '{"id":1,"name":"a"}'
    dec_r: JsonDecoder = new.from_text(raw)
    dec_r.pos = 1
    ok_r: bool = dec_r.try_match_key("id")
    dec_n: JsonDecoder = new.from_text(raw)
    dec_n.try_bind_ascii()
    dec_n.pos = 1
    ok_n: bool = dec_n.try_match_key("id")
    self.assertTrue(ok_r)
    self.assertTrue(ok_n)
    self.assertEqual(dec_r.pos, dec_n.pos)


class JsonNestedNavigationTests(TestCaseMixin):
  _test_tag = 214

  @override
  def test(self):
    raw: str = '{"id":"cmpl-1","choices":[{"index":0,"message":{"role":"assistant","content":"pong"}}]}'
    dec: JsonDecoder = new.from_text(raw)
    dec.begin_root_object()
    key: str = dec.load_key()
    self.assertEqual(key, "id")
    dec.skip_value()
    key = dec.load_key()
    self.assertEqual(key, "choices")
    dec.begin_array()
    self.assertFalse(dec.at_array_end())
    dec.begin_root_object()
    key = dec.load_key()
    self.assertEqual(key, "index")
    dec.skip_value()
    key = dec.load_key()
    self.assertEqual(key, "message")
    dec.begin_root_object()
    key = dec.load_key()
    self.assertEqual(key, "role")
    dec.skip_value()
    key = dec.load_key()
    self.assertEqual(key, "content")
    self.assertEqual(dec.load_str(), "pong")


class JsonScanTryBindTests(TestCaseMixin):
  _test_tag = 213

  @override
  def test(self):
    ascii_text: str = "[1,2]"
    dec: JsonDecoder = new.from_text(ascii_text)
    dec.try_bind_ascii()
    self.assertTrue(dec.ascii_ok)
    non_ascii: str = '"\u4e2d"'
    dec_u: JsonDecoder = new.from_text(non_ascii)
    dec_u.try_bind_ascii()
    self.assertFalse(dec_u.ascii_ok)


class JsonEncoderSmokeTests(TestCaseMixin):
  _test_tag = 300

  @override
  def test(self):
    enc: JsonEncoder = new()
    enc.begin_object()
    enc.end_object()
    self.assertEqual(enc.finish(), "{}")
    enc2: JsonEncoder = new()
    enc2.begin_object()
    enc2.dump_key("id")
    enc2.dump_int(1)
    enc2.end_object()
    self.assertEqual(enc2.finish(), '{"id":1}')


class JsonVarintScalarTests(TestCaseMixin):
  _test_tag = 310

  @override
  def test(self):
    small: varint = 42
    self.assertEqual(Json.dumps(small), "42")
    back: varint = Json.loads[varint]("42")
    self.assertEqual(str(back), "42")
    over: varint = 9223372036854775808
    self.assertEqual(Json.dumps(over), "9223372036854775808")
    over2: varint = Json.loads[varint]("9223372036854775808")
    self.assertTrue(over2 == over)
    neg: varint = -10000000000000000000
    self.assertEqual(Json.dumps(neg), "-10000000000000000000")
    neg2: varint = Json.loads[varint]("-10000000000000000000")
    self.assertTrue(neg2 == neg)


class JsonVarintContainerTests(TestCaseMixin):
  _test_tag = 320

  @override
  def test(self):
    one: varint = 1
    over: varint = 9223372036854775808
    seven: varint = -7
    xs: list[varint] = []
    xs.append(one)
    xs.append(over)
    xs.append(seven)
    self.assertEqual(Json.dumps(xs), "[1,9223372036854775808,-7]")
    ys: list[varint] = Json.loads[list[varint]](Json.dumps(xs))
    self.assertEqual(str(ys[0]), "1")
    self.assertEqual(str(ys[1]), "9223372036854775808")
    self.assertEqual(str(ys[2]), "-7")
    ten: varint = 10
    dec20: varint = 10000000000000000000
    d: dict[str, varint] = {}
    d["a"] = ten
    d["big"] = dec20
    self.assertEqual(Json.dumps(d), '{"a":10,"big":10000000000000000000}')
    d2: dict[str, varint] = Json.loads[dict[str, varint]](Json.dumps(d))
    self.assertEqual(str(d2["a"]), "10")
    self.assertEqual(str(d2["big"]), "10000000000000000000")


class JsonVarintDataclassTests(TestCaseMixin):
  _test_tag = 330

  @override
  def test(self):
    over: varint = 9223372036854775808
    rec: BigRecord = new(n=over)
    exp: str = '{"n":9223372036854775808}'
    self.assertEqual(Json.dumps(rec), exp)
    rec2: BigRecord = Json.loads[BigRecord](exp)
    self.assertEqual(str(rec2.n), "9223372036854775808")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
