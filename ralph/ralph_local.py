#!/usr/bin/env python3
"""
Ralph Local Runner - Runs Ralph optimization loop in Claude Code session
Reduced logging to avoid rate limits
"""
import os
import sys
from anthropic import Anthropic

def run_ralph_iteration():
    """Run one Ralph optimization iteration using Anthropic API"""

    # Get API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        return False

    # Read instructions
    instructions_path = os.path.join(os.path.dirname(__file__), 'CLAUDE.md')
    with open(instructions_path, 'r') as f:
        instructions = f.read()

    print(f"🤖 Ralph starting optimization cycle...")
    print(f"📖 Instructions: {len(instructions)} chars")

    # Call Claude API
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        messages=[{"role": "user", "content": instructions}]
    )

    # Print response (this is Ralph's analysis and actions)
    response_text = message.content[0].text
    print("\n" + "="*60)
    print("RALPH'S RESPONSE:")
    print("="*60 + "\n")
    print(response_text)

    # Check for completion signal
    if "<promise>COMPLETE</promise>" in response_text:
        print("\n✅ Ralph completed all optimizations!")
        return True

    return False

if __name__ == "__main__":
    try:
        completed = run_ralph_iteration()
        sys.exit(0 if completed else 1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
