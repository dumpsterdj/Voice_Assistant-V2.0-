@echo off
rem Adjust path to python in your venv
set PYTHON_EXE=C:\Users\dhruv\PycharmProjects\VoiceAssistant\.venv\Scripts\python.exe
set MODULE=voice_assistant.main

start "" "%PYTHON_EXE%" -m %MODULE% --allow-download --allow-arbitrary
exit
