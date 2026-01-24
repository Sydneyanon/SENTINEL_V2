"""
Telegram Alpha Group Monitor (Built-in)
Monitors Telegram groups for Solana token calls using Telethon

Alternative to solana-token-scraper - runs directly in SENTINEL

OPT-028: Enhanced reliability with reconnection logic and health checks
"""
import os
import re
import asyncio
from typing import Set, Dict, List
from datetime import datetime, timedelta
from loguru import logger
from telethon import TelegramClient, events
from telethon.tl.types import Message
from telethon.errors import (
    FloodWaitError,
    AuthKeyUnregisteredError,
    PhoneNumberBannedError,
    NetworkMigrateError,
    ConnectionError as TelethonConnectionError
)


class TelegramMonitor:
    """
    Monitors Telegram groups for Solana token contract addresses
    Integrates directly with SENTINEL's telegram_calls_cache
    """

    def __init__(self, telegram_calls_cache: Dict, active_tracker=None):
        """
        Initialize Telegram monitor

        Args:
            telegram_calls_cache: Reference to main.telegram_calls_cache
            active_tracker: Reference to ActiveTokenTracker for starting tracking
        """
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.phone = os.getenv('TELEGRAM_PHONE')  # Optional: for first-time auth

        self.telegram_calls_cache = telegram_calls_cache
        self.active_tracker = active_tracker  # OPT-052: For triggering tracking
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

        # OPT-028: Reconnection and health check tracking
        self.max_reconnect_attempts = 10
        self.reconnect_base_delay = 5  # seconds
        self.reconnect_max_delay = 300  # 5 minutes max
        self.last_message_time = None
        self.health_check_interval = 600  # 10 minutes
        self.connection_failures = 0
        self.is_running = False

        if not self.api_id or not self.api_hash:
            logger.warning("⚠️ TELEGRAM_API_ID and TELEGRAM_API_HASH not set - Telegram monitoring disabled")
            logger.info("   Get credentials at: https://my.telegram.org")

    async def initialize(self, monitored_groups: Dict[int, str]):
        """
        Initialize Telegram client and set up monitoring

        Args:
            monitored_groups: {channel_id: group_name} to monitor
        """
        logger.info("🔧 TELEGRAM MONITOR DIAGNOSTIC:")
        logger.info(f"   API_ID present: {bool(self.api_id)}")
        logger.info(f"   API_HASH present: {bool(self.api_hash)}")
        logger.info(f"   Phone present: {bool(self.phone)}")
        logger.info(f"   Groups to monitor: {len(monitored_groups)}")

        if not self.api_id or not self.api_hash:
            logger.warning("⚠️ Telegram monitor not initialized (missing credentials)")
            logger.warning("   Set TELEGRAM_API_ID and TELEGRAM_API_HASH in Railway")
            logger.warning("   Get credentials at: https://my.telegram.org")
            return False

        try:
            self.monitored_groups = monitored_groups

            # Create client
            logger.info("📱 Creating Telegram client...")
            self.client = TelegramClient(
                'sentinel_session',  # Session file
                int(self.api_id),
                self.api_hash
            )

            # Connect
            logger.info("🔌 Connecting to Telegram...")
            await self.client.start(phone=self.phone)

            me = await self.client.get_me()
            logger.info(f"✅ Telegram connected: @{me.username or me.phone}")
            logger.info(f"🔍 Monitoring {len(self.monitored_groups)} group(s):")
            for group_id, group_name in list(self.monitored_groups.items())[:5]:
                logger.info(f"   - {group_name} ({group_id})")
            if len(self.monitored_groups) > 5:
                logger.info(f"   ... and {len(self.monitored_groups) - 5} more")

            # Set up message handler
            @self.client.on(events.NewMessage(chats=list(self.monitored_groups.keys())))
            async def message_handler(event: Message):
                await self._handle_message(event)

            logger.info("✅ Message handler registered - listening for calls!")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram monitor: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def _handle_message(self, event: Message):
        """
        OPT-028: Handle new messages in monitored groups with health tracking
        """
        try:
            # OPT-028: Update last message time for health check
            self.last_message_time = datetime.utcnow()

            # Get message text
            text = event.message.message
            if not text:
                return

            # Debug: Log every 100th message to show monitor is active
            if not hasattr(self, '_message_count'):
                self._message_count = 0
                self._calls_detected = 0
            self._message_count += 1
            if self._message_count % 100 == 0:
                logger.info(f"📬 Telegram monitor active: {self._message_count} messages processed, {self._calls_detected} calls detected")

            # Get group info for logging
            chat_id = event.chat_id
            group_name = self.monitored_groups.get(chat_id, f"group_{chat_id}")

            # Extract Solana CAs from message (multiple methods)
            potential_cas = set()

            # Method 1: Direct CA regex match
            direct_matches = self.ca_pattern.findall(text)
            potential_cas.update(direct_matches)

            # Method 2: Extract from pump.fun URLs
            # Matches: pump.fun/GDfn8... or pump.fun/coin/GDfn8...
            pump_pattern = r'pump\.fun(?:/coin)?/([1-9A-HJ-NP-Za-km-z]{32,44})'
            pump_matches = re.findall(pump_pattern, text, re.IGNORECASE)
            potential_cas.update(pump_matches)

            # Method 3: Extract from dexscreener URLs
            # Matches: dexscreener.com/solana/GDfn8...
            dex_pattern = r'dexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})'
            dex_matches = re.findall(dex_pattern, text, re.IGNORECASE)
            potential_cas.update(dex_matches)

            if not potential_cas:
                return

            logger.info(f"📨 Message from {group_name} has {len(potential_cas)} CA(s)")
            logger.debug(f"   Message preview: {text[:100]}...")

            # Process each CA found
            for ca in potential_cas:
                # Skip known non-token addresses
                if ca in self.ignore_addresses:
                    logger.debug(f"   ⏭️  Skipped (known address): {ca[:8]}...")
                    continue

                # Basic validation (Solana CAs are typically 32-44 chars)
                if len(ca) < 32 or len(ca) > 44:
                    logger.debug(f"   ⏭️  Skipped (invalid length {len(ca)}): {ca}")
                    continue

                # Add to cache
                await self._add_call_to_cache(ca, group_name)
                self._calls_detected += 1

        except Exception as e:
            logger.error(f"❌ Error handling Telegram message: {e}")

    async def _add_call_to_cache(self, token_address: str, group_name: str):
        """
        Add detected call to telegram_calls_cache
        OPT-028: Enhanced logging with timestamps
        OPT-052: Triggers full analysis just like KOL buys!

        Args:
            token_address: Solana CA
            group_name: Name of the group that called it
        """
        try:
            now = datetime.utcnow()

            logger.info(f"🔥 TELEGRAM CALL detected: {token_address[:8]}... (group: {group_name})")
            logger.info(f"   Timestamp: {now.isoformat()}")  # OPT-028: Log timestamp for tracking

            # Add to cache (same structure as webhook)
            if token_address not in self.telegram_calls_cache:
                self.telegram_calls_cache[token_address] = {
                    'mentions': [],
                    'first_seen': now,
                    'groups': set(),
                    'tracked': False  # Track if we've started tracking this CA
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

            # OPT-052: Start tracking IMMEDIATELY (same as KOL buy)
            # This enables full analysis: data quality, emergency stops, rug detection, etc.
            if not self.telegram_calls_cache[token_address]['tracked']:
                logger.info(f"   🎯 OPT-052: Starting full analysis (same as KOL buy)")
                self.telegram_calls_cache[token_address]['tracked'] = True

                # Trigger tracking if active_tracker is available
                if self.active_tracker:
                    try:
                        await self.active_tracker.start_tracking(
                            token_address,
                            source='telegram_call'
                        )
                        logger.info(f"   ✅ Tracking started for {token_address[:8]}...")
                    except Exception as track_err:
                        logger.error(f"   ❌ Failed to start tracking: {track_err}")
                else:
                    logger.warning(f"   ⚠️  active_tracker not available (will track via webhook)")

        except Exception as e:
            logger.error(f"❌ Error adding call to cache: {e}")

    async def run(self):
        """
        OPT-028: Run the monitor with auto-recovery (blocking)
        """
        if not self.client:
            logger.warning("⚠️ Telegram monitor not initialized")
            return

        self.is_running = True
        self.last_message_time = datetime.utcnow()

        # Start health check loop in background
        health_check_task = asyncio.create_task(self._health_check_loop())

        try:
            logger.info("🔄 Telegram monitor running with auto-recovery enabled...")
            logger.info(f"   Reconnection: max {self.max_reconnect_attempts} attempts with exponential backoff")
            logger.info(f"   Health check: every {self.health_check_interval}s")

            while self.is_running:
                try:
                    # Run until disconnected
                    await self.client.run_until_disconnected()

                    # If we reach here, client disconnected
                    if self.is_running:
                        logger.warning("⚠️ Telegram client disconnected unexpectedly")
                        self.connection_failures += 1

                        # Attempt reconnection
                        logger.info(f"🔄 Attempting automatic reconnection (failure #{self.connection_failures})...")
                        success = await self._reconnect_with_backoff()

                        if not success:
                            logger.error("❌ Failed to reconnect - Telegram monitoring stopped")
                            break

                        logger.info("✅ Reconnection successful - resuming monitoring")

                except (TelethonConnectionError, NetworkMigrateError) as e:
                    logger.error(f"❌ Connection error: {e}")
                    self.connection_failures += 1

                    success = await self._reconnect_with_backoff()
                    if not success:
                        break

                except FloodWaitError as e:
                    logger.warning(f"⏰ Flood wait error - waiting {e.seconds}s before retry")
                    await asyncio.sleep(e.seconds)
                    continue

                except (AuthKeyUnregisteredError, PhoneNumberBannedError) as e:
                    logger.error(f"❌ Fatal authentication error: {e}")
                    logger.error("   Cannot recover - Telegram monitoring stopped")
                    break

                except Exception as e:
                    logger.error(f"❌ Unexpected error in Telegram monitor: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

                    self.connection_failures += 1
                    if self.connection_failures >= 3:
                        logger.error(f"❌ Too many failures ({self.connection_failures}) - attempting reconnection")
                        success = await self._reconnect_with_backoff()
                        if not success:
                            break
                    else:
                        await asyncio.sleep(5)

        finally:
            self.is_running = False
            health_check_task.cancel()
            logger.info("🛑 Telegram monitor loop exited")

    async def stop(self):
        """Stop the monitor"""
        self.is_running = False
        if self.client:
            await self.client.disconnect()
            logger.info("🛑 Telegram monitor stopped")

    async def _reconnect_with_backoff(self, attempt: int = 0) -> bool:
        """
        OPT-028: Reconnect with exponential backoff

        Args:
            attempt: Current reconnection attempt number

        Returns:
            bool: True if reconnection successful, False otherwise
        """
        if attempt >= self.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached - giving up")
            return False

        # Calculate exponential backoff delay
        delay = min(
            self.reconnect_base_delay * (2 ** attempt),
            self.reconnect_max_delay
        )

        logger.warning(f"⏳ Reconnecting in {delay}s (attempt {attempt + 1}/{self.max_reconnect_attempts})...")
        await asyncio.sleep(delay)

        try:
            logger.info("🔌 Attempting reconnection to Telegram...")

            # Disconnect if still connected
            if self.client and self.client.is_connected():
                await self.client.disconnect()

            # Create new client
            self.client = TelegramClient(
                'sentinel_session',
                int(self.api_id),
                self.api_hash
            )

            # Reconnect
            await self.client.start(phone=self.phone)

            # Re-register message handler
            @self.client.on(events.NewMessage(chats=list(self.monitored_groups.keys())))
            async def message_handler(event: Message):
                await self._handle_message(event)

            me = await self.client.get_me()
            logger.info(f"✅ Reconnected successfully: @{me.username or me.phone}")

            self.connection_failures = 0
            self.last_message_time = datetime.utcnow()

            return True

        except (TelethonConnectionError, NetworkMigrateError) as e:
            logger.error(f"❌ Reconnection failed (network error): {e}")
            return await self._reconnect_with_backoff(attempt + 1)

        except FloodWaitError as e:
            logger.warning(f"⏰ Flood wait error - must wait {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return await self._reconnect_with_backoff(attempt + 1)

        except (AuthKeyUnregisteredError, PhoneNumberBannedError) as e:
            logger.error(f"❌ Authentication error (cannot recover): {e}")
            return False

        except Exception as e:
            logger.error(f"❌ Reconnection failed (unexpected error): {e}")
            return await self._reconnect_with_backoff(attempt + 1)

    async def _health_check_loop(self):
        """
        OPT-028: Health check loop to detect stale connections

        Alerts if no messages received in health_check_interval
        """
        while self.is_running:
            await asyncio.sleep(self.health_check_interval)

            if not self.last_message_time:
                # No messages received yet (normal on startup)
                logger.debug("🏥 Health check: No messages received yet (normal on startup)")
                continue

            time_since_last_message = datetime.utcnow() - self.last_message_time

            if time_since_last_message > timedelta(seconds=self.health_check_interval):
                logger.warning(
                    f"🚨 HEALTH CHECK ALERT: No messages received in {time_since_last_message.total_seconds():.0f}s "
                    f"(threshold: {self.health_check_interval}s)"
                )
                logger.warning("   Possible causes:")
                logger.warning("   - Connection dropped silently")
                logger.warning("   - Groups are inactive (no one posting)")
                logger.warning("   - Bot token/channel ID issue")

                # Attempt reconnection if connection seems dead
                if not self.client or not self.client.is_connected():
                    logger.warning("   Connection is dead - attempting reconnection...")
                    success = await self._reconnect_with_backoff()
                    if not success:
                        logger.error("   ❌ Failed to reconnect - Telegram monitoring may be down")
                else:
                    logger.info("   Connection still active - groups may just be quiet")
            else:
                logger.debug(f"🏥 Health check: OK (last message {time_since_last_message.total_seconds():.0f}s ago)")


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
