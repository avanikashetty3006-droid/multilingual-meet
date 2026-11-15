# Run from the repo root.
git rm -f call-server/package-lock.json
Add-Content .gitignore "`n# local runtime files`nvaak.db`nvaak.db-*`ncall-server/vaak.db*`nmetrics.csv`nlatency_report.png`nlatency_vs_users.png`nspeech-service/models/`nspeech-service/audio/*.wav"
git status
