"""源文件与 Span（字节半开区间）。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileId:
  value: int


@dataclass(frozen=True)
class Span:
  file_id: FileId
  start: int
  end: int

  def __post_init__(self) -> None:
    if self.start < 0 or self.end < self.start:
      raise ValueError(f"invalid span {self.start}:{self.end}")


@dataclass
class SourceFile:
  file_id: FileId
  path: str
  text: str
  digest: str


@dataclass
class SourceManager:
  """UTF-8 源文本登记；列转换与缓存由调用方扩展。"""

  _files: list[SourceFile] = field(default_factory=list)
  _by_path: dict[str, FileId] = field(default_factory=dict)

  def add(self, path: str, text: str, digest: str) -> SourceFile:
    existing = self._by_path.get(path)
    if existing is not None:
      return self._files[existing.value]
    fid = FileId(len(self._files))
    sf = SourceFile(file_id=fid, path=path, text=text, digest=digest)
    self._files.append(sf)
    self._by_path[path] = fid
    return sf

  def get(self, file_id: FileId) -> SourceFile:
    return self._files[file_id.value]

  def get_by_path(self, path: str) -> SourceFile | None:
    fid = self._by_path.get(path)
    if fid is None:
      return None
    return self._files[fid.value]
