import time
import os
import sys
from datetime import datetime

def monitor_logs():
    log_files = [
        "backend/backend_debug.log",
        "backend/backend_error.log",
        "backend/backend_out.log"
    ]
    
    # Resolve absolute paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    abs_log_files = [os.path.join(base_dir, f) for f in log_files]
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Real-time Monitor...")
    print(f"Monitoring: {', '.join(log_files)}")
    print("Press Ctrl+C to stop.\n")
    
    files = {}
    for fpath in abs_log_files:
        if os.path.exists(fpath):
            f = open(fpath, 'r', encoding='utf-8', errors='ignore')
            # Seek to end
            f.seek(0, 2)
            files[fpath] = f
        else:
            print(f"[WARN] Log file not found: {fpath}")

    while True:
        try:
            had_data = False
            for fpath, f in files.items():
                line = f.readline()
                if line:
                    had_data = True
                    fname = os.path.basename(fpath)
                    
                    # Highlights
                    if "ERROR" in line or "Exception" in line or "Rejected" in line:
                        print(f"\033[91m[{fname}] {line.strip()}\033[0m") # Red
                    elif "TRADE" in line or "Order Placed" in line or "SUCCESS" in line:
                        print(f"\033[92m[{fname}] {line.strip()}\033[0m") # Green
                    elif "WARNING" in line or "WARN" in line:
                         print(f"\033[93m[{fname}] {line.strip()}\033[0m") # Yellow
                    elif "price_update" in line or "Heartbeat" in line:
                        continue # Skip noise
                    else:
                        print(f"[{fname}] {line.strip()}")
            
            if not had_data:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nStopping monitor.")
            break
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    # Enable Colors on Windows
    os.system('color')
    monitor_logs()
