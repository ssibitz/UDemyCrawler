@echo off
cls
echo.
REM pip install auto-py-to-exe
REM auto-py-to-exe
set CURR_PATH=%cd%
pyinstaller --noconfirm --onefile --windowed --icon "%CURR_PATH%/res/UDemyCrawler.ico" --add-data "%CURR_PATH%/res;res/" --add-data "%CURR_PATH%/icons;icons/"  "%CURR_PATH%/UDemyCrawler.py"