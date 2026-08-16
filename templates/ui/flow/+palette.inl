PY2CPP_IGNORE
#include "py2cpp/ui/flow/palette.h"
#include "py2cpp/ui/flow/canvas.h"
PY2CPP_END

#ifdef _WIN32

PY2CPP_BEGIN_SCOPE

void PyUIFlowPalette::bindCanvas(flow::canvas::PyUIFlowCanvas& canvas)
{
  this->_canvasPtr = (PyInt64)((INT_PTR)&canvas);
}

void PyUIFlowPalette::_dropNodeAtScreen(PyStr kind, PyInt scr_x, PyInt scr_y)
{
  if (this->_canvasPtr == 0 || !kind)
  {
    return;
  }
  flow::canvas::PyUIFlowCanvas* cv =
      (flow::canvas::PyUIFlowCanvas*)(INT_PTR)this->_canvasPtr;
  if (!cv->containsScreenPoint(scr_x, scr_y))
  {
    return;
  }
  PyInt csx = cv->clientFromScreen(scr_x, scr_y).__getitem__(0);
  PyInt csy = cv->clientFromScreen(scr_x, scr_y).__getitem__(1);
  PyFloat64 gx =
      cv->screenToWorld((PyFloat64)csx, (PyFloat64)csy).__getitem__(0);
  PyFloat64 gy =
      cv->screenToWorld((PyFloat64)csx, (PyFloat64)csy).__getitem__(1);
  cv->addNodeFromKind(kind, gx, gy);
  cv->invalidate();
}

PY2CPP_END_SCOPE

#else

PY2CPP_BEGIN_SCOPE

void PyUIFlowPalette::bindCanvas(flow::canvas::PyUIFlowCanvas& canvas)
{
  (void)canvas;
  this->_canvasPtr = 0;
}

void PyUIFlowPalette::_dropNodeAtScreen(PyStr kind, PyInt scr_x, PyInt scr_y)
{
  (void)kind;
  (void)scr_x;
  (void)scr_y;
}

PY2CPP_END_SCOPE

#endif
