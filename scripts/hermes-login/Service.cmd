@echo off
REM Service.cmd - Windows Task Scheduler trampoline for hermes login refresh
REM Per T9 pattern: cmd sets env, redirects to log, propagates exit
set HERMES_HOME=%USERPROFILE%\.hermes
set LOG_FILE=%HERMES_HOME%\logs\login-refresh-%date:~-4,4%%date:~-10,2%%date:~-7,2%.log
if not exist "%HERMES_HOME%\logs" mkdir "%HERMES_HOME%\logs"
"C:\Program Files\Git\usr\bin\bash.exe" "%HERMES_HOME%\bin\hermes-login-refresh.sh" >> "%LOG_FILE%" 2>&1
exit /b %ERRORLEVEL%