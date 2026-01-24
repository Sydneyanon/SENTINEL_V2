#!/usr/bin/env python3
"""
Ralph Executor - Executes instructions from Ralph's planning output
Runs after Ralph (API tool) generates execution instructions
"""

import json
import subprocess
import sys
from pathlib import Path

def execute_edit(instruction):
    """Execute a file edit instruction"""
    file_path = instruction['file_path']
    old_string = instruction['old_string']
    new_string = instruction['new_string']

    print(f"[EXEC] Editing {file_path}")

    # Read file
    with open(file_path, 'r') as f:
        content = f.read()

    # Replace
    if old_string not in content:
        print(f"[ERROR] Old string not found in {file_path}")
        return False

    new_content = content.replace(old_string, new_string, 1)

    # Write back
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"[SUCCESS] Edited {file_path}")
    return True

def execute_bash(instruction):
    """Execute a bash command"""
    command = instruction['command']
    description = instruction.get('description', 'Running command')

    print(f"[EXEC] {description}")
    print(f"[CMD] {command}")

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=300
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode == 0:
        print(f"[SUCCESS] Command completed")
        return True
    else:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
        return False

def execute_write(instruction):
    """Create a new file"""
    file_path = instruction['file_path']
    content = instruction['content']

    print(f"[EXEC] Writing {file_path}")

    # Create parent directories if needed
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    # Write file
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"[SUCCESS] Created {file_path}")
    return True

def execute_instructions(instructions_file):
    """Execute all instructions from JSON file"""
    print(f"[EXECUTOR] Reading instructions from {instructions_file}")

    with open(instructions_file, 'r') as f:
        instructions = json.load(f)

    print(f"[EXECUTOR] Found {len(instructions)} instructions to execute")

    results = []
    for i, instruction in enumerate(instructions, 1):
        print(f"\n[EXECUTOR] Executing instruction {i}/{len(instructions)}")
        print(f"[TYPE] {instruction['type']}")

        success = False
        if instruction['type'] == 'edit':
            success = execute_edit(instruction)
        elif instruction['type'] == 'bash':
            success = execute_bash(instruction)
        elif instruction['type'] == 'write':
            success = execute_write(instruction)
        else:
            print(f"[ERROR] Unknown instruction type: {instruction['type']}")

        results.append(success)

    # Summary
    print(f"\n[EXECUTOR] Execution complete")
    print(f"[EXECUTOR] Success: {sum(results)}/{len(results)}")

    return all(results)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python executor.py <instructions.json>")
        sys.exit(1)

    instructions_file = sys.argv[1]

    if not Path(instructions_file).exists():
        print(f"[ERROR] Instructions file not found: {instructions_file}")
        sys.exit(1)

    success = execute_instructions(instructions_file)
    sys.exit(0 if success else 1)
