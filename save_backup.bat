@echo off
echo ================================================
echo   Trade Yantra - Quick Backup to GitHub
echo ================================================
cd /d "c:\Users\bhave\Downloads\trade-yantra"

:: Generate timestamp for commit message
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATE=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a-%%b

set MSG=BACKUP: Manual save at %DATE% %TIME%

echo Staging files...
git add backend/ frontend/src/ frontend/public/ frontend/index.html frontend/package.json frontend/vite.config.js

echo Committing...
git commit -m "%MSG%"

echo Pushing to GitHub...
git push origin main

echo.
echo ================================================
echo   Backup Complete! Saved as: %MSG%
echo ================================================
pause
