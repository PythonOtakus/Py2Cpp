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
    self.assertIn("PyUInt64 _db", header)
    self.assertIn("PySqliteCursor(const PySqliteCursor& other) = delete", header)
    self.assertIn("PyUInt64 _stmt", header)
    self.assertNotIn("sqlite_connection_tail", header)
    self.assertNotIn("sqlite_cursor_tail", header)
    self.assertNotIn("__moved__", header)


if __name__ == "__main__":
  unittest.main()
