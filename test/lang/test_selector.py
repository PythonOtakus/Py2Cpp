"""``select("…")`` 集成测；含后处理 ``@sort`` / ``@group`` / ``@count``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

@dataclass
class Member:
    score: int
    name: str

@dataclass
class Team:
    name: str
    min_score: int = 0
    members: list[Member] @ optional = []

@copyable
class Org:
    teams: list[Team] = []

def build_org() -> Org:
    m1: Member = new(10, 'amy')
    m2: Member = new(0, 'bob')
    t: Team = Team(name='alpha')
    t.min_score = 5
    t.members.append(m1)
    t.members.append(m2)
    o: Org = new()
    o.teams.append(t)
    return o

class SelectFieldChainTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        org: Org = build_org()
        names: list[str] = org.select('.teams[0].name')
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0], 'alpha')

class SelectFilterListTests(TestCaseMixin):
    _test_tag = 10

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        hits: list[Member] = t.select('.members{.score > 0}')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, 'amy')

class SelectListRootTests(TestCaseMixin):
    _test_tag = 20

    @override
    def test(self):
        org: Org = build_org()
        t2: Team = Team(name='beta')
        org.teams.append(t2)
        last: list[Team] = org.teams.select('[-1]')
        self.assertEqual(len(last), 1)
        self.assertEqual(last[0].name, 'beta')

class SelectSliceTests(TestCaseMixin):
    _test_tag = 30

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        t.members.append(Member(5, 'c'))
        part: list[Member] = t.select('.members[:2]')
        self.assertEqual(len(part), 2)
        self.assertEqual(part[0].name, 'amy')
        self.assertEqual(part[1].name, 'bob')

class SelectSliceOmitTests(TestCaseMixin):
    _test_tag = 32

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        t.members.append(Member(5, 'c'))
        tail: list[Member] = t.select('.members[2:]')
        self.assertEqual(len(tail), 1)
        self.assertEqual(tail[0].name, 'c')
        all_members: list[Member] = t.select('.members[:]')
        self.assertEqual(len(all_members), 3)
        self.assertEqual(all_members[0].name, 'amy')
        self.assertEqual(all_members[2].name, 'c')

class SelectSliceStepTests(TestCaseMixin):
    _test_tag = 35

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        t.members.append(Member(5, 'c'))
        t.members.append(Member(7, 'd'))
        t.members.append(Member(9, 'e'))
        stepped: list[Member] = t.select('.members[1:4:2]')
        self.assertEqual(len(stepped), 2)
        self.assertEqual(stepped[0].name, 'bob')
        self.assertEqual(stepped[1].name, 'd')
        strided: list[Member] = t.select('.members[::2]')
        self.assertEqual(len(strided), 3)
        self.assertEqual(strided[0].name, 'amy')
        self.assertEqual(strided[1].name, 'c')
        self.assertEqual(strided[2].name, 'e')

@dataclass
class Bag:
    data: dict[str, int]

def build_bag() -> Bag:
    data: dict[str, int] = {'a': 10, 'b': 20}
    return new(data)

class SelectStrIndexTests(TestCaseMixin):
    _test_tag = 37

    @override
    def test(self):
        bag: Bag = build_bag()
        one: list[int] = bag.select(".data['a']")
        self.assertEqual(len(one), 1)
        self.assertEqual(one[0], 10)
        both: list[int] = bag.select(".data['a', 'b']")
        self.assertEqual(len(both), 2)
        self.assertEqual(both[0], 10)
        self.assertEqual(both[1], 20)
        miss: list[int] = bag.select(".data?['z']")
        self.assertEqual(len(miss), 0)

class SelectOptionalChainTests(TestCaseMixin):
    _test_tag = 38

    @override
    def test(self):
        o: Org = new()
        empty: list[str] = o.select('.teams?[0].name')
        self.assertEqual(len(empty), 0)
        org: Org = build_org()
        names: list[str] = org.select('.teams?[0].name')
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0], 'alpha')

class SelectProjectionTests(TestCaseMixin):
    _test_tag = 40

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        tags: list[str] = t.select('.members[0].(name, name)')
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0], 'amy')
        self.assertEqual(tags[1], 'amy')

class SelectMultiBracketTests(TestCaseMixin):
    _test_tag = 50

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        t.members.append(Member(5, 'c'))
        picked: list[Member] = t.select('.members[0, 1:3]')
        self.assertEqual(len(picked), 3)
        self.assertEqual(picked[0].name, 'amy')
        self.assertEqual(picked[1].name, 'bob')
        self.assertEqual(picked[2].name, 'c')

class SelectWildcardSliceTests(TestCaseMixin):
    _test_tag = 60

    @override
    def test(self):
        org: Org = build_org()
        t2: Team = Team(name='beta')
        org.teams.append(t2)
        names: list[str] = org.select('.teams[:].name')
        self.assertEqual(len(names), 2)
        self.assertEqual(names[0], 'alpha')
        self.assertEqual(names[1], 'beta')

class SelectDescendantTests(TestCaseMixin):
    _test_tag = 70

    @override
    def test(self):
        org: Org = build_org()
        t2: Team = Team(name='beta')
        org.teams.append(t2)
        names: list[str] = org.select('.teams..name')
        self.assertEqual(len(names), 4)
        self.assertEqual(names[0], 'alpha')
        self.assertEqual(names[1], 'beta')
        self.assertEqual(names[2], 'amy')
        self.assertEqual(names[3], 'bob')

class SelectBareFilterTests(TestCaseMixin):
    _test_tag = 80

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        hits: list[Member] = t.select('.members{.score}')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, 'amy')

class SelectFilterLocalBindingTests(TestCaseMixin):
    _test_tag = 85

    @override
    def test(self):
        org: Org = build_org()
        t: Team = org.teams[0]
        threshold: int = 5
        hits: list[Member] = t.select('.members{.score > threshold}')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, 'amy')

class SelectMultiPathTests(TestCaseMixin):
    _test_tag = 90

    @override
    def test(self):
        org: Org = build_org()
        t2: Team = Team(name='beta')
        org.teams.append(t2)
        via_bracket: list[str] = org.select('.teams[0, 1].name')
        self.assertEqual(len(via_bracket), 2)
        self.assertEqual(via_bracket[0], 'alpha')
        self.assertEqual(via_bracket[1], 'beta')
        via_proj: list[str] = org.select('.(teams[0], teams[1]).name')
        self.assertEqual(via_proj, via_bracket)

class SelectBindRefTests(TestCaseMixin):
    _test_tag = 95

    @override
    def test(self):
        org: Org = build_org()
        via_semi: list[str] = org.select('.teams[0]:$t; $t.name')
        self.assertEqual(len(via_semi), 1)
        self.assertEqual(via_semi[0], 'alpha')
        via_inline: list[str] = org.select('.teams[0]:$t.members[1].name')
        self.assertEqual(len(via_inline), 1)
        self.assertEqual(via_inline[0], 'bob')
        sibling: list[str] = org.select('.teams[0]:$t; $t.(members[0].name, members[1].name)')
        self.assertEqual(len(sibling), 2)
        self.assertEqual(sibling[0], 'amy')
        self.assertEqual(sibling[1], 'bob')

class SelectFilterBindRefTests(TestCaseMixin):
    _test_tag = 96

    @override
    def test(self):
        org: Org = build_org()
        names: list[str] = org.select('.teams[0]:$t.members{.score > $t.min_score}.name')
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0], 'amy')

class SelectSemicolonRootPathTests(TestCaseMixin):
    _test_tag = 97

    @override
    def test(self):
        org: Org = build_org()
        t2: Team = Team(name='beta')
        org.teams.append(t2)
        bound: list[str] = org.select('.teams[0]:$t; .teams[1].name')
        self.assertEqual(len(bound), 1)
        self.assertEqual(bound[0], 'beta')

def main() -> int:
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
if __name__ == '__main__':
    raise SystemExit(main())
