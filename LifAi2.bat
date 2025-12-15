@echo off
:: LifAi2 Launcher - Double-click to run
:: Activates virtual environment and launches the app without console window

cd /d "%~dp0"

:: Check if venv exists
if exist ".venv\Scripts\pythonw.exe" (
    :: Run with venv's pythonw (no console window)
    start "" ".venv\Scripts\pythonw.exe" run.pyw
) else if exist "venv\Scripts\pythonw.exe" (
    :: Alternative venv folder name
    start "" "venv\Scripts\pythonw.exe" run.pyw
) else (
    :: Fallback to system Python
    echo Virtual environment not found. Using system Python...
    start "" pythonw run.pyw
)
