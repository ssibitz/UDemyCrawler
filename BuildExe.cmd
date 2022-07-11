@echo off
cls
echo.
REM pip install auto-py-to-exe
REM auto-py-to-exe
set CURR_PATH=%cd%
pyinstaller --noconfirm --onefile --windowed --icon "%CURR_PATH%/UDemyCrawler.ico" --add-data "%CURR_PATH%/UDemyCrawler.ico;."  "%CURR_PATH%/UDemyCrawler.py"