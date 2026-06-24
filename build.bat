@echo off
echo Building dictation-me.exe...
pip install pyinstaller --quiet
pyinstaller dictation-me.spec --clean --noconfirm
echo.
echo Done! Find the exe at: dist\dictation-me.exe
pause
