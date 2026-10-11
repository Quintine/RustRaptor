@echo off
setlocal
cd /d "%~dp0"
"%~dp0bin\raptor-rust.exe" %*
exit /b %errorlevel%
