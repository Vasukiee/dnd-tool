@echo off
cd /d "%~dp0"
echo.
echo  Campaign Tool
echo ===============
echo.

REM Apre il browser dopo 3 secondi, in parallelo
start /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"

echo Server in avvio... il browser si aprira' automaticamente tra qualche secondo.
echo Per fermare il server, premi Ctrl+C in questa finestra.
echo.

python app.py

echo.
echo Il server e' stato fermato.
pause
