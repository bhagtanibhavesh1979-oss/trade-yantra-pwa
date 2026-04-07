import os

log_file = r"c:\Users\bhave\Downloads\trade-yantra\backend\backend_debug.log"

if os.path.exists(log_file):
    with open(log_file, 'rb') as f:
        try:
            f.seek(-5000, os.SEEK_END)
        except OSError:
            # File is smaller than 5000 bytes
            f.seek(0)
        
        content = f.read().decode('utf-8', errors='ignore')
        print(content)
else:
    print("Log file not found.")
