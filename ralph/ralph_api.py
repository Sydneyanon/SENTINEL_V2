#!/usr/bin/env python3
"""
Ralph API Runner - Uses Anthropic API directly instead of Claude CLI
"""
import os
import sys
from anthropic import Anthropic

def run_ralph_iteration():
    """Run one Ralph optimization iteration using Anthropic API"""

    # Get API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return False

    # Read instructions
    with open('/app/ralph/CLAUDE.md', 'r') as f:
        instructions = f.read()

    # Initialize client
    client = Anthropic(api_key=api_key)

    print("Running Ralph optimization iteration...")

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

    # Print response
    response_text = message.content[0].text
    print(response_text)

    # Check for completion signal
    if "<promise>COMPLETE</promise>" in response_text:
        print("\n✅ Ralph completed all optimizations!")
        return True

    return False

if __name__ == "__main__":
    completed = run_ralph_iteration()
    sys.exit(0 if completed else 1)
