@echo off
cd backend
set PYTHONIOENCODING=utf-8
python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload
pause
