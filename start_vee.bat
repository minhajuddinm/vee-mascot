@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set LOG=install_log.txt
echo === %date% %time% > %LOG%
where python >> %LOG% 2>&1
py -0p >> %LOG% 2>&1

set PY=
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PY (
    "%%P" -c "import tkinter" >nul 2>&1 && set "PY=%%P"
  )
)
if not defined PY (
  for /f "tokens=1,* delims= " %%A in ('py -0p 2^>nul') do (
    if not defined PY if exist "%%B" (
      "%%B" -c "import tkinter" >nul 2>&1 && set "PY=%%B"
    )
  )
)
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if not defined PY if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)
if not defined PY (
  echo No working Python with tkinter found. >> %LOG%
  echo No working Python found. See install_log.txt
  pause
  exit /b 1
)
echo Using: !PY! >> %LOG%
"!PY!" -m pip install --quiet --disable-pip-version-check uiautomation >> %LOG% 2>&1
set "PYW=!PY:python.exe=pythonw.exe!"
if exist "!PYW!" (
  start "" "!PYW!" vee_mascot.py
) else (
  start "" /min "!PY!" vee_mascot.py
)
echo Started >> %LOG%
