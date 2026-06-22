"""``py2cpp.sql.sqlite`` DB-API 子集（``:memory:``、``?`` 绑定）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.sql.sqlite import connect, SqliteConnection, SqliteCursor


class SqliteMemoryTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    conn: SqliteConnection = connect(":memory:")
    no_params: list[int] = []
    insert_rows: list[list[int]] = [[1], [2]]
    conn.execute("CREATE TABLE t(x INTEGER)", no_params)
    conn.executemany("INSERT INTO t VALUES(?)", insert_rows)
    conn.commit()
    cur: SqliteCursor = conn.execute("SELECT x FROM t ORDER BY x", no_params)
    rows: list[tuple[int]] = cur.fetchall()
    self.assertEqual(len(rows), 2)
    self.assertEqual(rows[0][0], 1)
    self.assertEqual(rows[1][0], 2)
    conn.close()


class SqliteRollbackTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    conn: SqliteConnection = connect(":memory:")
    no_params: list[int] = []
    one_row: list[int] = [1]
    conn.execute("CREATE TABLE t(x INTEGER)", no_params)
    conn.execute("BEGIN", no_params)
    conn.execute("INSERT INTO t VALUES(?)", one_row)
    conn.rollback()
    cur: SqliteCursor = conn.execute("SELECT count(*) FROM t", no_params)
    row: tuple[int] | None = cur.fetchone()
    self.assertFalse(row is None)
    if row is not None:
      self.assertEqual(row.value[0], 0)
    conn.close()


def main() -> int:
  suite: TestSuite = new()
  for Case in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Case())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
