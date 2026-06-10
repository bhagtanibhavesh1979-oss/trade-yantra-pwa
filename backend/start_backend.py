import os
import subprocess
import time
import sys

def kill_port(port):
    try:
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode()
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                print(f"Killing process {pid} on port {port}")
                os.system(f"taskkill /F /PID {pid}")
    except:
        pass

if __name__ == "__main__":
    print("--- EMERGENCY BACKEND RESTART ---")
    kill_port(8002)
    time.sleep(1)
    
    print("Starting main.py...")
    # Using subprocess.Popen so we can see output
    process = subprocess.Popen([sys.executable, "main.py"], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.STDOUT,
                             text=True,
                             encoding='utf-8')
                             
    for line in process.stdout:
        print(line, end='')
        if "Uvicorn running" in line:
            print("\nSERVER IS UP AND RUNNING!")
