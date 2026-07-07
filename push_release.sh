#!/bin/bash
set -euo pipefail
cd /mnt/c/Users/James/Documents/repo/HADashboard/xsense
git add -A
git commit -F .git/COMMIT_MSG_TMP
git pull --rebase origin main
git push origin main
git status -sb
git log --oneline -3
