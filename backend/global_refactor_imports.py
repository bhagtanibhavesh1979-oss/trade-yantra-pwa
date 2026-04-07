import os

# Files to refactor (ALL ROUTES)
files = [
    'routes/alerts.py',
    'routes/auth.py',
    'routes/indices.py',
    'routes/stream.py',
    'routes/live.py',
    'routes/paper.py',
    'routes/watchlist.py'
]

# Service instances to move to local imports
services = [
    'session_manager',
    'angel_service',
    'ws_manager',
    'paper_service',
    'live_service',
    'alert_service'
]

for f_path in files:
    if not os.path.exists(f_path): continue
    with open(f_path, 'r') as f:
        content = f.read()
    
    # Process each problematic service
    for s in services:
        import_line = f'from services.{s} import {s}'
        # If TOP LEVEL import exists (not indented)
        if import_line in content and f'\n{import_line}' in content:
            # Remove it
            content = content.replace(f'{import_line}\n', '')
            
            # Replace usage with local import + usage
            # This is a bit simple but should work for common FastAPI patterns
            content = content.replace(f'{s}.', f'from services.{s} import {s}\n    {s}.')

    with open(f_path, 'w') as f:
        f.write(content)
    print(f"Refactored {f_path}")

print("Global service import refactor complete")
