@echo off
cd /d "%~dp0"
set PYTHONPATH=src
echo ========================================================
echo   Scaffolding School Transport System Monorepo...
echo ========================================================
python -m software_factory.templates --archetype school_transport --out generated_apps\school_transport --title "VidyaVahan School Transport"
echo.
echo Monorepo generated at: %~dp0generated_apps\school_transport
echo Opening folder...
start "" "%~dp0generated_apps\school_transport"
pause

