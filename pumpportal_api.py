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

    def __init__(self, helius_api_key: Optional[str] = None):
        # Direct pump.fun frontend API (has social data!)
        self.base_url = "https://frontend-api.pump.fun"
        # Fallback to PumpPortal (legacy)
        self.pumpportal_base = "https://api.pumpportal.fun/api"
        # CoinGecko fallback (free tier)
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        # Helius RPC (for metadata_uri fetch)
        self.helius_api_key = helius_api_key
        # Track which source provided data for logging
        self.social_source_stats = {
            'pumpfun': 0,
            'pumpportal': 0,
            'coingecko': 0,
            'helius': 0,
            'none': 0
        }

    async def get_token_metadata(self, token_address: str) -> Optional[Dict]:
        """
        Fetch token metadata with comprehensive fallback chain:
        1. Pump.fun Frontend API (primary, has social data)
        2. PumpPortal API (legacy fallback)
        3. CoinGecko API (free tier, indexes Pump.fun early)
        4. Helius metadata_uri (manual JSON parse from on-chain metadata)

        Args:
            token_address: Token mint address

        Returns:
            Dict with token_name, token_symbol, socials, etc. or None if not found
        """
        # Try pump.fun frontend API first (has social data!)
        result = await self._fetch_from_pumpfun(token_address)
        if result:
            result['social_source'] = 'pumpfun'
            self.social_source_stats['pumpfun'] += 1
            return result

        # Fallback 1: PumpPortal API (legacy, may not have social data)
        logger.debug(f"   Trying PumpPortal fallback for {token_address[:8]}...")
        result = await self._fetch_from_pumpportal(token_address)
        if result:
            result['social_source'] = 'pumpportal'
            self.social_source_stats['pumpportal'] += 1
            return result

        # Fallback 2: CoinGecko API (free tier, early indexing)
        logger.debug(f"   Trying CoinGecko fallback for {token_address[:8]}...")
        result = await self._fetch_from_coingecko(token_address)
        if result:
            result['social_source'] = 'coingecko'
            self.social_source_stats['coingecko'] += 1
            return result

        # Fallback 3: Helius metadata_uri (on-chain metadata)
        if self.helius_api_key:
            logger.debug(f"   Trying Helius metadata fallback for {token_address[:8]}...")
            result = await self._fetch_from_helius(token_address)
            if result:
                result['social_source'] = 'helius'
                self.social_source_stats['helius'] += 1
                return result

        # All fallbacks failed
        logger.warning(f"⚠️  All social data sources failed for {token_address[:8]}")
        self.social_source_stats['none'] += 1
        return None

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

    async def _fetch_from_coingecko(self, token_address: str) -> Optional[Dict]:
        """
        Fallback: Fetch from CoinGecko API (free tier, indexes Pump.fun early)

        Endpoint: /onchain/networks/solana/tokens/{address}/info
        """
        try:
            url = f"{self.coingecko_base}/onchain/networks/solana/tokens/{token_address}/info"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # CoinGecko structure: data.attributes
                        attributes = data.get('data', {}).get('attributes', {})
                        name = attributes.get('name', '').strip()
                        symbol = attributes.get('symbol', '').strip()

                        if name and symbol:
                            # Extract social links from CoinGecko
                            links = attributes.get('links', {})
                            twitter = links.get('twitter_handle')
                            if twitter:
                                twitter = f"https://twitter.com/{twitter}"
                            telegram = links.get('telegram_handle')
                            if telegram:
                                telegram = f"https://t.me/{telegram}"
                            website = links.get('website')
                            if isinstance(website, list) and website:
                                website = website[0]  # Take first website

                            metadata = {
                                'token_name': name,
                                'token_symbol': symbol,
                                'description': attributes.get('description', ''),
                                'image_uri': attributes.get('image_url'),
                                'twitter': twitter,
                                'telegram': telegram,
                                'website': website,
                                'has_twitter': bool(twitter),
                                'has_telegram': bool(telegram),
                                'has_website': bool(website),
                                'social_count': sum([bool(twitter), bool(telegram), bool(website)])
                            }

                            logger.info(f"✅ CoinGecko API (fallback): ${symbol}")
                            return metadata
                        else:
                            return None
                    elif resp.status == 429:
                        logger.warning(f"⚠️  CoinGecko rate limit (429)")
                        return None
                    else:
                        return None

        except Exception as e:
            logger.debug(f"   CoinGecko fallback error: {e}")
            return None

    async def _fetch_from_helius(self, token_address: str) -> Optional[Dict]:
        """
        Fallback: Fetch from Helius RPC + parse on-chain metadata_uri

        This fetches the metadata_uri from on-chain data, then fetches
        the actual JSON metadata which may contain social links.
        """
        try:
            if not self.helius_api_key:
                return None

            url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"

            # Get token metadata account
            payload = {
                "jsonrpc": "2.0",
                "id": "helius-metadata",
                "method": "getAsset",
                "params": {
                    "id": token_address
                }
            }

            async with aiohttp.ClientSession() as session:
                # Fetch asset info from Helius
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    result = data.get('result', {})

                    # Extract basic metadata
                    content = result.get('content', {})
                    metadata_field = content.get('metadata', {})
                    name = metadata_field.get('name', '').strip()
                    symbol = metadata_field.get('symbol', '').strip()

                    if not (name and symbol):
                        return None

                    # Try to extract social links from metadata JSON
                    json_uri = content.get('json_uri')
                    twitter = None
                    telegram = None
                    website = None

                    if json_uri:
                        # Fetch the actual metadata JSON
                        try:
                            async with session.get(json_uri, timeout=aiohttp.ClientTimeout(total=3)) as json_resp:
                                if json_resp.status == 200:
                                    json_data = await json_resp.json()

                                    # Common fields in Pump.fun metadata
                                    twitter = json_data.get('twitter')
                                    telegram = json_data.get('telegram')
                                    website = json_data.get('website')

                                    # Alternative nested structure
                                    if not twitter:
                                        external_url = json_data.get('external_url', '')
                                        if 'twitter.com' in external_url or 'x.com' in external_url:
                                            twitter = external_url

                                    # Check properties or attributes
                                    properties = json_data.get('properties', {})
                                    if not website:
                                        website = properties.get('website') or properties.get('url')

                        except Exception as json_err:
                            logger.debug(f"   Helius JSON fetch error: {json_err}")

                    metadata = {
                        'token_name': name,
                        'token_symbol': symbol,
                        'description': metadata_field.get('description', ''),
                        'image_uri': content.get('links', {}).get('image'),
                        'twitter': twitter,
                        'telegram': telegram,
                        'website': website,
                        'has_twitter': bool(twitter),
                        'has_telegram': bool(telegram),
                        'has_website': bool(website),
                        'social_count': sum([bool(twitter), bool(telegram), bool(website)])
                    }

                    logger.info(f"✅ Helius metadata (fallback): ${symbol}")
                    return metadata

        except Exception as e:
            logger.debug(f"   Helius fallback error: {e}")
            return None

    def get_social_coverage_stats(self) -> Dict:
        """
        Returns statistics on social data source coverage

        Returns:
            Dict with source counts and coverage percentage
        """
        total = sum(self.social_source_stats.values())
        if total == 0:
            return {'coverage': 0.0, 'sources': self.social_source_stats}

        successful = total - self.social_source_stats['none']
        coverage_pct = (successful / total) * 100

        return {
            'coverage': round(coverage_pct, 1),
            'total_tokens': total,
            'successful': successful,
            'failed': self.social_source_stats['none'],
            'sources': self.social_source_stats.copy()
        }
