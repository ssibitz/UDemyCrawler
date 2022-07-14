@echo off
cls
echo.
echo Installing python installer if not already done by using pip:
pip install pyinstaller
set CURR_PATH=%cd%
pyinstaller --noconfirm --onefile --windowed --icon "%CURR_PATH%/res/UDemyCrawler.ico" --add-data "%CURR_PATH%/res;res/" --add-data "%CURR_PATH%/icons;icons/"  "%CURR_PATH%/UDemyCrawler.py"