import os

log_file = r"c:\Users\bhave\Downloads\trade-yantra\backend\backend_debug.log"

if os.path.exists(log_file):
    try:
        # Read the last 20000 bytes directly
        with open(log_file, 'rb') as f:
            f.seek(-20000, os.SEEK_END)
            content = f.read().decode('utf-8', errors='ignore')
            lines = content.splitlines()
            printed_something = False
            for i, line in enumerate(lines):
                if "Error" in line or "Traceback" in line or "Exception" in line:
                    print(line.strip())
                    printed_something = True
                    # Print subsequent 5 lines for context
                    for j in range(1, 6):
                        if i + j < len(lines):
                            print(lines[i + j].strip())
            
            if not printed_something:
                print("No error keywords found in last 20KB.")

    except Exception as e:
        print(f"Failed to read: {e}")
else:
    print("Log file not found.")

