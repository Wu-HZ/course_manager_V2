@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo      排课系统便携包打包工具
echo ========================================
echo.

cd /d "%~dp0.."

set PYTHON_VERSION=3.11.9
set PYTHON_EMBED_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip
set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py
set OUTPUT_DIR=portable_build
set PORTABLE_DIR=%OUTPUT_DIR%\排课系统

:: 检查必要工具
where curl >nul 2>&1
if errorlevel 1 (
    echo [错误] 需要 curl，请确保已安装或使用 Windows 10 以上版本
    pause
    exit /b 1
)

:: 清理旧的构建目录
if exist "%OUTPUT_DIR%" (
    echo [清理] 删除旧的构建目录...
    rmdir /s /q "%OUTPUT_DIR%"
)

mkdir "%PORTABLE_DIR%"
mkdir "%PORTABLE_DIR%\python"
mkdir "%PORTABLE_DIR%\data"

echo.
echo [1/6] 下载 Python 嵌入式版本...
curl -L -o "%OUTPUT_DIR%\python-embed.zip" "%PYTHON_EMBED_URL%"
if errorlevel 1 (
    echo [错误] Python 下载失败！
    pause
    exit /b 1
)

echo.
echo [2/6] 解压 Python...
powershell -Command "Expand-Archive -Path '%OUTPUT_DIR%\python-embed.zip' -DestinationPath '%PORTABLE_DIR%\python' -Force"

:: 修改 python311._pth 以支持 pip
echo [配置] 启用 pip 支持...
(
    echo python311.zip
    echo .
    echo Lib\site-packages
    echo import site
) > "%PORTABLE_DIR%\python\python311._pth"

echo.
echo [3/6] 安装 pip...
curl -L -o "%PORTABLE_DIR%\python\get-pip.py" "%GET_PIP_URL%"
"%PORTABLE_DIR%\python\python.exe" "%PORTABLE_DIR%\python\get-pip.py" --no-warn-script-location
del "%PORTABLE_DIR%\python\get-pip.py"

echo.
echo [4/6] 安装 Python 依赖...
"%PORTABLE_DIR%\python\python.exe" -m pip install --no-warn-script-location -r backend\requirements.txt
if errorlevel 1 (
    echo [错误] Python 依赖安装失败！
    pause
    exit /b 1
)

echo.
echo [5/6] 构建前端...
cd frontend
call npm install
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败！
    pause
    exit /b 1
)
cd ..

echo.
echo [6/6] 复制文件...
:: 复制后端代码
xcopy /E /I /Y "backend" "%PORTABLE_DIR%\backend"
:: 复制前端构建
xcopy /E /I /Y "frontend\dist" "%PORTABLE_DIR%\frontend\dist"
:: 复制启动脚本
copy /Y "portable\启动.bat" "%PORTABLE_DIR%\"
copy /Y "portable\停止.bat" "%PORTABLE_DIR%\"

:: 删除不需要的文件
del /q "%PORTABLE_DIR%\backend\db.sqlite3" 2>nul
rmdir /s /q "%PORTABLE_DIR%\backend\__pycache__" 2>nul
rmdir /s /q "%PORTABLE_DIR%\backend\core\__pycache__" 2>nul
rmdir /s /q "%PORTABLE_DIR%\backend\scheduler\__pycache__" 2>nul
rmdir /s /q "%PORTABLE_DIR%\backend\config\__pycache__" 2>nul
rmdir /s /q "%PORTABLE_DIR%\backend\core\migrations\__pycache__" 2>nul

:: 创建压缩包
echo.
echo [打包] 创建 ZIP 压缩包...
powershell -Command "Compress-Archive -Path '%PORTABLE_DIR%' -DestinationPath '%OUTPUT_DIR%\排课系统.zip' -Force"

echo.
echo ========================================
echo  打包完成！
echo  输出目录: %OUTPUT_DIR%\
echo  - 排课系统\     (便携版文件夹)
echo  - 排课系统.zip  (压缩包)
echo ========================================
echo.

:: 清理临时文件
del /q "%OUTPUT_DIR%\python-embed.zip" 2>nul

pause
