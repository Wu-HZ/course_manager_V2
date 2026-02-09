@echo off
chcp 65001 >nul
echo 正在停止排课系统...

:: 查找并终止 Python 进程（只终止 manage.py runserver）
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo list ^| findstr "PID:"') do (
    wmic process where "ProcessId=%%i" get CommandLine 2>nul | findstr "manage.py" >nul
    if not errorlevel 1 (
        taskkill /pid %%i /f >nul 2>&1
    )
)

echo 排课系统已停止。
timeout /t 2 >nul
