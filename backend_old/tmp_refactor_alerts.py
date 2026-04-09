import os

file_path = 'routes/alerts.py'
if os.path.exists(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        # Remove top level import
        if 'from services.session_manager import session_manager' in line:
            continue
        
        # Add local import before each usage
        if 'session_manager.get_session' in line or 'session_manager.save_session' in line:
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}from services.session_manager import session_manager\n")
        
        new_lines.append(line)

    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    print(f"Refactored {file_path}")
else:
    print(f"File {file_path} not found")
