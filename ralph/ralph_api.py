#!/usr/bin/env python3
"""
Ralph API Runner - Uses Anthropic API directly instead of Claude CLI
"""
import os
import sys
import traceback

# Environment-based logging (reduces Railway log spam)
DEBUG = os.getenv('RALPH_DEBUG', '').lower() == 'true'

def log_debug(msg):
    """Log debug messages only if RALPH_DEBUG=true"""
    if DEBUG:
        print(f"[DEBUG] {msg}", flush=True)

def log_info(msg):
    """Log important info messages"""
    print(f"[INFO] {msg}", flush=True)

def log_error(msg):
    """Log errors"""
    print(f"[ERROR] {msg}", flush=True)

try:
    from anthropic import Anthropic
    log_debug("Anthropic SDK imported successfully")
except ImportError as e:
    log_error(f"Failed to import anthropic: {e}")
    log_error("Install with: pip install anthropic")
    sys.exit(1)

def run_ralph_iteration():
    """Run one Ralph optimization iteration using Anthropic API"""

    try:
        # Get API key
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            log_error("ANTHROPIC_API_KEY not set")
            return False
        log_debug(f"API key found (length: {len(api_key)})")

        # Read instructions - use relative path that works both locally and in container
        script_dir = os.path.dirname(os.path.abspath(__file__))
        claude_md_path = os.path.join(script_dir, 'CLAUDE.md')
        with open(claude_md_path, 'r') as f:
            instructions = f.read()
        log_debug(f"Instructions loaded ({len(instructions)} chars)")

        # Initialize client
        client = Anthropic(api_key=api_key)
        log_info("Calling Claude API for optimization iteration...")

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

        log_info("API call successful")
        print("\n" + "="*60, flush=True)
        print("RALPH'S RESPONSE:", flush=True)
        print("="*60 + "\n", flush=True)

        # Print response (important - keep this)
        response_text = message.content[0].text
        print(response_text, flush=True)

        # Check for completion signal
        if "<promise>COMPLETE</promise>" in response_text:
            log_info("Ralph completed all optimizations!")
            return True

        return False

    except FileNotFoundError as e:
        log_error(f"File not found: {e}")
        return False
    except Exception as e:
        log_error(f"{e}")
        if DEBUG:
            print(f"Traceback:\n{traceback.format_exc()}", flush=True)
        return False

if __name__ == "__main__":
    log_info("Ralph iteration starting...")
    try:
        completed = run_ralph_iteration()
        exit_code = 0 if completed else 1
        log_info(f"Ralph iteration finished (exit code: {exit_code})")
        sys.exit(exit_code)
    except Exception as e:
        log_error(f"FATAL: {e}")
        if DEBUG:
            print(f"Traceback:\n{traceback.format_exc()}", flush=True)
        sys.exit(1)
