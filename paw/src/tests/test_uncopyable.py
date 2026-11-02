"""``@uncopyable``：类头 ``= delete`` 复制特殊成员 + 移动声明。"""
import unittest
from pathlib import Path


class TestUncopyable(unittest.TestCase):
  def test_sqlite_connection_cursor_header(self):
    root = Path(__file__).resolve().parents[2]
    header = (root / "generated" / "runtime" / "py2cpp" / "sql" / "sqlite.h").read_text(
      encoding="utf-8",
    )
    self.assertIn("PySqliteConnection(const PySqliteConnection& other) = delete", header)
    self.assertIn(
      "PySqliteConnection& operator=(const PySqliteConnection& other) = delete",
      header,
    )
    self.assertIn("PySqliteConnection(PySqliteConnection&& other)", header)
    self.assertIn("PyiSqlite3* _db", header)
    self.assertIn("PySqliteCursor(const PySqliteCursor& other) = delete", header)
    self.assertIn("PyiSqlite3Stmt* _stmt", header)
    self.assertNotIn("sqlite_connection_tail", header)
    self.assertNotIn("sqlite_cursor_tail", header)
    self.assertNotIn("__moved__", header)

  def test_scandir_iterator_move_assign_defined(self):
    root = Path(__file__).resolve().parents[2]
    header = (root / "generated" / "runtime" / "py2cpp" / "io" / "file.h").read_text(
      encoding="utf-8",
    )
    self.assertIn("PyScandirIterator(const PyScandirIterator& other) = delete", header)
    self.assertIn("PyScandirIterator& operator=(PyScandirIterator&& other)", header)
    inl = (root / "generated" / "runtime" / "py2cpp" / "io" / "file.inl").read_text(
      encoding="utf-8",
    )
    compact = inl.replace(" ", "")
    self.assertIn("PyScandirIterator::operator=(PyScandirIterator&&", compact)
    self.assertIn("::__move__(", compact)


if __name__ == "__main__":
  unittest.main()
