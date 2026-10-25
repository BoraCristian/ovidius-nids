@echo off
REM Ovidius NIDS launcher for Windows - double-click this file or run from cmd/PowerShell.
REM Uses the Python Launcher (`py`) which ships with every modern Python install.
REM
REM Tries a sensible Python version first (3.12 -> 3.13 -> 3.14 -> 3.11 -> default) because
REM scientific packages (scikit-learn, numpy) don't always have Windows wheels
REM for brand-new Python releases (3.15+) and would otherwise try to compile
REM from source, which needs Visual C++ Build Tools.

cd /d "%~dp0"

REM Prefer specific versions if they're installed
for %%V in (3.12 3.13 3.14 3.11) do (
  py -%%V -V >NUL 2>NUL
  if not errorlevel 1 (
    echo Using Python %%V
    py -%%V run.py %*
    goto :end
  )
)

where py >NUL 2>NUL
if %ERRORLEVEL%==0 (
  py run.py %*
  goto :end
)

where python >NUL 2>NUL
if %ERRORLEVEL%==0 (
  python run.py %*
  goto :end
)

echo.
echo [!] Python was not found on PATH.
echo     Install Python 3.12 from https://www.python.org/downloads/windows/
echo     and make sure to check "Add python.exe to PATH" during setup.
echo.
REM Only pause when Python wasn't found - so the user can actually read the
REM error.  When run.py exits normally (incl. Ctrl+C), cmd already asks
REM "Terminate batch job (Y/N)?" - adding a `pause` on top made users have to
REM confirm twice.
pause
goto :eof

:end
