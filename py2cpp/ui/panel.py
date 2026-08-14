"""``UIPanelMixin``：``Self.iter_fields(public_only=True)`` + ``Self.get_field_annotation[Meta]`` 译期展开。"""

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
  _panel_form: UIFormLayout = new()
  _panel_form_ready: bool = False
  _panel_win: UIWindow = new()

  def draw_panel(self, win: UIWindow @ref) -> None:
    self._panel_win = win
    self._ensure_panel_form()
    self._panel_form.apply(win)

  def panel_sync_from_form(self) -> None:
    self._panel_form.sync_from_native(self._panel_win)
    self._sync_fields_from_form()

  def panel_on_bool_changed(self, _: bool) -> None:
    self.panel_sync_from_form()

  def panel_on_str_changed(self, _: str) -> None:
    self.panel_sync_from_form()

  def panel_on_int_changed(self, _: int) -> None:
    self.panel_sync_from_form()

  def panel_on_float_changed(self, _: float64) -> None:
    self.panel_sync_from_form()

  def _form_add_slider(
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
    w.value_changed += self.panel_on_int_changed
    form.add_slider(label, w)

  @overload
  def _form_add_value(
    self, form: UIFormLayout @ref, field: str, label: str, value: bool
  ) -> None:
    cb: UICheckBox = new()
    cb.checked = value
    cb.state_changed += self.panel_on_bool_changed
    form.add_checkbox(label, cb)

  @overload
  def _form_add_value(
    self, form: UIFormLayout @ref, field: str, label: str, value: str
  ) -> None:
    le: UILineEdit = new()
    le.text = value
    le.text_changed += self.panel_on_str_changed
    form.add_line_edit(label, le)

  @overload
  def _form_add_value(
    self, form: UIFormLayout @ref, field: str, label: str, value: int
  ) -> None:
    ie: UIIntEdit = new()
    ie.value = value
    ie.value_changed += self.panel_on_int_changed
    form.add_int_edit(label, ie)

  @overload
  def _form_add_value(
    self, form: UIFormLayout @ref, field: str, label: str, value: float64
  ) -> None:
    fe: UIFloatEdit = new()
    fe.value = value
    fe.value_changed += self.panel_on_float_changed
    form.add_float_edit(label, fe)

  @overload
  def _row_value(self, form: UIFormLayout @ref, row: int, _: bool) -> bool:
    return form.row_bool(row)

  @overload
  def _row_value(self, form: UIFormLayout @ref, row: int, _: str) -> str:
    return form.row_str(row)

  @overload
  def _row_value(self, form: UIFormLayout @ref, row: int, _: int) -> int:
    return form.row_int(row)

  @overload
  def _row_value(self, form: UIFormLayout @ref, row: int, _: float64) -> float64:
    return form.row_float(row)

  @overload
  def _push_widget_row(self, form: UIFormLayout @ref, row: int, value: bool) -> None:
    form.push_row_bool(row, value)

  @overload
  def _push_widget_row(self, form: UIFormLayout @ref, row: int, value: str) -> None:
    form.push_row_str(row, value)

  @overload
  def _push_widget_row(self, form: UIFormLayout @ref, row: int, value: int) -> None:
    form.push_row_int(row, value)

  @overload
  def _push_widget_row(self, form: UIFormLayout @ref, row: int, value: float64) -> None:
    form.push_row_float(row, value)

  def panel_sync_to_form(self) -> None:
    """宿主字段 → 控件 ``__set``（postsetter 内 ``_sync_to_native`` 更新 Win32）。"""
    row: int = 0
    for field in Self.iter_fields(public_only=True):
      invisible = Self.get_field_annotation[UIInvisibleMeta](field)
      if invisible is not None:
        continue
      slider = Self.get_field_annotation[UISliderMeta](field)
      if slider is not None:
        self._panel_form.push_row_int(row, getattr(self, field))
      else:
        self._push_widget_row(self._panel_form, row, getattr(self, field))
      row += 1

  def _ensure_panel_form(self) -> None:
    if self._panel_form_ready:
      return
    self._panel_form.clear()
    for field in Self.iter_fields(public_only=True):
      label: str = field
      ui_label = Self.get_field_annotation[UILabelMeta](field)
      if ui_label is not None:
        label = ui_label.text
      invisible = Self.get_field_annotation[UIInvisibleMeta](field)
      if invisible is not None:
        continue
      slider = Self.get_field_annotation[UISliderMeta](field)
      if slider is not None:
        self._form_add_slider(
          self._panel_form,
          field,
          label,
          slider.lo,
          slider.hi,
          getattr(self, field),
        )
      else:
        self._form_add_value(self._panel_form, field, label, getattr(self, field))

    btn_id: int = 0
    for method in Self.iter_methods[UIButtonMeta]():
      label: str = method
      ui_btn = Self.get_method_annotation[UIButtonMeta](method)
      if ui_btn is not None and ui_btn.label:
        label = ui_btn.label
      btn: UIPushButton = new()
      btn.id = btn_id
      btn.text = label
      btn.clicked += self.panel_sync_from_form
      btn.clicked += getattr(self, method)
      btn.clicked += self.panel_sync_to_form
      self._panel_form.add_button(btn)
      btn_id += 1

    self._panel_form_ready = True

  def _sync_fields_from_form(self) -> None:
    row: int = 0
    for field in Self.iter_fields(public_only=True):
      invisible = Self.get_field_annotation[UIInvisibleMeta](field)
      if invisible is not None:
        continue
      slider = Self.get_field_annotation[UISliderMeta](field)
      if slider is not None:
        setattr(self, field, self._panel_form.row_int(row))
      else:
        setattr(
          self,
          field,
          self._row_value(self._panel_form, row, getattr(self, field)),
        )
      row += 1

  def create_panel(self, title: str = "", width: int = -1, height: int = -1) -> UIWindow:
    """创建已布局的 Win32 面板窗口，尚未 ``UIApp.run()``；参数同 ``show_panel``。"""
    self._panel_win = new()
    if not UIApp.is_available():
      return self._panel_win
    self._panel_win.title = title
    if not self._panel_win.title:
      self._panel_win.title = Self.__name__
    self._panel_win.show(width, height)
    self.draw_panel(self._panel_win)
    if width < 0 or height < 0:
      self._panel_win.resize(width, height)
    return self._panel_win

  def show_panel(self, title: str = "", width: int = -1, height: int = -1) -> int:
    """打开 Win32 面板并阻塞至关闭；``width``/``height`` 默认 ``-1`` 按控件自适应；``title`` 为空时用 ``Self.__name__``。"""
    if not UIApp.is_available():
      return 1
    win: UIWindow = self.create_panel(title, width, height)
    ret: int = UIApp.run()
    self._panel_form.sync_from_native(win)
    self._sync_fields_from_form()
    return ret
