"""
PumpPortal API Client - Fetch token metadata from Pump.fun Frontend API
Includes social data (Twitter, Telegram, website) for pre-grad tokens
"""
import asyncio
import aiohttp
from typing import Optional, Dict
from loguru import logger

# Retries with exponential backoff
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    logger.warning("⚠️  tenacity not installed - API retries disabled (install: pip install tenacity)")


class PumpPortalAPI:
    """Client for Pump.fun Frontend API - Gets social data for pre-grad tokens"""

    def __init__(self):
        # Direct pump.fun frontend API (has social data!)
        self.base_url = "https://frontend-api.pump.fun"
        # Fallback to PumpPortal (legacy)
        self.pumpportal_base = "https://api.pumpportal.fun/api"

    async def get_token_metadata(self, token_address: str) -> Optional[Dict]:
        """
        Fetch token metadata from Pump.fun Frontend API (with social data)

        NEW: Uses pump.fun frontend API directly to get social links
        for pre-grad tokens (Twitter, Telegram, website)

        Args:
            token_address: Token mint address

        Returns:
            Dict with token_name, token_symbol, socials, etc. or None if not found
        """
        # Try pump.fun frontend API first (has social data!)
        result = await self._fetch_from_pumpfun(token_address)
        if result:
            return result

        # Fallback to PumpPortal API (legacy, may not have social data)
        logger.debug(f"   Trying PumpPortal fallback for {token_address[:8]}...")
        result = await self._fetch_from_pumpportal(token_address)
        return result

    async def _fetch_from_pumpfun(self, token_address: str, attempt: int = 1) -> Optional[Dict]:
        """
        Fetch from pump.fun frontend API (BEST - has social data)

        Retries with exponential backoff: 3 attempts, 1s → 2s → 4s delays
        """
        try:
            url = f"{self.base_url}/coins/{token_address}"
            logger.debug(f"   📡 Pump.fun API: {url} (attempt {attempt}/3)")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Extract metadata
                        name = data.get('name', '').strip()
                        symbol = data.get('symbol', '').strip()

                        # Only return if we got actual data
                        if name and symbol:
                            # Extract social links (may be None if creator didn't add them)
                            twitter = data.get('twitter')
                            telegram = data.get('telegram')
                            website = data.get('website')

                            metadata = {
                                'token_name': name,
                                'token_symbol': symbol,
                                'description': data.get('description', ''),
                                'image_uri': data.get('image_uri'),
                                'twitter': twitter,
                                'telegram': telegram,
                                'website': website,
                                # NEW: Process social data for conviction scoring
                                'has_twitter': bool(twitter),
                                'has_telegram': bool(telegram),
                                'has_website': bool(website),
                                'social_count': sum([bool(twitter), bool(telegram), bool(website)])
                            }

                            # Log social data
                            if metadata['social_count'] > 0:
                                socials = []
                                if twitter: socials.append('Twitter')
                                if telegram: socials.append('Telegram')
                                if website: socials.append('Website')
                                logger.info(f"✅ Pump.fun API: ${symbol} | Socials: {', '.join(socials)}")
                            else:
                                logger.info(f"✅ Pump.fun API: ${symbol} (no socials - creator didn't add)")

                            return metadata
                        else:
                            logger.warning(f"⚠️  Pump.fun API returned empty name/symbol for {token_address[:8]}")
                            return None

                    elif resp.status in [429, 503]:
                        # Rate limited or server error - retry with backoff
                        if attempt < 3:
                            delay = 2 ** attempt  # 1s, 2s, 4s
                            logger.warning(f"⚠️  Pump.fun API {resp.status} - retry in {delay}s...")
                            await asyncio.sleep(delay)
                            return await self._fetch_from_pumpfun(token_address, attempt + 1)
                        else:
                            logger.warning(f"⚠️  Pump.fun API {resp.status} after 3 attempts")
                            return None

                    else:
                        logger.warning(f"⚠️  Pump.fun API returned {resp.status} for {token_address[:8]}")
                        return None

        except asyncio.TimeoutError:
            if attempt < 3:
                delay = 2 ** attempt
                logger.warning(f"⏰ Pump.fun API timeout - retry in {delay}s...")
                await asyncio.sleep(delay)
                return await self._fetch_from_pumpfun(token_address, attempt + 1)
            else:
                logger.warning(f"⏰ Pump.fun API timeout after 3 attempts")
                return None

        except Exception as e:
            logger.error(f"❌ Pump.fun API error: {e}")
            return None

    async def _fetch_from_pumpportal(self, token_address: str) -> Optional[Dict]:
        """
        Fallback: Fetch from PumpPortal API (may not have social data)
        """
        try:
            url = f"{self.pumpportal_base}/token/{token_address}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        name = data.get('name', '').strip()
                        symbol = data.get('symbol', '').strip()

                        if name and symbol:
                            metadata = {
                                'token_name': name,
                                'token_symbol': symbol,
                                'description': data.get('description', ''),
                                'image_uri': data.get('image'),
                                'twitter': data.get('twitter'),
                                'telegram': data.get('telegram'),
                                'website': data.get('website'),
                                'has_twitter': bool(data.get('twitter')),
                                'has_telegram': bool(data.get('telegram')),
                                'has_website': bool(data.get('website')),
                                'social_count': sum([
                                    bool(data.get('twitter')),
                                    bool(data.get('telegram')),
                                    bool(data.get('website'))
                                ])
                            }

                            logger.info(f"✅ PumpPortal API (fallback): ${symbol}")
                            return metadata
                        else:
                            return None
                    else:
                        return None

        except Exception as e:
            logger.debug(f"   PumpPortal fallback error: {e}")
            return None
