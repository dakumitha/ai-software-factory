@echo off
cd /d "%~dp0"
set PYTHONPATH=src
echo ========================================================
echo   AI Software Factory - Web Control Room
echo ========================================================
echo Starting server on http://127.0.0.1:8080 ...
start http://127.0.0.1:8080
python -m software_factory --web
pause

