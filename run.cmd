@echo off
cls
d:
cd D:\UDemyCrawler
start "C:\Users\Petra Sibitz\AppData\Local\Programs\Python\Python39\pythonw.exe" "C:\Users\Petra Sibitz\AppData\Local\JetBrains\Toolbox\apps\PyCharm-P\ch-0\221.5591.52\plugins\python\helpers\pydev\pydevd.py" --multiprocess --qt-support=auto --client 127.0.0.1 --port 51594 --file D:/UDemyCrawler/UDemyCrawler.py


REM start pythonw.exe UDemyCrawler.py