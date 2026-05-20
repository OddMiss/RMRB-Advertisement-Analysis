@echo off
REM 1. Set the Current Working Directory to the folder where this .bat file is
cd /d "%~dp0"

REM 2. Run Python
REM ".." means "go up one folder" (back to the root) to find python
"..\..\python-3.11.9-embed-amd64\python.exe" "TEST.py"

pause