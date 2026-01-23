"""
Web-based Telegram Authentication
Run this temporarily on Railway to authenticate via browser
"""
import os
import asyncio
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient
import uvicorn

app = FastAPI()

# Credentials
api_id = int(os.getenv('TELEGRAM_API_ID', '33811421'))
api_hash = os.getenv('TELEGRAM_API_HASH', 'ec5a841d8e108a980c3af61ed4f97df9')
phone = os.getenv('TELEGRAM_PHONE', '+61413194229')

# Global client
client = None
auth_state = {
    'status': 'not_started',
    'message': '',
    'phone_code_hash': None
}

@app.get("/", response_class=HTMLResponse)
async def home():
    return f"""
    <html>
        <head>
            <title>Telegram Authentication</title>
            <style>
                body {{ font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }}
                button {{ padding: 10px 20px; font-size: 16px; cursor: pointer; }}
                input {{ padding: 8px; font-size: 16px; width: 200px; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
                .info {{ color: blue; }}
            </style>
        </head>
        <body>
            <h1>🔐 Telegram Authentication</h1>
            <p><strong>Status:</strong> <span class="info">{auth_state['status']}</span></p>
            <p>{auth_state['message']}</p>

            <h3>Step 1: Request Code</h3>
            <form action="/send-code" method="post">
                <button type="submit">Send Verification Code to +61413194229</button>
            </form>

            <hr>

            <h3>Step 2: Enter Code</h3>
            <form action="/verify-code" method="post">
                <input type="text" name="code" placeholder="Enter code from Telegram" required>
                <button type="submit">Verify Code</button>
            </form>

            <hr>

            <p><small>Phone: {phone}</small></p>
        </body>
    </html>
    """

@app.post("/send-code")
async def send_code():
    global client, auth_state

    try:
        # Create client
        client = TelegramClient('sentinel_session', api_id, api_hash)
        await client.connect()

        # Send code
        result = await client.send_code_request(phone)
        auth_state['phone_code_hash'] = result.phone_code_hash
        auth_state['status'] = 'code_sent'
        auth_state['message'] = f'✅ Verification code sent to {phone}! Check Telegram and enter the code below.'

        return {"status": "success", "message": "Code sent! Check your Telegram."}

    except Exception as e:
        auth_state['status'] = 'error'
        auth_state['message'] = f'❌ Error: {str(e)}'
        return {"status": "error", "message": str(e)}

@app.post("/verify-code")
async def verify_code(code: str = Form(...)):
    global client, auth_state

    try:
        if not client or not auth_state['phone_code_hash']:
            auth_state['message'] = '❌ Please request a code first!'
            return {"status": "error", "message": "Request code first"}

        # Sign in with code
        await client.sign_in(phone, code, phone_code_hash=auth_state['phone_code_hash'])

        # Get user info
        me = await client.get_me()

        auth_state['status'] = 'authenticated'
        auth_state['message'] = f'🎉 SUCCESS! Authenticated as {me.first_name} (@{me.username or "no username"})'

        # Session file is now created!
        await client.disconnect()

        return {
            "status": "success",
            "message": f"✅ Authenticated! Session file created. You can now stop this server and commit sentinel_session.session"
        }

    except Exception as e:
        auth_state['status'] = 'error'
        auth_state['message'] = f'❌ Error: {str(e)}'
        return {"status": "error", "message": str(e)}

@app.get("/status")
async def status():
    return auth_state

if __name__ == "__main__":
    print("=" * 70)
    print("WEB-BASED TELEGRAM AUTHENTICATION")
    print("=" * 70)
    print("\n1. Open browser to: http://localhost:8001")
    print("2. Click 'Send Verification Code'")
    print("3. Enter code from Telegram")
    print("4. Session file will be created: sentinel_session.session")
    print("5. Commit and push the session file")
    print("\n" + "=" * 70)
    uvicorn.run(app, host="0.0.0.0", port=8001)
