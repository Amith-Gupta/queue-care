@echo off
echo ====================================================
echo   QueueCare - Push to GitHub Helper
echo ====================================================
echo.

set /p REPO_URL="Enter your GitHub Repository URL (e.g. https://github.com/your-username/QueueCare.git): "

if "%REPO_URL%"=="" (
    echo Error: Repository URL cannot be empty.
    pause
    exit /b
)

echo.
echo Initializing Git repository...
git init
git add .
git commit -m "Initial commit: QueueCare - Smart Hospital Token System"
git branch -M main
git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo.
echo Pushing to GitHub...
git push -u origin main

echo.
echo ====================================================
echo Done! Your project has been uploaded to GitHub.
echo ====================================================
pause
