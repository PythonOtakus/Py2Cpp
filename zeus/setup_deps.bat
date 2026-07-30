@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ZEUS_ROOT=%~dp0"
cd /d "%ZEUS_ROOT%"

set "PY=python"
set "GLFW_VER=3.4"
set "GLFW_DIR=%ZEUS_ROOT%third_party\glfw"
set "GLFW_ZIP=%ZEUS_ROOT%third_party\glfw-%GLFW_VER%.bin.WIN64.zip"
set "GLFW_URL=https://github.com/glfw/glfw/releases/download/%GLFW_VER%/glfw-%GLFW_VER%.bin.WIN64.zip"

if exist "%GLFW_DIR%\include\GLFW\glfw3.h" (
  echo [zeus] GLFW already present: %GLFW_DIR%
  exit /b 0
)

mkdir "%ZEUS_ROOT%third_party" 2>nul
echo [zeus] downloading GLFW %GLFW_VER% WIN64...
%PY% -c "import urllib.request, pathlib; p=pathlib.Path(r'%GLFW_ZIP%'); p.parent.mkdir(parents=True, exist_ok=True); urllib.request.urlretrieve(r'%GLFW_URL%', p); print('downloaded', p.stat().st_size)"
if errorlevel 1 (
  echo ERROR: failed to download GLFW
  exit /b 1
)

echo [zeus] extracting...
%PY% -c "import zipfile, shutil, pathlib; root=pathlib.Path(r'%ZEUS_ROOT%third_party'); z=root/'glfw-%GLFW_VER%.bin.WIN64.zip'; ex=root/'_glfw_extract'; shutil.rmtree(ex, ignore_errors=True); zipfile.ZipFile(z).extractall(ex); src=ex/'glfw-%GLFW_VER%.bin.WIN64'; dst=root/'glfw'; shutil.rmtree(dst, ignore_errors=True); dst.mkdir(parents=True); shutil.copytree(src/'include', dst/'include'); shutil.copytree(src/'lib-vc2022', dst/'lib-vc2022'); shutil.rmtree(ex, ignore_errors=True); z.unlink(missing_ok=True); assert (dst/'include/GLFW/glfw3.h').is_file()"
if errorlevel 1 (
  echo ERROR: failed to extract GLFW
  exit /b 1
)

echo [zeus] GLFW ready at %GLFW_DIR%
exit /b 0
