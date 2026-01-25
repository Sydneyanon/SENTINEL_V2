#!/usr/bin/env python3
"""
Diagnostic Script - Check What Code is Actually Running on Railway

This script outputs what's actually deployed and running.
Deploy this to Railway and check the logs to see the output.
"""
import os
import sys
from pathlib import Path

print("=" * 80)
print("🔍 RAILWAY CODE DIAGNOSTIC")
print("=" * 80)

# 1. Git Information
print("\n📋 GIT STATUS:")
print("-" * 80)
os.system("git status")

print("\n📝 GIT BRANCH:")
print("-" * 80)
os.system("git branch -v")

print("\n📜 RECENT COMMITS:")
print("-" * 80)
os.system("git log --oneline -10")

print("\n🔄 UNCOMMITTED CHANGES:")
print("-" * 80)
os.system("git diff HEAD --stat")

# 2. File Information
print("\n📁 FILE INFORMATION:")
print("-" * 80)

files_to_check = [
    'scoring/conviction_engine.py',
    'config.py',
    'active_token_tracker.py'
]

for filepath in files_to_check:
    if os.path.exists(filepath):
        lines = len(open(filepath).readlines())
        print(f"✅ {filepath}: {lines} lines")
    else:
        print(f"❌ {filepath}: NOT FOUND")

# 3. Search for Mystery Code
print("\n🔍 SEARCHING FOR 'BUY/SELL RATIO' CODE:")
print("-" * 80)

conviction_path = 'scoring/conviction_engine.py'
if os.path.exists(conviction_path):
    with open(conviction_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    # Search for buy/sell related code
    matches = []
    for i, line in enumerate(lines, 1):
        if 'buy' in line.lower() and 'sell' in line.lower():
            matches.append((i, line.strip()))

    if matches:
        print(f"Found {len(matches)} lines mentioning buy/sell:")
        for line_num, line in matches[:20]:  # Show first 20
            print(f"  Line {line_num}: {line[:100]}")
    else:
        print("❌ NO 'buy/sell' code found")

    # Search for specific scoring patterns
    if '"Buy/Sell Ratio"' in content or "'Buy/Sell Ratio'" in content:
        print("\n✅ FOUND 'Buy/Sell Ratio' logging!")
        for i, line in enumerate(lines, 1):
            if 'Buy/Sell Ratio' in line:
                print(f"  Line {i}: {line.strip()}")
    else:
        print("\n❌ NO 'Buy/Sell Ratio' logging found")

    # Check score denominators
    if '/113' in content:
        print("\n✅ FOUND '/113' (BASE SCORE: /113)")
        for i, line in enumerate(lines, 1):
            if '/113' in line:
                print(f"  Line {i}: {line.strip()}")
    else:
        print("\n❌ NO '/113' found (should be /85 in git)")

else:
    print("❌ conviction_engine.py NOT FOUND!")

# 4. Show actual scoring code snippet
print("\n📝 ACTUAL VOLUME SCORING CODE (lines 120-135):")
print("-" * 80)
if os.path.exists(conviction_path):
    with open(conviction_path, 'r') as f:
        lines = f.readlines()

    # Show lines around volume scoring
    start_line = 119  # 0-indexed
    end_line = 135

    if len(lines) >= end_line:
        for i in range(start_line, min(end_line, len(lines))):
            print(f"{i+1:4d}: {lines[i]}", end='')
    else:
        print(f"File only has {len(lines)} lines (git has 745)")

# 5. Environment info
print("\n🌍 ENVIRONMENT:")
print("-" * 80)
print(f"Python: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"Railway: {os.getenv('RAILWAY_ENVIRONMENT', 'Not set')}")
print(f"Git branch (env): {os.getenv('RAILWAY_GIT_BRANCH', 'Not set')}")

# 6. Sample of conviction scoring function
print("\n🔬 CONVICTION SCORING FUNCTION SIGNATURE:")
print("-" * 80)
if os.path.exists(conviction_path):
    with open(conviction_path, 'r') as f:
        content = f.read()

    # Find the analyze_token function
    if 'def analyze_token' in content:
        idx = content.index('def analyze_token')
        snippet = content[idx:idx+500]
        print(snippet[:500])
    else:
        print("❌ analyze_token function not found!")

print("\n" + "=" * 80)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 80)
print("\nCopy all of this output and share with Claude for analysis.")
