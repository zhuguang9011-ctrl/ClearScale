@echo off
setlocal
cd /d "%~dp0"

if not exist "plugin\ai_diffusion.desktop" (
  echo ERROR: plugin\ai_diffusion.desktop was not found.
  echo Put this repair file inside the Product-Editor-Full folder.
  pause
  exit /b 1
)

if not exist "krita\share\krita\pykrita" mkdir "krita\share\krita\pykrita"
xcopy /E /I /Y "plugin\ai_diffusion" "krita\share\krita\pykrita\ai_diffusion" >nul
copy /Y "plugin\ai_diffusion.desktop" "krita\share\krita\pykrita\ai_diffusion.desktop" >nul

if errorlevel 1 (
  echo ERROR: AI plugin repair failed.
  pause
  exit /b 1
)

echo AI Image Diffusion plugin copied successfully.
echo Now run START.cmd. If needed, enable AI Image Diffusion in the Python Plugin Manager and restart once.
pause
