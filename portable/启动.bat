@echo off
chcp 65001 >nul
title 排课系统

echo ========================================
echo         排课系统启动中...
echo ========================================
echo.

cd /d "%~dp0"

:: 检查 Python 环境
if not exist "python\python.exe" (
    echo [错误] 未找到 Python 环境！
    echo 请确保 python 文件夹存在。
    pause
    exit /b 1
)

:: 设置环境变量
set DJANGO_DEBUG=false
set SERVE_FRONTEND=true
set PATH=%~dp0python;%~dp0python\Scripts;%PATH%

:: 检查数据库，如果不存在则初始化
if not exist "data\db.sqlite3" (
    echo [首次运行] 正在初始化数据库...
    mkdir data 2>nul
    python\python.exe backend\manage.py migrate --run-syncdb
    if errorlevel 1 (
        echo [错误] 数据库初始化失败！
        pause
        exit /b 1
    )
    echo [成功] 数据库初始化完成！
    echo.
)

set DB_PATH=%~dp0data\db.sqlite3

:: 启动服务器
echo [启动] 正在启动服务器...
echo.
echo ========================================
echo   服务器已启动！
echo   请在浏览器中访问: http://127.0.0.1:8000
echo
echo   按 Ctrl+C 或关闭此窗口可停止服务
echo ========================================
echo.

:: 延迟2秒后打开浏览器
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

:: 启动 Django 服务器
python\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload

pause
