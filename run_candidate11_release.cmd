@echo off
setlocal
cd /d "%~dp0"
ml\.venv\Scripts\python.exe -u ml\palettebrain\run_candidate11_release.py --resume %*
exit /b %errorlevel%
