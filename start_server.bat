@echo off
SETLOCAL

:: Activate the virtual environment
CALL sub_genie\Scripts\activate

python websocket_server.py

pause
ENDLOCAL