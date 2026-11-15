@echo off
echo ========================================================
echo Syncing and Pushing multilingual-meet to GitHub...
echo ========================================================
cd /d "%~dp0"

echo [1/4] Fetching latest changes from GitHub...
git fetch origin

echo [2/4] Merging remote main into local main...
git checkout main
git pull origin main --allow-unrelated-histories --strategy-option=ours --no-edit

echo [3/4] Pushing main branch...
git push -u origin main

echo [4/4] Merging remote role3-speech and pushing...
git checkout role3-speech
git pull origin role3-speech --allow-unrelated-histories --strategy-option=ours --no-edit
git merge main --no-edit
git push -u origin role3-speech

echo.
echo ========================================================
echo Successfully pushed everything to GitHub!
echo Check: https://github.com/avanikashetty3006-droid/multilingual-meet
echo ========================================================
pause
