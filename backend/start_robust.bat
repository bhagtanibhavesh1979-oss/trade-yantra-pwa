
@echo off
echo Starting Backend... > run_log.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8002 >> run_log.txt 2>&1
echo Done. >> run_log.txt
