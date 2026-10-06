@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" "cut_video_app.py" %*
) else (
    python cut_video_app.py %*
)
