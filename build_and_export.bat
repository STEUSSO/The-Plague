@echo off
echo ==============================================
echo   Building The Plague Docker Image
echo ==============================================

docker build -t the-plague-bot:latest .
if %errorlevel% neq 0 (
    echo [ERROR] Docker build failed. Make sure Docker is running.
    pause
    exit /b %errorlevel%
)

echo.
echo ==============================================
echo   Exporting Image to the-plague-bot.tar
echo ==============================================

docker save -o the-plague-bot.tar the-plague-bot:latest
if %errorlevel% neq 0 (
    echo [ERROR] Docker save failed.
    pause
    exit /b %errorlevel%
)

echo.
echo ==============================================
echo   SUCCESS! Image saved to: the-plague-bot.tar
echo   You can now upload 'the-plague-bot.tar' to your server!
echo ==============================================
pause
