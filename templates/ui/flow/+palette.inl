PY2CPP_IGNORE
#include "py2cpp/ui/flow/palette.h"
#include "py2cpp/ui/flow/canvas.h"
PY2CPP_END

#ifdef _WIN32

PY2CPP_BEGIN_SCOPE

void UIFlowPalette::bind_canvas(flow::canvas::UIFlowCanvas& canvas)
{
  this->_canvas_ptr = (PyInt64)((INT_PTR)&canvas);
}

void UIFlowPalette::_drop_node_at_screen(PyStr kind, PyInt scr_x, PyInt scr_y)
{
  if (this->_canvas_ptr == 0 || !kind)
  {
    return;
  }
  flow::canvas::UIFlowCanvas* cv =
      (flow::canvas::UIFlowCanvas*)(INT_PTR)this->_canvas_ptr;
  if (!cv->contains_screen_point(scr_x, scr_y))
  {
    return;
  }
  PyInt csx = cv->client_from_screen(scr_x, scr_y).__getitem__(0);
  PyInt csy = cv->client_from_screen(scr_x, scr_y).__getitem__(1);
  PyFloat64 gx =
      cv->screen_to_world((PyFloat64)csx, (PyFloat64)csy).__getitem__(0);
  PyFloat64 gy =
      cv->screen_to_world((PyFloat64)csx, (PyFloat64)csy).__getitem__(1);
  cv->add_node_from_kind(kind, gx, gy);
  cv->invalidate();
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void UIFlowPalette::bind_canvas(flow::canvas::UIFlowCanvas& canvas)
{
  (void)canvas;
  this->_canvas_ptr = 0;
}

void UIFlowPalette::_drop_node_at_screen(PyStr kind, PyInt scr_x, PyInt scr_y)
{
  (void)kind;
  (void)scr_x;
  (void)scr_y;
}

PY2CPP_END_SCOPE

#endif
