@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist node_modules call npm install
if not exist engine\realesrgan-ncnn-vulkan.exe call npm run engine:win
call npm start
if errorlevel 1 pause
