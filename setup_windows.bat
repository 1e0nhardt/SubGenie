@echo off
SETLOCAL

:: Check for Python
py -V 2>nul
IF %ERRORLEVEL% NEQ 0 (
    echo Python is not installed.
    echo Please download and install Python from https://www.python.org/downloads/
    pause
    EXIT /B
)

:: Create a virtual environment if it doesn't exist
IF NOT EXIST "sub_genie" (
    echo Creating virtual environment...
    py -m venv sub_genie
)

:: Activate the virtual environment
CALL sub_genie\Scripts\activate

:: Upgrade pip and install requirements
echo Upgrading pip and installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: 解决 OMP: Error #15: Initializing libiomp5md.dll, but found libiomp5md.dll already initialized.
move sub_genie\Library\bin\libiomp5md.dll sub_genie\Library\libiomp5md.dll

echo Setup complete.
pause
ENDLOCAL