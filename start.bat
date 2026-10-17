@echo off
rem 双击启动 B站学习助手（无控制台窗口）
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if errorlevel 1 (
    echo 未找到 pythonw.exe，请先安装 Python 3.10 及以上版本。
    pause
    exit /b 1
)
start "" pythonw.exe app.py
