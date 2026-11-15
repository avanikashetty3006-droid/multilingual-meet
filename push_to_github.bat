@echo off
echo ========================================================
echo Pushing multilingual-meet to GitHub...
echo ========================================================
cd /d "%~dp0"

echo [1/2] Pushing main branch...
git push -u origin main

echo.
echo [2/2] Pushing role3-speech branch...
git push -u origin role3-speech

echo.
echo ========================================================
echo Done! Check your repository at:
echo https://github.com/avanikashetty3006-droid/multilingual-meet
echo ========================================================
pause
