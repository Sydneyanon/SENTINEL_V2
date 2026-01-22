"""
PumpPortal API Client - Fetch token metadata
"""
import asyncio
import aiohttp
from typing import Optional, Dict
from loguru import logger


class PumpPortalAPI:
    """Client for PumpPortal REST API"""

    def __init__(self):
        self.base_url = "https://api.pumpportal.fun/api"

    async def get_token_metadata(self, token_address: str) -> Optional[Dict]:
        """
        Fetch token metadata from PumpPortal API

        Args:
            token_address: Token mint address

        Returns:
            Dict with token_name, token_symbol, etc. or None if not found
        """
        try:
            url = f"{self.base_url}/token/{token_address}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Extract metadata
                        name = data.get('name', '').strip()
                        symbol = data.get('symbol', '').strip()

                        # Only return if we got actual data (not empty strings)
                        if name and symbol:
                            metadata = {
                                'token_name': name,
                                'token_symbol': symbol,
                                'description': data.get('description', ''),
                                'image_uri': data.get('image'),
                                'twitter': data.get('twitter'),
                                'telegram': data.get('telegram'),
                                'website': data.get('website'),
                            }

                            logger.info(f"✅ PumpPortal API: ${symbol} / {name}")
                            return metadata
                        else:
                            logger.warning(f"⚠️ PumpPortal API returned empty name/symbol for {token_address[:8]}")
                            return None
                    else:
                        logger.warning(f"⚠️ PumpPortal API returned {resp.status} for {token_address[:8]}")
                        return None

        except asyncio.TimeoutError:
            logger.warning(f"⏰ PumpPortal API timeout for {token_address[:8]}")
            return None
        except Exception as e:
            logger.error(f"❌ PumpPortal API error: {e}")
            return None
