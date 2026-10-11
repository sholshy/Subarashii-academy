import sys

with open('tournament_ui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The orphaned code starts around line 860.
# Let's find exactly the line index where `            for p in self.manager.players:`
# occurs inside `rollback_to_setup_ui`
start_idx = -1
for i, line in enumerate(lines):
    if "def rollback_to_setup_ui(self):" in line:
        # Search forward for the start of orphaned code
        for j in range(i, len(lines)):
            if "            for p in self.manager.players:" in lines[j]:
                start_idx = j
                break
        break

if start_idx != -1:
    end_idx = -1
    for j in range(start_idx, len(lines)):
        if "    def show_drop_dialog(self):" in lines[j]:
            end_idx = j
            break
    
    if end_idx != -1:
        # Delete from start_idx up to end_idx - 1 (keeping the empty line before show_drop_dialog if it exists, but let's just delete strictly to end_idx)
        del lines[start_idx:end_idx]
        with open('tournament_ui.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"Deleted orphaned code from line {start_idx+1} to {end_idx}")
    else:
        print("End pattern not found.")
else:
    print("Start pattern not found.")
