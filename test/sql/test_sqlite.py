"""``py2cpp.sql.sqlite`` DB-API 子集（``:memory:``、``?`` 绑定）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.sql.sqlite import connect, SqliteConnection, SqliteCursor


class SqliteMemoryTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    conn: SqliteConnection = connect(":memory:")
    noParams: list[int] = []
    insertRows: list[list[int]] = [[1], [2]]
    conn.execute("CREATE TABLE t(x INTEGER)", noParams)
    conn.executeMany("INSERT INTO t VALUES(?)", insertRows)
    conn.commit()
    cur: SqliteCursor = conn.execute("SELECT x FROM t ORDER BY x", noParams)
    rows: list[tuple[int]] = cur.fetchAll()
    self.assertEqual(len(rows), 2)
    self.assertEqual(rows[0][0], 1)
    self.assertEqual(rows[1][0], 2)
    conn.close()


class SqliteRollbackTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    conn: SqliteConnection = connect(":memory:")
    noParams: list[int] = []
    oneRow: list[int] = [1]
    conn.execute("CREATE TABLE t(x INTEGER)", noParams)
    conn.execute("BEGIN", noParams)
    conn.execute("INSERT INTO t VALUES(?)", oneRow)
    conn.rollback()
    cur: SqliteCursor = conn.execute("SELECT count(*) FROM t", noParams)
    row: tuple[int] | None = cur.fetchOne()
    self.assertFalse(row is None)
    if row is not None:
      self.assertEqual(row.value[0], 0)
    conn.close()


def main() -> int:
  suite: TestSuite = new()
  for Case in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Case())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
