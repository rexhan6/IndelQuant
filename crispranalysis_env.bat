@echo off
title CRISPR Analysis Environment
color 0A

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║         CRISPR Analysis Environment v0.0.1beta          ║
echo  ╠══════════════════════════════════════════════════════════╣
echo  ║  AdapterRemoval v3.0.0                                  ║
echo  ║  CRISPResso2 v2.3.4                                     ║
echo  ║  Python 3.10.20                                         ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

set "CONDA_PREFIX=C:\Users\Rex Han\.conda\envs\crispranalysis"
set "PATH=%CONDA_PREFIX%;%CONDA_PREFIX%\Scripts;%CONDA_PREFIX%\Library\bin;%PATH%"
set "PYTHONPATH=%CONDA_PREFIX%\lib\site-packages;%PYTHONPATH%"

cd /d "F:\Cherryclaw"

echo [OK] Environment activated
echo [OK] Working directory: F:\Cherryclaw
echo.
echo Quick test commands:
echo   adapterremoval3 --version
echo   CRISPResso --version
echo   python -c "import CRISPResso2; print('CRISPResso2 OK')"
echo.

cmd /k "echo Ready. Type commands below:"
