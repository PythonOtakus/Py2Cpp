"""``py2cpp.io.path.Path``（``pathlib`` 子集）回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.io.file import getcwd
from py2cpp.io.path import Path
from py2cpp.system.environ import environ
from py2cpp.io.file.path import join
from py2cpp.test.test_temp import _TEST_TEMP, ensure_test_temp
_TEST_DIR: str = 'test_path_dir'
_TEST_FILE: str = 'test_path_file.txt'
_TEST_GLOB: str = 'glob_a.txt'

class PathPureTests(TestCaseMixin):
    _test_tag = 1

    @override
    def test(self):
        root: Path = new('foo')
        child: Path = root / 'bar'
        self.assertEqual(str(child), 'foo\\bar')
        self.assertEqual(child.name, 'bar')
        self.assertEqual(str(child.parent), 'foo')
        deep: Path = root / 'a' / 'b'
        self.assertEqual(deep.name, 'b')
        self.assertEqual(str(deep.parent), 'foo\\a')
        setup: Path = new('my/library/setup.py')
        self.assertEqual(setup.stem, 'setup')
        self.assertEqual(setup.suffix, '.py')
        setup_suffixes: list[str] = ['.py']
        self.assertEqual(setup.suffixes, setup_suffixes)
        tar: Path = new('archive.tar.gz')
        tar_suffixes: list[str] = ['.tar', '.gz']
        self.assertEqual(tar.suffixes, tar_suffixes)
        dotted: Path = new('a.b.c')
        self.assertEqual(dotted.suffix, '.c')
        hidden: Path = new('.bashrc')
        self.assertEqual(hidden.suffix, '')
        parent_dot: Path = new('..')
        self.assertEqual(parent_dot.suffix, '')
        trailing: Path = new('file.')
        self.assertEqual(trailing.suffix, '')
        self.assertEqual(str(setup.with_name('run.py')), 'my\\library\\run.py')
        self.assertEqual(str(setup.with_suffix('.txt')), 'my\\library\\setup.txt')
        self.assertEqual(str(setup.with_stem('config')), 'my\\library\\config.py')
        self.assertEqual(str(setup.with_segments('c', 'd', 'e')), 'c\\d\\e')
        joined: Path = setup.joinpath('x')
        self.assertEqual(joined.name, 'x')
        self.assertFalse(root.is_absolute())
        win_abs: Path = new('C:\\Windows')
        self.assertTrue(win_abs.is_absolute())
        win: Path = new('foo\\bar')
        self.assertEqual(win.as_posix(), 'foo/bar')
        parts: list[str] = setup.parts
        self.assertEqual(parts[0], 'my')
        self.assertEqual(parts[1], 'library')
        self.assertEqual(parts[2], 'setup.py')
        par: Path = new('foo/bar/baz')
        plist: list[Path] = par.parents
        self.assertEqual(str(plist[0]), 'foo\\bar')
        self.assertEqual(str(plist[1]), 'foo')
        rel_src: Path = new('foo/bar')
        rel: Path = rel_src.relative_to('foo')
        self.assertEqual(str(rel), 'bar')
        rel_base: Path = new('foo/bar')
        self.assertTrue(rel_base.is_relative_to('foo'))
        rel_other: Path = new('foo/bar')
        self.assertFalse(rel_other.is_relative_to('baz'))
        match_txt: Path = new('readme.txt')
        self.assertTrue(match_txt.match('*.txt'))
        full_match_p: Path = new('C:\\a\\b.txt')
        self.assertTrue(full_match_p.full_match('*.txt'))
        ab_src: Path = new('foo')
        ab: Path = ab_src.absolute()
        self.assertTrue(ab.is_absolute())
        self.assertEqual(Path('foo'), Path('foo'))
        self.assertNotEqual(Path('foo'), Path('bar'))
        self.assertEqual(hash(Path('x')), hash(Path('x')))

class PathClassMethodTests(TestCaseMixin):
    _test_tag = 5

    @override
    def test(self):
        cwd_p: Path = new.cwd()
        self.assertTrue(cwd_p.is_absolute())
        home: Path = new.home()
        self.assertTrue(home.is_absolute())
        if 'USERPROFILE' in environ:
            self.assertTrue(str(home).startswith(environ['USERPROFILE'][:3]))
        uri: Path = new.from_uri('file:///C:/temp/x')
        self.assertTrue(uri.is_absolute())
        uri_src: Path = new('C:\\temp\\y')
        back: str = uri_src.absolute().as_uri()
        self.assertTrue(back.startswith('file:'))

class PathExistsTests(TestCaseMixin):
    """存在性 / IO / 枚举；拆 helper 避免单函数栈帧过大（MSVC /GS）。"""
    _test_tag = 10

    def _prepare_tree(self) -> Path:
        ensure_test_temp()
        cwd: str = getcwd()
        cwd_p: Path = new(cwd)
        self.assertTrue(cwd_p.exists())
        self.assertTrue(cwd_p.is_dir())
        dir_path: Path = new(join(join(cwd, _TEST_TEMP), _TEST_DIR))
        file_path: Path = dir_path / _TEST_FILE
        nested: Path = dir_path / 'a' / 'b'
        sub_a: Path = dir_path / 'a'
        glob_file: Path = dir_path / _TEST_GLOB
        if file_path.exists():
            file_path.unlink()
        if glob_file.exists():
            glob_file.unlink()
        if nested.exists():
            nested.rmdir()
        if sub_a.exists():
            sub_a.rmdir()
        if dir_path.exists():
            dir_path.rmdir()
        nested.mkdir(511, True)
        self.assertTrue(nested.is_dir())
        nested.mkdir(511, False, True)
        dir_path.mkdir(511, False, True)
        self.assertTrue(dir_path.is_dir())
        self.assertFalse(file_path.exists())
        return dir_path

    def _exercise_file_io(self, dir_path: Path) -> Path:
        file_path: Path = dir_path / _TEST_FILE
        w = file_path.open('wb')
        self.assertTrue(w)
        self.assertEqual(w.write('x'), 1)
        w.close()
        self.assertTrue(file_path.is_file())
        self.assertFalse(file_path.is_dir())
        self.assertEqual(file_path.read_text(), 'x')
        self.assertEqual(file_path.write_text('yz'), 2)
        self.assertEqual(file_path.read_text(), 'yz')
        self.assertEqual(file_path.read_bytes(), b'yz')
        self.assertEqual(file_path.write_bytes(b'ab'), 2)
        self.assertEqual(file_path.read_bytes(), b'ab')
        st = file_path.stat()
        self.assertTrue(st.st_size >= 2)
        self.assertEqual(file_path.lstat().st_size, st.st_size)
        file_path.touch()
        ghost: Path = dir_path / 'no_such_file.tmp'
        ghost.unlink(True)
        self.assertEqual(file_path.write_text('data'), 4)
        return file_path

    def _exercise_rename(self, file_path: Path, dir_path: Path) -> None:
        moved: Path = dir_path / 'moved.txt'
        if moved.exists():
            moved.unlink()
        file_path.rename(moved)
        self.assertFalse(file_path.exists())
        self.assertTrue(moved.exists())
        moved.replace(file_path)
        self.assertTrue(file_path.exists())
        file_path.unlink()

    def _exercise_iterdir(self, dir_path: Path) -> None:
        names: int = 0
        ent: Path = new('')
        for ent in dir_path.iterdir():
            names += 1
        self.assertTrue(names >= 1)

    def _exercise_walk(self, dir_path: Path) -> None:
        steps: int = 0
        for step in dir_path.walk():
            steps += 1
        self.assertTrue(steps >= 1)

    def _exercise_glob_walk(self, dir_path: Path) -> None:
        glob_file: Path = dir_path / _TEST_GLOB
        glob_file.write_text('g')
        found: int = 0
        hit: Path = new('')
        for hit in dir_path.glob('glob_*.txt'):
            found += 1
            self.assertEqual(hit.name, _TEST_GLOB)
        self.assertEqual(found, 1)
        found = 0
        for hit in dir_path.rglob('glob_*.txt'):
            found += 1
        self.assertEqual(found, 1)
        self._exercise_iterdir(dir_path)
        self._exercise_walk(dir_path)

    def _teardown_tree(self, dir_path: Path) -> None:
        nested: Path = dir_path / 'a' / 'b'
        sub_a: Path = dir_path / 'a'
        glob_file: Path = dir_path / _TEST_GLOB
        if glob_file.exists():
            glob_file.unlink()
        nested.rmdir()
        sub_a.rmdir()
        dir_path.rmdir()

    @override
    def test(self):
        dir_path: Path = self._prepare_tree()
        file_path: Path = self._exercise_file_io(dir_path)
        self._exercise_rename(file_path, dir_path)
        self._exercise_glob_walk(dir_path)
        self._teardown_tree(dir_path)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iter_subclasses(sort_const='_test_tag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
