#!/usr/bin/env python3
"""
Ralph API Runner - Uses Anthropic API directly instead of Claude CLI
"""
import os
import sys
import traceback

print("=== Ralph API Runner Starting ===", flush=True)

try:
    print("Importing anthropic...", flush=True)
    from anthropic import Anthropic
    print("✓ Anthropic imported successfully", flush=True)
except ImportError as e:
    print(f"ERROR: Failed to import anthropic: {e}", flush=True)
    print("Install with: pip install anthropic", flush=True)
    sys.exit(1)

def run_ralph_iteration():
    """Run one Ralph optimization iteration using Anthropic API"""

    try:
        print("Checking ANTHROPIC_API_KEY...", flush=True)
        # Get API key
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set", flush=True)
            return False
        print(f"✓ API key found (length: {len(api_key)})", flush=True)

        print("Reading instructions from /app/ralph/CLAUDE.md...", flush=True)
        # Read instructions
        with open('/app/ralph/CLAUDE.md', 'r') as f:
            instructions = f.read()
        print(f"✓ Instructions loaded ({len(instructions)} chars)", flush=True)

        print("Initializing Anthropic client...", flush=True)
        # Initialize client
        client = Anthropic(api_key=api_key)
        print("✓ Client initialized", flush=True)

        print("Calling Claude API (model: claude-sonnet-4-5-20250929)...", flush=True)
        # Call Claude API
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[
                {
                    "role": "user",
                    "content": instructions
                }
            ]
        )

        print("✓ API call successful", flush=True)
        print("\n" + "="*60, flush=True)
        print("RALPH'S RESPONSE:", flush=True)
        print("="*60 + "\n", flush=True)

        # Print response
        response_text = message.content[0].text
        print(response_text, flush=True)

        # Check for completion signal
        if "<promise>COMPLETE</promise>" in response_text:
            print("\n✅ Ralph completed all optimizations!", flush=True)
            return True

        return False

    except FileNotFoundError as e:
        print(f"ERROR: File not found: {e}", flush=True)
        return False
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        print(f"Traceback:\n{traceback.format_exc()}", flush=True)
        return False

if __name__ == "__main__":
    print("Starting Ralph iteration...", flush=True)
    try:
        completed = run_ralph_iteration()
        exit_code = 0 if completed else 1
        print(f"\nExiting with code: {exit_code}", flush=True)
        sys.exit(exit_code)
    except Exception as e:
        print(f"FATAL ERROR: {e}", flush=True)
        print(f"Traceback:\n{traceback.format_exc()}", flush=True)
        sys.exit(1)
