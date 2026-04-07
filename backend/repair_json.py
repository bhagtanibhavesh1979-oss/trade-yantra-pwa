import json
import os
import shutil

def repair_json(filepath):
    print(f"Repairing {filepath}...")
    if not os.path.exists(filepath):
        print("File does not exist.")
        return

    # Create backup first
    backup = filepath + ".repair_bak"
    shutil.copy2(filepath, backup)
    print(f"Backup created: {backup}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to find where the first valid JSON ends
        # We find the LAST '}' and try to parse up to there
        last_brace = content.rfind('}')
        if last_brace == -1:
            print("No '}' found.")
            return

        # Attempt to find the correct closing brace if there's trailing garbage
        repaired_data = None
        current_pos = last_brace
        while current_pos > 0:
            try:
                candidate = content[:current_pos+1]
                repaired_data = json.loads(candidate)
                print(f"Success! Found valid JSON ending at index {current_pos}")
                break
            except json.JSONDecodeError:
                # Look for the previous '}'
                current_pos = content.rfind('}', 0, current_pos)
        
        if repaired_data:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(repaired_data, f, indent=4)
            print("File repaired successfully.")
        else:
            print("Could not find any valid JSON prefix.")
            # Fallback: if it's multiple objects concatenated, the error might be elsewhere
            # But "Extra data" usually means valid JSON + garbage
    except Exception as e:
        print(f"Error during repair: {e}")

if __name__ == "__main__":
    repair_json(r"backend/data/sessions.json")
    repair_json(r"backend/data/sessions.json.bak")
