@echo off
chcp 65001 >nul
echo ========================================
echo   Install fastp into the crispranalysis environment
echo ========================================
echo.

set "CONDA=C:\Users\Rex Han\miniconda3\Scripts\conda.exe"

if not exist "%CONDA%" (
    echo [ERROR] Conda not found: %CONDA%
    pause
    exit /b 1
)

echo [Conda] %CONDA%
echo [Environment] crispranalysis
echo.
echo Installing fastp, please wait...
echo.

"%CONDA%" install -n crispranalysis -c bioconda fastp -y
if errorlevel 1 (
    echo.
    echo [ERROR] fastp installation failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Verify installation
echo ========================================
"%CONDA%" run -n crispranalysis fastp --version
echo.
pause
