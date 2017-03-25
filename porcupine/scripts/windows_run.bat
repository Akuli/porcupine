@echo off
rem run a python file in command prompt
rem usage: windows_run "PATH\TO\PYTHON" "DIRNAME" "BASENAME.py"
rem this file uses CRLF instead of LF because windows doesn't know LF

rem it's important not to quote these here because windows is windows
pushd %2
%1 %3
popd

echo.
echo.-----------------------------
echo.Your program completed. Press Enter to close this window...
set /p junk=
