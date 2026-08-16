"""``UIPanelMixin``：``Self.iterFields(publicOnly=True)`` + ``Self.getFieldAnnotation[Meta]`` 译期展开。"""

from ..builtins import *
from .layout import UIFormLayout
from .meta import UIInvisibleMeta, UIButtonMeta, UILabelMeta, UISliderMeta
from .widget import (
  UICheckBox,
  UIFloatEdit,
  UIIntEdit,
  UILineEdit,
  UIPushButton,
  UISlider,
)
from .app import UIApp
from .window import UIWindow


@mixin
class UIPanelMixin:
  _panelForm: UIFormLayout = new()
  _panelFormReady: bool = False
  _panelWin: UIWindow = new()

  def drawPanel(self, win: UIWindow @ref) -> None:
    self._panelWin = win
    self._ensurePanelForm()
    self._panelForm.apply(win)

  def panelSyncFromForm(self) -> None:
    self._panelForm.syncFromNative(self._panelWin)
    self._syncFieldsFromForm()

  def panelOnBoolChanged(self, _: bool) -> None:
    self.panelSyncFromForm()

  def panelOnStrChanged(self, _: str) -> None:
    self.panelSyncFromForm()

  def panelOnIntChanged(self, _: int) -> None:
    self.panelSyncFromForm()

  def panelOnFloatChanged(self, _: float64) -> None:
    self.panelSyncFromForm()

  def _formAddSlider(
    self,
    form: UIFormLayout @ref,
    field: str,
    label: str,
    lo: int,
    hi: int,
    value: int,
  ) -> None:
    w: UISlider = new()
    w.value = value
    w.lo = lo
    w.hi = hi
    w.valueChanged += self.panelOnIntChanged
    form.addSlider(label, w)

  @overload
  def _formAddValue(
    self, form: UIFormLayout @ref, field: str, label: str, value: bool
  ) -> None:
    cb: UICheckBox = new()
    cb.checked = value
    cb.stateChanged += self.panelOnBoolChanged
    form.addCheckbox(label, cb)

  @overload
  def _formAddValue(
    self, form: UIFormLayout @ref, field: str, label: str, value: str
  ) -> None:
    le: UILineEdit = new()
    le.text = value
    le.textChanged += self.panelOnStrChanged
    form.addLineEdit(label, le)

  @overload
  def _formAddValue(
    self, form: UIFormLayout @ref, field: str, label: str, value: int
  ) -> None:
    ie: UIIntEdit = new()
    ie.value = value
    ie.valueChanged += self.panelOnIntChanged
    form.addIntEdit(label, ie)

  @overload
  def _formAddValue(
    self, form: UIFormLayout @ref, field: str, label: str, value: float64
  ) -> None:
    fe: UIFloatEdit = new()
    fe.value = value
    fe.valueChanged += self.panelOnFloatChanged
    form.addFloatEdit(label, fe)

  @overload
  def _rowValue(self, form: UIFormLayout @ref, row: int, _: bool) -> bool:
    return form.rowBool(row)

  @overload
  def _rowValue(self, form: UIFormLayout @ref, row: int, _: str) -> str:
    return form.rowStr(row)

  @overload
  def _rowValue(self, form: UIFormLayout @ref, row: int, _: int) -> int:
    return form.rowInt(row)

  @overload
  def _rowValue(self, form: UIFormLayout @ref, row: int, _: float64) -> float64:
    return form.rowFloat(row)

  @overload
  def _pushWidgetRow(self, form: UIFormLayout @ref, row: int, value: bool) -> None:
    form.pushRowBool(row, value)

  @overload
  def _pushWidgetRow(self, form: UIFormLayout @ref, row: int, value: str) -> None:
    form.pushRowStr(row, value)

  @overload
  def _pushWidgetRow(self, form: UIFormLayout @ref, row: int, value: int) -> None:
    form.pushRowInt(row, value)

  @overload
  def _pushWidgetRow(self, form: UIFormLayout @ref, row: int, value: float64) -> None:
    form.pushRowFloat(row, value)

  def panelSyncToForm(self) -> None:
    """宿主字段 → 控件 ``__set``（postsetter 内 ``_syncToNative`` 更新 Win32）。"""
    row: int = 0
    for field in Self.iterFields(publicOnly=True):
      invisible = Self.getFieldAnnotation[UIInvisibleMeta](field)
      if invisible is not None:
        continue
      slider = Self.getFieldAnnotation[UISliderMeta](field)
      if slider is not None:
        self._panelForm.pushRowInt(row, getattr(self, field))
      else:
        self._pushWidgetRow(self._panelForm, row, getattr(self, field))
      row += 1

  def _ensurePanelForm(self) -> None:
    if self._panelFormReady:
      return
    self._panelForm.clear()
    for field in Self.iterFields(publicOnly=True):
      label: str = field
      uiLabel = Self.getFieldAnnotation[UILabelMeta](field)
      if uiLabel is not None:
        label = uiLabel.text
      invisible = Self.getFieldAnnotation[UIInvisibleMeta](field)
      if invisible is not None:
        continue
      slider = Self.getFieldAnnotation[UISliderMeta](field)
      if slider is not None:
        self._formAddSlider(
          self._panelForm,
          field,
          label,
          slider.lo,
          slider.hi,
          getattr(self, field),
        )
      else:
        self._formAddValue(self._panelForm, field, label, getattr(self, field))

    btnId: int = 0
    for method in Self.iterMethods[UIButtonMeta]():
      label: str = method
      uiBtn = Self.getMethodAnnotation[UIButtonMeta](method)
      if uiBtn is not None and uiBtn.label:
        label = uiBtn.label
      btn: UIPushButton = new()
      btn.id = btnId
      btn.text = label
      btn.clicked += self.panelSyncFromForm
      btn.clicked += getattr(self, method)
      btn.clicked += self.panelSyncToForm
      self._panelForm.addButton(btn)
      btnId += 1

    self._panelFormReady = True

  def _syncFieldsFromForm(self) -> None:
    row: int = 0
    for field in Self.iterFields(publicOnly=True):
      invisible = Self.getFieldAnnotation[UIInvisibleMeta](field)
      if invisible is not None:
        continue
      slider = Self.getFieldAnnotation[UISliderMeta](field)
      if slider is not None:
        setattr(self, field, self._panelForm.rowInt(row))
      else:
        setattr(
          self,
          field,
          self._rowValue(self._panelForm, row, getattr(self, field)),
        )
      row += 1

  def createPanel(self, title: str = "", width: int = -1, height: int = -1) -> UIWindow:
    """创建已布局的 Win32 面板窗口，尚未 ``UIApp.run()``；参数同 ``showPanel``。"""
    self._panelWin = new()
    if not UIApp.isAvailable():
      return self._panelWin
    self._panelWin.title = title
    if not self._panelWin.title:
      self._panelWin.title = Self.__name__
    self._panelWin.show(width, height)
    self.drawPanel(self._panelWin)
    if width < 0 or height < 0:
      self._panelWin.resize(width, height)
    return self._panelWin

  def showPanel(self, title: str = "", width: int = -1, height: int = -1) -> int:
    """打开 Win32 面板并阻塞至关闭；``width``/``height`` 默认 ``-1`` 按控件自适应；``title`` 为空时用 ``Self.__name__``。"""
    if not UIApp.isAvailable():
      return 1
    win: UIWindow = self.createPanel(title, width, height)
    ret: int = UIApp.run()
    self._panelForm.syncFromNative(win)
    self._syncFieldsFromForm()
    return ret
