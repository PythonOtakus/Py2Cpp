"""``py2cpp.io.path.Path``（``pathlib`` 子集）回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from py2cpp.io.path import Path
from py2cpp.system.environ import environ

from py2cpp.test.test_temp import _TestTemp, ensureTestTemp
_TestDir: str = 'test_path_dir'
_TestFile: str = 'test_path_file.txt'
_TestGlob: str = 'glob_a.txt'

class PathPureTests(TestCaseMixin):
    _testTag = 1

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
        setupSuffixes: list[str] = ['.py']
        self.assertEqual(setup.suffixes, setupSuffixes)
        tar: Path = new('archive.tar.gz')
        tarSuffixes: list[str] = ['.tar', '.gz']
        self.assertEqual(tar.suffixes, tarSuffixes)
        dotted: Path = new('a.b.c')
        self.assertEqual(dotted.suffix, '.c')
        hidden: Path = new('.bashrc')
        self.assertEqual(hidden.suffix, '')
        parentDot: Path = new('..')
        self.assertEqual(parentDot.suffix, '')
        trailing: Path = new('file.')
        self.assertEqual(trailing.suffix, '')
        self.assertEqual(str(setup.withName('run.py')), 'my\\library\\run.py')
        self.assertEqual(str(setup.withSuffix('.txt')), 'my\\library\\setup.txt')
        self.assertEqual(str(setup.withStem('config')), 'my\\library\\config.py')
        self.assertEqual(str(setup.withSegments('c', 'd', 'e')), 'c\\d\\e')
        joined: Path = setup.joinPath('x')
        self.assertEqual(joined.name, 'x')
        self.assertFalse(root.isAbsolute())
        winAbs: Path = new('C:\\Windows')
        self.assertTrue(winAbs.isAbsolute())
        win: Path = new('foo\\bar')
        self.assertEqual(win.asPosix(), 'foo/bar')
        parts: list[str] = setup.parts
        self.assertEqual(parts[0], 'my')
        self.assertEqual(parts[1], 'library')
        self.assertEqual(parts[2], 'setup.py')
        par: Path = new('foo/bar/baz')
        plist: list[Path] = par.parents
        self.assertEqual(str(plist[0]), 'foo\\bar')
        self.assertEqual(str(plist[1]), 'foo')
        relSrc: Path = new('foo/bar')
        rel: Path = relSrc.relativeTo('foo')
        self.assertEqual(str(rel), 'bar')
        relBase: Path = new('foo/bar')
        self.assertTrue(relBase.isRelativeTo('foo'))
        relOther: Path = new('foo/bar')
        self.assertFalse(relOther.isRelativeTo('baz'))
        matchTxt: Path = new('readme.txt')
        self.assertTrue(matchTxt.match('*.txt'))
        fullMatchP: Path = new('C:\\a\\b.txt')
        self.assertTrue(fullMatchP.fullMatch('*.txt'))
        abSrc: Path = new('foo')
        ab: Path = abSrc.absolute()
        self.assertTrue(ab.isAbsolute())
        self.assertEqual(Path('foo'), Path('foo'))
        self.assertNotEqual(Path('foo'), Path('bar'))
        self.assertEqual(hash(Path('x')), hash(Path('x')))

class PathClassMethodTests(TestCaseMixin):
    _testTag = 5

    @override
    def test(self):
        cwdP: Path = new.cwd()
        self.assertTrue(cwdP.isAbsolute())
        home: Path = new.home()
        self.assertTrue(home.isAbsolute())
        if 'USERPROFILE' in environ:
            self.assertTrue(str(home).startsWith(environ['USERPROFILE'][:3]))
        uri: Path = new.fromUri('file:///C:/temp/x')
        self.assertTrue(uri.isAbsolute())
        uriSrc: Path = new('C:\\temp\\y')
        back: str = uriSrc.absolute().asUri()
        self.assertTrue(back.startsWith('file:'))

class PathExistsTests(TestCaseMixin):
    """存在性 / IO / 枚举；拆 helper 避免单函数栈帧过大（MSVC /GS）。"""
    _testTag = 10

    def _prepareTree(self) -> Path:
        ensureTestTemp()
        cwd: Path = new.cwd()
        cwdP: Path = new(cwd)
        self.assertTrue(cwdP.exists())
        self.assertTrue(cwdP.isDir())
        dirPath: Path = cwd / _TestTemp / _TestDir
        filePath: Path = dirPath / _TestFile
        nested: Path = dirPath / 'a' / 'b'
        subA: Path = dirPath / 'a'
        globFile: Path = dirPath / _TestGlob
        if filePath.exists():
            filePath.unlink()
        if globFile.exists():
            globFile.unlink()
        if nested.exists():
            nested.rmdir()
        if subA.exists():
            subA.rmdir()
        if dirPath.exists():
            dirPath.rmdir()
        nested.mkdir(511, True)
        self.assertTrue(nested.isDir())
        nested.mkdir(511, False, True)
        dirPath.mkdir(511, False, True)
        self.assertTrue(dirPath.isDir())
        self.assertFalse(filePath.exists())
        return dirPath

    def _exerciseFileIo(self, dirPath: Path) -> Path:
        filePath: Path = dirPath / _TestFile
        w = filePath.open('wb')
        self.assertTrue(w)
        self.assertEqual(w.write('x'), 1)
        w.close()
        self.assertTrue(filePath.isFile())
        self.assertFalse(filePath.isDir())
        self.assertEqual(filePath.readText(), 'x')
        self.assertEqual(filePath.writeText('yz'), 2)
        self.assertEqual(filePath.readText(), 'yz')
        self.assertEqual(filePath.readBytes(), b'yz')
        self.assertEqual(filePath.writeBytes(b'ab'), 2)
        self.assertEqual(filePath.readBytes(), b'ab')
        st = filePath.stat()
        self.assertTrue(st.stSize >= 2)
        self.assertEqual(filePath.lstat().stSize, st.stSize)
        filePath.touch()
        ghost: Path = dirPath / 'no_such_file.tmp'
        ghost.unlink(True)
        self.assertEqual(filePath.writeText('data'), 4)
        return filePath

    def _exerciseRename(self, filePath: Path, dirPath: Path) -> None:
        moved: Path = dirPath / 'moved.txt'
        if moved.exists():
            moved.unlink()
        filePath.rename(moved)
        self.assertFalse(filePath.exists())
        self.assertTrue(moved.exists())
        moved.replace(filePath)
        self.assertTrue(filePath.exists())
        filePath.unlink()

    def _exerciseIterdir(self, dirPath: Path) -> None:
        names: int = 0
        ent: Path = new('')
        for ent in dirPath.iterDir():
            names += 1
        self.assertTrue(names >= 1)

    def _exerciseWalk(self, dirPath: Path) -> None:
        steps: int = 0
        for step in dirPath.walk():
            steps += 1
        self.assertTrue(steps >= 1)

    def _exerciseGlobWalk(self, dirPath: Path) -> None:
        globFile: Path = dirPath / _TestGlob
        globFile.writeText('g')
        found: int = 0
        hit: Path = new('')
        for hit in dirPath.glob('glob_*.txt'):
            found += 1
            self.assertEqual(hit.name, _TestGlob)
        self.assertEqual(found, 1)
        found = 0
        for hit in dirPath.rglob('glob_*.txt'):
            found += 1
        self.assertEqual(found, 1)
        self._exerciseIterdir(dirPath)
        self._exerciseWalk(dirPath)

    def _teardownTree(self, dirPath: Path) -> None:
        nested: Path = dirPath / 'a' / 'b'
        subA: Path = dirPath / 'a'
        globFile: Path = dirPath / _TestGlob
        if globFile.exists():
            globFile.unlink()
        nested.rmdir()
        subA.rmdir()
        dirPath.rmdir()

    @override
    def test(self):
        dirPath: Path = self._prepareTree()
        filePath: Path = self._exerciseFileIo(dirPath)
        self._exerciseRename(filePath, dirPath)
        self._exerciseGlobWalk(dirPath)
        self._teardownTree(dirPath)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
