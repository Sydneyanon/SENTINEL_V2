"""
Telegram Alpha Group Monitor (Built-in)
Monitors Telegram groups for Solana token calls using Telethon

Alternative to solana-token-scraper - runs directly in SENTINEL
"""
import os
import re
import asyncio
from typing import Set, Dict, List
from datetime import datetime
from loguru import logger
from telethon import TelegramClient, events
from telethon.tl.types import Message


class TelegramMonitor:
    """
    Monitors Telegram groups for Solana token contract addresses
    Integrates directly with SENTINEL's telegram_calls_cache
    """

    def __init__(self, telegram_calls_cache: Dict):
        """
        Initialize Telegram monitor

        Args:
            telegram_calls_cache: Reference to main.telegram_calls_cache
        """
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.phone = os.getenv('TELEGRAM_PHONE')  # Optional: for first-time auth

        self.telegram_calls_cache = telegram_calls_cache
        self.client = None
        self.monitored_groups: Dict[int, str] = {}  # {channel_id: group_name}

        # Solana CA regex pattern (base58, 32-44 chars)
        self.ca_pattern = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

        # Known non-token addresses to ignore
        self.ignore_addresses = {
            'So11111111111111111111111111111111111111112',  # Wrapped SOL
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
        }

        if not self.api_id or not self.api_hash:
            logger.warning("⚠️ TELEGRAM_API_ID and TELEGRAM_API_HASH not set - Telegram monitoring disabled")
            logger.info("   Get credentials at: https://my.telegram.org")

    async def initialize(self, monitored_groups: Dict[int, str]):
        """
        Initialize Telegram client and set up monitoring

        Args:
            monitored_groups: {channel_id: group_name} to monitor
        """
        if not self.api_id or not self.api_hash:
            logger.warning("⚠️ Telegram monitor not initialized (missing credentials)")
            return False

        try:
            self.monitored_groups = monitored_groups

            # Create client
            self.client = TelegramClient(
                'sentinel_session',  # Session file
                int(self.api_id),
                self.api_hash
            )

            # Connect
            await self.client.start(phone=self.phone)

            me = await self.client.get_me()
            logger.info(f"✅ Telegram connected: @{me.username or me.phone}")
            logger.info(f"🔍 Monitoring {len(self.monitored_groups)} group(s)")

            # Set up message handler
            @self.client.on(events.NewMessage(chats=list(self.monitored_groups.keys())))
            async def message_handler(event: Message):
                await self._handle_message(event)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram monitor: {e}")
            return False

    async def _handle_message(self, event: Message):
        """Handle new messages in monitored groups"""
        try:
            # Get message text
            text = event.message.message
            if not text:
                return

            # Get group info for logging
            chat_id = event.chat_id
            group_name = self.monitored_groups.get(chat_id, f"group_{chat_id}")

            # Extract Solana CAs from message
            potential_cas = self.ca_pattern.findall(text)
            if not potential_cas:
                return

            logger.info(f"📨 Message from {group_name} has {len(potential_cas)} CA(s)")

            # Process each CA found
            for ca in potential_cas:
                # Skip known non-token addresses
                if ca in self.ignore_addresses:
                    continue

                # Basic validation (Solana CAs are typically 32-44 chars)
                if len(ca) < 32 or len(ca) > 44:
                    continue

                # Add to cache
                await self._add_call_to_cache(ca, group_name)

        except Exception as e:
            logger.error(f"❌ Error handling Telegram message: {e}")

    async def _add_call_to_cache(self, token_address: str, group_name: str):
        """
        Add detected call to telegram_calls_cache

        Args:
            token_address: Solana CA
            group_name: Name of the group that called it
        """
        try:
            now = datetime.utcnow()

            logger.info(f"🔥 TELEGRAM CALL detected: {token_address[:8]}... (group: {group_name})")

            # Add to cache (same structure as webhook)
            if token_address not in self.telegram_calls_cache:
                self.telegram_calls_cache[token_address] = {
                    'mentions': [],
                    'first_seen': now,
                    'groups': set()
                }

            # Add this mention
            self.telegram_calls_cache[token_address]['mentions'].append({
                'timestamp': now,
                'group': group_name
            })
            self.telegram_calls_cache[token_address]['groups'].add(group_name)

            mention_count = len(self.telegram_calls_cache[token_address]['mentions'])
            group_count = len(self.telegram_calls_cache[token_address]['groups'])

            logger.info(f"   📊 Total mentions: {mention_count} from {group_count} group(s)")

        except Exception as e:
            logger.error(f"❌ Error adding call to cache: {e}")

    async def run(self):
        """Run the monitor (blocking)"""
        if not self.client:
            logger.warning("⚠️ Telegram monitor not initialized")
            return

        try:
            logger.info("🔄 Telegram monitor running...")
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"❌ Telegram monitor crashed: {e}")

    async def stop(self):
        """Stop the monitor"""
        if self.client:
            await self.client.disconnect()
            logger.info("🛑 Telegram monitor stopped")


# Helper script functions

async def list_user_groups():
    """
    Helper function to list all groups the user is in
    Returns: List of (group_id, group_name) tuples
    """
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')

    if not api_id or not api_hash:
        print("❌ TELEGRAM_API_ID and TELEGRAM_API_HASH must be set")
        print("   Get credentials at: https://my.telegram.org")
        return []

    client = TelegramClient('list_groups_session', int(api_id), api_hash)

    try:
        await client.start(phone=phone)

        print("\n🔍 Fetching your Telegram groups...\n")

        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                # Get clean group name
                group_name = dialog.name
                group_id = dialog.id

                # Format for display
                groups.append((group_id, group_name))
                print(f"  {len(groups)}. {group_name}")
                print(f"     ID: {group_id}")
                print()

        await client.disconnect()

        print(f"\n✅ Found {len(groups)} groups/channels")
        return groups

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


async def generate_config_template(groups: List[tuple]):
    """
    Generate Python config template from group list

    Args:
        groups: List of (group_id, group_name) tuples
    """
    if not groups:
        print("No groups to generate config for")
        return

    print("\n" + "="*70)
    print("TELEGRAM GROUPS CONFIG (add to config.py)")
    print("="*70)
    print("\n# Telegram Groups to Monitor")
    print("TELEGRAM_GROUPS = {")

    for group_id, group_name in groups:
        # Clean group name for use as dict key
        safe_name = group_name.lower().replace(' ', '_').replace('-', '_')
        safe_name = re.sub(r'[^a-z0-9_]', '', safe_name)

        print(f"    {group_id}: '{safe_name}',  # {group_name}")

    print("}")
    print("\n" + "="*70)


# Standalone helper script
if __name__ == "__main__":
    async def main():
        print("="*70)
        print("TELEGRAM GROUP FINDER")
        print("="*70)
        print("\nThis script will:")
        print("1. Connect to your Telegram account")
        print("2. List all groups you're in")
        print("3. Generate config.py template")
        print("\nMake sure you've set:")
        print("  export TELEGRAM_API_ID='your_api_id'")
        print("  export TELEGRAM_API_HASH='your_api_hash'")
        print("  export TELEGRAM_PHONE='+1234567890'  # (optional)")
        print("\n" + "="*70 + "\n")

        # List groups
        groups = await list_user_groups()

        if groups:
            # Generate config
            await generate_config_template(groups)

            print("\n💡 Next steps:")
            print("1. Copy the TELEGRAM_GROUPS config above")
            print("2. Add it to config.py")
            print("3. Edit to keep only groups you want to monitor")
            print("4. Restart SENTINEL")

    asyncio.run(main())
