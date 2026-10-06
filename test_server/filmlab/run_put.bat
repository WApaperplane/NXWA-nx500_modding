@echo off
REM 上传 ARM 可执行文件到 NX500。
REM MSYS_NO_PATHCONV=1 是必须的：否则 Git Bash 会把 /opt/usr/... 转成
REM C:/Users/.../opt/usr/...，文件会传到完全错误的位置。
setlocal
set MSYS_NO_PATHCONV=1
set MSYS2_ARG_CONV_EXCL=*

if "%~1"=="" goto usage
set IP=%~1
set LOCAL=%~2
set REMOTE=%~3

C:\Users\31623\.workbuddy\binaries\python\versions\3.13.12\python.exe "%~dp0telnet_put.py" %IP% %LOCAL% %REMOTE%
exit /b %ERRORLEVEL%

:usage
echo 用法: run_put.bat ^<ip^> ^<local-file^> ^<remote-path^>
echo 示例: run_put.bat 192.168.0.105 out/x11probe.arm /opt/usr/nx-ks/filmlab/x11probe.arm
